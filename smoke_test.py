# -*- coding: utf-8 -*-
"""关键 OD 冒烟测试 + 安全项验证。"""
import json
import os
import urllib.request
import urllib.error

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'metrocount.settings')
django.setup()

from subway.models import Station


def name_id(n, ln):
    return Station.objects.get(name=n, line__name=ln).id


def fetch(oid, did):
    url = f'http://127.0.0.1:8000/api/stations/{oid}/fares/?destination={did}'
    with urllib.request.urlopen(url, timeout=10) as r:
        return json.loads(r.read())


cases = [
    ('蟠龙路', '17号线', '浦东1号2号航站楼', '2号线'),    # 双备选
    ('上海松江站', '9号线', '浦东1号2号航站楼', '磁悬浮'),  # 曾 24000 魔数
    ('中春路', '9号线', '浦东1号2号航站楼', '磁悬浮'),     # 曾 24000 魔数
    ('浦东1号2号航站楼', '磁悬浮', '上海松江站', '9号线'),  # 曾 maglev 标记不符
    ('虹桥2号航站楼', '市域机场线', '虹桥2号航站楼', '2号线'),  # 同站 fare 0
]
for o_n, o_l, d_n, d_l in cases:
    try:
        oid = name_id(o_n, o_l)
        did = name_id(d_n, d_l)
        data = fetch(oid, did)
        t = data.get('trip', {})
        alts = data.get('alternatives', [])
        print(f'{o_n}({o_l})->{d_n}({d_l}): fare={t.get("fare")} min={t.get("minutes")} alt={len(alts)}')
        for a in alts:
            segs = [s.get('line') for s in a.get('segments', [])]
            print(f'   备选 maglev={a.get("maglev")} airport={a.get("airport")} '
                  f'fare={a.get("fare")} min={a.get("minutes")} seg={segs}')
    except Exception as e:
        print(f'{o_n}({o_l})->{d_n}({d_l}): ERROR {e}')

# 参数校验：非数字 destination 应返回 400
try:
    urllib.request.urlopen('http://127.0.0.1:8000/api/stations/2192/fares/?destination=abc', timeout=10)
    print('参数校验: 未拦截 (BAD)')
except urllib.error.HTTPError as e:
    print('参数校验: 非数字返回', e.code, '(GOOD)')

# admin 路由应不可访问
try:
    urllib.request.urlopen('http://127.0.0.1:8000/admin/', timeout=10)
    print('admin: 仍可访问 (BAD)')
except urllib.error.HTTPError as e:
    print('admin: 返回', e.code, '(GOOD)')

# 首页 200
try:
    urllib.request.urlopen('http://127.0.0.1:8000/', timeout=10)
    print('首页: 200 (GOOD)')
except Exception as e:
    print('首页: ERROR', e)
