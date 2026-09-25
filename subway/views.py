import math
import heapq
from collections import defaultdict

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

from .models import Line, Station, Edge


# SVG path data for each line, redrawn to match the official Shanghai Metro map layout.
# Coordinates in viewBox 0 0 100 140. Transfer stations are aligned across lines.
LINE_PATHS = {
    # 1号线 红色 南北: 富锦路->上海火车站->人民广场->徐家汇->上海南站->莘庄
    "1":  "M 48,3 L 48,12 L 47,22 L 46,32 L 45,40 L 45,45 L 46,50 L 50,55 L 48,60 L 46,64 L 43,68 L 40,74 L 36,80 L 33,86 L 30,91 L 28,96",
    # 2号线 浅绿 东西横贯: 徐泾东->虹桥->中山公园->静安寺->人民广场->陆家嘴->世纪大道->龙阳路->浦东机场
    "2":  "M 3,55 L 8,55 L 12,55 L 20,55 L 28,54 L 33,53 L 40,53 L 44,53 L 50,55 L 54,55 L 58,56 L 63,60 L 67,62 L 70,65 L 76,73 L 83,82 L 89,92 L 95,100",
    # 3号线 黄色 东北-西南: 江杨北路->虹口足球场->上海火车站->曹杨路->中山公园->上海南站
    "3":  "M 66,4 L 64,14 L 61,24 L 58,34 L 54,42 L 47,45 L 45,45 L 41,48 L 37,50 L 34,52 L 33,58 L 35,65 L 37,72 L 35,80 L 33,86 L 32,90",
    # 4号线 深紫 环线
    "4":  "M 45,45 C 38,46 33,50 32,57 C 31,64 34,72 38,76 C 43,79 50,79 55,76 C 60,73 64,68 65,62 C 66,55 63,48 58,46 C 53,44 48,44 45,45 Z",
    # 5号线 紫色 南: 莘庄->颛桥->西渡->奉贤新城
    "5":  "M 28,96 L 28,102 L 28,108 L 27,115 L 26,122 L 25,129 L 24,135",
    # 6号线 品红 东北-东南: 港城路->巨峰路->世纪大道->东方体育中心
    "6":  "M 84,14 L 82,24 L 79,34 L 75,44 L 70,52 L 65,57 L 63,60 L 64,66 L 63,73 L 61,80 L 58,85",
    # 7号线 橙色 西北-东南: 美兰湖->上海大学->镇坪路->静安寺->常熟路->东安路->龙阳路->花木
    "7":  "M 18,3 L 19,8 L 20,13 L 21,18 L 23,23 L 25,28 L 27,33 L 29,38 L 31,43 L 34,48 L 37,51 L 40,53 L 42,54 L 45,58 L 47,63 L 50,68 L 55,72 L 61,76 L 66,78 L 71,80 L 76,82",
    # 8号线 浅蓝 南北偏东: 市光路->虹口足球场->人民广场->老西门->东方体育中心->沈杜公路
    "8":  "M 61,5 L 60,14 L 58,23 L 56,32 L 54,40 L 52,47 L 50,55 L 51,62 L 53,69 L 55,76 L 57,82 L 58,85 L 56,92 L 54,100 L 52,108",
    # 9号线 青绿 东西偏南: 松江->七宝->徐家汇->肇嘉浜路->陆家浜路->世纪大道->曹路
    "9":  "M 2,96 L 7,91 L 14,86 L 21,81 L 28,76 L 35,72 L 40,70 L 43,68 L 46,66 L 49,64 L 53,63 L 58,62 L 63,61 L 69,62 L 76,64 L 83,66 L 91,67 L 96,67",
    # 10号线 紫色 东北-西南: 基隆路->五角场->四平路->南京东路->新天地->虹桥/航中路
    "10": "M 80,6 L 78,16 L 75,26 L 71,36 L 66,42 L 61,46 L 56,49 L 53,52 L 50,55 L 49,60 L 46,63 L 42,65 L 38,66 L 33,66 L 27,64 L 20,61 L 14,57 L 10,55",
    # 11号线 棕色 西北-东南: 花桥->嘉定北->南翔->曹杨路->江苏路->徐家汇->东方体育中心->迪士尼
    "11": "M 3,10 L 6,20 L 10,30 L 16,40 L 23,48 L 30,54 L 34,57 L 36,62 L 38,67 L 43,68 L 47,73 L 53,78 L 58,82 L 58,85 L 62,89 L 67,92 L 73,95 L 80,97 L 88,98",
    # 12号线 深绿 西-东: 七莘路->龙漕路->陕西南路->南京西路->曲阜路->巨峰路->金海路
    "12": "M 16,78 L 24,74 L 31,69 L 38,63 L 42,58 L 46,55 L 49,52 L 51,50 L 54,48 L 58,45 L 63,42 L 69,39 L 76,36 L 84,33 L 92,31",
    # 13号线 粉色 西-东南: 金运路->真北路->武宁路->汉中路->南京西路->新天地->世博->北蔡->张江路
    "13": "M 8,48 L 16,49 L 24,50 L 31,51 L 38,52 L 44,53 L 47,53 L 50,55 L 52,60 L 55,67 L 58,73 L 61,77 L 66,79 L 73,81 L 81,83 L 87,84",
    # 14号线 橄榄绿 西-东: 封浜->真新新村->武定路->静安寺->大世界->陆家嘴->桂桥路
    "14": "M 3,46 L 13,47 L 23,48 L 31,49 L 37,50 L 41,51 L 45,52 L 48,53 L 51,54 L 55,55 L 59,56 L 63,57 L 68,58 L 75,59 L 83,59 L 93,60",
    # 15号线 黄绿 南北偏西: 顾村公园->上海大学->长风公园->红宝石路->上海南站->紫竹高新区
    "15": "M 26,10 L 27,20 L 28,30 L 29,40 L 30,48 L 32,54 L 34,60 L 35,66 L 36,73 L 35,80 L 34,88 L 33,96 L 32,104 L 31,112 L 30,120 L 29,128",
    # 16号线 棕橙 东南: 龙阳路->周浦东->新场->惠南->滴水湖
    "16": "M 70,65 L 72,73 L 75,81 L 77,89 L 79,99 L 82,109 L 85,117 L 88,125 L 90,131",
    # 17号线 青色 西: 虹桥火车站->赵巷->青浦新城->东方绿舟
    "17": "M 12,55 L 8,58 L 5,63 L 3,70 L 2,78 L 1,86 L 0,94",
    # 18号线 薄荷绿 南北偏东: 长江南路->国权路->龙阳路->御桥->周浦->航头
    "18": "M 60,3 L 59,11 L 58,19 L 57,27 L 56,35 L 56,43 L 57,51 L 59,58 L 63,62 L 67,68 L 70,77 L 72,87 L 74,97 L 75,107 L 76,117 L 77,127 L 78,135",
    # 浦江线 灰: 沈杜公路->汇臻路
    "浦江线": "M 52,108 L 51,113 L 50,118 L 49,123 L 48,128",
    # 市域机场线 浅青: 虹桥->中春路->景洪路->三林南->康桥东->迪士尼->浦东机场
    "机场线": "M 12,55 L 20,60 L 30,67 L 42,74 L 55,79 L 68,82 L 80,84 L 95,86",
}

def fare_by_distance(km):
    """Shanghai Metro current fare (现行票价).
    0-6km=3元, 之后每10km加1元.
    Ref: official shmetro.com fare calculator
    """
    if km <= 6:
        return 3
    return 3 + math.ceil((km - 6) / 10)


# ---------------------------------------------------------------
# 市域机场线 (Airport Link Line) 独立计价
# 官方规则：市域线起乘价 4 元，与普通地铁出站换乘、不连续计费。
# 站间票价直接采用官方《市域机场线站间票价表》（运营方公布，见截图），
# 不再按普通地铁里程分段计算。
# ---------------------------------------------------------------
AIRPORT_LINE = '市域机场线'
AIRPORT_STATIONS = [
    '虹桥2号航站楼', '中春路', '景洪路', '三林南', '康桥东',
    '上海国际旅游度假区', '浦东1号2号航站楼',
]
# 机场线站间真实运营里程（公里，估算/官方公开，用于展示）
AIRPORT_DIST = {
    '虹桥2号航站楼': 0.0, '中春路': 12.1, '景洪路': 27.0, '三林南': 37.5,
    '康桥东': 50.0, '上海国际旅游度假区': 55.3, '浦东1号2号航站楼': 69.9,
}
# 官方站间票价表（元），对称
AIRPORT_FARES = {
    ('虹桥2号航站楼', '中春路'): 4, ('虹桥2号航站楼', '景洪路'): 9,
    ('虹桥2号航站楼', '三林南'): 11, ('虹桥2号航站楼', '康桥东'): 17,
    ('虹桥2号航站楼', '上海国际旅游度假区'): 20, ('虹桥2号航站楼', '浦东1号2号航站楼'): 26,
    ('中春路', '景洪路'): 7, ('中春路', '三林南'): 9, ('中春路', '康桥东'): 14,
    ('中春路', '上海国际旅游度假区'): 17, ('中春路', '浦东1号2号航站楼'): 24,
    ('景洪路', '三林南'): 4, ('景洪路', '康桥东'): 8, ('景洪路', '上海国际旅游度假区'): 11,
    ('景洪路', '浦东1号2号航站楼'): 17,
    ('三林南', '康桥东'): 6, ('三林南', '上海国际旅游度假区'): 9, ('三林南', '浦东1号2号航站楼'): 15,
    ('康桥东', '上海国际旅游度假区'): 4, ('康桥东', '浦东1号2号航站楼'): 10,
    ('上海国际旅游度假区', '浦东1号2号航站楼'): 7,
}


def airport_fare(a, b):
    if a == b:
        return 0
    return AIRPORT_FARES.get((a, b)) or AIRPORT_FARES.get((b, a)) or 4


def split_line_groups(path_ids, edge_meta):
    """把站点 id 路径按连续乘车线拆分为 [(line_name, [ids...]), ...]，换乘边断开。"""
    groups = []
    cur = None
    for u, v in zip(path_ids, path_ids[1:]):
        ln = edge_meta.get((u, v), ('未知', 0, 0))[0]
        if ln == '换乘':
            if cur is not None:
                groups.append(cur)
                cur = None
            continue
        if cur is None:
            cur = [ln, [u, v]]
        elif ln == cur[0]:
            cur[1].append(v)
        else:
            groups.append(cur)
            cur = [ln, [u, v]]
    if cur is not None:
        groups.append(cur)
    return groups


def path_riding_km(path_ids, edge_meta):
    """路径上的乘车里程之和（换乘边为 0）。"""
    return sum(edge_meta.get((u, v), ('', 0, 0))[2]
               for u, v in zip(path_ids, path_ids[1:]))


def fare_for_plan(path_ids, edge_meta, name_of, plain_shortest_km=None):
    """按「实际展示给乘客的乘坐方案」计价。

    - 方案含市域机场线：机场线段按官方站间票价表计费，普通段按连续里程价计费，
      两者相加（市域线与普通地铁出站换乘、不连续计费）；
    - 方案全程为普通地铁线：按该 OD 在普通网上的最短乘车里程计价
      （plain_shortest_km，官方按 OD 最短里程收费，与实际乘坐路径无关）；
    - 方案没有坐机场线就不收机场线费用（同址换乘站物理上等价，选了机场线站
      对象但乘普通线不应加收起乘价）。
    """
    groups = split_line_groups(path_ids, edge_meta)
    if not groups:
        return 0
    has_airport = any(g[0] == AIRPORT_LINE for g in groups)
    if not has_airport:
        km = plain_shortest_km
        if km is None:
            km = path_riding_km(path_ids, edge_meta)
        return fare_by_distance(km) if km and km > 0 else 0
    total = 0
    ordinary_km = 0.0
    for ln, ids in groups:
        if ln == AIRPORT_LINE:
            total += airport_fare(name_of[ids[0]], name_of[ids[-1]])
        else:
            ordinary_km += sum(edge_meta.get((x, y), ('', 0, 0))[2]
                               for x, y in zip(ids, ids[1:]))
    if ordinary_km > 0:
        total += fare_by_distance(ordinary_km)
    return total


# 机场线中仅机场线可达（普通地铁网无对应站）的站点：
# 查询涉及这些站点时，机场线作为第一选择（完整计价图）。
AIRPORT_ONLY = ['景洪路', '三林南', '康桥东', '上海国际旅游度假区']

# 磁悬浮（上海磁浮示范运营线）：独立票价体系。
# 单程普通席 50 元（官方票价，见运营方票价政策）。
# 作为「更快备选」供机场往返，不进入主计价图（默认方案仍走地铁/机场线）。
MAGLEV_LINE = '磁悬浮'
MAGLEV_FARE = 50


# Distance coefficient per line: km per minute of travel time.
# Urban lines average ~30km/h (0.5 km/min).
# Express/outer suburban lines (16, 17, 11 branch) are faster ~60km/h.
LINE_KM_PER_MIN = {
    '16号线': 1.0,   # express: Longyang Rd -> Dishui Lake ~59km in 57min
    '17号线': 0.8,   # suburban: Hongqiao -> Oriental Land
    '11号线': 0.6,   # long suburban section to Huaqiao
    '浦江线': 0.4,
    '市域机场线': 1.5,  # high-speed airport link
}
DEFAULT_KM_PER_MIN = 0.5


# Transfer penalty used for ROUTING only (minutes). Real transfer walk+wait is
# typically 5-8 min; weighting it higher makes the planner prefer fewer transfers.
TRANSFER_PENALTY_MIN = 8


def build_graph(include_maglev=False, include_airport=True):
    """Build BOTH graphs from real Edge data.
    - adj_km:  edge weight = riding km (transfer = 0). Dijkstra here finds the
      SHORTEST riding distance, which is what Shanghai Metro prices by.
    - adj_min: edge weight = minutes (transfer = TRANSFER_PENALTY_MIN). Dijkstra
      here finds the FASTEST route with few transfers, used for the route plan.
    - edge_meta: {(u, v): (line_name, travel_time_min)} for rendering.
    The maglev line never enters the main pricing graph (only the alternative).
    The airport link is excluded from ordinary OD pricing (include_airport=False)
    so it is not chosen first, but stays enabled when an endpoint is only
    reachable by the airport link.
    Returns: (adj_km, adj_min, edge_meta)
    """
    adj_km = defaultdict(list)
    adj_min = defaultdict(list)
    edge_meta = {}
    for e in Edge.objects.select_related('line').all():
        if not include_maglev:
            # 主计价图不含磁悬浮线路本身；磁悬浮站仅与 2 号线对应站同址互联
            # （磁悬浮↔机场线互联只用于备选图，防止机场线站被 0km 中继到 2 号线）
            if e.line.name == MAGLEV_LINE:
                continue
            if e.from_station.line.name == MAGLEV_LINE or e.to_station.line.name == MAGLEV_LINE:
                other = e.to_station if e.from_station.line.name == MAGLEV_LINE else e.from_station
                if other.line.name != '2号线':
                    continue
        if e.line.name == AIRPORT_LINE and not include_airport:
            # 普通 OD 计价不优先走机场线（机场线站仍经换乘边可达）
            continue
        if e.line.name == '换乘':
            km = 0
            minutes = TRANSFER_PENALTY_MIN
        elif e.distance_km is not None:
            km = e.distance_km
            minutes = e.travel_time
        else:
            kmpm = LINE_KM_PER_MIN.get(e.line.name, DEFAULT_KM_PER_MIN)
            km = e.travel_time * kmpm
            minutes = e.travel_time
        adj_km[e.from_station_id].append((e.to_station_id, km))
        adj_km[e.to_station_id].append((e.from_station_id, km))
        adj_min[e.from_station_id].append((e.to_station_id, minutes))
        adj_min[e.to_station_id].append((e.from_station_id, minutes))
        edge_meta[(e.from_station_id, e.to_station_id)] = (e.line.name, e.travel_time, km)
        edge_meta[(e.to_station_id, e.from_station_id)] = (e.line.name, e.travel_time, km)

    return adj_km, adj_min, edge_meta


def dijkstra(adj, start_id):
    """Dijkstra shortest path from start.
    Returns (dist, prev): {station_id: weight_sum}, {station_id: previous_station_id}
    """
    dist = {start_id: 0}
    prev = {}
    pq = [(0, start_id)]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist.get(u, float('inf')):
            continue
        for v, w in adj.get(u, []):
            nd = d + w
            if nd < dist.get(v, float('inf')):
                dist[v] = nd
                prev[v] = u
                heapq.heappush(pq, (nd, v))
    return dist, prev


def request_time_graph(adj_min, edge_meta, origin_group, dest_group=()):
    """按具体 OD 调整时间图上的同站换乘边权：

    - 起点同站组内的换乘边权置 0：乘客进站时直接选择对应线路站台，
      不存在“乘车后下车换乘”的步行与二次候车成本（如上海南站 1/3/15 号线，
      从 1 号线站对象出发坐 3 号线不应被罚 8 分钟）；
    - 终点同站组内的换乘边权置 3：下车后步行到目标站厅出站，无需二次候车；
    - 其余中途换乘保持 TRANSFER_PENALTY_MIN。
    """
    og = set(origin_group)
    dg = set(dest_group)
    if not og and not dg:
        return adj_min
    adj = {}
    for u, edges in adj_min.items():
        new_edges = []
        for v, w in edges:
            if edge_meta.get((u, v), ('', 0, 0))[0] == '换乘':
                pair = {u, v}
                if pair <= og:
                    w = 0
                elif pair <= dg:
                    w = 3
            new_edges.append((v, w))
        adj[u] = new_edges
    return adj


# Cache graphs at module level (rebuilt when server starts)
_GRAPH_CACHE = {}   # (include_maglev, include_airport) -> graph
_NAME_OF_CACHE = None
_LINE_COLORS_CACHE = None


def name_of_all():
    """id -> station name, cached at module level."""
    global _NAME_OF_CACHE
    if _NAME_OF_CACHE is None:
        _NAME_OF_CACHE = {s.id: s.name for s in Station.objects.all()}
    return _NAME_OF_CACHE


def line_colors():
    global _LINE_COLORS_CACHE
    if _LINE_COLORS_CACHE is None:
        _LINE_COLORS_CACHE = {l.name: l.color for l in Line.objects.all()}
    return _LINE_COLORS_CACHE


def get_graph(include_maglev=False, include_airport=True):
    key = (include_maglev, include_airport)
    if key not in _GRAPH_CACHE:
        _GRAPH_CACHE[key] = build_graph(
            include_maglev=include_maglev, include_airport=include_airport)
    return _GRAPH_CACHE[key]  # (adj_km, adj_min, edge_meta)


def index(request):
    lines = [l for l in Line.objects.prefetch_related('stations').all()
             if l.name != '换乘']
    lines.sort(key=lambda l: int(l.code) if l.code.isdigit() else 999)

    # Baidu-map colors so legend matches the on-page SVG network map
    BAIDU_COLORS = {
        '1号线': '#D53940', '2号线': '#7FBE29', '3号线': '#F5D503', '4号线': '#3F267F',
        '5号线': '#885196', '6号线': '#C32A67', '7号线': '#DD762E', '8号线': '#4795D4',
        '9号线': '#94C7E9', '10号线': '#C0B2D2', '11号线': '#7C343C', '12号线': '#327660',
        '13号线': '#DA9DBE', '14号线': '#615E38', '15号线': '#C3B292', '16号线': '#A4CEC0',
        '17号线': '#AC7A70', '18号线': '#B58A57', '浦江线': '#A39892', '市域机场线': '#2A5F7C',
        '磁悬浮': '#B3B3B3',
    }
    for l in lines:
        l.baidu_color = BAIDU_COLORS.get(l.name, l.color)

    # name -> {line_name: station_id}, line_name -> ordered stations
    name_lines_ids = defaultdict(dict)
    line_stations = defaultdict(list)
    for line in lines:
        for station in line.stations.all():
            name_lines_ids[station.name][line.name] = station.id
            line_stations[line.name].append(station)

    # Select options grouped by line (二级目录). Transfer stations appear under
    # every line they serve, annotated with the other lines (换乘标注).
    groups = []
    for line in lines:
        opts = []
        for st in line_stations[line.name]:
            others = [l for l in name_lines_ids[st.name] if l != line.name]
            if others:
                label = f'{st.name}（换乘 {"、".join(others)}）'
            else:
                label = st.name
            opts.append({'id': st.id, 'label': label})
        groups.append({'line': line.name, 'color': line.baidu_color, 'stations': opts})

    # Search index: name -> lines & per-line ids
    search_data = [
        {'name': name, 'lines': list(d.keys()), 'ids': {l: d[l] for l in d}}
        for name, d in name_lines_ids.items()
    ]
    search_data.sort(key=lambda x: x['name'])

    return render(request, 'subway/index.html', {
        'lines': lines, 'groups': groups, 'search_data': search_data,
    })


def build_trip_plan(origin, dest_id, prev, edge_meta):
    """Reconstruct route path, split into line segments with time & transfers."""
    path_ids = [dest_id]
    guard = 0
    while path_ids[-1] != origin.id:
        guard += 1
        if guard > 3000:
            break
        path_ids.append(prev[path_ids[-1]])
    path_ids.reverse()

    name_map = {s.id: s.name for s in Station.objects.filter(pk__in=path_ids)}

    segments = []
    cur_line = None
    cur_start = None
    total_minutes = 0
    for i in range(len(path_ids) - 1):
        u, v = path_ids[i], path_ids[i + 1]
        line_name, travel_time, _ = edge_meta.get((u, v), ('未知', 0, 0))
        total_minutes += travel_time
        if line_name == '换乘':
            if cur_line is not None:
                segments.append({
                    'line': cur_line,
                    'from': name_map[path_ids[cur_start]],
                    'to': name_map[path_ids[i]],
                    'stopCount': i - cur_start,
                    'stations': [name_map[path_ids[j]] for j in range(cur_start, i + 1)],
                })
                cur_line = None
            continue
        if cur_line is None:
            cur_line = line_name
            cur_start = i
        elif line_name != cur_line:
            segments.append({
                'line': cur_line,
                'from': name_map[path_ids[cur_start]],
                'to': name_map[path_ids[i]],
                'stopCount': i - cur_start,
                'stations': [name_map[path_ids[j]] for j in range(cur_start, i + 1)],
            })
            cur_line = line_name
            cur_start = i
    if cur_line is not None:
        segments.append({
            'line': cur_line,
            'from': name_map[path_ids[cur_start]],
            'to': name_map[path_ids[-1]],
            'stopCount': len(path_ids) - 1 - cur_start,
            'stations': [name_map[path_ids[j]] for j in range(cur_start, len(path_ids))],
        })

    for seg in segments:
        seg['color'] = line_colors().get(seg['line'], '#666666')
    return {
        'segments': segments,
        'minutes': total_minutes,
        'transfers': len(segments) - 1 if segments else 0,
        'route': [name_map[s] for s in path_ids],
    }


def fare_with_maglev(path_ids, edge_meta, name_of):
    """Fare of the maglev alternative path:
    maglev sections +50 yuan each; airport-link sections priced by the official
    table; ordinary sections keep the standard continuous distance fare.
    """
    groups = []
    cur = None
    for u, v in zip(path_ids, path_ids[1:]):
        ln = edge_meta.get((u, v), ('未知', 0, 0))[0]
        if ln == '换乘':
            if cur is not None:
                groups.append(cur)
                cur = None
            continue
        if cur is None:
            cur = [ln, [u, v]]
        elif ln == cur[0]:
            cur[1].append(v)
        else:
            groups.append(cur)
            cur = [ln, [u, v]]
    if cur is not None:
        groups.append(cur)
    if not groups:
        return 0
    maglev_total = 0
    airport_total = 0
    ordinary_km = 0.0
    for ln, ids in groups:
        if ln == MAGLEV_LINE:
            maglev_total += MAGLEV_FARE
        elif ln == AIRPORT_LINE:
            airport_total += airport_fare(name_of[ids[0]], name_of[ids[-1]])
        else:
            ordinary_km += sum(
                edge_meta.get((x, y), ('', 0, 0))[2] for x, y in zip(ids, ids[1:]))
    return maglev_total + airport_total + (fare_by_distance(ordinary_km) if ordinary_km > 0 else 0)


def build_airport_alt(origin, dest, main_minutes, origin_group=(), dest_group=()):
    """Alternative via the airport link (if actually used and faster).
    Runs Dijkstra on the full graph (ordinary + airport link, maglev excluded)
    with the time weight; returns the plan only when the fastest path uses the
    airport link and beats the main plan.
    """
    adj_km, adj_min_raw, edge_meta = get_graph(include_maglev=False,
                                               include_airport=True)
    adj_min = request_time_graph(adj_min_raw, edge_meta, origin_group, dest_group)
    dist, prev = dijkstra(adj_min, origin.id)
    if dest.id not in prev and dest.id != origin.id:
        return None
    path_ids = [dest.id]
    guard = 0
    while path_ids[-1] != origin.id:
        guard += 1
        if guard > 3000:
            break
        path_ids.append(prev[path_ids[-1]])
    path_ids.reverse()
    lines_on_path = {edge_meta.get((u, v), ('', 0, 0))[0]
                     for u, v in zip(path_ids, path_ids[1:])}
    if AIRPORT_LINE not in lines_on_path:
        return None
    plan = build_trip_plan(origin, dest.id, prev, edge_meta)
    if plan['minutes'] >= main_minutes:
        return None
    name_of = name_of_all()
    fare = fare_with_maglev(path_ids, edge_meta, name_of)
    km = sum(edge_meta.get((u, v), ('', 0, 0))[2] for u, v in zip(path_ids, path_ids[1:]))
    return {
        'fare': fare,
        'distance_km': round(km, 1),
        'minutes': plan['minutes'],
        'transfers': plan['transfers'],
        'segments': plan['segments'],
        'route': plan['route'],
        'maglev': False,
        'airport': True,
        '_path': path_ids,
    }


def backtrace(prev, start, stop):
    """Rebuild id list from `start` back to `stop` via prev; guarded against loops."""
    ids = [start]
    cur = start
    guard = 0
    while cur != stop:
        guard += 1
        if guard > 3000:
            return None
        nxt = prev.get(cur)
        if nxt is None:
            return None
        ids.append(nxt)
        cur = nxt
    ids.reverse()
    return ids


def build_maglev_alt(origin, dest, main_minutes, origin_group=(), dest_group=()):
    """Alternative that explicitly rides the maglev (if faster than the main plan).
    Tries both directions (origin -> Longyang Rd -> maglev -> Pudong Airport ->
    dest and the reverse). Candidates that would loop back onto the maglev
    (i.e. the exit end already appears in the origin->entry leg, or the entry
    end already appears in the exit->dest leg) are skipped.
    """
    adj_km, adj_min, edge_meta = get_graph(include_maglev=True)
    # 入口/出口两段在地铁（+机场线）图上计算，磁悬浮只走 entry->exit 一段，
    # 避免“先借道磁悬浮再回来”的来回绕行。
    adj_min_plain = defaultdict(list)
    for u, edges in adj_min.items():
        for v, w in edges:
            if edge_meta.get((u, v), ('', 0, 0))[0] == MAGLEV_LINE:
                continue
            adj_min_plain[u].append((v, w))
    # 起终点同站组换乘权与主方案同口径（入口段起点 0、出口段终点 3）
    adj_p1 = request_time_graph(adj_min_plain, edge_meta, origin_group)
    adj_p2 = request_time_graph(adj_min_plain, edge_meta, (), dest_group)
    mag_st = {s.name: s for s in Station.objects.filter(line__name=MAGLEV_LINE)}
    if '龙阳路' not in mag_st or '浦东1号2号航站楼' not in mag_st:
        return None
    dist_o, prev_o = dijkstra(adj_p1, origin.id)
    best = None
    for entry_name, exit_name in [('龙阳路', '浦东1号2号航站楼'),
                                  ('浦东1号2号航站楼', '龙阳路')]:
        entry = mag_st[entry_name]
        exit_st = mag_st[exit_name]
        if entry.id not in dist_o:
            continue
        p1 = backtrace(prev_o, entry.id, origin.id)
        if p1 is None:
            continue
        if exit_st.id in p1:
            continue  # 入口侧已过出口端，磁悬浮段已覆盖，避免回环
        dist_e, prev_e = dijkstra(adj_p2, exit_st.id)
        if dest.id not in dist_e:
            continue
        p2 = backtrace(prev_e, dest.id, exit_st.id)
        if p2 is None:
            continue
        if entry.id in p2:
            continue  # 出口侧已过入口端，避免回环
        # 起终点位于磁浮同一侧时，出口段会重走入口段（如市区->浦东坐磁浮再折回市区），
        # 拼接路径出现重复站会使回溯链断裂、磁浮段丢失，此类回环方案直接剔除。
        if set(p1) & set(p2):
            continue
        mag_edge = edge_meta.get((entry.id, exit_st.id))
        if mag_edge is None:
            continue
        total = dist_o[entry.id] + mag_edge[1] + dist_e[dest.id]
        if best is None or total < best[0]:
            best = (total, p1, p2)
    if best is None:
        return None
    total, p1, p2 = best
    # path = p1 (ends at entry) + p2 (starts at exit); entry->exit is the maglev edge
    path_ids = p1 + p2
    full_prev = {}
    for u, v in zip(path_ids, path_ids[1:]):
        full_prev[v] = u
    plan = build_trip_plan(origin, dest.id, full_prev, edge_meta)
    # 快慢比较必须与主方案同口径（build_trip_plan 的 edge_meta 时间）；
    # total 用的是请求级权重（起点 0/终点 3/中途 8），仅用于两个方向间择优。
    if plan['minutes'] >= main_minutes:
        return None
    name_of = name_of_all()
    fare = fare_with_maglev(path_ids, edge_meta, name_of)
    km = sum(edge_meta.get((u, v), ('', 0, 0))[2] for u, v in zip(path_ids, path_ids[1:]))
    return {
        'fare': fare,
        'distance_km': round(km, 1),
        'minutes': plan['minutes'],
        'transfers': plan['transfers'],
        'segments': plan['segments'],
        'route': plan['route'],
        'maglev': True,
        'airport': False,
        '_path': path_ids,
    }


def build_alternatives(origin, dest, main_minutes, origin_group=(), dest_group=()):
    """All faster alternatives: airport-link plan and/or maglev plan."""
    alts = []
    airport_alt = build_airport_alt(origin, dest, main_minutes,
                                    origin_group, dest_group)
    if airport_alt:
        alts.append(airport_alt)
    maglev_alt = build_maglev_alt(origin, dest, main_minutes,
                                  origin_group, dest_group)
    if maglev_alt:
        # 去重：与机场线备选完全同路径时只保留一条
        if not any(a.get('_path') == maglev_alt.get('_path') for a in alts):
            alts.append(maglev_alt)
    for a in alts:
        a.pop('_path', None)
    return alts


def station_fares(request, station_id):
    origin = get_object_or_404(Station.objects.select_related('line'), pk=station_id)
    destination_id = request.GET.get('destination')
    name_of = name_of_all()

    # 纯普通地铁网（不含机场线/磁悬浮）的最短里程，用于全普通方案计价
    plain_adj_km, _, _ = get_graph(include_airport=False)
    plain_dist, _ = dijkstra(plain_adj_km, origin.id)

    if destination_id:
        # Single trip mode: show origin -> destination with route plan
        try:
            dest_id = int(destination_id)
        except (TypeError, ValueError):
            return JsonResponse({
                'error': 'destination 参数必须为站点 ID',
                'origin': {'id': origin.id, 'name': origin.name, 'line': origin.line.name},
                'fares': [],
                'trip': None,
                'alternatives': [],
            }, status=400)
        dest = get_object_or_404(Station.objects.select_related('line'), pk=dest_id)
        # 机场线不作为普通 OD 的第一选择；当起/终点属于机场线
        # （含仅机场线可达站）时，机场线作为第一选择启用
        use_airport = (origin.line.name == AIRPORT_LINE
                       or dest.line.name == AIRPORT_LINE
                       or origin.name in AIRPORT_ONLY
                       or dest.name in AIRPORT_ONLY)
        _, adj_min_raw, edge_meta = get_graph(include_airport=use_airport)
        origin_group = list(
            Station.objects.filter(name=origin.name).values_list('id', flat=True))
        dest_group = list(
            Station.objects.filter(name=dest.name).values_list('id', flat=True))
        adj_min = request_time_graph(adj_min_raw, edge_meta,
                                     origin_group, dest_group)
        dist_min, prev = dijkstra(adj_min, origin.id)   # 最快方案 -> 展示与计价
        if dest_id not in dist_min or dest_id == origin.id:
            return JsonResponse({
                'origin': {'id': origin.id, 'name': origin.name, 'line': origin.line.name},
                'fares': [],
                'trip': None,
            })
        path_ids = backtrace(prev, dest_id, origin.id)
        plan = build_trip_plan(origin, dest_id, prev, edge_meta)
        groups = split_line_groups(path_ids, edge_meta)
        uses_airport = any(g[0] == AIRPORT_LINE for g in groups)
        if uses_airport:
            # 展示方案含机场线：机场段按官方表、普通段按里程，分段相加
            fare = fare_for_plan(path_ids, edge_meta, name_of,
                                 plain_shortest_km=plain_dist.get(dest_id))
            show_km = path_riding_km(path_ids, edge_meta)
        else:
            # 全程普通线：按普通网最短乘车里程计价（与官方 OD 计价口径一致）
            show_km = plain_dist.get(dest_id, 0.0)
            fare = fare_by_distance(show_km) if show_km > 0 else 0
        alternative = build_alternatives(origin, dest, plan['minutes'],
                                         origin_group, dest_group)
        return JsonResponse({
            'origin': {'id': origin.id, 'name': origin.name, 'line': origin.line.name},
            'fares': [{
                'id': dest.id,
                'name': dest.name,
                'line': dest.line.name,
                'distance_km': round(show_km, 1),
                'fare': fare,
            }],
            'trip': {
                'origin': f'{origin.name}（{origin.line.name}）',
                'destination': f'{dest.name}（{dest.line.name}）',
                'distance_km': round(show_km, 1),
                'fare': fare,
                'minutes': plan['minutes'],
                'transfers': plan['transfers'],
                'segments': plan['segments'],
                'route': plan['route'],
            },
            'alternatives': alternative,
        })
    # List mode: all reachable stations.
    # 普通起点的主方案不借道机场线（与单 trip 模式口径一致）；机场线起点用全图。
    # 票价一律按时间图（实际展示方案）计价：含机场线则分段，否则按普通网最短里程。
    origin_is_airport = (origin.line.name == AIRPORT_LINE
                         or origin.name in AIRPORT_ONLY)
    origin_group = list(
        Station.objects.filter(name=origin.name).values_list('id', flat=True))
    if origin_is_airport:
        adj_km, adj_min_raw, edge_meta = get_graph()
    else:
        adj_km, adj_min_raw, edge_meta = get_graph(include_airport=False)
    adj_min = request_time_graph(adj_min_raw, edge_meta, origin_group)
    dist_km, _ = dijkstra(adj_km, origin.id)     # 最短里程 -> 同名站合并
    dist_min, prev = dijkstra(adj_min, origin.id)  # 最快方案 -> 计价
    # Batch fetch all stations in ONE query, merge transfer stations by name.
    all_stations = {
        s.id: s
        for s in Station.objects.select_related('line').filter(pk__in=list(dist_km.keys()))
    }
    name_best = {}   # name -> (km, station)
    name_lines_map = defaultdict(set)
    for sid, km in dist_km.items():
        if sid == origin.id:
            continue
        dst = all_stations.get(sid)
        if dst is None:
            continue
        if dst.name == origin.name:
            continue  # transfer counterpart of origin itself
        if dst.name not in name_best or km < name_best[dst.name][0]:
            name_best[dst.name] = (km, dst)
        name_lines_map[dst.name].add(dst.line.name)

    results = []
    for name, (km, dst) in name_best.items():
        lines_str = '、'.join(sorted(name_lines_map[name])) if len(name_lines_map[name]) > 1 else dst.line.name
        pids = backtrace(prev, dst.id, origin.id)
        if pids is None:
            continue
        grps = split_line_groups(pids, edge_meta)
        if any(g[0] == AIRPORT_LINE for g in grps):
            fare = fare_for_plan(pids, edge_meta, name_of,
                                 plain_shortest_km=plain_dist.get(dst.id))
            show_km = path_riding_km(pids, edge_meta)
        else:
            show_km = plain_dist.get(dst.id, km)
            fare = fare_by_distance(show_km) if show_km > 0 else 0
        results.append({
            'id': dst.id,
            'name': name,
            'line': lines_str,
            'distance_km': round(show_km, 1),
            'fare': fare,
        })

    # 普通起点：补算仅机场线可达的 4 个专属站（机场线即第一选择，分段计价）
    if not origin_is_airport:
        _, adj2_min_raw, em2 = get_graph(include_airport=True)
        adj2_min = request_time_graph(adj2_min_raw, em2, origin_group)
        d2min, p2min = dijkstra(adj2_min, origin.id)
        existing = {r['name'] for r in results}
        for nm in AIRPORT_ONLY:
            st = Station.objects.filter(name=nm, line__name=AIRPORT_LINE).first()
            if st is None or st.id not in d2min or nm in existing:
                continue
            pids = backtrace(p2min, st.id, origin.id)
            if pids is None:
                continue
            f2 = fare_for_plan(pids, em2, name_of,
                               plain_shortest_km=plain_dist.get(st.id))
            results.append({
                'id': st.id,
                'name': nm,
                'line': AIRPORT_LINE,
                'distance_km': round(path_riding_km(pids, em2), 1),
                'fare': f2,
            })

    results.sort(key=lambda r: (r['fare'], r['distance_km']))

    return JsonResponse({
        'origin': {'id': origin.id, 'name': origin.name, 'line': origin.line.name},
        'fares': results,
        'trip': None,
    })
