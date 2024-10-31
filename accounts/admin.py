from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin

User = get_user_model()


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = (
        "username",
        "email",
        "employee_id",
        "role",
        "rank",
        "department",
        "is_staff",
    )
    list_filter = ("role", "rank", "department", "is_staff", "is_superuser")
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        (
            "Personal info",
            {"fields": ("first_name", "last_name", "email", "employee_id")},
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Company info", {"fields": ("role", "rank", "department")}),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "password1",
                    "password2",
                    "employee_id",
                    "role",
                    "rank",
                    "department",
                ),
            },
        ),
    )
    search_fields = (
        "username",
        "first_name",
        "last_name",
        "email",
        "employee_id",
    )
    ordering = ("username",)
