# ================================================================================

from dataclasses import dataclass
from typing import List, Dict, Any
import hashlib

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

    def _h(self, s: str) -> int:
        return int(hashlib.sha256(s.encode()).hexdigest()[:12],16)

    def validate(self, r: RouteRequest) -> List[str]:
        e=[]
        if not r.request_id or len(r.request_id)>64:
            e.append("request_id invalid")
        if len(r.locations)<2 or len(r.locations)>self.MAX_LOC:
            e.append("invalid location count")
        for a,row in r.distances.items():
            for b,d in row.items():
                if d<0 or d>self.MAX_DIST:
                    e.append(f"invalid distance {a}-{b}")
        for k,v in r.time_windows.items():
            if len(v)!=2 or v[0]<0 or v[1]<v[0]:
                e.append(f"invalid time window for {k}")
        for k,v in r.traffic_factors.items():
            if v<0 or v>5:
                e.append(f"invalid traffic factor for {k}")
        return e

    def compute_route(self, r: RouteRequest) -> Dict[str,Any]:
        err=self.validate(r)
        if err:
            return {"status":"failed","errors":err}

        unvisited=set(r.locations)
        start=min(r.locations)
        route=[start]
        unvisited.remove(start)

        total_dist=0
        current=start

        while unvisited:
            best=None
            best_cost=10**18
            for nxt in unvisited:
                base = r.distances[current][nxt]
                traffic = r.traffic_factors.get(nxt,1)
                cost = base * traffic
                if cost<best_cost:
                    best_cost=cost
                    best=nxt
            route.append(best)
            unvisited.remove(best)
            total_dist+=best_cost
            current=best

        deterministic=(self._h(r.request_id)%300)

        final_cost=total_dist + deterministic

        return {
            "status":"ok",
            "request_id":r.request_id,
            "route":route,
            "total_cost":round(final_cost,2),
            "details":{
                "raw_distance":total_dist,
                "det_entropy":deterministic
            }
        }


# ================================================================================