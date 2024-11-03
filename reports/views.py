from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db.models import Count, Avg, Q, F, Sum
from datetime import datetime, timedelta
from tasks.models import Task, TaskEvaluation
from django.db.models.functions import TruncDate
from django.contrib.auth import get_user_model
from django.utils import timezone
from collections import defaultdict

User = get_user_model()

class ReportViewSet(viewsets.ViewSet):
    @action(detail=False, methods=["get"])
    def personal_report(self, request):
        user = request.user
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        employee_id = request.query_params.get("employee_id")  # 다른 직원 보고서 조회용

        if not start_date or not end_date:
            return Response(
                {"error": "start_date와 end_date는 필수 파라미터입니다."},
                status=400,
            )

        # 권한 체크
        if employee_id and employee_id != str(user.id):
            target_user = User.objects.get(id=employee_id)
            if not self.can_view_employee_report(user, target_user):
                return Response({"error": "권한이 없습니다."}, status=403)
            report_user = target_user
        else:
            report_user = user

        tasks = Task.objects.filter(
            assignee=report_user,
            created_at__range=[start_date, end_date]
        )

        # 선택된 기간에 작업이 없는 경우
        if not tasks.exists():
            return Response({
                "basic_stats": {
                    "total_tasks": 0,
                    "completed_tasks": 0,
                    "in_progress_tasks": 0,
                    "delayed_tasks": 0,
                },
                "time_stats": {
                    "average_completion_time": None,
                    "estimated_vs_actual": 0,
                    "daily_work_hours": [],
                },
                "quality_stats": {
                    "average_score": 0,
                    "review_rejection_rate": 0,
                    "rework_rate": 0,
                },
                "distribution_stats": {
                    "priority_distribution": [],
                    "difficulty_distribution": [],
                    "status_distribution": [],
                },
                # 작업이 없는 경우 comparison_stats도 null로 반환
                "comparison_stats": None
            })

        # 기본 통계
        basic_stats = {
            "total_tasks": tasks.count(),
            "completed_tasks": tasks.filter(status="DONE").count(),
            "in_progress_tasks": tasks.filter(status="IN_PROGRESS").count(),
            "delayed_tasks": len([task for task in tasks if task.is_delayed]),
        }

        # 시간 관리 통계
        time_stats = {
            "average_completion_time": tasks.filter(
                status="DONE",
                completed_at__isnull=False
            ).aggregate(
                avg_time=Avg(F('completed_at') - F('start_date'))
            )["avg_time"],
            "estimated_vs_actual": self.calculate_time_efficiency(tasks),
            "daily_work_hours": self.calculate_daily_hours(tasks),
        }

        # 품질 지표
        quality_stats = {
            "average_score": TaskEvaluation.objects.filter(
                task__in=tasks
            ).aggregate(avg_score=Avg('performance_score'))["avg_score"],
            "review_rejection_rate": self.calculate_rejection_rate(tasks),
            "rework_rate": self.calculate_rework_rate(tasks),
        }

        # 작업 분포
        distribution_stats = {
            "priority_distribution": self.calculate_distribution(tasks, "priority"),
            "difficulty_distribution": self.calculate_distribution(tasks, "difficulty"),
            "status_distribution": self.calculate_distribution(tasks, "status"),
        }

        # 비교 분석 (팀장 이상만)
        comparison_stats = {}
        if self.can_view_team_stats(user):
            comparison_stats = {
                "team_comparison": self.get_team_comparison(report_user, start_date, end_date),
                "department_comparison": self.get_department_comparison(report_user, start_date, end_date),
            }

        return Response({
            "basic_stats": basic_stats,
            "time_stats": time_stats,
            "quality_stats": quality_stats,
            "distribution_stats": distribution_stats,
            "comparison_stats": comparison_stats,
        })

    def can_view_employee_report(self, user, target_user):
        """직원 보고서 조회 권한 확인"""
        if user.is_superuser:
            return True
            
        # 본인 보고서는 항상 볼 수 있음
        if user.id == target_user.id:
            return True
            
        # 같은 부서 내에서 팀장 이상은 부서원의 보고서를 볼 수 있음
        if user.department == target_user.department and user.rank in [
            "MANAGER", 
            "DEPUTY_GENERAL_MANAGER", 
            "GENERAL_MANAGER", 
            "DIRECTOR"
        ]:
            return True
            
        # 상위 부서(본부)의 본부장/이사는 하위 부서(팀)의 보고서를 볼 수 있음
        if target_user.department.parent and user.department == target_user.department.parent and user.rank in [
            "GENERAL_MANAGER",
            "DIRECTOR"
        ]:
            return True
            
        # 이사는 모든 부서의 보고서를 볼 수 있음
        if user.rank == "DIRECTOR":
            return True
            
        return False

    def calculate_time_efficiency(self, tasks):
        """작업 시간 효율성 계산"""
        completed_tasks = tasks.filter(status="DONE", estimated_hours__gt=0)
        if not completed_tasks.exists():
            return 0
            
        total_estimated = completed_tasks.aggregate(Sum('estimated_hours'))['estimated_hours__sum'] or 0
        total_actual = completed_tasks.aggregate(Sum('actual_hours'))['actual_hours__sum'] or 0
        
        if total_estimated == 0:
            return 0
            
        return (total_actual / total_estimated) * 100

    def calculate_daily_hours(self, tasks):
        """일별 작업 시간 계산"""
        daily_hours = []
        tasks_with_logs = tasks.filter(time_logs__isnull=False).distinct()
        
        for task in tasks_with_logs:
            logs = task.time_logs.all()
            for log in logs:
                date = log.start_time.date()
                hours = 0
                if log.end_time:
                    duration = log.end_time - log.start_time
                    hours = duration.total_seconds() / 3600
                    daily_hours.append({
                        'date': date.isoformat(),
                        'hours': round(hours, 1)
                    })
        
        return sorted(daily_hours, key=lambda x: x['date'])

    def calculate_rejection_rate(self, tasks):
        """검토 반려율 계산"""
        evaluated_tasks = tasks.filter(evaluations__isnull=False).distinct()
        if not evaluated_tasks.exists():
            return 0
            
        rejected_tasks = evaluated_tasks.filter(evaluations__performance_score__lt=3)
        return (rejected_tasks.count() / evaluated_tasks.count()) * 100

    def calculate_rework_rate(self, tasks):
        """재작업률 계산"""
        completed_tasks = tasks.filter(status="DONE")
        if not completed_tasks.exists():
            return 0
            
        # 상태가 DONE에서 다른 상태로 변경된 이력이 있는 작업을 재작업으로 간주
        rework_tasks = completed_tasks.filter(
            history__previous_status="DONE",
            history__new_status__in=["IN_PROGRESS", "REVIEW"]
        ).distinct()
        
        return (rework_tasks.count() / completed_tasks.count()) * 100

    def calculate_distribution(self, tasks, field):
        """작업 분포 계산"""
        distribution = tasks.values(field).annotate(count=Count(field))
        total = tasks.count()
        
        # 필드별 정렬 순서 정의
        field_order = {
            'priority': ['URGENT', 'HIGH', 'MEDIUM', 'LOW'],
            'difficulty': ['VERY_HARD', 'HARD', 'MEDIUM', 'EASY'],
            'status': ['TODO', 'IN_PROGRESS', 'REVIEW', 'DONE', 'HOLD']
        }
        
        # 비율 계산 및 필드명 매핑
        result = []
        for item in distribution:
            field_value = item[field]
            count = item['count']
            percentage = (count / total * 100) if total > 0 else 0
            result.append({
                "field": field_value,
                "count": count,
                "percentage": round(percentage, 1)
            })
        
        # 정렬된 결과 반환
        if field in field_order:
            result.sort(key=lambda x: field_order[field].index(x['field']) 
                       if x['field'] in field_order[field] else len(field_order[field]))
        
        return result

    def get_team_comparison(self, user, start_date, end_date):
        """팀 비교 통계 계산"""
        team_tasks = Task.objects.filter(
            assignee__department=user.department,
            created_at__range=[start_date, end_date]
        )
        
        # 팀 평균 완료 시간 계산
        avg_completion_time = self.calculate_team_average(team_tasks)
        if avg_completion_time:
            hours = avg_completion_time.total_seconds() // 3600
            minutes = (avg_completion_time.total_seconds() % 3600) // 60
            avg_completion_time_str = f"{int(hours)}h {int(minutes)}m"
        else:
            avg_completion_time_str = "0h 0m"
        
        # 내 완료 시간 계산
        my_tasks = Task.objects.filter(
            assignee=user,
            created_at__range=[start_date, end_date],
            status="DONE",
            completed_at__isnull=False
        )
        my_completion_time = None
        if my_tasks.exists():
            total_time = sum((task.completed_at - task.start_date).total_seconds() for task in my_tasks)
            avg_time = total_time / my_tasks.count()
            hours = int(avg_time // 3600)
            minutes = int((avg_time % 3600) // 60)
            my_completion_time = f"{hours}h {minutes}m"
        else:
            my_completion_time = "0h 0m"
        
        return {
            "team_avg_completion_time": avg_completion_time_str,
            "team_avg_score": round(self.calculate_team_score(team_tasks) or 0, 1),
            "my_completion_time": my_completion_time,  # 추가
            "relative_efficiency": self.calculate_relative_efficiency(
                Task.objects.filter(assignee=user, created_at__range=[start_date, end_date]),
                team_tasks
            ),
            "relative_quality": self.calculate_relative_quality(
                Task.objects.filter(assignee=user, created_at__range=[start_date, end_date]),
                team_tasks
            )
        }

    def get_department_comparison(self, user, start_date, end_date):
        """부서 비교 통계 계산"""
        dept = user.department
        if dept.parent:  # 팀인 경우 상위 부서(본부) 기준
            dept = dept.parent
            
        dept_tasks = Task.objects.filter(
            assignee__department__parent=dept,
            created_at__range=[start_date, end_date]
        )
        
        # 부서 평균 완료 시간 계산
        avg_completion_time = self.calculate_dept_average(dept_tasks)
        if avg_completion_time:
            hours = avg_completion_time.total_seconds() // 3600
            minutes = (avg_completion_time.total_seconds() % 3600) // 60
            avg_completion_time_str = f"{int(hours)}h {int(minutes)}m"
        else:
            avg_completion_time_str = "0h 0m"
        
        # 내 완료 시간 계산
        my_tasks = Task.objects.filter(
            assignee=user,
            created_at__range=[start_date, end_date],
            status="DONE",
            completed_at__isnull=False
        )
        my_completion_time = None
        if my_tasks.exists():
            total_time = sum((task.completed_at - task.start_date).total_seconds() for task in my_tasks)
            avg_time = total_time / my_tasks.count()
            hours = int(avg_time // 3600)
            minutes = int((avg_time % 3600) // 60)
            my_completion_time = f"{hours}h {minutes}m"
        else:
            my_completion_time = "0h 0m"
        
        return {
            "dept_avg_completion_time": avg_completion_time_str,
            "dept_avg_score": round(self.calculate_dept_score(dept_tasks) or 0, 1),
            "my_completion_time": my_completion_time,  # 추가
            "relative_efficiency": self.calculate_relative_efficiency(
                Task.objects.filter(assignee=user, created_at__range=[start_date, end_date]),
                dept_tasks
            ),
            "relative_quality": self.calculate_relative_quality(
                Task.objects.filter(assignee=user, created_at__range=[start_date, end_date]),
                dept_tasks
            )
        }

    def can_view_team_stats(self, user):
        return user.role == "ADMIN" or user.role == "MANAGER" or user.rank in ["DIRECTOR", "GENERAL_MANAGER"]

    def calculate_team_average(self, tasks):
        completed_tasks = tasks.filter(
            status="DONE",
            completed_at__isnull=False
        )
        if not completed_tasks.exists():
            return None
        
        return completed_tasks.aggregate(
            avg_time=Avg(F('completed_at') - F('start_date'))
        )["avg_time"]

    def calculate_team_score(self, tasks):
        evaluations = TaskEvaluation.objects.filter(task__in=tasks)
        if not evaluations.exists():
            return None
        
        return evaluations.aggregate(
            avg_score=Avg('performance_score')
        )["avg_score"]

    def calculate_dept_average(self, tasks):
        completed_tasks = tasks.filter(
            status="DONE",
            completed_at__isnull=False
        )
        if not completed_tasks.exists():
            return None
        
        return completed_tasks.aggregate(
            avg_time=Avg(F('completed_at') - F('start_date'))
        )["avg_time"]

    def calculate_dept_score(self, tasks):
        evaluations = TaskEvaluation.objects.filter(task__in=tasks)
        if not evaluations.exists():
            return None
        
        return evaluations.aggregate(
            avg_score=Avg('performance_score')
        )["avg_score"]

    def calculate_team_avg_score(self, team_tasks):
        """팀 평균 평가 점수 계산"""
        evaluations = TaskEvaluation.objects.filter(task__in=team_tasks)
        return evaluations.aggregate(Avg('performance_score'))['performance_score__avg'] or 0

    def calculate_dept_avg_score(self, dept_tasks):
        """부서 평균 평가 점수 계산"""
        evaluations = TaskEvaluation.objects.filter(task__in=dept_tasks)
        return evaluations.aggregate(Avg('performance_score'))['performance_score__avg'] or 0

    def calculate_relative_efficiency(self, user_tasks, comparison_tasks):
        """상대적 효율성 계산"""
        user_efficiency = self.calculate_time_efficiency(user_tasks)
        comparison_efficiency = self.calculate_time_efficiency(comparison_tasks)
        
        if comparison_efficiency == 0:
            return 0
            
        return (user_efficiency / comparison_efficiency) * 100

    def calculate_relative_quality(self, user_tasks, comparison_tasks):
        """상대적 품질 점수 계산"""
        user_score = self.calculate_team_avg_score(user_tasks)
        comparison_score = self.calculate_team_avg_score(comparison_tasks)
        
        if comparison_score == 0:
            return 0
            
        return (user_score / comparison_score) * 100

    def calculate_rank_in_team(self, user):
        """팀 내 순위 계산"""
        team_members = User.objects.filter(department=user.department)
        rankings = []
        
        for member in team_members:
            tasks = Task.objects.filter(assignee=member, status="DONE")
            score = self.calculate_team_avg_score(tasks)
            rankings.append((member, score))
            
        rankings.sort(key=lambda x: x[1], reverse=True)
        for rank, (member, _) in enumerate(rankings, 1):
            if member == user:
                return rank
                
        return len(rankings)

    def calculate_rank_in_department(self, user):
        """부서 내 순위 계산"""
        dept_members = User.objects.filter(department__parent=user.department.parent)
        rankings = []
        
        for member in dept_members:
            tasks = Task.objects.filter(assignee=member, status="DONE")
            score = self.calculate_dept_avg_score(tasks)
            rankings.append((member, score))
            
        rankings.sort(key=lambda x: x[1], reverse=True)
        for rank, (member, _) in enumerate(rankings, 1):
            if member == user:
                return rank
                
        return len(rankings)
