from django.db import models
from django.conf import settings


class ReportTemplate(models.Model):
    name = models.CharField(max_length=100)
    content = models.JSONField()  # 템플릿 구조
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE
    )
    created_at = models.DateTimeField(auto_now_add=True)
