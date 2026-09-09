# ================================================================================

from dataclasses import dataclass
from typing import Dict, Any, List
import hashlib

@dataclass
class GridBalanceInput:
    grid_id: str
    demand_mw: float
    supply_mw: float
    frequency_hz: float
    reserve_margin_pct: float
    outage_flags: Dict[str,bool]
    system_factors: Dict[str,float]

class GridBalanceEngine:
    MAX_MW = 1_000_000
    MAX_FREQ_DEV = 5
    MAX_MARGIN = 100

    OUTAGE_WEIGHT = {
        "gen_unit_out": 300,
        "transmission_out": 350,
        "substation_out": 250
    }

    SYS_WEIGHT = {
        "reactive_power": 4.0,
        "harmonics": 5.0,
        "thermal_stress": 6.0
    }

    def _h(self,s:str)->int:
        return int(hashlib.sha256(s.encode()).hexdigest()[:14],16)

    def validate(self,g:GridBalanceInput)->List[str]:
        e=[]
        if not g.grid_id or len(g.grid_id)>64:
            e.append("grid_id invalid")
        if g.demand_mw<0 or g.demand_mw>self.MAX_MW:
            e.append("demand_mw invalid")
        if g.supply_mw<0 or g.supply_mw>self.MAX_MW:
            e.append("supply_mw invalid")
        if not(45 <= g.frequency_hz <= 65):
            e.append("frequency_hz invalid")
        if not(0 <= g.reserve_margin_pct <= self.MAX_MARGIN):
            e.append("reserve_margin_pct invalid")
        for k in g.outage_flags.keys():
            if k not in self.OUTAGE_WEIGHT:
                e.append(f"unsupported outage flag {k}")
        for k,v in g.system_factors.items():
            if k not in self.SYS_WEIGHT:
                e.append(f"unsupported system factor {k}")
            if v<0 or v>100:
                e.append(f"system factor {k} out of range")
        return e

    def assess(self,g:GridBalanceInput)->Dict[str,Any]:
        err=self.validate(g)
        if err:
            return {"status":"failed","errors":err}

        demand_supply_gap = g.demand_mw - g.supply_mw
        gap_penalty = (abs(demand_supply_gap)/self.MAX_MW) * 400

        freq_penalty = max(0, abs(50 - g.frequency_hz) - 0.1) * 200

        margin_bonus = g.reserve_margin_pct * 3

        outage_penalty = sum(self.OUTAGE_WEIGHT[k] for k,v in g.outage_flags.items() if v)

        sys_penalty = 0
        for k,v in g.system_factors.items():
            sys_penalty += v * self.SYS_WEIGHT[k]

        deterministic = (self._h(g.grid_id) % 400)

        raw = margin_bonus - (gap_penalty + freq_penalty + outage_penalty + sys_penalty) + deterministic
        score = max(0,min(1000,raw))

        if score>700:
            tier="stable"
        elif score>450:
            tier="balanced"
        elif score>250:
            tier="risky"
        else:
            tier="critical"

        return {
            "status":"ok",
            "grid_id":g.grid_id,
            "grid_score":round(score,2),
            "tier":tier,
            "details":{
                "gap_penalty":gap_penalty,
                "freq_penalty":freq_penalty,
                "margin_bonus":margin_bonus,
                "outage_penalty":outage_penalty,
                "sys_penalty":sys_penalty,
                "det_entropy":deterministic
            }
        }

# ================================================================================