# ================================================================================

from dataclasses import dataclass
from typing import Dict, Any, List
import hashlib

@dataclass
class MachineLifecycleInput:
    machine_id: str
    install_year: int
    operating_hours: float
    maintenance_events: Dict[str,int]
    component_age: Dict[str,float]
    load_factor: float

class MachineLifecycleEngine:
    CURRENT_YEAR = 2025
    MAX_HOURS = 200000
    MAX_COMPONENT_AGE = 100
    MAX_LOAD = 5.0

    MAINT_WEIGHT = {
        "preventive": -20,
        "corrective": 50,
        "overhaul": 80,
        "minor_repair": 10
    }

    COMPONENT_WEIGHT = {
        "bearing": 2.0,
        "motor": 3.0,
        "gearbox": 2.5,
        "controls": 1.5
    }

    def _h(self,s:str)->int:
        return int(hashlib.sha256(s.encode()).hexdigest()[:12],16)

    def validate(self,m:MachineLifecycleInput)->List[str]:
        e=[]
        if not m.machine_id or len(m.machine_id)>64:
            e.append("machine_id invalid")
        if m.install_year<1900 or m.install_year>self.CURRENT_YEAR:
            e.append("install_year invalid")
        if m.operating_hours<0 or m.operating_hours>self.MAX_HOURS:
            e.append("operating_hours invalid")
        if m.load_factor<=0 or m.load_factor>self.MAX_LOAD:
            e.append("load_factor invalid")
        for k in m.maintenance_events.keys():
            if k not in self.MAINT_WEIGHT:
                e.append(f"unsupported maintenance event {k}")
        for k,v in m.component_age.items():
            if k not in self.COMPONENT_WEIGHT:
                e.append(f"unsupported component {k}")
            if v<0 or v>self.MAX_COMPONENT_AGE:
                e.append(f"component age {k} invalid")
        return e

    def assess(self,m:MachineLifecycleInput)->Dict[str,Any]:
        err=self.validate(m)
        if err:
            return {"status":"failed","errors":err}

        age_years = self.CURRENT_YEAR - m.install_year
        age_factor = age_years * 10

        hour_factor = (m.operating_hours / self.MAX_HOURS) * 300

        maint_penalty = sum(self.MAINT_WEIGHT[k] * v for k,v in m.maintenance_events.items())

        comp_penalty = 0
        for k,v in m.component_age.items():
            pct = v / self.MAX_COMPONENT_AGE
            comp_penalty += pct * (self.COMPONENT_WEIGHT[k] * 100)

        load_penalty = (m.load_factor - 1) * 100

        deterministic = (self._h(m.machine_id) % 250)

        raw = age_factor + hour_factor + maint_penalty + comp_penalty + load_penalty + deterministic
        score = max(0,min(1000,raw))

        if score < 250:
            tier="healthy"
        elif score < 500:
            tier="aging"
        elif score < 750:
            tier="risky"
        else:
            tier="end_of_life"

        return {
            "status":"ok",
            "machine_id":m.machine_id,
            "lifecycle_score":round(score,2),
            "tier":tier,
            "details":{
                "age_factor":age_factor,
                "hour_factor":hour_factor,
                "maint_penalty":maint_penalty,
                "comp_penalty":comp_penalty,
                "load_penalty":load_penalty,
                "det_entropy":deterministic
            }
        }

# ================================================================================