# -*- coding: utf-8 -*-
"""将上海磁悬浮线（龙阳路 — 浦东1号2号航站楼）接入计价体系。

- 独立线路「磁悬浮」（code=M, 灰色 #B3B3B3）
- 内部边：龙阳路 ↔ 浦东1号2号航站楼，约 30 km / 8 分钟（最高时速 300 km/h）
- 换乘边：与 2 号线龙阳路、2 号线/市域机场线浦东机场同站互联
票价规则（单程普通席 50 元）与备选方案逻辑在 subway/views.py 中实现。
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'metrocount.settings')
django.setup()

from subway.models import Line, Station, Edge

MAGLEV = '磁悬浮'

line, _ = Line.objects.get_or_create(
    name=MAGLEV, defaults=dict(code='M', color='#B3B3B3'))
print('line:', line.id, line.code, line.color)

# 磁悬浮两端站点（换乘站）
names = ['龙阳路', '浦东1号2号航站楼']
created = {}
for i, n in enumerate(names):
    st, created[n] = Station.objects.get_or_create(
        name=n, line=line, defaults=dict(is_transfer=True, sequence=i + 1))
    print('station:', st.id, repr(st.name))

ly_m = Station.objects.get(name='龙阳路', line=line)
pd_m = Station.objects.get(name='浦东1号2号航站楼', line=line)

# 磁悬浮内部边：30 km / 8 min
Edge.objects.get_or_create(
    from_station=ly_m, to_station=pd_m, line=line,
    defaults=dict(travel_time=8, distance_km=30.0))
print('maglev edge: Longyang Rd <-> Pudong Airport (30km/8min)')

transfer_line = Line.objects.get(name='换乘')

# 换乘边（每对只需一条，图按双向建）
transfers = [
    (ly_m, Station.objects.get(name='龙阳路', line=Line.objects.get(name='2号线'))),
    (pd_m, Station.objects.get(name='浦东1号2号航站楼', line=Line.objects.get(name='2号线'))),
    (pd_m, Station.objects.get(name='浦东1号2号航站楼', line=Line.objects.get(name='市域机场线'))),
]
for frm, to in transfers:
    Edge.objects.get_or_create(
        from_station=frm, to_station=to, line=transfer_line,
        defaults=dict(travel_time=5, distance_km=0.0))
    print(f'transfer edge: {frm.name}({frm.line.name}) <-> {to.name}({to.line.name})')

print('DONE')
