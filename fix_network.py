# -*- coding: utf-8 -*-
"""数据修复（幂等）：
删除错误的异名换乘边 一大会址·黄陂南路(1/14号线) <-> 一大会址·新天地(10/13号线)。
百度地图公交查询（2026-09 核对）：两站间无任何地铁换乘方案，仅地面公交/步行约 500m，
不属于上海地铁换乘站（1号线与10号线的官方换乘站为陕西南路）。
"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'metrocount.settings')
django.setup()

from subway.models import Edge, Station

hp_ids = set(Station.objects.filter(name='一大会址·黄陂南路').values_list('id', flat=True))
xtd_ids = set(Station.objects.filter(name='一大会址·新天地').values_list('id', flat=True))

bad = list(Edge.objects.filter(line__name='换乘').filter(
    from_station_id__in=hp_ids, to_station_id__in=xtd_ids))
bad += list(Edge.objects.filter(line__name='换乘').filter(
    from_station_id__in=xtd_ids, to_station_id__in=hp_ids))

deleted = 0
for e in set(bad):
    print(f'删除错误换乘边: {e.from_station.name}({e.from_station.line.name}) '
          f'<-> {e.to_station.name}({e.to_station.line.name})')
    e.delete()
    deleted += 1
print(f'共删除 {deleted} 条')

# 复核：全库不应再有异名换乘边
left = 0
for e in Edge.objects.filter(line__name='换乘').select_related('from_station', 'to_station'):
    if e.from_station.name != e.to_station.name:
        left += 1
        print('仍有异名边:', e.from_station.name, '<->', e.to_station.name)
print('剩余异名换乘边:', left)
