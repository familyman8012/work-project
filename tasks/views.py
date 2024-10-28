from django.shortcuts import render
from rest_framework import viewsets
from .models import Task, TaskComment
from .serializers import TaskSerializer, TaskCommentSerializer
from rest_framework.permissions import IsAuthenticated
from django_filters import rest_framework as filters

# Create your views here.


class TaskFilter(filters.FilterSet):
    class Meta:
        model = Task
        fields = {
            "status": ["exact"],
            "priority": ["exact"],
            "assignee": ["exact"],
            "reporter": ["exact"],
            "department": ["exact"],
            "created_at": ["gte", "lte"],
            "due_date": ["gte", "lte"],
        }


class TaskViewSet(viewsets.ModelViewSet):
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = [IsAuthenticated]
    filterset_class = TaskFilter


class TaskCommentViewSet(viewsets.ModelViewSet):
    queryset = TaskComment.objects.all()
    serializer_class = TaskCommentSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["task", "author"]
