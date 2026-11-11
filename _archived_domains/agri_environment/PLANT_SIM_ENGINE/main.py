# ================================================================================

from dataclasses import dataclass
from typing import Dict, Any, List
import hashlib

@dataclass
class PlantInput:
    plant_id: str
    production_lines: int
    uptime_hours: float
    downtime_hours: float
    defect_rate: float
    throughput_units: int
    resource_constraints: Dict[str,int]

class PlantSimEngine:
    MAX_LINES = 200
    MAX_HOURS = 100000
    MAX_DEFECT = 100
    MAX_THROUGHPUT = 10000000

    RESOURCE_WEIGHT = {
        "labor_shortage":180,
        "material_delay":220,
        "machine_unavailability":260,
        "utility_fluctuation":140
    }

    def _h(self,s:str)->int:
        return int(hashlib.sha256(s.encode()).hexdigest()[:14],16)

    def validate(self,p:PlantInput)->List[str]:
        e=[]
        if not p.plant_id or len(p.plant_id)>64:
            e.append("plant_id invalid")
        if p.production_lines<=0 or p.production_lines>self.MAX_LINES:
            e.append("production_lines invalid")
        if p.uptime_hours<0 or p.uptime_hours>self.MAX_HOURS:
            e.append("uptime_hours invalid")
        if p.downtime_hours<0 or p.downtime_hours>self.MAX_HOURS:
            e.append("downtime_hours invalid")
        if not(0 <= p.defect_rate <= self.MAX_DEFECT):
            e.append("defect_rate invalid")
        if p.throughput_units<0 or p.throughput_units>self.MAX_THROUGHPUT:
            e.append("throughput_units invalid")
        for k in p.resource_constraints.keys():
            if k not in self.RESOURCE_WEIGHT:
                e.append(f"unsupported resource constraint {k}")
        return e

    def simulate(self,p:PlantInput)->Dict[str,Any]:
        err=self.validate(p)
        if err:
            return {"status":"failed","errors":err}

        uptime_eff = (p.uptime_hours / (p.uptime_hours + p.downtime_hours)) * 500 if (p.uptime_hours + p.downtime_hours)>0 else 0
        defect_penalty = p.defect_rate * 3
        throughput_score = min(300, p.throughput_units / 10000)

        resource_penalty = sum(self.RESOURCE_WEIGHT[k] for k,v in p.resource_constraints.items() if v)

        deterministic = (self._h(p.plant_id) % 250)

        raw = uptime_eff + throughput_score - defect_penalty - resource_penalty + deterministic
        score = max(0,min(1000,raw))

        if score>700:
            tier="high_performance"
        elif score>450:
            tier="efficient"
        elif score>250:
            tier="strained"
        else:
            tier="critical"

        return {
            "status":"ok",
            "plant_id":p.plant_id,
            "performance_score":round(score,2),
            "tier":tier,
            "details":{
                "uptime_eff":uptime_eff,
                "defect_penalty":defect_penalty,
                "throughput_score":throughput_score,
                "resource_penalty":resource_penalty,
                "det_entropy":deterministic
            }
        }

# ================================================================================