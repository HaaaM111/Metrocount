from django.urls import path

from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('map/', views.map_view, name='map'),
    path('api/stations/<int:station_id>/fares/', views.station_fares, name='station-fares'),
]
