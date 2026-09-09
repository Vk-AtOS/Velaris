# ================================================================================

from dataclasses import dataclass
from typing import Dict, Any, List
import hashlib

@dataclass
class WarehouseFlowInput:
    warehouse_id: str
    inbound_units: int
    outbound_units: int
    storage_capacity: int
    picking_efficiency: float
    putaway_efficiency: float
    congestion_flags: Dict[str,bool]

class WarehouseFlowEngine:
    MAX_UNITS = 5_000_000
    MAX_CAPACITY = 10_000_000

    CONGESTION_WEIGHT = {
        "dock_congestion":150,
        "aisle_block":200,
        "storage_overflow":300,
        "equipment_shortage":120
    }

    def _h(self,s:str)->int:
        return int(hashlib.sha256(s.encode()).hexdigest()[:12],16)

    def validate(self,w:WarehouseFlowInput)->List[str]:
        e=[]
        if not w.warehouse_id or len(w.warehouse_id)>64:
            e.append("warehouse_id invalid")
        if w.inbound_units<0 or w.inbound_units>self.MAX_UNITS:
            e.append("inbound_units invalid")
        if w.outbound_units<0 or w.outbound_units>self.MAX_UNITS:
            e.append("outbound_units invalid")
        if w.storage_capacity<=0 or w.storage_capacity>self.MAX_CAPACITY:
            e.append("storage_capacity invalid")
        if not(0 < w.picking_efficiency <= 1.0):
            e.append("picking_efficiency invalid")
        if not(0 < w.putaway_efficiency <= 1.0):
            e.append("putaway_efficiency invalid")
        for k in w.congestion_flags.keys():
            if k not in self.CONGESTION_WEIGHT:
                e.append(f"unsupported congestion flag {k}")
        return e

    def assess(self,w:WarehouseFlowInput)->Dict[str,Any]:
        err=self.validate(w)
        if err:
            return {"status":"failed","errors":err}

        flow_ratio = (w.inbound_units + w.outbound_units) / w.storage_capacity
        flow_score = max(0, min(500, flow_ratio * 300))

        eff_score = (w.picking_efficiency + w.putaway_efficiency) * 100
        eff_penalty = max(0, 200 - eff_score)

        congestion_penalty = sum(self.CONGESTION_WEIGHT[k] for k,v in w.congestion_flags.items() if v)

        deterministic = (self._h(w.warehouse_id) % 250)

        raw = flow_score - eff_penalty - congestion_penalty + deterministic
        score = max(0, min(1000, raw))

        if score > 700:
            tier="optimal"
        elif score > 450:
            tier="stable"
        elif score > 250:
            tier="strained"
        else:
            tier="critical"

        return {
            "status":"ok",
            "warehouse_id":w.warehouse_id,
            "flow_score":round(score,2),
            "tier":tier,
            "details":{
                "flow_ratio":flow_ratio,
                "eff_penalty":eff_penalty,
                "congestion_penalty":congestion_penalty,
                "det_entropy":deterministic
            }
        }

# ================================================================================