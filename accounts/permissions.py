from rest_framework import permissions


class IsManagerOrAbove(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.rank in [
            "MANAGER",
            "DEPUTY_GENERAL_MANAGER",
            "GENERAL_MANAGER",
            "DIRECTOR",
        ]


class CanViewDepartmentTasks(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        # 같은 부서이거나 상위 직급자인 경우 접근 허용
        return (
            request.user.department == obj.department
            or request.user.rank > obj.assignee.rank
        )
