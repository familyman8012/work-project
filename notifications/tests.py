from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from notifications.models import Notification
from tasks.models import Task
from organizations.models import Department

User = get_user_model()


class NotificationTests(APITestCase, TransactionTestCase):
    def setUp(self):
        # 테스트 부서 생성
        self.department = Department.objects.create(
            name="테스트부서", code="TEST001"
        )

        # 테스트 사용자 생성
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass123",
            email="test@example.com",
            employee_id="EMP001",
            department=self.department,
            role="EMPLOYEE",
            rank="STAFF",
        )

        # 테스트용 작업 생성
        self.task = Task.objects.create(
            title="Test Task",
            description="Test Description",
            assignee=self.user,
            reporter=self.user,
            start_date="2024-03-20T00:00:00Z",
            due_date="2024-03-21T00:00:00Z",
            department=self.department,
            status="TODO",
            priority="MEDIUM",
        )

        # 테스트용 알림 생성
        self.notification = Notification.objects.create(
            recipient=self.user,
            notification_type="TASK_ASSIGNED",
            task=self.task,
            message="새로운 작업이 할당되었습니다.",
        )

        # API 클라이언트에 인증 추가
        self.client.force_authenticate(user=self.user)

    def test_get_unread_count(self):
        """읽지 않은 알림 개수 조회 테스트"""
        url = reverse("notification-unread-count")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_mark_all_read(self):
        """모든 알림 읽음 처리 테스트"""
        url = reverse("notification-mark-all-read")
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response.data["detail"], "모든 알림이 읽음 처리되었습니다."
        )

        # 실제로 알림이 읽음 처리되었는지 확인
        unread_count = Notification.objects.filter(
            recipient=self.user, is_read=False
        ).count()
        self.assertEqual(unread_count, 0)
