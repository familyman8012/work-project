from django.shortcuts import render
from rest_framework import viewsets, status
from django.contrib.auth import get_user_model
from .serializers import UserSerializer, UserDetailSerializer
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from datetime import datetime
from tasks.models import Task
from tasks.serializers import TaskSerializer

# Create your views here.

User = get_user_model()


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.action in ["retrieve", "me"]:
            return UserDetailSerializer
        return UserSerializer

    @action(detail=False, methods=["get"])
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def tasks_current(self, request, pk=None):
        user = self.get_object()
        tasks = Task.objects.filter(assignee=user, status="IN_PROGRESS")
        serializer = TaskSerializer(tasks, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def tasks_history(self, request, pk=None):
        user = self.get_object()
        status = request.query_params.get("status")
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")

        tasks = Task.objects.filter(assignee=user)

        if status:
            tasks = tasks.filter(status=status)
        if start_date:
            tasks = tasks.filter(start_date__gte=start_date)
        if end_date:
            tasks = tasks.filter(due_date__lte=end_date)

        serializer = TaskSerializer(tasks, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["get"])
    def tasks_statistics(self, request, pk=None):
        user = self.get_object()
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")

        tasks = Task.objects.filter(assignee=user)
        if start_date:
            tasks = tasks.filter(start_date__gte=start_date)
        if end_date:
            tasks = tasks.filter(due_date__lte=end_date)

        total_tasks = tasks.count()
        completed_tasks = tasks.filter(status="DONE").count()
        in_progress_tasks = tasks.filter(status="IN_PROGRESS").count()
        delayed_tasks = len([task for task in tasks if task.is_delayed])

        completion_rate = (
            (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
        )

        tasks_by_priority = {
            "HIGH": tasks.filter(priority="HIGH").count(),
            "MEDIUM": tasks.filter(priority="MEDIUM").count(),
            "LOW": tasks.filter(priority="LOW").count(),
        }

        return Response(
            {
                "total_tasks": total_tasks,
                "completed_tasks": completed_tasks,
                "in_progress_tasks": in_progress_tasks,
                "delayed_tasks": delayed_tasks,
                "completion_rate": completion_rate,
                "tasks_by_priority": tasks_by_priority,
            }
        )


class UserSearchViewSet(viewsets.ViewSet):
    @action(detail=False, methods=["get"])
    def search_by_experience(self, request):
        task_keyword = request.query_params.get("task_keyword", "")
        users = User.objects.filter(
            assigned_tasks__title__icontains=task_keyword
        ).distinct()
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def search_by_department(self, request):
        department_id = request.query_params.get("department_id")
        users = User.objects.filter(department_id=department_id)
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def search_by_rank(self, request):
        rank = request.query_params.get("rank")
        users = User.objects.filter(rank=rank)
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)
