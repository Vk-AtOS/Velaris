"""ROUTE_OPTIMIZATION_ENGINE: a round trip through every location, by a real heuristic.

Method: build a tour with nearest neighbour from the depot, then improve it with
2-opt (reverse a segment whenever that shortens the tour) until no reversal
helps. The result reports the distance of the first tour and of the improved one.

  leg cost = distance(a, b) x traffic factor of b (1.0 when none is given)

The depot is the first entry of `locations` unless `depot` names another. A
missing distance a->b falls back to b->a; if neither exists the request fails.
ponytail: a heuristic, not an exact solver (fine up to MAX_LOC = 30 stops), and
time windows are validated but NOT used: the distance matrix carries no travel
times. Add a time matrix and a windowed insertion step if windows must bind.
"""
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from velaris.agentkit import biz_common as kit

logger = logging.getLogger("ROUTE_OPTIMIZATION_ENGINE")


@dataclass
class RouteRequest:
    request_id: str
    locations: List[str]
    distances: Dict[str, Dict[str, float]]
    time_windows: Dict[str, List[int]]
    traffic_factors: Dict[str, float]


class RouteOptimizationEngine:
    MAX_LOC = 30
    MAX_DIST = 100000

    def health_check(self) -> Dict[str, Any]:
        return kit.health("ROUTE_OPTIMIZATION_ENGINE")

    def validate(self, r: RouteRequest) -> List[str]:
        e = kit.dataclass_errors(r, [], ["distances", "time_windows", "traffic_factors"], ["locations"])
        if kit.ident(getattr(r, "request_id", None), 64) is None:
            e.append("request_id invalid")
        if e:
            return e
        if len(r.locations) < 2 or len(r.locations) > self.MAX_LOC:
            e.append("invalid location count")
        if any(kit.ident(x) is None for x in r.locations) or len(set(r.locations)) != len(r.locations):
            e.append("locations must be distinct non-empty strings")
        for a, row in r.distances.items():
            if not isinstance(row, dict):
                e.append(f"distances[{a}] must be a mapping")
                continue
            e += [f"invalid distance {a}-{b}" for b, d in row.items() if kit.number(d, 0, self.MAX_DIST) is None]
        for k, w in r.time_windows.items():
            if not isinstance(w, (list, tuple)) or len(w) != 2 or kit.number(w[0], 0) is None \
                    or kit.number(w[1], w[0]) is None:
                e.append(f"invalid time window for {k}")
        e += [f"invalid traffic factor for {k}" for k, f in r.traffic_factors.items()
              if kit.number(f, 0, 5) is None]
        return e

    def compute_route(self, r: RouteRequest, depot: Optional[str] = None) -> Dict[str, Any]:
        err = self.validate(r)
        if not err and depot is not None and depot not in r.locations:
            err.append("depot is not one of the locations")
        if err:
            return kit.failed(err)
        locs = list(r.locations)
        start = depot or locs[0]

        def dist(a: str, b: str) -> Optional[float]:
            d = r.distances.get(a, {}).get(b)
            return d if d is not None else r.distances.get(b, {}).get(a)

        missing = [f"missing distance {a}-{b}" for i, a in enumerate(locs) for b in locs[i + 1:]
                   if dist(a, b) is None]
        if missing:
            return kit.failed(missing[:20])

        def cost(a: str, b: str) -> float:
            return dist(a, b) * r.traffic_factors.get(b, 1.0)

        def tour_cost(t: List[str]) -> float:
            return sum(cost(a, b) for a, b in zip(t, t[1:] + t[:1]))

        tour, left = [start], [x for x in locs if x != start]
        while left:                                   # nearest neighbour; ties go to the earlier location
            nxt = min(left, key=lambda x: cost(tour[-1], x))
            tour.append(nxt)
            left.remove(nxt)
        first_cost = tour_cost(tour)
        best, passes, improved = first_cost, 0, True
        while improved:                               # 2-opt; whole-tour cost so one-way distances stay correct
            improved, passes = False, passes + 1
            for i in range(1, len(tour) - 1):
                for j in range(i + 1, len(tour)):
                    candidate = tour[:i] + tour[i:j + 1][::-1] + tour[j + 1:]
                    c = tour_cost(candidate)
                    if c < best - 1e-9:
                        tour, best, improved = candidate, c, True
        closed = tour + [start]
        return {
            "status": "ok", "request_id": r.request_id, "route": closed,
            "total_distance": round(sum(dist(a, b) for a, b in zip(closed, closed[1:])), 4),
            "total_cost": round(best, 4), "nearest_neighbour_cost": round(first_cost, 4),
            "improvement_by_2opt": round(first_cost - best, 4), "two_opt_passes": passes,
            "legs": [{"from": a, "to": b, "distance": dist(a, b), "cost": round(cost(a, b), 4)}
                     for a, b in zip(closed, closed[1:])],
            "time_windows_applied": False,
            "method": "nearest neighbour from the depot, then 2-opt until no segment reversal shortens the tour",
            "optimality": "heuristic: a good tour, not proven shortest",
        }
