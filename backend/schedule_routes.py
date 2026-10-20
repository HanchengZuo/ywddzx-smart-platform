"""Small deterministic geographic routes; no network, paid AI or new dependency."""
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


def length(route, origin):
    points = [origin] + [coordinate(p) for p in route] + [origin]
    return sum(distance(a, b) for a, b in zip(points, points[1:]))


def optimized(route, origin):
    """2-opt only accepts strictly shorter round trips, so it is deterministic and bounded."""
    result = list(route)
    for _ in range(20):
        best, score = result, length(result, origin)
        for i in range(len(result)):
            for j in range(i+2, len(result)+1):
                candidate = result[:i] + result[i:j][::-1] + result[j:]
                cost = length(candidate, origin)
                if cost + 1e-6 < score:
                    best, score = candidate, cost
        if best is result: break
        result = best
    return result


def field_routes(stations, team_count, quota, origin):
    """Seed separate directions, grow compact clusters, then improve each return journey."""
    remaining = sorted((s for s in stations if coordinate(s)), key=lambda s: s['station_id'])
    routes = []
    for _ in range(team_count):
        if not remaining: break
        # Spread seeds to avoid assigning every group a long trip in the same direction.
        seed = min(remaining, key=lambda s: distance(origin, coordinate(s))) if not routes else max(
            remaining, key=lambda s: min(distance(coordinate(s), coordinate(r[0])) for r in routes))
        remaining.remove(seed)
        routes.append([seed])
    for _ in range(quota-1):
        for route in routes:
            if not remaining: break
            station = min(remaining, key=lambda s: length(route+[s], origin)-length(route, origin))
            remaining.remove(station)
            route.append(station)
    return [optimized(route, origin) for route in routes]
