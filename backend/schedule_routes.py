"""Coverage-first selection and compact station groups, independent of travel routes."""
from collections import Counter
from fractions import Fraction
from math import asin, cos, isfinite, radians, sin, sqrt

ORIGIN_ADDRESS = '上海市浦东新区世纪大道1200号'
# China Petroleum Shanghai Tower, OSM way 965366026 centroid (121.5271139,31.227512325)
# converted from WGS84 to the GCJ-02 coordinates used by the station map.
# Source: https://www.openstreetmap.org/way/965366026 (OpenStreetMap contributors).
ORIGIN_POINT = (121.53144968, 31.22541333)


def coordinate(value):
    try:
        if isinstance(value, dict):
            value = (value['longitude'], value['latitude'])
        if not isinstance(value, (tuple, list)) or len(value) != 2 or any(isinstance(n, bool) for n in value):
            return None
        lng, lat = map(float, value)
        # Only Shanghai and surrounding service area; reject zero, NaN and swapped coordinates.
        return (lng, lat) if isfinite(lng) and isfinite(lat) and 119 < lng < 123 and 29 < lat < 33 else None
    except (TypeError, ValueError, KeyError):
        return None


def distance(a, b):
    x1, y1, x2, y2 = map(radians, (*a, *b))
    h = sin((y2-y1)/2)**2 + cos(y1)*cos(y2)*sin((x2-x1)/2)**2
    return 12742 * asin(sqrt(min(1, h)))


def regional_coverage(rows, day):
    """Any actual checklist covers a station; current/future plans reserve untouched stations."""
    regions = {}
    for row in rows:
        item = regions.setdefault(row['region'], dict(region=row['region'], total=0, checked=0, reserved=0))
        item['total'] += 1
        checked = any(c['status'] == 'completed' for c in row['cells'].values())
        reserved = any(c['status'] == 'assigned' and c.get('scheduled_date') and
                       c['scheduled_date'] >= day.isoformat() for c in row['cells'].values())
        item['checked'] += int(checked)
        item['reserved'] += int(reserved and not checked)
    return list(regions.values())


def regional_targets(stations, count, coverage):
    """Water-fill the lowest coverage rates, not equal raw station counts or map distance."""
    remaining = Counter((s.get('region', ''), bool(s.get('covered'))) for s in stations)
    stats = {r['region']: dict(r, selected=0, newly_covered=0) for r in coverage}
    for s in stations:
        region = s.get('region', '')
        if region not in stats:
            total = sum(n for (name, _), n in remaining.items() if name == region)
            stats[region] = dict(region=region,total=total,checked=0,reserved=0,selected=0,newly_covered=0)
    order = {region: i for i, region in enumerate(stats)}
    targets = Counter()
    for _ in range(min(count,len(stations))):
        choices = [r for r in stats.values() if remaining[(r['region'],False)] or remaining[(r['region'],True)]]
        def score(r):
            base = r['checked'] + r['reserved'] + r['newly_covered']
            return (Fraction(base,max(1,r['total'])),
                    Fraction(base + bool(remaining[(r['region'],False)]),max(1,r['total'])),order[r['region']])
        chosen = min(choices,key=score)
        region = chosen['region']
        covered = not bool(remaining[(region,False)])
        remaining[(region,covered)] -= 1
        targets[(region,covered)] += 1
        chosen['selected'] += 1
        chosen['newly_covered'] += int(not covered)
    for r in stats.values():
        r['current_rate'] = round(100*r['checked']/max(1,r['total']),1)
        r['projected_rate'] = round(100*(r['checked']+r['reserved']+r['newly_covered'])/max(1,r['total']),1)
    return targets,list(stats.values())


def field_routes(stations, team_count, quota, origin=None, *, coverage=None, required_ids=()):
    """Keep the legacy entry point; origin is intentionally ignored, not a route objective."""
    if team_count <= 0 or quota <= 0: return []
    stations = sorted((s for s in stations if coordinate(s)),key=lambda s:s['station_id'])
    if not stations: return []
    required_ids=set(required_ids)
    required=[s for s in stations if s['station_id'] in required_ids]
    regular=[s for s in stations if s['station_id'] not in required_ids]
    targets=Counter((s.get('region',''),bool(s.get('covered')),True) for s in required)
    fill,_ = regional_targets(regular,max(0,team_count*quota-len(required)),coverage or [])
    targets.update({(region,covered,False):n for (region,covered),n in fill.items()})
    category = lambda i: (stations[i].get('region',''),bool(stations[i].get('covered')),stations[i]['station_id'] in required_ids)
    points = [coordinate(s) for s in stations]
    distances = [[distance(a,b) for b in points] for a in points]
    remaining = set(range(len(stations)))
    groups = []
    # Spread group seeds, then grow with nearby stations within the already fixed regional quotas.
    for _ in range(min(team_count,sum(targets.values()))):
        choices = [i for i in sorted(remaining) if targets[category(i)]]
        if not choices: break
        if groups:
            seed = max(choices,key=lambda i:(min(distances[i][g[0]] for g in groups),-i))
        else:
            seed = min(choices,key=lambda i:(sum(sorted(distances[i][j] for j in choices)[:quota]),i))
        groups.append([seed]); remaining.remove(seed); targets[category(seed)] -= 1
    for _ in range(quota-1):
        for group in groups:
            choices = [i for i in sorted(remaining) if targets[category(i)]]
            if not choices: break
            chosen = min(choices,key=lambda i:(max(distances[i][j] for j in group),
                                               sum(distances[i][j] for j in group),i))
            group.append(chosen); remaining.remove(chosen); targets[category(chosen)] -= 1
    # Bounded local swaps reduce total pairwise distance without changing regional coverage or capacities.
    for _ in range(8):
        best,delta = None,-1e-6
        for a,group in enumerate(groups):
            for x in group:
                old = sum(distances[x][p] for p in group)
                for y in sorted(remaining):
                    if category(x) != category(y): continue
                    change = sum(distances[y][p] for p in group if p!=x)-old
                    if change < delta: best,delta = (a,x,None,y),change
                for b in range(a+1,len(groups)):
                    for y in groups[b]:
                        change = (sum(distances[y][p]-distances[x][p] for p in group if p!=x)
                                  +sum(distances[x][p]-distances[y][p] for p in groups[b] if p!=y))
                        if change < delta: best,delta = (a,x,b,y),change
        if best is None: break
        a,x,b,y = best
        groups[a][groups[a].index(x)] = y
        if b is None: remaining.remove(y); remaining.add(x)
        else: groups[b][groups[b].index(y)] = x
    return [[stations[i] for i in sorted(group)] for group in groups]


def cluster_diameter(stations):
    return max((distance(coordinate(a),coordinate(b)) for i,a in enumerate(stations) for b in stations[i+1:]),default=0)
