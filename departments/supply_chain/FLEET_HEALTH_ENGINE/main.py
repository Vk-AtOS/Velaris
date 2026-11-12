"""FLEET_HEALTH_ENGINE: a vehicle's condition from its usage, wear and service records.

Explicit rules, each reported with the reading that triggered it:
  * an active fault code maps to an action in FAULT_ACTIONS; a brake or engine fault takes
    the vehicle out of service;
  * a wear reading at or past its limit in WEAR_LIMITS asks for replacement, within 10
    points of it asks for inspection (battery_health is the other way round: low is bad);
  * service is due when distance since the last service reaches the interval. The interval
    is the manufacturer's and must be supplied; without it the service check is `needs_data`.

condition: out_of_service > attention > serviceable. The limits are this engine's
defaults (percent worn), not a manufacturer's schedule; pass `wear_limits` to override.
There is no composite health score.
"""
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from velaris.agentkit import biz_common as kit

logger = logging.getLogger("FLEET_HEALTH_ENGINE")

FAULT_ACTIONS = {   # fault -> (grounds the vehicle?, action)
    "brake_fault": (True, "Do not operate; repair brakes before any further use."),
    "engine_fault": (True, "Do not operate; diagnose the engine fault."),
    "transmission_fault": (False, "Book a transmission diagnosis; avoid heavy loads until done."),
    "cooling_fault": (False, "Check coolant level and fan before the next long run."),
    "sensor_fault": (False, "Read and clear the sensor code at the next service."),
}
WEAR_LIMITS = {"tire_wear": 80, "brake_wear": 80, "engine_degradation": 70}   # % worn: replace at or above
BATTERY_MIN = 40        # % health: replace at or below
INSPECT_MARGIN = 10


@dataclass
class VehicleStatus:
    vehicle_id: str
    mileage: float                # km on the odometer
    engine_hours: float
    fault_codes: Dict[str, bool]
    wear_metrics: Dict[str, float]
    usage_pattern: str


class FleetHealthEngine:
    SUPPORTED_USAGE = {"city", "highway", "mixed"}
    MAX_MILEAGE = 2_000_000
    MAX_HOURS = 50_000
    FAULT_WEIGHT = {k: 0 for k in FAULT_ACTIONS}          # recognised fault codes (weights no longer used)
    WEAR_THRESHOLDS = {"tire_wear": (0, 100), "brake_wear": (0, 100),
                       "engine_degradation": (0, 100), "battery_health": (0, 100)}

    def health_check(self) -> Dict[str, Any]:
        return kit.health("FLEET_HEALTH_ENGINE")

    def validate(self, v: VehicleStatus) -> List[str]:
        e = kit.dataclass_errors(v, ["mileage", "engine_hours"], ["fault_codes", "wear_metrics"],
                                 texts=["usage_pattern"])
        if kit.ident(getattr(v, "vehicle_id", None), 64) is None:
            e.append("vehicle_id invalid")
        if e:
            return e
        if v.mileage < 0 or v.mileage > self.MAX_MILEAGE:
            e.append("mileage invalid")
        if v.engine_hours < 0 or v.engine_hours > self.MAX_HOURS:
            e.append("engine_hours invalid")
        if v.usage_pattern not in self.SUPPORTED_USAGE:
            e.append("unsupported usage_pattern")
        e += [f"unsupported fault code {k}" for k in v.fault_codes if k not in self.FAULT_WEIGHT]
        for k, reading in v.wear_metrics.items():
            if k not in self.WEAR_THRESHOLDS:
                e.append(f"unsupported wear metric {k}")
            elif kit.number(reading, *self.WEAR_THRESHOLDS[k]) is None:
                e.append(f"wear metric {k} out of range")
        return e

    def assess(self, v: VehicleStatus, last_service_km: Any = None, service_interval_km: Any = None,
               wear_limits: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        err = self.validate(v)
        limits = dict(WEAR_LIMITS)
        if wear_limits is not None:
            if not isinstance(wear_limits, dict) or any(
                    k not in WEAR_LIMITS or kit.number(x, 1, 100) is None for k, x in wear_limits.items()):
                err.append(f"wear_limits must map {sorted(WEAR_LIMITS)} to a percentage from 1 to 100")
            else:
                limits.update(wear_limits)
        last = None if last_service_km is None else kit.number(last_service_km, 0)
        interval = None if service_interval_km is None else kit.number(service_interval_km, 1)
        if (last_service_km is not None and last is None) or (service_interval_km is not None and interval is None):
            err.append("last_service_km must be >= 0 and service_interval_km >= 1")
        elif not err and last is not None and last > v.mileage:
            err.append("last_service_km is beyond the odometer reading")
        if err:
            return kit.failed(err)

        actions, grounded, attention = [], False, False
        for fault in sorted(k for k, on in v.fault_codes.items() if on):
            stops, action = FAULT_ACTIONS[fault]
            grounded, attention = grounded or stops, True
            actions.append({"rule": f"fault:{fault}", "reading": "active", "action": action})
        for metric, reading in sorted(v.wear_metrics.items()):
            if metric == "battery_health":
                replace, inspect = reading <= BATTERY_MIN, reading <= BATTERY_MIN + INSPECT_MARGIN
                limit = f"<= {BATTERY_MIN}%"
            else:
                replace, inspect = reading >= limits[metric], reading >= limits[metric] - INSPECT_MARGIN
                limit = f">= {limits[metric]}%"
            if replace or inspect:
                attention = True
                part = metric.replace("_wear", "").replace("_health", "").replace("_degradation", "")
                actions.append({"rule": f"wear:{metric}", "reading": f"{reading}% (replace at {limit})",
                                "action": f"{'Replace or overhaul' if replace else 'Inspect'} {part}."})
        if last is None or interval is None:
            service = {"status": "needs_data",
                       "reason": "supply last_service_km and the manufacturer's service_interval_km"}
        else:
            since = v.mileage - last
            service = {"status": "ok", "km_since_service": round(since, 1), "interval_km": interval,
                       "km_until_due": round(interval - since, 1), "due": since >= interval}
            if since >= interval:
                attention = True
                actions.append({"rule": "service:interval", "reading": f"{since:.0f} km since service",
                                "action": f"Service overdue by {since - interval:.0f} km."})
        return {
            "status": "ok", "vehicle_id": v.vehicle_id,
            "condition": "out_of_service" if grounded else "attention" if attention else "serviceable",
            "actions": actions, "service": service,
            "km_per_engine_hour": round(v.mileage / v.engine_hours, 2) if v.engine_hours else None,
            "limits_used": {**limits, "battery_health_min": BATTERY_MIN, "inspect_margin": INSPECT_MARGIN},
            "inputs_not_used": ["usage_pattern"],
        }
