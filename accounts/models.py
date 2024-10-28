from django.contrib.auth.models import AbstractUser
from django.db import models

# Create your models here.


class User(AbstractUser):
    ROLE_CHOICES = [
        ("EMPLOYEE", "일반 직원"),
        ("MANAGER", "관리자"),
        ("ADMIN", "최고 관리자"),
    ]

    RANK_CHOICES = [
        ("STAFF", "사원"),
        ("SENIOR", "주임"),
        ("ASSISTANT_MANAGER", "대리"),
        ("MANAGER", "과장"),
        ("DEPUTY_GENERAL_MANAGER", "차장"),
        ("GENERAL_MANAGER", "부장"),
        ("DIRECTOR", "이사"),
    ]

    employee_id = models.CharField(
        max_length=10, unique=True, help_text="사원 번호"
    )
    role = models.CharField(
        max_length=20, choices=ROLE_CHOICES, default="EMPLOYEE"
    )
    rank = models.CharField(
        max_length=30, choices=RANK_CHOICES, default="STAFF"
    )
    department = models.ForeignKey(
        "organizations.Department",
        on_delete=models.SET_NULL,
        null=True,
        related_name="employees",
    )

    class Meta:
        verbose_name = "사용자"
        verbose_name_plural = "사용자들"
