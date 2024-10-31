from django_filters import rest_framework as filters
from .models import Notification


class NotificationFilter(filters.FilterSet):
    is_read = filters.BooleanFilter()

    class Meta:
        model = Notification
        fields = ["is_read"]
