from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    recipient_name = serializers.CharField(
        source="recipient.username", read_only=True
    )
    task_title = serializers.CharField(source="task.title", read_only=True)

    class Meta:
        model = Notification
        fields = [
            "id",
            "recipient",
            "recipient_name",
            "notification_type",
            "task",
            "task_title",
            "message",
            "is_read",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]
