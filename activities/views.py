from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Activity
from .serializers import ActivitySerializer

class ActivityViewSet(viewsets.ModelViewSet):
    serializer_class = ActivitySerializer

    def get_queryset(self):
        return Activity.objects.filter(
            task__department=self.request.user.department
        ).order_by('-created_at')

    @action(detail=False, methods=['get'])
    def recent(self, request):
        activities = self.get_queryset()[:10]  # 최근 10개만
        serializer = self.get_serializer(activities, many=True)
        return Response(serializer.data) 