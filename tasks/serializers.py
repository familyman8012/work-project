from rest_framework import serializers
from .models import (
    Task,
    TaskComment,
    TaskAttachment,
    TaskHistory,
    TaskTimeLog,
    TaskEvaluation,
)


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
        read_only_fields = ["id", "author", "created_at", "updated_at"]


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
    is_delayed = serializers.BooleanField(read_only=True)

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
            "estimated_hours",
            "actual_hours",
            "is_delayed",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class TaskAttachmentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(
        source="uploaded_by.username", read_only=True
    )

    class Meta:
        model = TaskAttachment
        fields = [
            "id",
            "task",
            "file",
            "filename",
            "uploaded_by",
            "uploaded_by_name",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class TaskHistorySerializer(serializers.ModelSerializer):
    changed_by_name = serializers.CharField(
        source="changed_by.username", read_only=True
    )

    class Meta:
        model = TaskHistory
        fields = [
            "id",
            "task",
            "changed_by",
            "changed_by_name",
            "previous_status",
            "new_status",
            "comment",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class TaskTimeLogSerializer(serializers.ModelSerializer):
    logged_by_name = serializers.CharField(
        source="logged_by.username", read_only=True
    )
    duration = serializers.DurationField(read_only=True)

    class Meta:
        model = TaskTimeLog
        fields = [
            "id",
            "task",
            "start_time",
            "end_time",
            "duration",
            "logged_by",
            "logged_by_name",
        ]
        read_only_fields = ["id", "duration", "logged_by"]


class TaskEvaluationSerializer(serializers.ModelSerializer):
    evaluator_name = serializers.CharField(
        source="evaluator.username", read_only=True
    )
    task = TaskSerializer(read_only=True)
    task_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = TaskEvaluation
        fields = [
            "id",
            "task",
            "task_id",
            "evaluator",
            "evaluator_name",
            "difficulty",
            "performance_score",
            "feedback",
            "created_at",
        ]
        read_only_fields = ["id", "evaluator", "created_at"]

    def create(self, validated_data):
        if "task" not in validated_data:
            raise serializers.ValidationError(
                {"task": "This field is required."}
            )
        return super().create(validated_data)


class TaskCalendarSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = [
            "id",
            "title",
            "start_date",
            "due_date",
            "status",
            "priority",
            "is_milestone",
            "assignee",
            "is_delayed",
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["color"] = self.get_status_color(instance.status)
        data["textColor"] = "#ffffff"
        data["progress"] = self.get_progress(instance)
        return data

    def get_status_color(self, status):
        colors = {
            "TODO": "#9e9e9e",
            "IN_PROGRESS": "#1976d2",
            "REVIEW": "#ed6c02",
            "DONE": "#2e7d32",
            "HOLD": "#d32f2f",
        }
        return colors.get(status, "#9e9e9e")

    def get_progress(self, task):
        if task.estimated_hours and task.actual_hours:
            return min((task.actual_hours / task.estimated_hours) * 100, 100)
        return 0
