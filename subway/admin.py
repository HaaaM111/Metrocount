from django.contrib import admin

from .models import Line, Station


@admin.register(Line)
class LineAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'color')


@admin.register(Station)
class StationAdmin(admin.ModelAdmin):
    list_display = ('name', 'line', 'sequence')
    list_filter = ('line',)
    search_fields = ('name',)
