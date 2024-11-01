from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from .models import ReportTemplate

User = get_user_model()


class ReportTemplateModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            employee_id="EMP001",
        )
        self.template = ReportTemplate.objects.create(
            name="테스트 템플릿",
            content={"title": "제목", "body": "내용"},
            created_by=self.user,
        )

    def test_template_creation(self):
        self.assertEqual(self.template.name, "테스트 템플릿")
        self.assertEqual(self.template.content["title"], "제목")
        self.assertEqual(self.template.created_by, self.user)


class ReportTemplateAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
            employee_id="EMP001",
        )
        self.template = ReportTemplate.objects.create(
            name="테스트 템플릿",
            content={"title": "제목", "body": "내용"},
            created_by=self.user,
        )
        self.client.force_authenticate(user=self.user)

    def test_get_templates(self):
        url = reverse("reporttemplate-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["name"], "테스트 템플릿")
