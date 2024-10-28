from django.shortcuts import render
from rest_framework import viewsets
from .models import Department
from .serializers import DepartmentSerializer
from rest_framework.permissions import IsAuthenticated

# Create your views here.


class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [IsAuthenticated]
    filterset_fields = ["parent"]
