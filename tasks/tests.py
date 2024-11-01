from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from organizations.models import Department
from .models import Task, TaskComment, TaskAttachment

User = get_user_model()


class TaskModelTest(TestCase):
    def setUp(self):
        self.department = Department.objects.create(
            name="테스트부서", code="TEST001"
        )
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            employee_id="EMP001",
            department=self.department,
            role="EMPLOYEE",
            rank="STAFF",
        )
        self.task = Task.objects.create(
            title="테스트 작업",
            description="테스트 설명",
            status="TODO",
            priority="MEDIUM",
            assignee=self.user,
            reporter=self.user,
            department=self.department,
            start_date="2024-03-20T00:00:00Z",
            due_date="2024-03-21T00:00:00Z",
        )

    def test_task_creation(self):
        self.assertEqual(self.task.title, "테스트 작업")
        self.assertEqual(self.task.status, "TODO")
        self.assertEqual(self.task.assignee, self.user)
        self.assertEqual(self.task.department, self.department)

    def test_task_str(self):
        self.assertEqual(str(self.task), "테스트 작업")

    def test_is_delayed(self):
        from django.utils import timezone
        from datetime import timedelta

        self.task.due_date = timezone.now() - timedelta(days=1)
        self.task.save()
        self.assertTrue(self.task.is_delayed)


class TaskAPITest(APITestCase):
    def setUp(self):
        self.department = Department.objects.create(
            name="테스트부서", code="TEST001"
        )
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            employee_id="EMP001",
            department=self.department,
            role="EMPLOYEE",
            rank="STAFF",
        )
        self.task = Task.objects.create(
            title="테스트 작업",
            description="테스트 설명",
            status="TODO",
            priority="MEDIUM",
            assignee=self.user,
            reporter=self.user,
            department=self.department,
            start_date="2024-03-20T00:00:00Z",
            due_date="2024-03-21T00:00:00Z",
        )
        self.client.force_authenticate(user=self.user)

    def test_get_tasks(self):
        url = reverse("task-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["title"], "테스트 작업")

    def test_create_task_comment(self):
        url = reverse("taskcomment-list")
        data = {
            "task": self.task.id,
            "content": "테스트 코멘트",
            "author": self.user.id,
        }
        response = self.client.post(url, data)

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["content"], "테스트 코멘트")
        self.assertEqual(response.data["author"], self.user.id)
