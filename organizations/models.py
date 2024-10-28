from django.db import models

# Create your models here.


class Department(models.Model):
    name = models.CharField(max_length=100, verbose_name="부서명")
    code = models.CharField(
        max_length=10, unique=True, verbose_name="부서코드"
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="children",
        verbose_name="상위부서",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "부서"
        verbose_name_plural = "부서들"

    def __str__(self):
        return self.name
