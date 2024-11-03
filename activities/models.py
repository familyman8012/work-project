from django.db import models
from django.conf import settings

class Activity(models.Model):
    ACTIVITY_TYPES = [
        ("TASK_CREATED", "작업 생성"),
        ("TASK_UPDATED", "작업 수정"),
        ("TASK_COMPLETED", "작업 완료"),
        ("COMMENT_ADDED", "코멘트 추가"),
        ("STATUS_CHANGED", "상태 변경"),
    ]

    type = models.CharField(max_length=50, choices=ACTIVITY_TYPES)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    task = models.ForeignKey('tasks.Task', on_delete=models.CASCADE)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at'] 