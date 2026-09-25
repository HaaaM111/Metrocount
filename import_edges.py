"""Import edges from CSV into the Edge model.
CSV format: 起点站ID, 终点站ID, 所属线路, 运行方向, 通行时间, 状态
Station CSV has: 站点ID, 站点名, 所属路线, 运营状态
"""
import csv
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'metrocount.settings')
django.setup()

from subway.models import Station, Line, Edge

CSV_DIR = os.path.expandvars(r'%TEMP%\shmetro_data')

# 1. Build mapping from CSV station ID -> (station_name, line_name)
csv_stations = {}
with open(os.path.join(CSV_DIR, 'Station.csv'), encoding='utf-8') as f:
    for row in csv.DictReader(f):
        csv_stations[int(row['站点ID'])] = {
            'name': row['站点名'],
            'line': row['所属路线'],
        }

print(f'CSV stations: {len(csv_stations)}')

# 2. Build mapping: (station_name, line_name) -> db Station id
db_map = {}
for s in Station.objects.select_related('line').all():
    db_map[(s.name, s.line.name)] = s.id

# 3. Build CSV ID -> db ID mapping
csv_to_db = {}
missing = []
for csv_id, info in csv_stations.items():
    key = (info['name'], info['line'])
    if key in db_map:
        csv_to_db[csv_id] = db_map[key]
    else:
        missing.append(key)

print(f'Mapped: {len(csv_to_db)}, Missing: {len(missing)}')
if missing:
    print('Missing examples:', missing[:10])

# 4. Clear existing edges
Edge.objects.all().delete()

# 5. Import edges
created = 0
errors = []
with open(os.path.join(CSV_DIR, 'Edge.csv'), encoding='utf-8') as f:
    for row in csv.DictReader(f):
        from_csv = int(row['起点站ID'])
        to_csv = int(row['终点站ID'])
        line_name = row['所属线路']
        time_min = int(row['通行时间'])

        if from_csv not in csv_to_db or to_csv not in csv_to_db:
            errors.append(f'Unknown station: {from_csv} or {to_csv}')
            continue

        # Find line
        try:
            line = Line.objects.get(name=line_name)
        except Line.DoesNotExist:
            errors.append(f'Unknown line: {line_name}')
            continue

        Edge.objects.create(
            from_station_id=csv_to_db[from_csv],
            to_station_id=csv_to_db[to_csv],
            line=line,
            travel_time=time_min,
        )
        created += 1

print(f'Edges created: {created}')
if errors:
    print(f'Errors: {len(errors)}')
    for e in errors[:10]:
        print(f'  {e}')

# 6. Verify
total = Edge.objects.count()
print(f'Total edges in DB: {total}')
