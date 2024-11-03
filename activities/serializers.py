from rest_framework import serializers
from .models import Activity

class ActivitySerializer(serializers.ModelSerializer):
    task_title = serializers.CharField(source='task.title', read_only=True)
    
    class Meta:
        model = Activity
        fields = [
            'id', 
            'type', 
            'description', 
            'created_at',
            'task_id',
            'task_title'
        ] 