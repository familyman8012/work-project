from django.db import models
from django.conf import settings

# Create your models here.


class Task(models.Model):
    STATUS_CHOICES = [
        ("TODO", "예정"),
        ("IN_PROGRESS", "진행중"),
        ("REVIEW", "검토중"),
        ("DONE", "완료"),
        ("HOLD", "보류"),
    ]

    PRIORITY_CHOICES = [
        ("LOW", "낮음"),
        ("MEDIUM", "보통"),
        ("HIGH", "높음"),
        ("URGENT", "긴급"),
    ]

    title = models.CharField(max_length=200, verbose_name="작업명")
    description = models.TextField(verbose_name="작업 설명")
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="TODO",
        verbose_name="상태",
    )
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default="MEDIUM",
        verbose_name="우선순위",
    )

    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="assigned_tasks",
        verbose_name="담당자",
    )

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reported_tasks",
        verbose_name="보고자",
    )

    department = models.ForeignKey(
        "organizations.Department",
        on_delete=models.CASCADE,
        related_name="tasks",
        verbose_name="담당 부서",
    )

    start_date = models.DateTimeField(verbose_name="시작일")
    due_date = models.DateTimeField(verbose_name="마감일")
    completed_at = models.DateTimeField(
        null=True, blank=True, verbose_name="완료일"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "작업"
        verbose_name_plural = "작업들"

    def __str__(self):
        return self.title


class TaskComment(models.Model):
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="comments",
        verbose_name="작업",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="task_comments",
        verbose_name="작성자",
    )
    content = models.TextField(verbose_name="내용")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "작업 코멘트"
        verbose_name_plural = "작업 코멘트들"
