# -*- coding: utf-8 -*-
"""Generate Baidu-style Shanghai metro SVG (v2, path-assigned station colors).
- 25 line paths verbatim from Baidu
- 432 stations: color = its nearest path's Baidu color; transfer = white ring
- labels verbatim from Baidu SVG

说明：
这个脚本负责把 Baidu 提供的上海地铁线路和站点数据，重新组合成一张
可展示的 SVG 地图。核心思路是：
1. 先读取线路 path 与站点坐标；
2. 将每条 SVG 路径解析成离散点；
3. 对每个站点找离它最近的线路；
4. 根据线路颜色给站点着色，并保留站名标签；
5. 最后输出到 static/subway/maps/shmetro-map.svg。
"""

# 这是一个 Django 项目脚本，虽然它不直接渲染页面，
# 但为了方便复用项目配置和后续数据处理逻辑，需要先初始化 Django。
import json, re, os, sys, math, io
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'metrocount.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import django
django.setup()

# 读取两份原始 JSON：
# - baidu_paths.json: 线路路径信息，包含每条线的 SVG d 属性和颜色
# - baidu_stations.json: 站点列表，包含坐标、类型、名称等
paths = json.load(open('baidu_paths.json', encoding='utf-8'))
if isinstance(paths, dict) and 'result' in paths:
    paths = paths['result']
stations = json.load(open('baidu_stations.json', encoding='utf-8'))
if isinstance(stations, dict) and 'result' in stations:
    stations = stations['result']

# ---- 交互地图密度分级支持 ----
# 整图（低缩放）下只标注三线及以上换乘枢纽与线路徽章，放大后逐步显示全部站名。
from subway.models import Station as DjStation
from django.db.models import Count

FONT = 22
LINE_DY = 30

hub_names = set(
    DjStation.objects.values('name')
    .annotate(n=Count('line', distinct=True))
    .filter(n__gte=3)
    .values_list('name', flat=True)
)
print('hub stations:', len(hub_names))

# 门户级枢纽：整图（low）档仅标注这些，避免市中心枢纽名物理叠字
_major = set(
    DjStation.objects.values('name')
    .annotate(n=Count('line', distinct=True))
    .filter(n__gte=4)
    .values_list('name', flat=True)
)
GATEWAY_HUBS = {
    '人民广场', '虹桥火车站', '虹桥2号航站楼', '浦东1号2号航站楼',
    '上海火车站', '上海南站',
}
major_hub_names = _major | GATEWAY_HUBS
print('major hub stations:', len(major_hub_names), sorted(major_hub_names))

# 百度线路色 -> 线路简称（#800000 为 11 号线支线着色，同标 11）
BAIDU_COLOR_TO_SHORT = {
    '#D53940': '1', '#7FBE29': '2', '#F5D503': '3', '#3F267F': '4',
    '#885196': '5', '#C32A67': '6', '#DD762E': '7', '#4795D4': '8',
    '#94C7E9': '9', '#C0B2D2': '10', '#7C343C': '11', '#800000': '11',
    '#327660': '12', '#DA9DBE': '13', '#615E38': '14', '#C3B292': '15',
    '#A4CEC0': '16', '#AC7A70': '17', '#B58A57': '18', '#A39892': '浦江',
    '#B3B3B3': '磁浮', '#2A5F7C': '机场',
}

# 解析 SVG path 的 d 属性，将一段连续的 M/L/Q/C/S 命令转成离散点序列，
# 便于后续计算“某站点离哪条线最近”。
def parse_d(d):
    pts = []
    # 正则匹配命令和后面的参数串，例如：M123,456L...Q...
    tokens = re.findall(r'([MLQCSZ])([\d\.\-,\s]*)', d)
    last = None
    for cmd, rest in tokens:
        if cmd == 'Z':
            # 关闭路径，通常不参与坐标计算
            continue
        nums = [float(x) for x in re.findall(r'[\d\.\-]+', rest)]

        if cmd == 'M' and len(nums) >= 2:
            last = (nums[0], nums[1]); pts.append(last)
        elif cmd == 'L' and len(nums) >= 2:
            last = (nums[0], nums[1]); pts.append(last)
        elif cmd == 'Q' and len(nums) >= 4:
            # 二次贝塞尔曲线：起点 + 控制点 + 终点
            c = (nums[0], nums[1]); e = (nums[2], nums[3])
            for i in range(1, 7):
                t = i / 6.0
                x = (1-t)*(1-t)*last[0] + 2*(1-t)*t*c[0] + t*t*e[0]
                y = (1-t)*(1-t)*last[1] + 2*(1-t)*t*c[1] + t*t*e[1]
                pts.append((x, y))
            last = e
        elif cmd == 'C' and len(nums) >= 6:
            # 三次贝塞尔曲线：起点 + 控制点1 + 控制点2 + 终点
            c1 = (nums[0], nums[1]); c2 = (nums[2], nums[3]); e = (nums[4], nums[5])
            for i in range(1, 7):
                t = i / 6.0
                x = (1-t)**3*last[0] + 3*(1-t)**2*t*c1[0] + 3*(1-t)*t*t*c2[0] + t**3*e[0]
                y = (1-t)**3*last[1] + 3*(1-t)**2*t*c1[1] + 3*(1-t)*t*t*c2[1] + t**3*e[1]
                pts.append((x, y))
            last = e
        elif cmd == 'S' and len(nums) >= 2:
            # S 命令通常可视为一段平滑曲线，取末端点作为新起点
            last = (nums[-2], nums[-1]); pts.append(last)
    return pts

# 去除“抖动型”冗余点：
# 某些路径中相邻三点可能高度接近，导致折线看起来有很多小毛刺。
# 这里用容差 tol 去掉这类近似重复点，以让线段更顺滑。
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

# 把每条线路的 SVG 路径都转换成离散点折线，后续用作“最近线路”计算。
polys = [dedupe_wiggle(parse_d(p['d'])) for p in paths]

# 计算点到线段的最短距离，核心用于判断站点更接近哪条线路。
def seg_dist(px, py, ax, ay, bx, by):
    vx, vy = bx-ax, by-ay
    wx, wy = px-ax, py-ay
    L2 = vx*vx + vy*vy
    if L2 == 0:
        # 退化线段：点到点的距离
        return math.hypot(px-ax, py-ay)
    # 投影参数 t 用于求垂足落点，限制在 [0,1] 区间表示在线段上。
    t = max(0.0, min(1.0, (wx*vx + wy*vy) / L2))
    return math.hypot(px-(ax+t*vx), py-(ay+t*vy))

# 计算某点到一条折线多段路径的距离，取最短段的距离即可。
def poly_dist(px, py, poly):
    best = 1e18
    for i in range(len(poly)-1):
        d = seg_dist(px, py, poly[i][0], poly[i][1], poly[i+1][0], poly[i+1][1])
        if d < best:
            best = d
    return best

# 找到某个站点最近的线路编号，用于为站点分配线路颜色。
def nearest_path(x, y):
    best_i, best_d = -1, 1e18
    for i, poly in enumerate(polys):
        d = poly_dist(x, y, poly)
        if d < best_d:
            best_d, best_i = d, i
    return best_i

# 对站名中的 XML 特殊字符做转义，避免 &、<、> 破坏 SVG 结构。
def esc(t):
    return t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

# 生成 SVG 结果列表，后面统一写入文件。
# 先计算内容实际边界（线路顶点 + 站名标签），收紧画布，消除原图四周空白。
xs = []; ys = []
for p in paths:
    for pt in parse_d(p['d']):
        xs.append(pt[0]); ys.append(pt[1])
for st in stations:
    xs.append(st['x']); ys.append(st['y'])
    # text-anchor=middle：标签向两侧各占约半个字宽
    w = FONT * len(st['t']) / 2.0
    xs.append(st['x'] + w); xs.append(st['x'] - w)
    ys.append(st['y'] + 3 * LINE_DY + FONT); ys.append(st['y'] - 3 * LINE_DY - FONT)
PAD = 60
vx0 = max(0, math.floor(min(xs)) - PAD)
vy0 = max(0, math.floor(min(ys)) - PAD)
vx1 = math.ceil(max(xs)) + PAD
vy1 = math.ceil(max(ys)) + PAD
vw = vx1 - vx0
vh = vy1 - vy0
print('content bbox:', (min(xs), min(ys), max(xs), max(ys)), 'viewBox', (vx0, vy0, vw, vh))

out = []
out.append(f'<svg xmlns="http://www.w3.org/2000/svg" width="{vw}" height="{vh}" viewBox="{vx0} {vy0} {vw} {vh}" font-family="Helvetica, Arial, sans-serif">')
out.append(f'<rect x="{vx0}" y="{vy0}" width="{vw}" height="{vh}" fill="#ffffff"/>')

# 先按原始 Baidu 路线逐条绘制底层线路，保持线条颜色、宽度和样式一致。
for p in paths:
    out.append(f'<path class="metro-line" d="{p["d"]}" fill="none" stroke="{p["stroke"]}" stroke-width="10" stroke-linecap="round" stroke-linejoin="round"/>')

# 再渲染站点：
# - 换乘站绘制白色外圈 + 颜色填充点；普通站绘制白底色圆圈（颜色取最近线路）。
# - 站名：按最近线路分组、沿线弧长排序后，相邻站一上一下交替错位
#   （偶数位在上、奇数位在下，text-anchor=middle 居中于站上方/下方），
#   并加白色描边（paint-order=stroke）保证压线时清晰可读。
def arc_at(poly, px, py):
    """站到折线的投影弧长（用于沿线顺序排序）。"""
    best = 1e18
    best_arc = 0.0
    acc = 0.0
    for i in range(len(poly) - 1):
        ax, ay = poly[i]
        bx, by = poly[i + 1]
        vx, vy = bx - ax, by - ay
        wx, wy = px - ax, py - ay
        L2 = vx * vx + vy * vy
        if L2 == 0:
            d = math.hypot(px - ax, py - ay)
            if d < best:
                best = d
                best_arc = acc
            continue
        t = max(0.0, min(1.0, (wx * vx + wy * vy) / L2))
        d = math.hypot(px - (ax + t * vx), py - (ay + t * vy))
        if d < best:
            best = d
            best_arc = acc + math.hypot(vx * t, vy * t)
        acc += math.hypot(vx, vy)
    return best_arc


# 按最近线路分组，再按沿线弧长排序
line_stations = [[] for _ in paths]
for st in stations:
    cx = st['x'] + (12.5 if st['type'] == 'i' else 0)
    cy = st['y'] + (12.5 if st['type'] == 'i' else 0)
    pi = nearest_path(cx, cy)
    line_stations[pi].append((arc_at(polys[pi], cx, cy), st))

drawn_names = set()
labels = []
for lst in line_stations:
    lst.sort(key=lambda x: x[0])
    for idx, (_arc, st) in enumerate(lst):
        if st['t'] in drawn_names:
            continue
        drawn_names.add(st['t'])
        cx = st['x'] + (12.5 if st['type'] == 'i' else 0)
        cy = st['y'] + (12.5 if st['type'] == 'i' else 0)
        pi = nearest_path(cx, cy)
        col = paths[pi]['stroke']
        if st['type'] == 'i':
            out.append(f'<circle class="dot transfer-ring" cx="{cx}" cy="{cy}" r="12.5" fill="#ffffff" stroke="{col}" stroke-width="3" data-name="{esc(st["t"])}" data-color="{col}"/>')
            out.append(f'<circle class="dot transfer-core" cx="{cx}" cy="{cy}" r="4.5" fill="{col}" data-name="{esc(st["t"])}" data-color="{col}"/>')
        else:
            out.append(f'<ellipse class="dot station-dot" cx="{st["x"]}" cy="{st["y"]}" rx="8" ry="8" fill="#ffffff" stroke="{col}" stroke-width="3" data-name="{esc(st["t"])}" data-color="{col}"/>')
        # 一上一下交替给出初始错位；最终位置由后面的碰撞避让统一排布
        dy0 = -LINE_DY if idx % 2 == 0 else LINE_DY
        name = st['t']
        if st['type'] == 'i':
            if name in major_hub_names:
                lbl_cls = 'lbl lbl-transfer lbl-hub lbl-hub-major'
                rank = 0
            elif name in hub_names:
                lbl_cls = 'lbl lbl-transfer lbl-hub'
                rank = 1
            else:
                lbl_cls = 'lbl lbl-transfer'
                rank = 2
        else:
            lbl_cls = 'lbl lbl-station'
            rank = 3
        labels.append((cx, cy, dy0, name, col, lbl_cls, rank))

# 标签碰撞避让：按枢纽/换乘/普通与名字长度优先占位，
# 每个标签在初始侧（上或下）最多排 3 层，再尝试对侧，保证相邻线路标签不叠字。
def label_box(cx, cy, dy, name):
    half_w = FONT * len(name) * 0.52
    half_h = FONT * 0.52
    bx, by = cx, cy + dy - FONT * 0.32
    return (bx - half_w, by - half_h, bx + half_w, by + half_h)

def overlap(a, b, gap=4.0):
    return not (a[2] + gap < b[0] or b[2] + gap < a[0]
                or a[3] + gap < b[1] or b[3] + gap < a[1])

placed_boxes = []
labels.sort(key=lambda r: (r[6], -len(r[3])))
# 手工错位：物理相邻、自动避让仍叠字的门户站（虹桥枢纽两场站）
MANUAL_DY = {'虹桥火车站': -52, '虹桥2号航站楼': 52}
for cx, cy, dy0, name, col, lbl_cls, rank in labels:
    side = -1 if dy0 < 0 else 1
    candidates = [side * LINE_DY * k for k in (1, 2, 3)] + [-side * LINE_DY * k for k in (1, 2, 3)] + [0]
    chosen = candidates[0]
    if name in MANUAL_DY:
        chosen = MANUAL_DY[name]
    else:
        for dy in candidates:
            box = label_box(cx, cy, dy, name)
            if not any(overlap(box, b) for b in placed_boxes):
                chosen = dy
                break
    placed_boxes.append(label_box(cx, cy, chosen, name))
    out.append(
        f'<text class="{lbl_cls}" x="{cx:.1f}" y="{cy + chosen:.1f}" font-size="{FONT}" font-weight="500"'
        f' fill="#000000" text-anchor="middle" paint-order="stroke" stroke="#ffffff"'
        f' stroke-width="5" stroke-linejoin="round" data-name="{esc(name)}"'
        f' data-color="{col}">{esc(name)}</text>'
    )

# 线路徽章：整图模式下辅助识别线路（前端按缩放级别控制显隐与字号补偿）
def poly_length(poly):
    return sum(math.hypot(poly[i+1][0]-poly[i][0], poly[i+1][1]-poly[i][1])
               for i in range(len(poly)-1))

def point_at_arc(poly, target):
    acc = 0.0
    for i in range(len(poly)-1):
        seg = math.hypot(poly[i+1][0]-poly[i][0], poly[i+1][1]-poly[i][1])
        if acc + seg >= target:
            r = 0 if seg == 0 else (target - acc) / seg
            return (poly[i][0] + r*(poly[i+1][0]-poly[i][0]),
                    poly[i][1] + r*(poly[i+1][1]-poly[i][1]))
        acc += seg
    return poly[-1]

best_poly_by_color = {}
for p, poly in zip(paths, polys):
    L = poly_length(poly)
    cur = best_poly_by_color.get(p['stroke'])
    if cur is None or L > cur[0]:
        best_poly_by_color[p['stroke']] = (L, poly)

# 枢纽坐标，徽章选位时避让
hub_pts = [(st['x'], st['y']) for st in stations if st['t'] in hub_names]
placed_badges = []

def choose_badge_point(poly, L, cand_ts):
    # 候选弧长比例中，选离枢纽站/已放徽章最远的位置
    best_pt, best_score = None, -1.0
    blockers = hub_pts + placed_badges
    for t in cand_ts:
        pt = point_at_arc(poly, L * t)
        score = min([math.hypot(pt[0]-q[0], pt[1]-q[1]) for q in blockers] or [1e9])
        if score > best_score:
            best_score, best_pt = score, pt
    return best_pt

for color, (L, poly) in best_poly_by_color.items():
    short = BAIDU_COLOR_TO_SHORT.get(color)
    if not short:
        continue
    # 长线两端区域各一枚，短线只在中部一枚
    slot_list = ([0.15, 0.22, 0.30], [0.70, 0.78, 0.85]) if L >= 3000 else ([0.30, 0.50, 0.70],)
    for cands in slot_list:
        bx, by = choose_badge_point(poly, L, cands)
        placed_badges.append((bx, by))
        out.append(
            f'<g class="line-badge" pointer-events="none">'
            f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="17" fill="{color}" stroke="#ffffff" stroke-width="3"/>'
            f'<text class="badge-text" x="{bx:.1f}" y="{by+1:.1f}" font-size="20" font-weight="700"'
            f' fill="#ffffff" text-anchor="middle" dominant-baseline="central">{esc(short)}</text>'
            f'</g>'
        )

# 封闭 SVG，并写入项目静态资源目录，供前端直接引用。
out.append('</svg>')
svg = '\n'.join(out)
with io.open(r'static\subway\maps\shmetro-map.svg', 'w', encoding='utf-8') as f:
    f.write(svg)
print('written', len(svg), 'chars')