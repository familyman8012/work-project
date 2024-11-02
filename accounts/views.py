from django.shortcuts import render
from rest_framework import viewsets, status
from django.contrib.auth import get_user_model
from .serializers import UserSerializer, UserDetailSerializer
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from datetime import datetime
from tasks.models import Task
from tasks.serializers import TaskSerializer
from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters
from rest_framework.pagination import PageNumberPagination
from organizations.models import Department
from django.db.models import Case, When, IntegerField

# Create your views here.

User = get_user_model()


# 페이지네이션 클래스 정의
class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response({
            'count': self.page.paginator.count,  # 전체 결과 수
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'results': data
        })


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter]
    search_fields = ["first_name", "last_name", "employee_id", "email"]

    def get_queryset(self):
        user = self.request.user
        queryset = User.objects.select_related("department").filter(is_active=True)
        department_id = self.request.query_params.get('department')
        rank = self.request.query_params.get('rank')

        # 일반 직원은 접근 불가
        if user.role == "EMPLOYEE":
            return User.objects.none()

        # 부서 필터링 공통 함수
        def get_department_users(dept_id):
            """부서 ID를 받아서 해당 부서와 산하 팀의 모든 직원 ID 목록을 반환"""
            try:
                dept = Department.objects.get(id=dept_id)
                print(f"\n=== Department Filter Debug ===")
                print(f"Selected Department: {dept.name}")
                print(f"Parent ID: {dept.parent_id}")
                
                if dept.parent is None:  # 본부인 경우
                    # 본부와 산하 팀의 모든 직원
                    child_depts = Department.objects.filter(parent=dept.id)
                    dept_ids = [dept.id] + list(child_depts.values_list('id', flat=True))
                    print(f"Child Departments: {[d.name for d in child_depts]}")
                    print(f"Department IDs: {dept_ids}")
                    return dept_ids
                else:  # 팀인 경우
                    return [dept.id]
            except Department.DoesNotExist:
                return []

        # 사용자 권한별 처리
        if user.role == "ADMIN":
            if department_id:
                dept_ids = get_department_users(department_id)
                if dept_ids:
                    print(f"Admin - Filtering by departments: {dept_ids}")
                    queryset = queryset.filter(department_id__in=dept_ids)

        elif user.rank in ["GENERAL_MANAGER", "DIRECTOR"]:
            if user.department.parent is None:  # 본부장/이사가 본부 소속인 경우
                if department_id:
                    dept_ids = get_department_users(department_id)
                    if dept_ids:
                        print(f"Director/GM - Filtering by departments: {dept_ids}")
                        queryset = queryset.filter(department_id__in=dept_ids)
                else:
                    # 자신의 본부 전체 직원
                    dept_ids = get_department_users(user.department.id)
                    print(f"Director/GM - Default departments: {dept_ids}")
                    queryset = queryset.filter(department_id__in=dept_ids)

        elif user.role == "MANAGER":
            queryset = queryset.filter(department=user.department)

        # 검색어 처리
        search = self.request.query_params.get("search")
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(employee_id__icontains=search)
                | Q(email__icontains=search)
            )

        # rank 필터링 추가
        if rank:
            queryset = queryset.filter(rank=rank)

        print(f"Final Query: {queryset.query}")
        print(f"Result Count: {queryset.count()}")
        
        # 본부 소속 직원이 먼저 나오도록 정렬하고, 같은 팀 내에서는 직급 순으로 정렬
        # CASE문을 사용하여 직급 순서 정의
        return queryset.order_by(
            "-department__parent_id",  # NULL(본부)이 먼저 오도록 내림차순 정렬
            "department__name",        # 부서명으로 정렬
            Case(                      # 직급 순서 정의
                When(rank="DIRECTOR", then=0),
                When(rank="GENERAL_MANAGER", then=1),
                When(rank="DEPUTY_GENERAL_MANAGER", then=2),
                When(rank="MANAGER", then=3),
                When(rank="ASSISTANT_MANAGER", then=4),
                When(rank="SENIOR", then=5),
                When(rank="STAFF", then=6),
                default=7,
                output_field=IntegerField(),
            ),
            "first_name"              # 마지막으로 이름순
        )

    def get_serializer_class(self):
        if self.action in ["retrieve", "me", "list"]:
            return UserDetailSerializer
        return UserSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        
        # 페이지네이션 적용
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def tasks_current(self, request, pk=None):
        user = self.get_object()
        tasks = Task.objects.filter(assignee=user, status="IN_PROGRESS")
        serializer = TaskSerializer(tasks, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def tasks_history(self, request, pk=None):
        user = self.get_object()
        status = request.query_params.get("status")
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")

        tasks = Task.objects.filter(assignee=user)

        if status:
            tasks = tasks.filter(status=status)
        if start_date:
            tasks = tasks.filter(start_date__gte=start_date)
        if end_date:
            tasks = tasks.filter(due_date__lte=end_date)

        serializer = TaskSerializer(tasks, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def tasks_statistics(self, request, pk=None):
        user = self.get_object()
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")

        tasks = Task.objects.filter(assignee=user)
        if start_date:
            tasks = tasks.filter(start_date__gte=start_date)
        if end_date:
            tasks = tasks.filter(due_date__lte=end_date)

        total_tasks = tasks.count()
        completed_tasks = tasks.filter(status="DONE").count()
        in_progress_tasks = tasks.filter(status="IN_PROGRESS").count()
        delayed_tasks = len([task for task in tasks if task.is_delayed])

        completion_rate = (
            (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        )

        tasks_by_priority = {
            "HIGH": tasks.filter(priority="HIGH").count(),
            "MEDIUM": tasks.filter(priority="MEDIUM").count(),
            "LOW": tasks.filter(priority="LOW").count(),
        }

        return Response(
            {
                "total_tasks": total_tasks,
                "completed_tasks": completed_tasks,
                "in_progress_tasks": in_progress_tasks,
                "delayed_tasks": delayed_tasks,
                "completion_rate": completion_rate,
                "tasks_by_priority": tasks_by_priority,
            }
        )

    @action(detail=True, methods=["get"])
    def tasks_statistics_detail(self, request, pk=None):
        user = self.get_object()
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")

        tasks = Task.objects.filter(assignee=user)
        if start_date:
            tasks = tasks.filter(start_date__gte=start_date)
        if end_date:
            tasks = tasks.filter(due_date__lte=end_date)

        # 우선순위 분포
        priority_distribution = {
            "URGENT": tasks.filter(priority="URGENT").count(),
            "HIGH": tasks.filter(priority="HIGH").count(),
            "MEDIUM": tasks.filter(priority="MEDIUM").count(),
            "LOW": tasks.filter(priority="LOW").count(),
        }

        # 난이도 분포
        difficulty_distribution = {
            "VERY_HARD": tasks.filter(difficulty="VERY_HARD").count(),
            "HARD": tasks.filter(difficulty="HARD").count(),
            "MEDIUM": tasks.filter(difficulty="MEDIUM").count(),
            "EASY": tasks.filter(difficulty="EASY").count(),
        }

        # 평균 작업 완료 시간 (완료된 작업만)
        completed_tasks = tasks.filter(status="DONE", completed_at__isnull=False)
        avg_completion_time = 0
        if completed_tasks.exists():
            total_hours = sum(
                (task.completed_at - task.start_date).total_seconds() / 3600
                for task in completed_tasks
                if task.completed_at and task.start_date
            )
            avg_completion_time = total_hours / completed_tasks.count()

        # 지연된 작업 비율
        total_tasks = tasks.count()
        delayed_tasks = len([task for task in tasks if task.is_delayed])
        delay_rate = (delayed_tasks / total_tasks * 100) if total_tasks > 0 else 0

        # 월별 통계
        monthly_stats = {}
        for task in tasks:
            month_key = task.start_date.strftime("%Y-%m")
            if month_key not in monthly_stats:
                monthly_stats[month_key] = {
                    "total": 0,
                    "completed": 0,
                    "delayed": 0,
                    "avg_completion_time": 0,
                }
            
            monthly_stats[month_key]["total"] += 1
            if task.status == "DONE":
                monthly_stats[month_key]["completed"] += 1
            if task.is_delayed:
                monthly_stats[month_key]["delayed"] += 1

        # 평균 점수 계산 (평가가 있는 완료된 작업만)
        completed_tasks_with_eval = tasks.filter(
            status="DONE",
            evaluations__isnull=False
        )
        avg_score = 0
        if completed_tasks_with_eval.exists():
            total_score = sum(
                task.evaluations.first().performance_score
                for task in completed_tasks_with_eval
                if task.evaluations.exists()
            )
            avg_score = total_score / completed_tasks_with_eval.count()

        return Response({
            "priority_distribution": priority_distribution,
            "difficulty_distribution": difficulty_distribution,
            "avg_completion_time": round(avg_completion_time, 2),
            "delay_rate": round(delay_rate, 2),
            "monthly_stats": monthly_stats,
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks.count(),
            "delayed_tasks": delayed_tasks,
            "avg_score": round(avg_score, 2),
        })


class UserSearchViewSet(viewsets.ViewSet):
    @action(detail=False, methods=["get"])
    def search_by_experience(self, request):
        task_keyword = request.query_params.get("task_keyword", "")
        users = User.objects.filter(
            assigned_tasks__title__icontains=task_keyword
        ).distinct()
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def search_by_department(self, request):
        department_id = request.query_params.get("department_id")
        users = User.objects.filter(department_id=department_id)
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def search_by_rank(self, request):
        rank = request.query_params.get("rank")
        users = User.objects.filter(rank=rank)
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)
