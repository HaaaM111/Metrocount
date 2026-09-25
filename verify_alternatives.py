# -*- coding: utf-8 -*-
"""全站备选路径回归测试。

批量检查机场线 / 磁悬浮备选逻辑：
- 每个 OD：API 必须返回 200（无 400/404/500），trip 结构合法；
- 备选（若有）：minutes 必须小于主方案、票价计算完成、
  分段线路名必须真实存在于数据库、磁悬浮/机场线标记与分段一致；
- 覆盖：机场线 7 站、磁悬浮 2 站、各普通线路代表站的全部组合。

用法：服务器运行后执行
  .\\.venv\\Scripts\\python.exe verify_alternatives.py
"""
import json
import random
import sys
import urllib.request

BASE = 'http://127.0.0.1:8000'
VALID_LINES = None


def fetch(origin_id, dest_id):
    url = f'{BASE}/api/stations/{origin_id}/fares/?destination={dest_id}'
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            return resp.status, json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode('utf-8'))
        except Exception:
            body = {}
        return e.code, body
    except Exception as exc:
        return -1, {'error': str(exc)}


def main():
    random.seed(2026)
    import os
    import django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'metrocount.settings')
    django.setup()
    from subway.models import Line, Station

    global VALID_LINES
    VALID_LINES = set(Line.objects.exclude(name='换乘').values_list('name', flat=True))

    lines = Line.objects.exclude(name='换乘').order_by('id')
    reps = []            # [(id, name, line_name)]
    airport_ids = []
    maglev_ids = []
    for line in lines:
        sts = list(line.stations.all())
        if not sts:
            continue
        if line.name == '市域机场线':
            airport_ids = [s.id for s in sts]
            reps += [(s.id, s.name, line.name) for s in sts]
            continue
        if line.name == '磁悬浮':
            maglev_ids = [s.id for s in sts]
            reps += [(s.id, s.name, line.name) for s in sts]
            continue
        # 每普通线取首 / 中 / 尾 + 换乘站
        picked = {sts[0].id, sts[len(sts) // 2].id, sts[-1].id}
        for s in sts:
            if s.is_transfer:
                picked.add(s.id)
        for s in sts:
            if s.id in picked:
                reps.append((s.id, s.name, line.name))

    rep_ids = [r[0] for r in reps]
    rep_by_id = {r[0]: r for r in reps}

    pairs = []          # (origin_id, dest_id)
    raw_pairs = []
    for aid in airport_ids + maglev_ids:
        for rid in rep_ids:
            if aid != rid:
                raw_pairs.append((aid, rid))
    for rid in rep_ids:
        for aid in airport_ids + maglev_ids:
            if rid != aid:
                raw_pairs.append((rid, aid))
    # 普通 OD 抽样
    for rid in rep_ids:
        for _ in range(6):
            d = random.choice(rep_ids)
            if rid != d:
                raw_pairs.append((rid, d))
    seen = set()
    for p in raw_pairs:
        if p not in seen:
            seen.add(p)
            pairs.append(p)

    fails = []
    checked = 0
    alt_count = 0
    for oid, did in pairs:
        status, data = fetch(oid, did)
        checked += 1
        o = rep_by_id.get(oid)
        d = rep_by_id.get(did)
        tag = f'{o[1]}({o[2]})->{d[1]}({d[2]})'
        if status != 200:
            fails.append(f'{tag}: HTTP {status} {data.get("error", "")}'.strip())
            continue
        trip = data.get('trip')
        if trip is None:
            fails.append(f'{tag}: trip 为空')
            continue
        if not (isinstance(trip.get('fare'), (int, float)) and trip['fare'] > 0):
            if not (o[1] == d[1] and trip.get('fare') == 0):
                # 同站名换乘（同一物理站点不同线路）无实际乘车 -> fare=0 允许
                fails.append(f'{tag}: fare 异常 {trip.get("fare")}')
        for seg in trip.get('segments', []):
            if seg.get('line') not in VALID_LINES:
                fails.append(f'{tag}: 主方案线路非法 {seg.get("line")}')
        for alt in data.get('alternatives', []):
            alt_count += 1
            if alt.get('minutes', 0) >= trip.get('minutes', 0):
                fails.append(f'{tag}: 备选不快 {alt["minutes"]} >= {trip["minutes"]}')
            if not (isinstance(alt.get('fare'), (int, float)) and alt['fare'] > 0):
                fails.append(f'{tag}: 备选 fare 异常 {alt.get("fare")}')
            seg_lines = [s.get('line') for s in alt.get('segments', [])]
            for ln in seg_lines:
                if ln not in VALID_LINES:
                    fails.append(f'{tag}: 备选线路非法 {ln}')
            has_mag = '磁悬浮' in seg_lines
            has_air = '市域机场线' in seg_lines
            if alt.get('maglev') and not has_mag:
                fails.append(f'{tag}: maglev 标记与分段不符 {seg_lines}')
            if alt.get('airport') and not has_air:
                fails.append(f'{tag}: airport 标记与分段不符 {seg_lines}')
            if (not alt.get('maglev')) and (not alt.get('airport')):
                fails.append(f'{tag}: 备选无 fast 标记 {seg_lines}')

    print(f'=== 备选路径回归 ===  OD: {checked}  备选: {alt_count}')
    if fails:
        print(f'FAIL {len(fails)}')
        for f in fails[:60]:
            print('  -', f)
        sys.exit(1)
    print('PASS: 全部 OD 正常，备选均快于主方案且分段/标记一致')


if __name__ == '__main__':
    main()
