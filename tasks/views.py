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

User = get_user_model()


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class TaskViewSet(viewsets.ModelViewSet):
    queryset = Task.objects.all().order_by("-created_at")
    serializer_class = TaskSerializer
    pagination_class = StandardResultsSetPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = ["title", "description"]
    filterset_fields = ["status", "priority", "department", "assignee"]

    def get_queryset(self):
        queryset = Task.objects.all().order_by("-created_at")

        # 시작일, 종료일 필터링
        start_date = self.request.query_params.get("start_date_after")
        end_date = self.request.query_params.get("due_date_before")
        is_delayed = self.request.query_params.get("is_delayed")

        if start_date:
            queryset = queryset.filter(start_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(due_date__lte=end_date)

        # 지연된 작업 필터링
        if is_delayed == "true":
            queryset = queryset.filter(
                due_date__lt=timezone.now(),  # 마감일이 현재보다 이전
                status__in=[
                    "TODO",
                    "IN_PROGRESS",
                    "REVIEW",
                ],  # 완료되지 않은 작업
            )

        return queryset

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

            # 검토 요청 시 관리자에게 알림
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
                            message=f"작업이 마감일을 초과했습니다: {instance.title}",
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
            return Response({"detail": "일정이 충돌합니다."}, status=400)

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

        # 작업 ID로 필터링
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
