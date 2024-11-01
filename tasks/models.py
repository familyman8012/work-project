from django.db import models
from django.conf import settings
from django.utils import timezone

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

    estimated_hours = models.FloatField(
        verbose_name="예상 소요 시간", null=True, blank=True
    )
    actual_hours = models.FloatField(
        verbose_name="실제 소요 시간", null=True, blank=True
    )
    difficulty = models.CharField(
        max_length=20,
        choices=[
            ("EASY", "쉬움"),
            ("MEDIUM", "보통"),
            ("HARD", "어려움"),
            ("VERY_HARD", "매우 어려움"),
        ],
        default="MEDIUM",
        verbose_name="난이도",
    )

    class Meta:
        verbose_name = "작업"
        verbose_name_plural = "작업들"

    def __str__(self):
        return self.title

    @property
    def is_delayed(self):
        if self.due_date and self.status != "DONE":
            return timezone.now() > self.due_date
        return False

    def delete(self, *args, **kwargs):
        # 관련된 모든 데이터 삭제
        self.comments.all().delete()
        self.time_logs.all().delete()
        self.history.all().delete()
        self.attachments.all().delete()
        self.evaluations.all().delete()
        super().delete(*args, **kwargs)


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


class TaskAttachment(models.Model):
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="attachments",
        verbose_name="작업",
    )
    file = models.FileField(
        upload_to="task_attachments/", verbose_name="첨부파일"
    )
    filename = models.CharField(max_length=255, verbose_name="파일명")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name="업로더",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "작업 첨부파일"
        verbose_name_plural = "작업 첨부파일들"


class TaskHistory(models.Model):
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="history",
        verbose_name="작업",
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name="변경자",
    )
    previous_status = models.CharField(
        max_length=20, choices=Task.STATUS_CHOICES, verbose_name="이전 상태"
    )
    new_status = models.CharField(
        max_length=20, choices=Task.STATUS_CHOICES, verbose_name="새로운 상태"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    comment = models.TextField(blank=True, verbose_name="변경 사유")

    class Meta:
        verbose_name = "작업 히스토리"
        verbose_name_plural = "작업 히스토리들"


class TaskTimeLog(models.Model):
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="time_logs",
        verbose_name="작업",
    )
    start_time = models.DateTimeField(verbose_name="시작 시간")
    end_time = models.DateTimeField(
        null=True, blank=True, verbose_name="종료 시간"
    )
    duration = models.DurationField(
        null=True, blank=True, verbose_name="소요 시간"
    )
    logged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name="기록자",
    )

    class Meta:
        verbose_name = "작업 시간 로그"
        verbose_name_plural = "작업 시간 로그들"


class TaskEvaluation(models.Model):
    DIFFICULTY_CHOICES = [
        ("EASY", "쉬움"),
        ("MEDIUM", "보통"),
        ("HARD", "어려움"),
        ("VERY_HARD", "매우 어려움"),
    ]

    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="evaluations",
        verbose_name="작업",
    )
    evaluator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name="평가자",
    )
    difficulty = models.CharField(
        max_length=20, choices=DIFFICULTY_CHOICES, verbose_name="난이도"
    )
    performance_score = models.IntegerField(
        choices=[(i, i) for i in range(1, 6)], verbose_name="수행 점수"
    )
    feedback = models.TextField(verbose_name="피드백")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "작업 평가"
        verbose_name_plural = "작업 평가들"
