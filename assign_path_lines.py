# -*- coding: utf-8 -*-
"""Assign each Baidu station to its nearest path, then infer line per path."""
import json, re, os, sys, math
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'metrocount.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import django
django.setup()
from subway.models import Station

paths = json.load(open('baidu_paths.json', encoding='utf-8'))
if isinstance(paths, dict) and 'result' in paths:
    paths = paths['result']
stations = json.load(open('baidu_stations.json', encoding='utf-8'))
if isinstance(stations, dict) and 'result' in stations:
    stations = stations['result']

# db station -> lines
name_lines = {}
for s in Station.objects.all():
    name_lines.setdefault(s.name, set()).add(s.line.name)

def parse_d(d):
    pts = []
    tokens = re.findall(r'([MLQCSZ])([\d\.\-,\s]*)', d)
    last = None
    for cmd, rest in tokens:
        if cmd == 'Z':
            continue
        nums = [float(x) for x in re.findall(r'[\d\.\-]+', rest)]
        if cmd == 'M' and len(nums) >= 2:
            last = (nums[0], nums[1]); pts.append(last)
        elif cmd == 'L' and len(nums) >= 2:
            last = (nums[0], nums[1]); pts.append(last)
        elif cmd == 'Q' and len(nums) >= 4:
            c = (nums[0], nums[1]); e = (nums[2], nums[3])
            for i in range(1, 7):
                t = i / 6.0
                x = (1-t)*(1-t)*last[0] + 2*(1-t)*t*c[0] + t*t*e[0]
                y = (1-t)*(1-t)*last[1] + 2*(1-t)*t*c[1] + t*t*e[1]
                pts.append((x, y))
            last = e
        elif cmd == 'C' and len(nums) >= 6:
            c1 = (nums[0], nums[1]); c2 = (nums[2], nums[3]); e = (nums[4], nums[5])
            for i in range(1, 7):
                t = i / 6.0
                x = (1-t)**3*last[0] + 3*(1-t)**2*t*c1[0] + 3*(1-t)*t*t*c2[0] + t**3*e[0]
                y = (1-t)**3*last[1] + 3*(1-t)**2*t*c1[1] + 3*(1-t)*t*t*c2[1] + t**3*e[1]
                pts.append((x, y))
            last = e
        elif cmd == 'S' and len(nums) >= 2:
            last = (nums[-2], nums[-1]); pts.append(last)
    return pts

def dedupe_wiggle(pts, tol=8.0):
    pts = list(pts)
    changed = True
    while changed:
        changed = False
        i = 0
        while i < len(pts) - 2:
            a, c = pts[i], pts[i+2]
            if abs(a[0]-c[0]) <= tol and abs(a[1]-c[1]) <= tol:
                del pts[i+1:i+3]
                changed = True
            else:
                i += 1
    return pts

polys = []
for p in paths:
    polys.append(dedupe_wiggle(parse_d(p['d'])))

def seg_dist(px, py, ax, ay, bx, by):
    vx, vy = bx-ax, by-ay
    wx, wy = px-ax, py-ay
    L2 = vx*vx + vy*vy
    if L2 == 0:
        return math.hypot(px-ax, py-ay)
    t = max(0.0, min(1.0, (wx*vx + wy*vy) / L2))
    return math.hypot(px-(ax+t*vx), py-(ay+t*vy))

def poly_dist(px, py, poly):
    best = 1e18
    for i in range(len(poly)-1):
        d = seg_dist(px, py, poly[i][0], poly[i][1], poly[i+1][0], poly[i+1][1])
        if d < best:
            best = d
    return best

# assign stations to nearest path
assign = {}
for st in stations:
    x = st['x'] + (10 if st['type'] == 'i' else 0)
    y = st['y'] + (10 if st['type'] == 'i' else 0)
    best_i, best_d = -1, 1e18
    for i, poly in enumerate(polys):
        d = poly_dist(x, y, poly)
        if d < best_d:
            best_d, best_i = d, i
    assign.setdefault(best_i, []).append((st, best_d))

# infer line per path from DB names
print('path | stroke | stations | inferred line | unmatched names')
for i, p in enumerate(paths):
    names = [s['t'] for s, d in assign.get(i, [])]
    # count per DB line
    cnt = {}
    unmatched = []
    for n in names:
        ls = name_lines.get(n)
        if ls:
            for l in ls:
                cnt[l] = cnt.get(l, 0) + 1
        else:
            unmatched.append(n)
    top = sorted(cnt.items(), key=lambda kv: -kv[1])[:3]
    print(f"[{i}] {p['stroke']} n={len(names)} lines={top} unmatched={unmatched[:8]}")
