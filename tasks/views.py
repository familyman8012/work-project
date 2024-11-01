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
)
from .filters import TaskFilter
from datetime import datetime
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from notifications.models import Notification
from datetime import timedelta
from django.db.models import Q
from django.contrib.auth import get_user_model

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

        if start_date:
            queryset = queryset.filter(start_date__gte=start_date)
        if end_date:
            queryset = queryset.filter(due_date__lte=end_date)

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
                message=f"새로운 작업이 배정되었습니다: {task.title}",
            )


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


# DashboardViewSet, UserSearchViewSet, ReportViewSet는 추가 요구사항에 따라 구현 필요
