"""VELOCITY_LOOP: where one piece of work lost its time.

accelerate(task) takes a task with the stages it has passed through:

    {"id": "T-17", "stages": [{"name": "review", "entered": "2026-11-02T09:00",
                               "left": "2026-11-04T17:00", "active_hours": 3}, ...]}

and computes, from the timestamps:
  hours in each stage and its share of the lead time,
  the bottleneck (the stage that held the task longest),
  flow efficiency = active hours / lead time, when every stage reports active_hours.

It then proposes looking at the bottleneck first. That is a suggestion for a
person: `final` stays "ready_for_approval" and the agent changes nothing. It does
not speed anything up by itself, and it measures elapsed clock time, not working hours.
"""
import logging
from datetime import datetime
from typing import Any, List, Optional

from velaris.agentkit import biz_common as kit

logger = logging.getLogger("VELOCITY_LOOP")
MAX_STAGES = 200


def _when(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.strip()).replace(tzinfo=None)
        except ValueError:
            return None
    return None


class VelocityLoop:
    def __init__(self, name="VELOCITY_LOOP"):
        self.name = name

    def health_check(self):
        return kit.health(self.name)

    def accelerate(self, task: dict):
        if not isinstance(task, dict):
            return kit.failed(["task must be an object with 'stages'"])
        stages = task.get("stages")
        if stages is None or stages == []:
            return kit.needs_data("the task has no stage history to measure", final=None)
        if not isinstance(stages, (list, tuple)) or len(stages) > MAX_STAGES:
            return kit.failed([f"stages must be a list of at most {MAX_STAGES} stages"])
        errors: List[str] = []
        rows = []
        for i, s in enumerate(stages):
            if not isinstance(s, dict) or kit.text(s.get("name")) is None:
                errors.append(f"stages[{i}].name must be a non-empty string")
                continue
            entered, left = _when(s.get("entered")), _when(s.get("left"))
            if entered is None or left is None or left < entered:
                errors.append(f"stages[{i}] needs ISO 'entered' and 'left' times, in that order")
                continue
            hours = (left - entered).total_seconds() / 3600
            active = s.get("active_hours")
            if active is not None and kit.number(active, 0, hours) is None:
                errors.append(f"stages[{i}].active_hours must be between 0 and the stage's {hours:.2f} hours")
                continue
            rows.append({"name": s["name"].strip(), "hours": hours, "active_hours": active})
        if errors:
            return kit.failed(errors)
        lead = sum(r["hours"] for r in rows)
        if lead == 0:
            return kit.needs_data("every stage has zero duration", final=None)
        for r in rows:
            r["share"] = round(r["hours"] / lead, 4)
            r["hours"] = round(r["hours"], 2)
        slowest = max(rows, key=lambda r: r["share"])            # first of equals
        all_active = all(r["active_hours"] is not None for r in rows)
        active_total = sum(r["active_hours"] for r in rows) if all_active else None
        return {
            "status": "ok", "task_id": task.get("id"), "lead_time_hours": round(lead, 2), "stages": rows,
            "bottleneck": slowest["name"], "bottleneck_share": slowest["share"],
            "flow_efficiency": round(active_total / lead, 4) if all_active else None,
            "proposal": f"Look at '{slowest['name']}' first: it held the task for {slowest['share']:.0%} "
                        "of its lead time.",
            "final": "ready_for_approval",
            "method": "elapsed clock hours per stage from the supplied timestamps",
        }
