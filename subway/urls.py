from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('api/stations/<int:station_id>/fares/', views.station_fares, name='station-fares'),
]
