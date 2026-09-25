"""
URL configuration for metrocount project.
"""
from django.urls import include, path

urlpatterns = [
    path('', include('subway.urls')),
]
