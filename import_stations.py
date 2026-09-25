"""Import Shanghai Metro stations from CSV and assign coordinates along SVG paths."""
import csv
import os
import re
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'metrocount.settings')
django.setup()

from subway.models import Line, Station
from subway.views import LINE_PATHS

CSV_PATH = r'C:\Users\22057\Downloads\Station.csv'

# Line name -> (code, color) for new lines not in DB
NEW_LINES = {
    '浦江线': ('浦江线', '#c7c7c7'),
    '市域机场线': ('机场线', '#e8b33a'),
}

# Map CSV line names to DB line names (CSV uses "1号线" etc.)
# DB already has lines 1-18 with proper names.

def parse_path_points(d):
    """Parse SVG path d string and return list of (x,y) points."""
    points = []
    # Match M/L commands with coordinate pairs
    tokens = re.findall(r'([ML])\s*([-\d.,\s]+)', d)
    for cmd, coords_str in tokens:
        coords = [float(v) for v in re.findall(r'-?[\d.]+', coords_str)]
        for i in range(0, len(coords), 2):
            points.append((coords[i], coords[i+1]))
    return points

def sample_path(points, t):
    """Sample a point along a polyline at parameter t (0..1)."""
    if len(points) < 2:
        return points[0] if points else (50, 50)
    # Compute segment lengths
    seg_lengths = []
    total = 0
    for i in range(len(points) - 1):
        dx = points[i+1][0] - points[i][0]
        dy = points[i+1][1] - points[i][1]
        seg_len = (dx**2 + dy**2) ** 0.5
        seg_lengths.append(seg_len)
        total += seg_len
    if total == 0:
        return points[0]
    target = t * total
    accumulated = 0
    for i, seg_len in enumerate(seg_lengths):
        if accumulated + seg_len >= target:
            ratio = (target - accumulated) / seg_len if seg_len > 0 else 0
            x = points[i][0] + ratio * (points[i+1][0] - points[i][0])
            y = points[i][1] + ratio * (points[i+1][1] - points[i][1])
            return (x, y)
        accumulated += seg_len
    return points[-1]


def main():
    # Read CSV
    rows = []
    with open(CSV_PATH, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = row['站点名'].strip()
            line_name = row['所属线路'].strip()
            if not name or not line_name:
                continue
            rows.append((name, line_name))

    print(f"Read {len(rows)} stations from CSV")

    # Clear existing stations
    Station.objects.all().delete()
    print("Cleared existing stations")

    # Ensure all lines exist
    existing_lines = {l.name: l for l in Line.objects.all()}
    for name, (code, color) in NEW_LINES.items():
        if name not in existing_lines:
            Line.objects.create(name=name, code=code, color=color)
            existing_lines[name] = Line.objects.get(name=name)
            print(f"Created line: {name}")

    # Group stations by line, preserving CSV order
    from collections import OrderedDict
    line_stations = OrderedDict()  # line_name -> list of station names in order
    for name, line_name in rows:
        if line_name not in line_stations:
            line_stations[line_name] = []
        line_stations[line_name].append(name)

    # Detect transfer stations (same name on multiple lines)
    name_count = {}
    for name, line_name in rows:
        name_count[name] = name_count.get(name, 0) + 1

    # Parse path points for each line
    # CSV order may be opposite to path direction; reverse these lines
    REVERSE_LINES = {'1', '3', '6', '8', '10', '15', '18'}
    line_path_points = {}
    for code, d in LINE_PATHS.items():
        pts = parse_path_points(d)
        if code in REVERSE_LINES:
            pts = list(reversed(pts))
        line_path_points[code] = pts

    # For new lines without paths, create a simple horizontal spread
    def simple_spread(name, count):
        """Generate a simple spread for lines without a defined path."""
        # Place in a loose grid area
        pts = []
        for i in range(count):
            t = i / max(count - 1, 1)
            pts.append((50 + t * 30, 120 - t * 10))
        return pts

    # Create stations
    created = 0
    for line_name, station_names in line_stations.items():
        line = existing_lines.get(line_name)
        if not line:
            print(f"WARNING: No line for {line_name}")
            continue
        n = len(station_names)
        path_pts = line_path_points.get(line.code)
        if not path_pts:
            path_pts = simple_spread(line_name, n)

        for idx, name in enumerate(station_names):
            t = idx / max(n - 1, 1)
            x, y = sample_path(path_pts, t)
            is_transfer = name_count.get(name, 1) > 1
            Station.objects.create(
                name=name,
                line=line,
                sequence=idx + 1,
                x=round(x),
                y=round(y),
                is_transfer=is_transfer,
            )
            created += 1

    print(f"Created {created} stations")
    print(f"Transfer stations: {Station.objects.filter(is_transfer=True).count()}")
    print(f"Total lines: {Line.objects.count()}")

    # Align transfer stations: set same-name stations to average coordinate
    from django.db.models import Avg
    transfer_names = [name for name, count in name_count.items() if count > 1]
    for name in transfer_names:
        avg_x = Station.objects.filter(name=name).aggregate(Avg('x'))['x__avg']
        avg_y = Station.objects.filter(name=name).aggregate(Avg('y'))['y__avg']
        Station.objects.filter(name=name).update(x=round(avg_x), y=round(avg_y))
    print(f"Aligned {len(transfer_names)} transfer stations")


if __name__ == '__main__':
    main()
