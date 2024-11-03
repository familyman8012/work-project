from rest_framework import viewsets, filters
from rest_framework.pagination import PageNumberPagination
from django_filters.rest_framework import DjangoFilterBackend
from .models import (
    Task,
    TaskComment,
    TaskAttachment,
    TaskHistory,
    TaskTimeLog,
    TaskEvaluation,
)
from organizations.models import Department
from .serializers import (
    TaskSerializer,
    TaskCommentSerializer,
    TaskAttachmentSerializer,
    TaskHistorySerializer,
    TaskTimeLogSerializer,
    TaskEvaluationSerializer,
    TaskCalendarSerializer,
)
from .filters import TaskFilter
from datetime import datetime
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from notifications.models import Notification
from datetime import timedelta
from django.db.models import Q
from django.contrib.auth import get_user_model
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Value, CharField
from django.db.models.functions import Concat
import math
from django.db.models import Avg

User = get_user_model()


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        # 전체 쿼리셋의 수를 사용
        count = self.page.paginator.count
        return Response({
            'count': count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'total_pages': math.ceil(count / self.page_size),
            'current_page': self.page.number,
            'results': data
        })


class TaskViewSet(viewsets.ModelViewSet):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["status", "priority", "assignee"]
    ordering_fields = ["start_date", "due_date", "created_at", "priority"]
    ordering = ["start_date"]

    def get_queryset(self):
        queryset = Task.objects.select_related('department', 'assignee').all()
        
        # 부서 필터링 로직
        department_id = self.request.query_params.get('department')
        if department_id:
            try:
                department_id = int(department_id)
                selected_dept = Department.objects.get(id=department_id)
                
                print(f"\n=== Department Filter Debug ===")
                print(f"Selected Department ID: {department_id}")
                print(f"Selected Department: {selected_dept.name}")
                print(f"Is HQ? {selected_dept.parent is None}")
                
                if selected_dept.parent is None:  # 본부인 경우
                    child_depts = Department.objects.filter(parent=department_id)
                    dept_ids = [department_id] + list(child_depts.values_list('id', flat=True))
                    
                    print(f"Child Departments: {[d.name for d in child_depts]}")
                    print(f"All Department IDs: {dept_ids}")
                    
                    # 각 부서별 작업 수 먼저 확인
                    for dept_id in dept_ids:
                        dept_tasks = Task.objects.filter(department_id=dept_id)
                        print(f"Tasks in dept {dept_id}: {dept_tasks.count()}")
                    
                    queryset = queryset.filter(department_id__in=dept_ids)
                else:
                    queryset = queryset.filter(department_id=department_id)
                
                # 최종 리셋 결과 확인
                print(f"Final queryset count: {queryset.count()}")
                print(f"SQL Query: {queryset.query}")
                print("=== End Debug ===\n")
                
            except (Department.DoesNotExist, ValueError) as e:
                print(f"Error: {e}")
                return Task.objects.none()

        # 검색어 처리
        search = self.request.query_params.get('search', '')
        if search:
            title_desc_search = Q(title__icontains=search) | Q(description__icontains=search)
            
            queryset = queryset.annotate(
                full_name=Concat(
                    'assignee__last_name',
                    'assignee__first_name',
                    output_field=CharField()
                )
            )
            
            name_search = Q(full_name__icontains=search)
            queryset = queryset.filter(title_desc_search | name_search)

        # 나머지 필터링 로직
        status = self.request.query_params.get('status')
        if status:
            queryset = queryset.filter(status=status)

        priority = self.request.query_params.get('priority')
        if priority:
            queryset = queryset.filter(priority=priority)

        start_date = self.request.query_params.get("start_date")
        end_date = self.request.query_params.get("end_date")

        if start_date:
            queryset = queryset.filter(start_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(due_date__lte=end_date)

        return queryset.distinct().order_by('start_date')

    def list(self, request, *args, **kwargs):
        # 1. 전체 쿼리셋 가져오기
        queryset = self.filter_queryset(self.get_queryset())
        
        # 2. 페이지네이션 적용 전의 전체 결과 저장
        total_results = queryset.count()
        
        # 3. 페이지네이션 적용
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            # 4. 페이지네이션된 응답에 전체 결과 수 포함
            return Response({
                'count': total_results,  # 전체 결과 수 (21)
                'next': self.paginator.get_next_link(),
                'previous': self.paginator.get_previous_link(),
                'total_pages': math.ceil(total_results / self.paginator.page_size),
                'current_page': self.paginator.page.number,
                'results': serializer.data
            })

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def paginate_queryset(self, queryset):
        # 페이지네이션 결과 로깅
        page = super().paginate_queryset(queryset)
        if page is not None:
            print(f"Page size: {len(page)}")
            print(f"Total pages: {self.paginator.page.paginator.num_pages}")
        return page

    def perform_update(self, serializer):
        old_instance = self.get_object()
        old_status = old_instance.status
        old_assignee = old_instance.assignee
        old_priority = old_instance.priority
        instance = serializer.save()

        notifications = []

        # 상태 변경 알림
        if old_status != instance.status:
            TaskHistoryViewSet.create_history(
                task=instance,
                previous_status=old_status,
                new_status=instance.status,
                user=self.request.user,
            )

            # 작업 완료 시 의존성 있는 작업들의 담당자에게 알림
            if instance.status == "DONE":
                dependent_tasks = Task.objects.filter(dependencies=instance)
                for dep_task in dependent_tasks:
                    notifications.append(
                        Notification(
                            recipient=dep_task.assignee,
                            notification_type="TASK_DEPENDENCY_COMPLETED",
                            task=dep_task,
                            message=f"선행 작업이 완료되었습니다: {instance.title}",
                            priority="HIGH",
                        )
                    )

            # 검토  리자에게 알림
            if instance.status == "REVIEW":
                managers = User.objects.filter(
                    department=instance.department,
                    role__in=["MANAGER", "ADMIN"],
                )
                for manager in managers:
                    notifications.append(
                        Notification(
                            recipient=manager,
                            notification_type="TASK_REVIEWED",
                            task=instance,
                            message=f"작업 검토가 요청되었습니다: {instance.title}",
                            priority="HIGH",
                        )
                    )

        # 우선순위 변경 알림
        if old_priority != instance.priority:
            notifications.append(
                Notification(
                    recipient=instance.assignee,
                    notification_type="TASK_PRIORITY_CHANGED",
                    task=instance,
                    message=(
                        f"작업 우선순위가 {old_priority}에서"
                        f" {instance.priority}로"
                        f" 변경되었습니다: {instance.title}"
                    ),
                    priority=(
                        "HIGH" if instance.priority == "URGENT" else "MEDIUM"
                    ),
                )
            )

        # 마감 임박 체크 (3일 이내)
        days_until_due = (instance.due_date - timezone.now()).days
        if 0 < days_until_due <= 3:
            if not Notification.objects.filter(
                task=instance,
                notification_type="TASK_DUE_SOON",
                created_at__gte=timezone.now() - timedelta(days=1),
            ).exists():
                notifications.append(
                    Notification(
                        recipient=instance.assignee,
                        notification_type="TASK_DUE_SOON",
                        task=instance,
                        message=(
                            f"작업 마감이 {days_until_due}일 남았습니다:"
                            f" {instance.title}"
                        ),
                        priority="HIGH",
                        expires_at=instance.due_date,
                    )
                )

        # 마감일 초과 체크
        elif days_until_due <= 0 and instance.status not in ["DONE", "HOLD"]:
            if not Notification.objects.filter(
                task=instance,
                notification_type="TASK_OVERDUE",
                created_at__gte=timezone.now() - timedelta(days=1),
            ).exists():
                # 담당자와 관리자에게 알림
                recipients = list(
                    User.objects.filter(
                        Q(id=instance.assignee.id)
                        | Q(
                            department=instance.department,
                            role__in=["MANAGER", "ADMIN"],
                        )
                    ).distinct()
                )

                for recipient in recipients:
                    notifications.append(
                        Notification(
                            recipient=recipient,
                            notification_type="TASK_OVERDUE",
                            task=instance,
                            message=f"작업이 마감일을 초과습다: {instance.title}",
                            priority="HIGH",
                        )
                    )

        # 일괄 알림 생성
        if notifications:
            Notification.objects.bulk_create(notifications)

    def perform_create(self, serializer):
        task = serializer.save(reporter=self.request.user)

        # 작업 배정 알림 생성
        if task.assignee != self.request.user:
            Notification.objects.create(
                recipient=task.assignee,
                notification_type="TASK_ASSIGNED",
                task=task,
                message=f"새로 업이 배정되었습다: {task.title}",
            )

    @action(detail=False, methods=["get"])
    def calendar(self, request):
        """캘린더 뷰를 위한 작업 목록 조회"""
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        assignee = request.query_params.get("assignee")
        department = request.query_params.get("department")

        queryset = self.get_queryset()

        if start_date and end_date:
            # 시간대를 포함한 datetime으로 변환
            start_datetime = timezone.make_aware(
                datetime.strptime(
                    f"{start_date} 00:00:00", "%Y-%m-%d %H:%M:%S"
                )
            )
            end_datetime = timezone.make_aware(
                datetime.strptime(f"{end_date} 23:59:59", "%Y-%m-%d %H:%M:%S")
            )

            queryset = queryset.filter(
                Q(start_date__range=[start_datetime, end_datetime])
                | Q(due_date__range=[start_datetime, end_datetime])
            )

        # 담당자 또는 부서 기준 필터링
        if assignee:
            queryset = queryset.filter(assignee=assignee)
        elif department:
            queryset = queryset.filter(department=department)

        serializer = TaskCalendarSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def update_dates(self, request, pk=None):
        """작업 일정 업데이트 (드래그 앤 드롭)"""
        task = self.get_object()
        new_start = request.data.get("start_date")
        new_end = request.data.get("due_date")

        # 일정 충돌 체크
        if self.check_schedule_conflict(
            task.assignee, new_start, new_end, exclude_task=task
        ):
            return Response({"detail": "일정이 충돌합다."}, status=400)

        serializer = self.get_serializer(task, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def workload(self, request):
        """리소스 할당 상황 조회"""
        date = request.query_params.get("date", datetime.now().date())
        department_id = request.query_params.get("department")

        queryset = User.objects.all()
        if department_id:
            queryset = queryset.filter(department_id=department_id)

        workload_data = []
        for user in queryset:
            tasks_count = Task.objects.filter(
                assignee=user, start_date__lte=date, due_date__gte=date
            ).count()
            workload_data.append(
                {
                    "user_id": user.id,
                    "user_name": f"{user.first_name} {user.last_name}",
                    "tasks_count": tasks_count,
                }
            )

        return Response(workload_data)

    @action(detail=True, methods=["get"])
    def tasks_current(self, request, pk=None):
        """사용자의 현재 진행중인 작업 목록 조회"""
        user = self.get_object()
        tasks = Task.objects.filter(
            assignee=user, status="IN_PROGRESS"
        ).order_by("-created_at")

        serializer = TaskSerializer(tasks, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def today_tasks(self, request):
        """대시보드용 오늘의 작업 조회 API"""
        user = request.user
        today = timezone.now().date()
        
        # 기본 쿼리셋 (오늘이 시작일과 마감일 사이에 있는 작업)
        queryset = Task.objects.filter(
            start_date__date__lte=today,  # 시작일이 오늘이 나 이전
            due_date__date__gte=today,    # 마감일이 오늘이거나 이후
            status__in=["TODO", "IN_PROGRESS", "REVIEW"]  # 완료되지 않은 작업만
        )

        # 권한에 따른 필터링
        if user.role != "ADMIN":
            if user.rank in ["DIRECTOR", "GENERAL_MANAGER"]:
                dept = Department.objects.get(id=user.department.id)
                if dept.parent is None:  # 본부인 경우
                    dept_ids = [dept.id]
                    child_dept_ids = Department.objects.filter(parent=dept).values_list('id', flat=True)
                    dept_ids.extend(child_dept_ids)
                    queryset = queryset.filter(department_id__in=dept_ids)
                else:  # 팀인 경우
                    queryset = queryset.filter(department=user.department)
            elif user.role == "MANAGER":
                queryset = queryset.filter(department=user.department)
            else:
                queryset = queryset.filter(assignee=user)

        serializer = TaskSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def delayed_tasks(self, request):
        """대시보드용 지연된 작업 조회 API"""
        user = request.user
        today = timezone.now().date()
        
        # 기본 쿼셋 (마감일이 오늘 이전이고 직 완료되지 않은 작업)
        queryset = Task.objects.filter(
            due_date__date__lt=today,  # 마감일이 오늘 이전인 작업
            status__in=["TODO", "IN_PROGRESS", "REVIEW"]  # 완료되지 않은 작업
        )

        # 권한에 따른 필터링 (today_tasks와 동일한 로직)
        if user.role != "ADMIN":
            if user.rank in ["DIRECTOR", "GENERAL_MANAGER"]:
                dept = Department.objects.get(id=user.department.id)
                if dept.parent is None:
                    dept_ids = [dept.id]
                    child_dept_ids = Department.objects.filter(parent=dept).values_list('id', flat=True)
                    dept_ids.extend(child_dept_ids)
                    queryset = queryset.filter(department_id__in=dept_ids)
                else:
                    queryset = queryset.filter(department=user.department)
            elif user.role == "MANAGER":
                queryset = queryset.filter(department=user.department)
            else:
                queryset = queryset.filter(assignee=user)

        serializer = TaskSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='workload-stats')
    def workload_stats(self, request):
        """작 부하 통계"""
        today = timezone.now().date()
        start_date = today - timedelta(days=7)
        
        # 권한에 따른 쿼리셋 필터링
        if request.user.role == "ADMIN":
            queryset = Task.objects.all()
        elif request.user.rank in ["DIRECTOR", "GENERAL_MANAGER"]:
            if request.user.department.parent is None:  # 본부장인 경우
                dept_ids = [request.user.department.id]
                child_dept_ids = Department.objects.filter(parent=request.user.department).values_list('id', flat=True)
                dept_ids.extend(child_dept_ids)
                queryset = Task.objects.filter(department_id__in=dept_ids)
            else:  # 팀장인 경우
                queryset = Task.objects.filter(department=request.user.department)
        else:
            queryset = Task.objects.filter(assignee=request.user)
        
        # 일별 통계 계산
        daily_stats = []
        for i in range(7):
            date = start_date + timedelta(days=i)
            stats = {
                'date': date.strftime('%Y-%m-%d'),
                'total': queryset.filter(start_date__date=date).count(),
                'completed': queryset.filter(
                    completed_at__date=date, 
                    status='DONE'
                ).count(),
                'inProgress': queryset.filter(
                    start_date__date=date, 
                    status='IN_PROGRESS'
                ).count(),
                'delayed': queryset.filter(
                    due_date__date=date,
                    status__in=['TODO', 'IN_PROGRESS']
                ).count()
            }
            daily_stats.append(stats)
        
        return Response(daily_stats)

    @action(detail=False, methods=['get'], url_path='priority-stats')
    def priority_stats(self, request):
        """우선순위별 작업 통계"""
        # 권한에 따른 쿼리셋 필터링
        if request.user.role == "ADMIN":
            queryset = Task.objects.all()
        elif request.user.rank in ["DIRECTOR", "GENERAL_MANAGER"]:
            if request.user.department.parent is None:
                dept_ids = [request.user.department.id]
                child_dept_ids = Department.objects.filter(parent=request.user.department).values_list('id', flat=True)
                dept_ids.extend(child_dept_ids)
                queryset = Task.objects.filter(department_id__in=dept_ids)
            else:
                queryset = Task.objects.filter(department=request.user.department)
        else:
            queryset = Task.objects.filter(assignee=request.user)

        stats = []
        total = queryset.count()
        for priority, _ in Task.PRIORITY_CHOICES:
            count = queryset.filter(priority=priority).count()
            percentage = (count / total * 100) if total > 0 else 0
            stats.append({
                'priority': priority,
                'count': count,
                'percentage': round(percentage, 1)
            })
        return Response(stats)

    @action(detail=False, methods=['get'], url_path='upcoming-deadlines')
    def upcoming_deadlines(self, request):
        """다가오는 마감일 작업"""
        today = timezone.now().date()
        end_date = today + timedelta(days=7)  # 일주일 이내 마감

        # 권한에 따른 쿼리셋 필터링
        if request.user.role == "ADMIN":
            queryset = Task.objects.all()
        elif request.user.rank in ["DIRECTOR", "GENERAL_MANAGER"]:
            if request.user.department.parent is None:
                dept_ids = [request.user.department.id]
                child_dept_ids = Department.objects.filter(parent=request.user.department).values_list('id', flat=True)
                dept_ids.extend(child_dept_ids)
                queryset = Task.objects.filter(department_id__in=dept_ids)
            else:
                queryset = Task.objects.filter(department=request.user.department)
        else:
            queryset = Task.objects.filter(assignee=request.user)

        upcoming_tasks = queryset.filter(
            due_date__date__range=[today, end_date],
            status__in=['TODO', 'IN_PROGRESS']
        ).order_by('due_date')[:5]  # 상위 5개만

        serializer = TaskSerializer(upcoming_tasks, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='team-performance')
    def team_performance(self, request):
        """팀 성과 통계"""
        # 권한에 따른 팀원 목록 조회
        if request.user.role == "ADMIN":
            team_members = User.objects.filter(
                is_active=True,
                rank__in=["STAFF", "SENIOR", "ASSISTANT_MANAGER", "MANAGER", "DEPUTY_GENERAL_MANAGER"]  # 본부장/이사 제외
            )
        elif request.user.rank in ["DIRECTOR", "GENERAL_MANAGER"]:
            if request.user.department.parent is None:
                dept_ids = [request.user.department.id]
                child_dept_ids = Department.objects.filter(parent=request.user.department).values_list('id', flat=True)
                dept_ids.extend(child_dept_ids)
                team_members = User.objects.filter(
                    department_id__in=dept_ids, 
                    is_active=True,
                    rank__in=["STAFF", "SENIOR", "ASSISTANT_MANAGER", "MANAGER", "DEPUTY_GENERAL_MANAGER"]  # 본부장/이사 제외
                )
            else:
                team_members = User.objects.filter(
                    department=request.user.department, 
                    is_active=True,
                    rank__in=["STAFF", "SENIOR", "ASSISTANT_MANAGER", "MANAGER", "DEPUTY_GENERAL_MANAGER"]  # 본부장/이사 제외
                )
        else:
            team_members = User.objects.filter(
                department=request.user.department, 
                is_active=True,
                rank__in=["STAFF", "SENIOR", "ASSISTANT_MANAGER", "MANAGER", "DEPUTY_GENERAL_MANAGER"]  # 본부장/이사 제외
            )

        # 각 팀원별 성과 계산
        performance_data = []
        for member in team_members:
            # 전체 작업 수와 완료된 작업 수 계산
            member_tasks = Task.objects.filter(assignee=member)
            total_tasks = member_tasks.count()
            completed_tasks = member_tasks.filter(status="DONE").count()
            completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
            
            # 평가 점수 계산 - 완료된 작업만 대상으로
            completed_task_ids = member_tasks.filter(status="DONE").values_list('id', flat=True)
            evaluations = TaskEvaluation.objects.filter(task_id__in=completed_task_ids)
            avg_score = evaluations.aggregate(Avg('performance_score'))['performance_score__avg'] or 0

            performance_data.append({
                'user_id': member.id,
                'name': f"{member.last_name}{member.first_name}",
                'completion_rate': round(completion_rate, 1),
                'task_count': total_tasks,
                'average_score': round(avg_score, 1)
            })

        return Response({
            'members': performance_data
        })

    @action(detail=False, methods=['get'], url_path='recent')
    def recent_activities(self, request):
        """최근 작업 활동 내역"""
        # 권한에 따른 쿼리셋 필터링
        if request.user.role == "ADMIN":
            queryset = TaskHistory.objects.all()
        elif request.user.rank in ["DIRECTOR", "GENERAL_MANAGER"]:
            if request.user.department.parent is None:
                dept_ids = [request.user.department.id]
                child_dept_ids = Department.objects.filter(parent=request.user.department).values_list('id', flat=True)
                dept_ids.extend(child_dept_ids)
                queryset = TaskHistory.objects.filter(task__department_id__in=dept_ids)
            else:
                queryset = TaskHistory.objects.filter(task__department=request.user.department)
        else:
            queryset = TaskHistory.objects.filter(
                Q(task__assignee=request.user) | Q(changed_by=request.user)
            )

        recent_activities = queryset.select_related(
            'task', 'changed_by'
        ).order_by('-created_at')[:10]

        def get_status_text(status: str) -> str:
            status_map = {
                "TODO": "예정",
                "IN_PROGRESS": "진행중",
                "REVIEW": "검토중",
                "DONE": "완료",
                "HOLD": "보류"
            }
            return status_map.get(status, status)

        activities_data = []
        for activity in recent_activities:
            activities_data.append({
                'id': activity.id,
                'type': 'STATUS_CHANGED',
                'description': f'작업 상태가 {get_status_text(activity.previous_status)}에서 {get_status_text(activity.new_status)}로 변경되었습니다.',
                'created_at': activity.created_at,
                'task_id': activity.task.id,
                'task_title': activity.task.title
            })

        return Response(activities_data)

    @action(detail=False, methods=['get'], url_path='stats')
    def stats(self, request):
        """작업 전반적인 통계"""
        today = timezone.now().date()
        last_week = today - timedelta(days=7)
        
        # 권한에 따른 쿼리셋 필터링
        if request.user.role == "ADMIN":
            queryset = Task.objects.all()
        elif request.user.rank in ["DIRECTOR", "GENERAL_MANAGER"]:
            if request.user.department.parent is None:
                dept_ids = [request.user.department.id]
                child_dept_ids = Department.objects.filter(parent=request.user.department).values_list('id', flat=True)
                dept_ids.extend(child_dept_ids)
                queryset = Task.objects.filter(department_id__in=dept_ids)
            else:
                queryset = Task.objects.filter(department=request.user.department)
        else:
            queryset = Task.objects.filter(assignee=request.user)

        # 이번 주 통계
        total_tasks = queryset.count()
        in_progress_tasks = queryset.filter(status="IN_PROGRESS").count()
        completed_tasks = queryset.filter(status="DONE").count()
        delayed_tasks = queryset.filter(
            due_date__date__lt=today,
            status__in=["TODO", "IN_PROGRESS"]
        ).count()

        # 지난 주 통계
        last_week_queryset = queryset.filter(created_at__date__lte=last_week)
        last_week_total = last_week_queryset.count()
        last_week_in_progress = last_week_queryset.filter(status="IN_PROGRESS").count()
        last_week_completed = last_week_queryset.filter(status="DONE").count()
        last_week_delayed = last_week_queryset.filter(
            due_date__date__lt=last_week,
            status__in=["TODO", "IN_PROGRESS"]
        ).count()

        # 증감률 계산
        def calculate_trend(current, previous):
            if previous == 0:
                return 100 if current > 0 else 0
            return round(((current - previous) / previous) * 100, 1)

        return Response({
            "total": {
                "count": total_tasks,
                "trend": calculate_trend(total_tasks, last_week_total)
            },
            "in_progress": {
                "count": in_progress_tasks,
                "trend": calculate_trend(in_progress_tasks, last_week_in_progress)
            },
            "completed": {
                "count": completed_tasks,
                "trend": calculate_trend(completed_tasks, last_week_completed)
            },
            "delayed": {
                "count": delayed_tasks,
                "trend": calculate_trend(delayed_tasks, last_week_delayed)
            }
        })


class TaskCommentViewSet(viewsets.ModelViewSet):
    queryset = TaskComment.objects.all()
    serializer_class = TaskCommentSerializer
    pagination_class = StandardResultsSetPagination
    filterset_fields = ["task"]

    def get_queryset(self):
        return TaskComment.objects.select_related("author").order_by(
            "-created_at"
        )

    def perform_create(self, serializer):
        comment = serializer.save(author=self.request.user)

        # 작업 담당자에게 코멘트 알림 (작성자가 담당자가 아닌 경우)
        if comment.task.assignee != self.request.user:
            Notification.objects.create(
                recipient=comment.task.assignee,
                notification_type="TASK_COMMENT",
                task=comment.task,
                message=(
                    "작업에 새로운 코멘트가 작성되었습니다:"
                    f" {comment.task.title}"
                ),
            )


class TaskAttachmentViewSet(viewsets.ModelViewSet):
    queryset = TaskAttachment.objects.all()
    serializer_class = TaskAttachmentSerializer


class TaskHistoryViewSet(viewsets.ModelViewSet):
    queryset = TaskHistory.objects.all()
    serializer_class = TaskHistorySerializer
    pagination_class = StandardResultsSetPagination
    filterset_fields = ["task"]

    def get_queryset(self):
        return TaskHistory.objects.select_related(
            "changed_by", "task"
        ).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(changed_by=self.request.user)

    # Task 상태 변경 시 히스토리 자동 생성을 위한 메서드 추가
    @classmethod
    def create_history(
        cls, task, previous_status, new_status, user, comment=""
    ):
        TaskHistory.objects.create(
            task=task,
            changed_by=user,
            previous_status=previous_status,
            new_status=new_status,
            comment=comment,
        )


class TaskTimeLogViewSet(viewsets.ModelViewSet):
    queryset = TaskTimeLog.objects.all()
    serializer_class = TaskTimeLogSerializer
    pagination_class = StandardResultsSetPagination
    filterset_fields = ["task"]

    def get_queryset(self):
        queryset = TaskTimeLog.objects.select_related("logged_by")
        task_id = self.request.query_params.get("task")
        if task_id:
            queryset = queryset.filter(task_id=task_id)
        return queryset.order_by("-start_time")

    def perform_create(self, serializer):
        data = self.request.data
        start_time = parse_datetime(data.get("start_time")) or timezone.now()
        end_time = (
            parse_datetime(data.get("end_time"))
            if data.get("end_time")
            else None
        )

        try:
            serializer.save(
                logged_by=self.request.user,
                start_time=start_time,
                end_time=end_time,
                duration=(end_time - start_time) if end_time else None,
            )
        except Exception as e:
            print(f"Error creating time log: {e}")
            raise

    def perform_update(self, serializer):
        data = self.request.data
        instance = serializer.instance
        start_time = instance.start_time
        end_time = parse_datetime(data.get("end_time")) or timezone.now()

        try:
            serializer.save(
                end_time=end_time,
                duration=(end_time - start_time) if end_time else None,
            )
        except Exception as e:
            print(f"Error updating time log: {e}")
            raise


class TaskEvaluationViewSet(viewsets.ModelViewSet):
    queryset = TaskEvaluation.objects.all()
    serializer_class = TaskEvaluationSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [filters.SearchFilter]
    search_fields = ["task__title"]  # 작업 제목으로 검색 가능

    def get_queryset(self):
        queryset = TaskEvaluation.objects.select_related("task", "evaluator")

        # 작업 ID로 필터
        task_id = self.request.query_params.get("task")
        if task_id:
            queryset = queryset.filter(task_id=task_id)
        else:
            # task_id가 없는 경우(목록 조회) 자신의 평가만 표시
            queryset = queryset.filter(evaluator=self.request.user)

        # 난이도로 필터링
        difficulty = self.request.query_params.get("difficulty")
        if difficulty:
            queryset = queryset.filter(difficulty=difficulty)

        return queryset.order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(evaluator=self.request.user)


# DashboardViewSet, UserSearchViewSet, ReportViewSet는 추가 요구사항에 따라 구현 필요
