"""Coverage-constrained groups ranked by directed driving seconds, never geometry."""
from collections import Counter
import hashlib
import json
from math import inf

from schedule_routes import coordinate, regional_targets
from schedule_common import ScheduleConflict


class DrivingPlanNeeded(Exception):
    def __init__(self, request):
        self.request = request


def driving_request(stations, team_count, quota, coverage, required_ids, capacities):
    return dict(stations=[dict(station_id=s['station_id'], region=s.get('region', ''),
                              covered=bool(s.get('covered')), point=list(coordinate(s)))
                          for s in sorted(stations, key=lambda s: s['station_id']) if coordinate(s)],
                team_count=team_count, quota=quota, capacities=capacities,
                coverage=coverage, required_ids=sorted(required_ids), algorithm='driving-time-v1')


def request_key(request):
    return hashlib.sha256(json.dumps(request, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def resolve_driving_plan(request, prepared):
    if prepared is None:
        raise DrivingPlanNeeded(request)
    if prepared['request_key'] != request_key(request):
        raise ScheduleConflict('站点、坐标、片区目标或人员容量已变化，请重新计算智能方案。')
    return prepared


def driving_groups(request, matrix):
    """Bounded heuristic: fixed coverage buckets, road-time growth and local swaps.

    Matrix.incoming queries many candidate origins to a selected destination at
    once. Only measured directed legs are used; missing directions are never
    filled with straight-line distance or copied from the opposite direction.
    """
    stations = request['stations']
    capacities = request['capacities']
    required = set(request['required_ids'])
    if not stations or not capacities:
        return []
    by_id = {s['station_id']: s for s in stations}
    required_stations = [s for s in stations if s['station_id'] in required]
    regular = [s for s in stations if s['station_id'] not in required]
    targets = Counter((s['region'], s['covered'], True) for s in required_stations)
    fill, _ = regional_targets(regular, max(0, sum(capacities) - len(required_stations)), request['coverage'])
    targets.update({(region, covered, False): n for (region, covered), n in fill.items()})
    category = lambda sid: (by_id[sid]['region'], by_id[sid]['covered'], sid in required)
    remaining = set(by_id)
    initial_targets = targets.copy()
    groups = []
    # Spread seeds across the already chosen regional buckets, not across a map.
    for _ in range(min(len(capacities), sum(targets.values()))):
        choices = [sid for sid in sorted(remaining) if targets[category(sid)]]
        if not choices:
            break
        seed = min(choices, key=lambda sid: (
            -int(sid in required),
            (initial_targets[category(sid)] - targets[category(sid)]) / initial_targets[category(sid)], sid))
        groups.append([seed])
        remaining.remove(seed)
        targets[category(seed)] -= 1

    # Existing members' incoming columns give real candidate -> member routes.
    # Time is the first criterion; driving metres only break equal-time ties.
    def pair(a, b):
        paths = [edge for edge in (matrix.edge(a, b), matrix.edge(b, a)) if edge is not None]
        return min(((p['seconds'], p['meters']) for p in paths), default=(inf, inf))

    def objective(group):
        return tuple(sum(pair(a, b)[index] for pos, a in enumerate(group) for b in group[pos + 1:])
                     for index in (0, 1))

    for _ in range(max(capacities) - 1):
        for index, group in enumerate(groups):
            if len(group) >= capacities[index]:
                continue
            choices = [sid for sid in sorted(remaining) if targets[category(sid)]]
            if not choices:
                continue
            for member in group:
                matrix.incoming(member, choices)
            candidate = min(choices, key=lambda sid: (*objective(group + [sid]), sid))
            if not all(pair(candidate, member)[0] < inf for member in group):
                raise matrix.unavailable('候选站点间没有可用驾车路径，请核对站点坐标或手动排班。')
            group.append(candidate)
            remaining.remove(candidate)
            targets[category(candidate)] -= 1

    # One bounded refinement pass can replace an isolated seed within the same
    # coverage bucket. No extra map calls occur inside the O(n*k) comparisons.
    selected = [sid for group in groups if len(group) > 1 for sid in group]
    for sid in selected:
        matrix.incoming(sid, sorted(by_id))
    for group in groups:
        if len(group) < 2:
            continue
        before = objective(group)
        best = None
        for old in group:
            for new in sorted(remaining):
                if category(old) != category(new) or old in required:
                    continue
                replacement = [new if sid == old else sid for sid in group]
                score = objective(replacement)
                if score < before:
                    before, best = score, (old, new)
        if best:
            old, new = best
            group[group.index(old)] = new
            remaining.remove(new)
            remaining.add(old)

    selected = [sid for group in groups for sid in group]
    for group in groups:
        if len(group) > 1:
            for sid in group:
                matrix.incoming(sid, selected)
    # Exchanges between groups preserve every coverage/priority count and each
    # team's capacity, but can avoid putting stations across a river together.
    for _ in range(2):
        changed = False
        for left in range(len(groups)):
            for right in range(left + 1, len(groups)):
                a, b = groups[left], groups[right]
                old_a, old_b = objective(a), objective(b)
                best = tuple(x + y for x, y in zip(old_a, old_b))
                exchange = None
                for x in a:
                    for y in b:
                        aa = [y if sid == x else sid for sid in a]
                        bb = [x if sid == y else sid for sid in b]
                        score = tuple(v + w for v, w in zip(objective(aa), objective(bb)))
                        if score < best:
                            best, exchange = score, (x, y)
                if exchange:
                    x, y = exchange
                    a[a.index(x)] = y
                    b[b.index(y)] = x
                    changed = True
        if not changed:
            break

    result = []
    for group in groups:
        # Ensure both directions for every final leg are measured. One-way roads
        # can make a->b and b->a different, so the display also preserves order.
        for sid in group:
            matrix.incoming(sid, group)
        ordered = shortest_order(group, matrix)
        legs = []
        for origin, destination in zip(ordered, ordered[1:]):
            edge = matrix.edge(origin, destination)
            if edge is None:
                raise matrix.unavailable('所选站点间没有连续可用的驾车路线，请核对坐标或手动排班。')
            legs.append(dict(origin_id=origin, destination_id=destination, **edge))
        result.append(dict(station_ids=ordered, seconds=sum(e['seconds'] for e in legs),
                           meters=sum(e['meters'] for e in legs), legs=legs))
    return result


def shortest_order(group, matrix):
    """Exact open Hamiltonian path for at most ten stations; no office detour."""
    if len(group) < 2:
        return list(group)
    ids = sorted(group)
    states = {(1 << i, i): (0, 0, (sid,)) for i, sid in enumerate(ids)}
    for mask in range(1, 1 << len(ids)):
        for last in range(len(ids)):
            current = states.get((mask, last))
            if current is None:
                continue
            for nxt, sid in enumerate(ids):
                if mask & (1 << nxt):
                    continue
                edge = matrix.edge(ids[last], sid)
                if edge is None:
                    continue
                score = (current[0] + edge['seconds'], current[1] + edge['meters'], current[2] + (sid,))
                key = (mask | (1 << nxt), nxt)
                if key not in states or score < states[key]:
                    states[key] = score
    choices = [value for (mask, _), value in states.items() if mask == (1 << len(ids)) - 1]
    if not choices:
        raise matrix.unavailable('所选站点之间无连续驾车路线，请核对坐标或手动排班。')
    return list(min(choices)[2])
