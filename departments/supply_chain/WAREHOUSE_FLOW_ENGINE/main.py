"""WAREHOUSE_FLOW_ENGINE: one period of warehouse flow, worked through as arithmetic.

  put away          = inbound units x putaway efficiency      (the rest waits at the dock)
  picked            = outbound units x picking efficiency     (the rest is pick backlog),
                      limited to the stock actually available
  closing stock     = opening stock + put away - picked
  utilisation       = closing stock / storage capacity
  periods until full = free space / net units stored per period, when stock is growing

Each raised congestion flag is listed with the standard first response for it,
and the engine reports where a flag disagrees with the numbers (for example
`storage_overflow` raised while utilisation is low). Efficiencies are fractions
of the period's work that gets done. There is no composite score.
"""
import logging
import math
from dataclasses import dataclass
from typing import Any, Dict, List

from velaris.agentkit import biz_common as kit

logger = logging.getLogger("WAREHOUSE_FLOW_ENGINE")

CONGESTION_ACTIONS = {
    "dock_congestion": "Stagger inbound appointments and clear the dock backlog first.",
    "aisle_block": "Clear blocked aisles before releasing further pick waves.",
    "storage_overflow": "Stop non-urgent inbound and move slow stock to overflow space.",
    "equipment_shortage": "Reassign or hire handling equipment for the constrained shift.",
}
HIGH_UTILISATION = 0.9


@dataclass
class WarehouseFlowInput:
    warehouse_id: str
    inbound_units: int
    outbound_units: int
    storage_capacity: int
    picking_efficiency: float
    putaway_efficiency: float
    congestion_flags: Dict[str, bool]


class WarehouseFlowEngine:
    MAX_UNITS = 5_000_000
    MAX_CAPACITY = 10_000_000
    CONGESTION_WEIGHT = {k: 0 for k in CONGESTION_ACTIONS}     # recognised flags (weights no longer used)

    def health_check(self) -> Dict[str, Any]:
        return kit.health("WAREHOUSE_FLOW_ENGINE")

    def validate(self, w: WarehouseFlowInput) -> List[str]:
        e = kit.dataclass_errors(w, ["inbound_units", "outbound_units", "storage_capacity",
                                     "picking_efficiency", "putaway_efficiency"], ["congestion_flags"])
        if kit.text(getattr(w, "warehouse_id", None), 64) is None:
            e.append("warehouse_id invalid")
        if e:
            return e
        if w.inbound_units < 0 or w.inbound_units > self.MAX_UNITS:
            e.append("inbound_units invalid")
        if w.outbound_units < 0 or w.outbound_units > self.MAX_UNITS:
            e.append("outbound_units invalid")
        if w.storage_capacity <= 0 or w.storage_capacity > self.MAX_CAPACITY:
            e.append("storage_capacity invalid")
        if not 0 < w.picking_efficiency <= 1.0:
            e.append("picking_efficiency invalid")
        if not 0 < w.putaway_efficiency <= 1.0:
            e.append("putaway_efficiency invalid")
        e += [f"unsupported congestion flag {k}" for k in w.congestion_flags if k not in self.CONGESTION_WEIGHT]
        return e

    def assess(self, w: WarehouseFlowInput, opening_stock: Any = 0) -> Dict[str, Any]:
        err = self.validate(w)
        stock = kit.number(opening_stock, 0, self.MAX_CAPACITY)
        if stock is None:
            err.append("opening_stock invalid")
        if err:
            return kit.failed(err)
        put_away = math.floor(w.inbound_units * w.putaway_efficiency)
        pickable = math.floor(w.outbound_units * w.picking_efficiency)
        picked = min(pickable, math.floor(stock + put_away))
        closing = stock + put_away - picked
        utilisation = closing / w.storage_capacity
        net = put_away - picked
        raised = sorted(k for k, on in w.congestion_flags.items() if on)
        findings = []
        if closing > w.storage_capacity:
            findings.append(f"closing stock {closing:.0f} exceeds capacity {w.storage_capacity}")
        if picked < pickable:
            findings.append(f"only {picked} of {pickable} pickable units were in stock")
        if "storage_overflow" in raised and utilisation < HIGH_UTILISATION:
            findings.append(f"storage_overflow is raised but utilisation is {utilisation:.0%}: check the flag "
                            "or the capacity figure")
        if "storage_overflow" not in raised and utilisation >= HIGH_UTILISATION:
            findings.append(f"utilisation is {utilisation:.0%} with no storage_overflow flag raised")
        return {
            "status": "ok", "warehouse_id": w.warehouse_id, "put_away": put_away,
            "dock_backlog": w.inbound_units - put_away, "picked": picked,
            "pick_backlog": w.outbound_units - picked, "closing_stock": closing,
            "utilisation": round(utilisation, 4), "net_units_stored": net,
            "periods_until_full": (math.ceil((w.storage_capacity - closing) / net)
                                   if net > 0 and closing < w.storage_capacity else None),
            "congestion": [{"flag": k, "action": CONGESTION_ACTIONS[k]} for k in raised],
            "findings": findings,
            "method": "put away = inbound x putaway efficiency; picked = outbound x picking efficiency "
                      "(limited by stock); utilisation = closing stock / capacity",
        }
