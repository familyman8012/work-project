from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend
from .models import (
    Task,
    TaskComment,
    TaskAttachment,
    TaskHistory,
    TaskTimeLog,
    TaskEvaluation,
)
from .serializers import (
    TaskSerializer,
    TaskCommentSerializer,
    TaskAttachmentSerializer,
    TaskHistorySerializer,
    TaskTimeLogSerializer,
    TaskEvaluationSerializer,
)
from .filters import TaskFilter


class TaskViewSet(viewsets.ModelViewSet):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    filterset_class = TaskFilter
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = ["title", "description"]


class TaskCommentViewSet(viewsets.ModelViewSet):
    queryset = TaskComment.objects.all()
    serializer_class = TaskCommentSerializer


class TaskAttachmentViewSet(viewsets.ModelViewSet):
    queryset = TaskAttachment.objects.all()
    serializer_class = TaskAttachmentSerializer


class TaskHistoryViewSet(viewsets.ModelViewSet):
    queryset = TaskHistory.objects.all()
    serializer_class = TaskHistorySerializer


class TaskTimeLogViewSet(viewsets.ModelViewSet):
    queryset = TaskTimeLog.objects.all()
    serializer_class = TaskTimeLogSerializer


class TaskEvaluationViewSet(viewsets.ModelViewSet):
    queryset = TaskEvaluation.objects.all()
    serializer_class = TaskEvaluationSerializer


# DashboardViewSet, UserSearchViewSet, ReportViewSet는 추가 요구사항에 따라 구현 필요
