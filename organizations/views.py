from rest_framework import viewsets, status
from rest_framework.response import Response
from .models import Department
from .serializers import DepartmentSerializer
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q


class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = Department.objects.all()

        # parent_isnull 파라미터로 본부만 또는 팀만 필터링
        parent_isnull = self.request.query_params.get("parent_isnull")
        if parent_isnull is not None:
            is_null = parent_isnull.lower() == "true"
            if is_null:
                # 본부만 조회하는 경우, 하위 부서도 함께 조회
                headquarters = queryset.filter(parent__isnull=True)
                teams = queryset.filter(parent__in=headquarters)
                queryset = headquarters | teams
            else:
                # 팀만 조회
                queryset = queryset.filter(parent__isnull=False)

        return queryset.order_by("parent_id", "code")

    def perform_create(self, serializer):
        # 권한 체크
        user = self.request.user
        if not (user.role == "ADMIN" or user.rank == "DIRECTOR"):
            raise PermissionError("부서를 생성할 권한이 없습니다.")

        serializer.save()

    def perform_update(self, serializer):
        # 권한 체크
        user = self.request.user
        if not (user.role == "ADMIN" or user.rank == "DIRECTOR"):
            raise PermissionError("부서를 수정할 권한이 없습니다.")

        serializer.save()

    def perform_destroy(self, instance):
        # 권한 체크
        user = self.request.user
        if not (user.role == "ADMIN" or user.rank == "DIRECTOR"):
            raise PermissionError("부서를 삭제할 권한이 없습니다.")

        # 본부 삭제 시 소속 팀도 함께 삭제
        if instance.parent is None:
            Department.objects.filter(parent=instance).delete()
        instance.delete()
