from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from .models import Department

User = get_user_model()


class DepartmentModelTest(TestCase):
    def setUp(self):
        self.parent_dept = Department.objects.create(
            name="상위부서", code="PARENT001"
        )
        self.dept = Department.objects.create(
            name="테스트부서", code="TEST001", parent=self.parent_dept
        )

    def test_department_creation(self):
        self.assertEqual(self.dept.name, "테스트부서")
        self.assertEqual(self.dept.code, "TEST001")
        self.assertEqual(self.dept.parent, self.parent_dept)

    def test_department_str(self):
        self.assertEqual(str(self.dept), "테스트부서")


class DepartmentAPITest(APITestCase):
    def setUp(self):
        self.department = Department.objects.create(
            name="테스트부서", code="TEST001"
        )
        self.user = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="admin123",
            employee_id="ADMIN001",
        )
        self.client.force_authenticate(user=self.user)

    def test_get_departments(self):
        url = reverse("department-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["name"], "테스트부서")
