from django.test import TestCase
from django.contrib.auth import get_user_model
from organizations.models import Department
from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse

User = get_user_model()


class UserModelTest(TestCase):
    def setUp(self):
        self.department = Department.objects.create(
            name="테스트부서", code="TEST001"
        )

    def test_create_user(self):
        user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            employee_id="EMP001",
            department=self.department,
            role="EMPLOYEE",
            rank="STAFF",
        )

        self.assertEqual(user.username, "testuser")
        self.assertEqual(user.email, "test@example.com")
        self.assertEqual(user.employee_id, "EMP001")
        self.assertEqual(user.department, self.department)
        self.assertEqual(user.role, "EMPLOYEE")
        self.assertEqual(user.rank, "STAFF")
        self.assertTrue(user.is_active)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_superuser(self):
        admin_user = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="admin123",
            employee_id="ADMIN001",
        )

        self.assertTrue(admin_user.is_superuser)
        self.assertTrue(admin_user.is_staff)

    def test_user_str_method(self):
        user = User.objects.create_user(
            username="testuser2",
            email="test2@example.com",
            password="testpass123",
            employee_id="EMP002",
        )
        self.assertEqual(str(user), "testuser2")

    def test_user_rank_choices(self):
        user = User.objects.create_user(
            username="testuser3",
            email="test3@example.com",
            password="testpass123",
            employee_id="EMP003",
            rank="MANAGER",
        )
        self.assertIn(user.rank, dict(User.RANK_CHOICES))


class UserAPITest(APITestCase):
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
        self.client.force_authenticate(user=self.user)

    def test_get_user_profile(self):
        url = reverse("user-detail", kwargs={"pk": self.user.pk})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "testuser")
        self.assertEqual(response.data["email"], "test@example.com")
