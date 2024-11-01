from django.core.management.base import BaseCommand
from django.utils import timezone
from notifications.models import Notification
from datetime import timedelta


class Command(BaseCommand):
    help = "오래된 알림 정리 및 만료된 알림 삭제"

    def handle(self, *args, **kwargs):
        # 30일 이상 된 읽은 알림 삭제
        old_notifications = Notification.objects.filter(
            is_read=True, created_at__lt=timezone.now() - timedelta(days=30)
        )
        deleted_count = old_notifications.count()
        old_notifications.delete()

        # 만료된 알림 삭제
        expired_notifications = Notification.objects.filter(
            expires_at__lt=timezone.now()
        )
        expired_count = expired_notifications.count()
        expired_notifications.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully deleted {deleted_count} old notifications and "
                f"{expired_count} expired notifications"
            )
        )
