from django.contrib import admin

from .models import Line, Station, Edge


@admin.register(Line)
class LineAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'color')


@admin.register(Station)
class StationAdmin(admin.ModelAdmin):
    list_display = ('name', 'line', 'sequence')
    list_filter = ('line',)
    search_fields = ('name',)


@admin.register(Edge)
class EdgeAdmin(admin.ModelAdmin):
    list_display = ('from_station', 'to_station', 'distance_km')
    list_filter = ('from_station__line', 'to_station__line')
    search_fields = ('from_station__name', 'to_station__name')
