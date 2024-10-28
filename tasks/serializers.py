from rest_framework import serializers
from .models import Task, TaskComment


class TaskCommentSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(
        source="author.username", read_only=True
    )

    class Meta:
        model = TaskComment
        fields = [
            "id",
            "task",
            "author",
            "author_name",
            "content",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class TaskSerializer(serializers.ModelSerializer):
    assignee_name = serializers.CharField(
        source="assignee.username", read_only=True
    )
    reporter_name = serializers.CharField(
        source="reporter.username", read_only=True
    )
    department_name = serializers.CharField(
        source="department.name", read_only=True
    )
    comments = TaskCommentSerializer(many=True, read_only=True)

    class Meta:
        model = Task
        fields = [
            "id",
            "title",
            "description",
            "status",
            "priority",
            "assignee",
            "assignee_name",
            "reporter",
            "reporter_name",
            "department",
            "department_name",
            "start_date",
            "due_date",
            "completed_at",
            "created_at",
            "updated_at",
            "comments",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]
