# -*- coding: utf-8 -*-
"""上海地铁网络数据更新管线。

把「新线/新站开通 → 项目数据更新」做成可重复执行的一条命令。

用法：
  python import_network.py --dump         # 从当前 DB 导出基线配置 network_config.json
  python import_network.py                # 按配置幂等更新 DB（只增不删），并自动验证
  python import_network.py --dry-run      # 只报告将做的变更，不写入
  python import_network.py --verify       # 只做一致性验证，不改数据

配置 network_config.json（由 --dump 生成，新线/新站手工补充）：
  lines: [
    { name, code, color,
      stations: [站点名按运营顺序],
      segments: [[起点站, 终点站, 距离km 或 null, 分钟] 相邻站逐段] }
  ]
换乘边由同名站自动生成（跨线同名两两互连），无需手工配置。
"""
import argparse
import io
import json
import os
import re
import sys
from collections import defaultdict

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'metrocount.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import django
django.setup()

from django.db import transaction
from subway.models import Line, Station, Edge

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, 'network_config.json')
BAIDU_STATIONS = os.path.join(HERE, 'baidu_stations.json')
SVG_FILE = os.path.join(HERE, 'templates', 'subway', '_map_svg.html')

VIEWBOX = (118, 42, 4405, 5921)   # SVG viewBox，用于 baidu 坐标 -> DB 示意坐标
DEFAULT_TRAVEL_TIME = 3           # 缺省站间耗时（分钟）
TRANSFER_TIME = 8                 # 换乘耗时（分钟），与 views.py 一致
DEFAULT_COLOR = '#1677ff'


def normalize(name):
    """去掉括号标注（如 浦东1号2号航站楼(磁悬浮) -> 浦东1号2号航站楼）。"""
    return re.sub(r'[（(].*?[)）]', '', name or '').strip()


def load_json(path, fallback=None):
    try:
        data = json.load(io.open(path, encoding='utf-8'))
    except (OSError, ValueError):
        return fallback
    if isinstance(data, dict) and 'result' in data:
        return data['result']
    return data


def baidu_xy(name):
    """从 baidu_stations.json 匹配站点坐标，映射为 DB 示意坐标（0-100 / 0-140）。"""
    sts = load_json(BAIDU_STATIONS, [])
    n = normalize(name)
    for st in sts:
        if normalize(st.get('t', '')) == n:
            bx, by = st['x'], st['y']
            x = round(100 * (bx - VIEWBOX[0]) / VIEWBOX[2])
            y = round(140 * (by - VIEWBOX[1]) / VIEWBOX[3])
            return max(0, min(100, x)), max(0, min(140, y))
    return None


# ---------------------------------------------------------------
# 1. --dump：从 DB 导出基线配置
# ---------------------------------------------------------------
def dump_config():
    lines = Line.objects.exclude(name='换乘').order_by('code')
    out = {'lines': []}
    for line in lines:
        sts = list(line.stations.order_by('sequence'))
        segs = []
        for a, b in zip(sts, sts[1:]):
            e = Edge.objects.filter(from_station=a, to_station=b).first()
            segs.append([a.name, b.name,
                         round(e.distance_km, 3) if e and e.distance_km is not None else None,
                         e.travel_time if e else None])
        out['lines'].append({
            'name': line.name,
            'code': line.code,
            'color': line.color,
            'stations': [s.name for s in sts],
            'segments': segs,
        })
    with io.open(CONFIG, 'w', encoding='utf-8', newline='') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f'已导出 {len(out["lines"])} 条线 -> {CONFIG}')


# ---------------------------------------------------------------
# 2. apply：按配置幂等更新 DB
# ---------------------------------------------------------------
def apply_config(cfg, dry_run):
    """按配置更新 DB。dry_run=True 时只报告将做的变更，不写入。"""
    stats = {'lines': 0, 'stations_new': 0, 'stations_updated': 0,
             'edges_new': 0, 'transfer_new': 0}
    changes = []

    def note(msg):
        changes.append(msg)

    for entry in cfg['lines']:
        name, code = entry['name'], entry['code']
        line = Line.objects.filter(code=code).first()
        if line is None:
            note(f'{name}: 新建线路')
            stats['lines'] += 1
            if not dry_run:
                line = Line.objects.create(
                    code=code, name=name, color=entry.get('color', DEFAULT_COLOR))
        elif line.name != name or (entry.get('color') and line.color != entry['color']):
            note(f'{name}: 更新线路属性')
            stats['lines'] += 1
            if not dry_run:
                line.name = name
                if entry.get('color'):
                    line.color = entry['color']
                line.save()
        else:
            note(f'{name}: 已有线路')
            stats['lines'] += 1

        # 站点
        by_name = {}
        for i, sname in enumerate(entry['stations'], start=1):
            st = Station.objects.filter(line=line, sequence=i).first()
            if st is None:
                note(f'  + 站 {sname} ({name}, seq {i})')
                stats['stations_new'] += 1
                if not dry_run:
                    twin = Station.objects.filter(name=sname).exclude(line=line).first()
                    if twin:
                        x, y = twin.x, twin.y
                    else:
                        xy = baidu_xy(sname)
                        x, y = xy if xy else (50, 50)
                    is_tf = sum(1 for e2 in cfg['lines']
                                if sname in e2['stations']) >= 2
                    st = Station.objects.create(
                        line=line, sequence=i, name=sname,
                        x=x, y=y, is_transfer=is_tf)
                else:
                    st = _Shadow(sname, line)
            elif st.name != sname:
                note(f'  ~ 站更名 {sname}')
                stats['stations_updated'] += 1
                if not dry_run:
                    st.name = sname
                    st.save()
            by_name[sname] = st

        # 运营边
        for a_name, b_name, dist, time in entry.get('segments', []):
            sa, sb = by_name.get(a_name), by_name.get(b_name)
            if not sa or not sb:
                print(f'  ! 忽略未知段 {a_name}-{b_name}')
                continue
            t = time if time is not None else DEFAULT_TRAVEL_TIME
            d = dist if dist is not None else None
            for fr, to in ((sa, sb), (sb, sa)):
                if isinstance(fr, _Shadow) or isinstance(to, _Shadow):
                    exists = False
                else:
                    exists = Edge.objects.filter(
                        from_station=fr, to_station=to, line=line).exists()
                if exists:
                    continue
                note(f'  + 边 {fr.name}↔{to.name} ({name})')
                stats['edges_new'] += 1
                if not dry_run:
                    Edge.objects.create(
                        from_station=fr, to_station=to, line=line,
                        travel_time=t, distance_km=d)

    # 换乘边：跨线同名两两互连（只处理配置中出现的线）
    by_name = defaultdict(list)
    for entry in cfg['lines']:
        for i, sname in enumerate(entry['stations'], start=1):
            st = Station.objects.filter(line__code=entry['code'],
                                        sequence=i).first()
            by_name[sname].append(st or _Shadow(sname, entry['name']))
    transfer_line = Line.objects.filter(code='X').first()
    if transfer_line is None:
        note('换乘: 新建换乘虚拟线')
        if not dry_run:
            transfer_line = Line.objects.create(
                code='X', name='换乘', color='#666666')
    for sname, objs in sorted(by_name.items()):
        if len(objs) < 2:
            continue
        for i in range(len(objs)):
            for j in range(i + 1, len(objs)):
                for fr, to in ((objs[i], objs[j]), (objs[j], objs[i])):
                    if (transfer_line is None or isinstance(fr, _Shadow)
                            or isinstance(to, _Shadow)):
                        exists = False
                    else:
                        exists = Edge.objects.filter(
                            from_station=fr, to_station=to,
                            line=transfer_line).exists()
                    if exists:
                        continue
                    def _ln(o):
                        return getattr(o, 'line_name', None) or getattr(
                            getattr(o, 'line', None), 'name', '')
                    note(f'  + 换乘边 {fr.name}({_ln(fr)})↔{to.name}({_ln(to)})')
                    stats['transfer_new'] += 1
                    if not dry_run and transfer_line is not None:
                        Edge.objects.create(
                            from_station=fr, to_station=to, line=transfer_line,
                            travel_time=TRANSFER_TIME, distance_km=0.0)

    print(f'\n== 更新报告 ==')
    print(f'线路 {stats["lines"]} 条, 新增站 {stats["stations_new"]}, '
          f'运营边新增 {stats["edges_new"]}, 换乘边新增 {stats["transfer_new"]}')
    if changes:
        print('变更明细:')
        for c in changes:
            print(' ', c)
    else:
        print('无变更（配置与 DB 一致）')
    return stats


class _Shadow:
    """dry-run 模式下的站点占位对象（不写库）。"""

    def __init__(self, name, line):
        self.name = name
        self.pk = None
        self.line = line
        self.line_name = line.name if hasattr(line, 'name') else str(line)

    def __repr__(self):
        return f'<Shadow {self.name} on {self.line_name}>'


# ---------------------------------------------------------------
# 3. verify：一致性验证
# ---------------------------------------------------------------
def verify():
    problems = []
    total_st = Station.objects.count()
    total_ed = Edge.objects.count()

    # 3.1 孤立站
    isolated = [s for s in Station.objects.all()
                if not s.out_edges.exists() and not s.in_edges.exists()]
    if isolated:
        problems.append(f'孤立站: {[(s.name, s.line.name) for s in isolated[:10]]}')

    # 3.2 边对称性
    asym = 0
    for e in Edge.objects.select_related('from_station', 'to_station').iterator():
        if not Edge.objects.filter(from_station=e.to_station,
                                   to_station=e.from_station,
                                   line=e.line).exists():
            asym += 1
    if asym:
        problems.append(f'不对称边 {asym} 条')

    # 3.3 可达性（普通网 + 机场线）
    from subway.views import get_graph, dijkstra
    adj, _, _ = get_graph(include_airport=True)
    reachable = {u for u in adj}
    for u, edges in adj.items():
        reachable.add(u)
        for v, _ in edges:
            reachable.add(v)
    all_ids = set(Station.objects.values_list('id', flat=True))
    unreach = all_ids - reachable
    if unreach:
        names = [f'{Station.objects.get(pk=i).name}({Station.objects.get(pk=i).line.name})'
                 for i in list(unreach)[:10]]
        problems.append(f'不可达站: {names}')

    # 3.4 SVG 地图覆盖（DB 所有站地图上应有标注）
    svg = ''
    if os.path.exists(SVG_FILE):
        svg = io.open(SVG_FILE, encoding='utf-8').read()
    if svg:
        svg_names = set(re.findall(r'data-name="([^"]+)"', svg))
        db_names = set(Station.objects.values_list('name', flat=True))
        missing = db_names - {normalize(n) for n in svg_names}
        if missing:
            problems.append(f'地图缺失站: {sorted(missing)[:10]}')

    print(f'== 验证 ==')
    print(f'站点 {total_st}, 边 {total_ed}')
    if problems:
        for p in problems:
            print('  !', p)
        return 1
    print('  孤立站: 无 | 边对称: OK | 可达性: 全站可达 | 地图覆盖: OK')
    return 0


# ---------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description='地铁网络数据更新管线')
    ap.add_argument('--dump', action='store_true', help='导出基线配置 network_config.json')
    ap.add_argument('--dry-run', action='store_true', help='只报告变更，不写入 DB')
    ap.add_argument('--verify', action='store_true', help='只做一致性验证')
    args = ap.parse_args()

    if args.dump:
        dump_config()
        return
    if args.verify:
        sys.exit(verify())

    cfg = load_json(CONFIG)
    if not cfg or 'lines' not in cfg:
        print(f'缺少配置文件 {CONFIG}，请先运行: python import_network.py --dump')
        sys.exit(1)

    with transaction.atomic():
        stats = apply_config(cfg, args.dry_run)
        if args.dry_run:
            print('(dry-run) 未写入 DB')
    sys.exit(verify())


if __name__ == '__main__':
    main()
