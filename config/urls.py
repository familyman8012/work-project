"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from django.views.generic import RedirectView
from rest_framework.permissions import AllowAny

from accounts.views import UserViewSet
from organizations.views import DepartmentViewSet
from tasks.views import (
    TaskViewSet,
    TaskCommentViewSet,
    TaskAttachmentViewSet,
    TaskHistoryViewSet,
    TaskTimeLogViewSet,
    TaskEvaluationViewSet,
)
from notifications.views import NotificationViewSet
from accounts.auth_views import logout
from reports.views import ReportViewSet

router = DefaultRouter()
router.register(r"users", UserViewSet)
router.register(r"departments", DepartmentViewSet)
router.register(r"tasks", TaskViewSet)
router.register(r"task-comments", TaskCommentViewSet)
router.register(r"task-attachments", TaskAttachmentViewSet)
router.register(r"task-history", TaskHistoryViewSet)
router.register(r"task-time-logs", TaskTimeLogViewSet)
router.register(r"task-evaluations", TaskEvaluationViewSet)
router.register(r"notifications", NotificationViewSet, basename="notification")
router.register(r"reports", ReportViewSet, basename="report")

urlpatterns = [
    path("", RedirectView.as_view(url="/api/docs/", permanent=False)),
    path("admin/", admin.site.urls),
    path("api/", include(router.urls)),
    path(
        "api/schema/",
        SpectacularAPIView.as_view(permission_classes=[AllowAny]),
        name="schema",
    ),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(
            url_name="schema", permission_classes=[AllowAny]
        ),
        name="swagger-ui",
    ),
    path(
        "api/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"
    ),
    path(
        "api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"
    ),
    path(
        "api/redoc/",
        SpectacularRedocView.as_view(
            url_name="schema", permission_classes=[AllowAny]
        ),
        name="redoc",
    ),
    path("api/auth/logout/", logout, name="auth_logout"),
]
