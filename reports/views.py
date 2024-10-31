from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count, Avg, Q
from datetime import datetime, timedelta
from tasks.models import Task


class ReportViewSet(viewsets.ViewSet):
    @action(detail=False, methods=["get"])
    def personal_report(self, request):
        user = request.user
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")

        if not start_date or not end_date:
            return Response(
                {"error": "start_date와 end_date는 필수 파라미터입니다."},
                status=400,
            )

        tasks = Task.objects.filter(
            assignee=user, created_at__range=[start_date, end_date]
        )

        data = {
            "total_tasks": tasks.count(),
            "completed_tasks": tasks.filter(status="DONE").count(),
            "in_progress_tasks": tasks.filter(status="IN_PROGRESS").count(),
            "average_completion_time": tasks.filter(status="DONE").aggregate(
                avg_time=Avg("completed_at")
            )["avg_time"],
        }
        return Response(data)

    @action(detail=False, methods=["get"])
    def department_report(self, request):
        department_id = request.query_params.get("department_id")
        # 부서별 실적 보고서 생성 로직
        return Response(data)

    @action(detail=False, methods=["get"])
    def performance_evaluation(self, request):
        user_id = request.query_params.get("user_id")
        # 인사평가 자료 생성 로직
        return Response(data)
