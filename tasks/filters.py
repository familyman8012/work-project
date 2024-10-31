from django_filters import rest_framework as filters
from .models import Task


class TaskFilter(filters.FilterSet):
    start_date_after = filters.DateTimeFilter(
        field_name="start_date", lookup_expr="gte"
    )
    due_date_before = filters.DateTimeFilter(
        field_name="due_date", lookup_expr="lte"
    )
    status = filters.ChoiceFilter(choices=Task.STATUS_CHOICES)
    priority = filters.ChoiceFilter(choices=Task.PRIORITY_CHOICES)
    assignee = filters.NumberFilter()
    department = filters.NumberFilter()
    search = filters.CharFilter(field_name="title", lookup_expr="icontains")

    class Meta:
        model = Task
        fields = ["status", "priority", "assignee", "department"]
