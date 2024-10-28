from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "employee_id",
            "role",
            "rank",
            "department",
        ]
        read_only_fields = ["id"]


class UserDetailSerializer(UserSerializer):
    department_name = serializers.CharField(
        source="department.name", read_only=True
    )

    class Meta(UserSerializer.Meta):
        fields = UserSerializer.Meta.fields + [
            "department_name",
            "first_name",
            "last_name",
        ]
