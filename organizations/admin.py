from django.contrib import admin
from .models import Department


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "parent")
    search_fields = ("name", "code")
    list_filter = ("parent",)
