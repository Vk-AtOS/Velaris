"""VHOE_ANALYTICS: how the work actually went, from completed-work records.

analyse(records) takes records of {"id", "worker", "started", "finished",
"due" (optional)} with times as epoch seconds and reports: how many were
completed, cycle time (finished - started) mean / median / 90th percentile in
hours, how many finished after their due time, and the same per worker.
Records with missing or impossible times are skipped and counted, never guessed.
"""
import statistics
from typing import Any, Dict, List

from velaris.agentkit.aicore_b_common import health, invalid, number

NAME = "VHOE_ANALYTICS"


def _cycle_stats(hours: List[float]) -> Dict[str, Any]:
    p90 = statistics.quantiles(hours, n=10, method="inclusive")[-1] if len(hours) > 1 else hours[0]
    return {"mean_hours": round(statistics.fmean(hours), 2), "median_hours": round(statistics.median(hours), 2),
            "p90_hours": round(p90, 2)}


class VHOE_ANALYTICSAgent:
    def health_check(self):
        return health(NAME)

    def analyse(self, records: Any) -> Dict[str, Any]:
        if not isinstance(records, list):
            return invalid("records must be a list")
        good, skipped = [], 0
        for r in records:
            start = number(r.get("started")) if isinstance(r, dict) else None
            end = number(r.get("finished")) if isinstance(r, dict) else None
            if start is None or end is None or end < start:
                skipped += 1
                continue
            due = number(r.get("due"))
            good.append({"worker": str(r.get("worker", "unknown")), "hours": (end - start) / 3600.0,
                         "late": None if due is None else end > due})
        if not good:
            return {"status": "no_data", "reason": "no usable records", "completed": 0, "skipped": skipped}
        with_due = [g for g in good if g["late"] is not None]
        late = sum(1 for g in with_due if g["late"])
        per_worker: Dict[str, Any] = {}
        for worker in sorted({g["worker"] for g in good}):
            mine = [g for g in good if g["worker"] == worker]
            per_worker[worker] = {"completed": len(mine), **_cycle_stats([g["hours"] for g in mine]),
                                  "late": sum(1 for g in mine if g["late"])}
        return {"status": "ok", "completed": len(good), "skipped": skipped,
                "cycle_time": _cycle_stats([g["hours"] for g in good]),
                "late": late, "late_rate": round(late / len(with_due), 3) if with_due else None,
                "per_worker": per_worker}
