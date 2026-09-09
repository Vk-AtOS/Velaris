# ================================================================================

from dataclasses import dataclass
from typing import Dict, Any, List
import hashlib

@dataclass
class VehicleStatus:
    vehicle_id: str
    mileage: float
    engine_hours: float
    fault_codes: Dict[str,bool]
    wear_metrics: Dict[str,float]
    usage_pattern: str

class FleetHealthEngine:
    SUPPORTED_USAGE = {"city","highway","mixed"}
    MAX_MILEAGE = 2_000_000
    MAX_HOURS = 50_000

    FAULT_WEIGHT = {
        "engine_fault":200,
        "transmission_fault":180,
        "brake_fault":150,
        "sensor_fault":80,
        "cooling_fault":120
    }

    WEAR_THRESHOLDS = {
        "tire_wear": (0,100),
        "brake_wear": (0,100),
        "engine_degradation": (0,100),
        "battery_health": (0,100)
    }

    USAGE_FACTOR = {
        "city":1.2,
        "highway":0.9,
        "mixed":1.0
    }

    def _h(self,s:str)->int:
        return int(hashlib.sha256(s.encode()).hexdigest()[:12],16)

    def validate(self,v:VehicleStatus)->List[str]:
        e=[]
        if not v.vehicle_id or len(v.vehicle_id)>64:
            e.append("vehicle_id invalid")
        if v.mileage<0 or v.mileage>self.MAX_MILEAGE:
            e.append("mileage invalid")
        if v.engine_hours<0 or v.engine_hours>self.MAX_HOURS:
            e.append("engine_hours invalid")
        if v.usage_pattern not in self.SUPPORTED_USAGE:
            e.append("unsupported usage_pattern")
        for k in v.fault_codes.keys():
            if k not in self.FAULT_WEIGHT:
                e.append(f"unsupported fault code {k}")
        for k,vv in v.wear_metrics.items():
            if k not in self.WEAR_THRESHOLDS:
                e.append(f"unsupported wear metric {k}")
            lo,hi=self.WEAR_THRESHOLDS[k]
            if vv<lo or vv>hi:
                e.append(f"wear metric {k} out of range")
        return e

    def assess(self,v:VehicleStatus)->Dict[str,Any]:
        err=self.validate(v)
        if err:
            return {"status":"failed","errors":err}

        mileage_factor = (v.mileage / self.MAX_MILEAGE) * 300
        hour_factor = (v.engine_hours / self.MAX_HOURS) * 200

        fault_penalty = sum(self.FAULT_WEIGHT[k] for k,val in v.fault_codes.items() if val)

        wear_penalty = 0
        for k,val in v.wear_metrics.items():
            lo,hi=self.WEAR_THRESHOLDS[k]
            pct = (val - lo) / (hi - lo)
            wear_penalty += pct * 150

        usage_factor = self.USAGE_FACTOR[v.usage_pattern]

        deterministic = (self._h(v.vehicle_id) % 250)

        raw = (mileage_factor + hour_factor + fault_penalty + wear_penalty) * usage_factor + deterministic
        score = max(0, min(1000, raw))

        if score < 250:
            tier="excellent"
        elif score < 450:
            tier="good"
        elif score < 700:
            tier="warning"
        else:
            tier="critical"

        return {
            "status":"ok",
            "vehicle_id":v.vehicle_id,
            "health_score":round(score,2),
            "tier":tier,
            "details":{
                "mileage_factor":mileage_factor,
                "hour_factor":hour_factor,
                "fault_penalty":fault_penalty,
                "wear_penalty":wear_penalty,
                "usage_factor":usage_factor,
                "det_entropy":deterministic
            }
        }

# ================================================================================