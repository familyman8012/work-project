from django.db import models
from django.conf import settings


class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ("TASK_ASSIGNED", "작업 배정"),
        ("TASK_STATUS_CHANGED", "작업 상태 변경"),
        ("TASK_COMMENT", "작업 코멘트"),
        ("TASK_MENTION", "작업 멘션"),
        ("TASK_DUE_SOON", "작업 마감 임박"),
        ("TASK_OVERDUE", "작업 기한 초과"),
        ("TASK_REVIEWED", "작업 검토 요청"),
        ("TASK_REVIEW_COMPLETED", "작업 검토 완료"),
        ("TASK_PRIORITY_CHANGED", "작업 우선순위 변경"),
        ("TASK_BLOCKED", "작업 차단됨"),
        ("TASK_UNBLOCKED", "작업 차단 해제"),
        ("TASK_DEPENDENCY_COMPLETED", "선행 작업 완료"),
    ]

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="수신자",
    )
    notification_type = models.CharField(
        max_length=30, choices=NOTIFICATION_TYPES, verbose_name="알림 유형"
    )
    task = models.ForeignKey(
        "tasks.Task", on_delete=models.CASCADE, verbose_name="관련 작업"
    )
    message = models.TextField(verbose_name="알림 내용")
    is_read = models.BooleanField(default=False, verbose_name="읽음 여부")
    created_at = models.DateTimeField(auto_now_add=True)

    # 알림 중요도 추가
    PRIORITY_CHOICES = [
        ("HIGH", "높음"),
        ("MEDIUM", "중간"),
        ("LOW", "낮음"),
    ]
    priority = models.CharField(
        max_length=10,
        choices=PRIORITY_CHOICES,
        default="MEDIUM",
        verbose_name="알림 중요도",
    )

    # 알림 만료 시간 추가
    expires_at = models.DateTimeField(
        null=True, blank=True, verbose_name="알림 만료 시간"
    )

    class Meta:
        verbose_name = "알림"
        verbose_name_plural = "알림들"
