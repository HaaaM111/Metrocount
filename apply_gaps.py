# -*- coding: utf-8 -*-
"""Fill Edge.distance_km with real station gaps (Fandom / official data)."""
import json, os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'metrocount.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import django
django.setup()
from subway.models import Edge, Line, Station

gaps = json.load(open('station_gaps_raw.json', encoding='utf-8'))

# Merge branch lists for lines that have branches in the JSON
def json_lines_for(db_line_name):
    if db_line_name == '5号线':
        return gaps.get('5号线', []) + gaps.get('5号线支线', [])
    return gaps.get(db_line_name, [])

# DB uses newer/alternate station names; map to JSON names (line-scoped)
NAME_MAP = {
    '1号线': {'一大会址·黄陂南路': '黄陂南路'},
    '10号线': {'一大会址·新天地': '新天地'},
    '13号线': {'一大会址·新天地': '新天地'},
    '14号线': {'一大会址·黄陂南路': '黄陂南路'},
    '9号线': {'上海松江站': '松江南站'},
    '17号线': {'国家会展中心': '诸光路'},
    '2号线': {'浦东南路': '东昌路', '浦东1号2号航站楼': '浦东国际机场'},
    '4号线': {'向城路': '浦电路'},
    '15号线': {'景洪路': '景西路'},
}

# Extra adjacency pairs missing from JSON lists (line, stationA, stationB, gap_m)
EXTRA_PAIRS = {
    '5号线': [('东川路', '金平路', 1459)],
}

def build_adj(json_lines, line_name):
    """name -> {(neighbor, gap_m)}; direction independent."""
    adj = {}
    for i in range(1, len(json_lines)):
        a, b, g = json_lines[i-1][0], json_lines[i][0], json_lines[i][2]
        adj.setdefault(a, set()).add((b, g))
        adj.setdefault(b, set()).add((a, g))
    # line-scoped name mapping: alias DB name -> JSON name (kept under both keys)
    for alias, real in NAME_MAP.get(line_name, {}).items():
        if real in adj:
            adj.setdefault(alias, set()).update(adj[real])
    for x, y, g in EXTRA_PAIRS.get(line_name, []):
        adj.setdefault(x, set()).add((y, g))
        adj.setdefault(y, set()).add((x, g))
    return adj

Edge.objects.update(distance_km=None)  # reset before re-apply
matched = 0
skipped = []
line_stats = {}
for line in Line.objects.exclude(name='换乘').prefetch_related('stations'):
    adj = build_adj(json_lines_for(line.name), line.name)
    if not adj:
        continue
    stations = list(line.stations.all().order_by('sequence'))
    ok = 0
    for i in range(len(stations) - 1):
        a, b = stations[i], stations[i + 1]
        pair = adj.get(a.name, set())
        hit = [g for (n, g) in pair if n == b.name]
        if not hit:
            pair = adj.get(b.name, set())
            hit = [g for (n, g) in pair if n == a.name]
        if not hit:
            skipped.append(f'{line.name}: {a.name}->{b.name}')
            continue
        km = round(hit[0] / 1000.0, 3)
        Edge.objects.filter(from_station=a, to_station=b, line=line).update(distance_km=km)
        Edge.objects.filter(from_station=b, to_station=a, line=line).update(distance_km=km)
        ok += 1
        matched += 1
    line_stats[line.name] = f'{ok}/{len(stations)-1}'

print('matched edges:', matched)
print('per line:')
for k, v in line_stats.items():
    print(f'  {k}: {v}')
print('skipped:', len(skipped))
for s in skipped[:40]:
    print('  -', s)
