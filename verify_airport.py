# -*- coding: utf-8 -*-
"""Verify airport line fares against the official table + regression on normal OD."""
import os, sys, json
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'metrocount.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import django
django.setup()
from django.test import RequestFactory
from subway.views import station_fares, AIRPORT_FARES
from subway.models import Station

rf = RequestFactory()

# official table (upper triangle), keyed by (a, b) station names
official = dict(AIRPORT_FARES)
stations = ['虹桥2号航站楼', '中春路', '景洪路', '三林南', '康桥东', '上海国际旅游度假区', '浦东1号2号航站楼']

def get_fare(o_name, d_name):
    o = Station.objects.filter(name=o_name, line__name='市域机场线').first()
    d = Station.objects.filter(name=d_name, line__name='市域机场线').first()
    req = rf.get(f'/api/stations/{o.id}/fares/?destination={d.id}')
    data = json.loads(station_fares(req, o.id).content.decode('utf-8'))
    t = data['trip']
    return t['fare'], t['distance_km'], t

fails = 0
print('=== 机场线 OD 对照官方票价表 ===')
for i in range(len(stations)):
    for j in range(i + 1, len(stations)):
        a, b = stations[i], stations[j]
        expected = official.get((a, b), official.get((b, a)))
        fare, km, t = get_fare(a, b)
        ok = fare == expected
        fails += (not ok)
        print(f"{'OK ' if ok else 'FAIL'} {a}→{b}: ¥{fare} (官¥{expected}) | {km}km | {t['minutes']}min 换乘{t['transfers']}")

print()
print('=== 机场线 相邻站（含跨线计价代表性 OD） ===')
for a, b, exp in [
    ('虹桥2号航站楼', '浦东1号2号航站楼', 26),
    ('虹桥2号航站楼', '徐家汇', None),
    ('浦东1号2号航站楼', '人民广场', None),
    ('三林南', '徐家汇', None),
]:
    try:
        o = Station.objects.filter(name=a, line__name='市域机场线').first()
        d = Station.objects.filter(name=b).first()
        if d is None:
            d = Station.objects.filter(name=b, line__name='1号线').first()
        req = rf.get(f'/api/stations/{o.id}/fares/?destination={d.id}')
        data = json.loads(station_fares(req, o.id).content.decode('utf-8'))
        t = data['trip']
        segs = ' -> '.join(f"[{s['line']}]{s['from']}→{s['to']}" for s in t['segments'])
        print(f"{a}→{b}: ¥{t['fare']} (参考¥{exp if exp else '-'}) | {t['distance_km']}km | {segs}")
    except Exception as e:
        print(f'{a}→{b}: ERR {e}')

print()
print('=== 普通线路回归（7 锚点） ===')
tests = [
    ('漕宝路', '徐家汇', 3), ('徐家汇', '东方体育中心', 4), ('莘庄', '东方体育中心', 4),
    ('陆家嘴', '滴水湖', 9), ('人民广场', '徐家汇', 4), ('徐家汇', '陆家嘴', 4),
    ('莘庄', '人民广场', 5),
]
all_ok = True
for o_name, d_name, expected in tests:
    o = Station.objects.filter(name=o_name).first()
    d = Station.objects.filter(name=d_name).first()
    req = rf.get(f'/api/stations/{o.id}/fares/?destination={d.id}')
    data = json.loads(station_fares(req, o.id).content.decode('utf-8'))
    t = data['trip']
    ok = t and t['fare'] == expected
    all_ok &= bool(ok)
    print(f"{'OK ' if ok else 'FAIL'} {o_name}->{d_name}: ¥{t['fare']} (期望¥{expected}) | {t['distance_km']}km")
print('普通回归:', 'PASS' if all_ok else 'FAIL', '| 机场线:', 'PASS' if fails == 0 else f'{fails} FAIL')
