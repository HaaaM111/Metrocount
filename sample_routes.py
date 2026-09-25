# -*- coding: utf-8 -*-
"""导出抽样 OD 的系统推荐方案（时间图），供与百度地图核对。"""
import os, django, json
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'metrocount.settings')
django.setup()

from django.test import RequestFactory
from subway.views import station_fares
from subway.models import Station

rf = RequestFactory()

cases = [
    ('人民广场', None, '嘉定新城', None),
    ('人民广场', None, '浦东1号2号航站楼', '2号线'),
    ('徐家汇', None, '浦东1号2号航站楼', '2号线'),
    ('松江新城', '9号线', '嘉定新城', '11号线'),
    ('虹桥火车站', None, '迪士尼', '11号线'),
    ('东方绿舟', '17号线', '滴水湖', '16号线'),
    ('上海南站', None, '中山公园', None),
    ('莘庄', None, '江湾体育场', '10号线'),
    ('美兰湖', '7号线', '港城路', '6号线'),
    ('沈杜公路', '8号线', '汇臻路', '浦江线'),
    ('龙阳路', '2号线', '浦东1号2号航站楼', '2号线'),
    ('封浜', '14号线', '桂桥路', '14号线'),
    ('顾村公园', None, '紫竹高新区', '15号线'),
    ('长江南路', '18号线', '航头', '18号线'),
    ('花桥', '11号线', '迪士尼', '11号线'),
    ('市光路', '8号线', '沈杜公路', '8号线'),
    ('基隆路', '10号线', '虹桥火车站', None),
    ('金运路', '13号线', '张江路', '13号线'),
    ('七莘路', '12号线', '金海路', '12号线'),
    ('富锦路', '1号线', '莘庄', '1号线'),
]

for o_name, o_line, d_name, d_line in cases:
    o = Station.objects.filter(name=o_name, line__name=o_line).first() if o_line else Station.objects.filter(name=o_name).first()
    d = Station.objects.filter(name=d_name, line__name=d_line).first() if d_line else Station.objects.filter(name=d_name).first()
    if not o or not d:
        print(f'### {o_name} -> {d_name}: 缺站 o={bool(o)} d={bool(d)}')
        continue
    req = rf.get(f'/api/stations/{o.id}/fares/?destination={d.id}')
    data = json.loads(station_fares(req, o.id).content.decode('utf-8'))
    t = data.get('trip')
    if not t:
        print(f'### {o_name}({o.line.name}) -> {d_name}({d.line.name}): 无方案')
        continue
    segs = '  =>  '.join(f"[{s['line']}]{s['from']}→{s['to']}({s['stopCount']}站)" for s in t['segments'])
    alts = []
    for a in data.get('alternatives', []):
        tag = '磁悬浮' if a.get('maglev') else '机场线'
        asegs = '+'.join(s['line'] for s in a['segments'])
        alts.append(f"{tag} ¥{a['fare']}/{a['minutes']}min({asegs})")
    print(f"### {o_name}({o.line.name}) -> {d_name}({d.line.name})")
    print(f"    主: ¥{t['fare']} {t['minutes']}min 换乘{t['transfers']} | {segs}")
    for a in alts:
        print(f"    备选: {a}")
