"""VELOCITY_LOOP: where one piece of work lost its time.

accelerate(task) takes a task with the stages it has passed through:

    {"id": "T-17", "stages": [{"name": "review", "entered": "2026-11-02T09:00",
                               "left": "2026-11-04T17:00", "active_hours": 3}, ...]}

and computes, from the timestamps:
  hours in each stage and its share of the lead time (lead time = hours covered by at least one stage: a gap between
  stages is not counted and time where stages overlap is counted once, reported as overlap_hours),
  the bottleneck (the stage that held the task longest),
  flow efficiency = active hours / lead time, when every stage reports active_hours.

Times with an offset ("+05:30", "Z") are converted to UTC before they are compared, so stages recorded in different
zones line up; a time with no offset is taken as UTC. It then proposes looking at the bottleneck first. That is a suggestion for a
person: `final` stays "ready_for_approval" and the agent changes nothing. It does
not speed anything up by itself, and it measures elapsed clock time, not working hours.
"""
import logging
from datetime import datetime, timezone
from typing import Any, List, Optional, Tuple

from velaris.agentkit import biz_common as kit

logger = logging.getLogger("VELOCITY_LOOP")
MAX_STAGES = 200


def _utc(value: datetime) -> datetime:
    """An aware time converted to UTC, a naive one taken as UTC; always returned naive so they compare."""
    return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo is not None else value


def _when(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return _utc(value)
    if isinstance(value, str):
        try:
            return _utc(datetime.fromisoformat(value.strip().replace("Z", "+00:00")))
        except ValueError:
            return None
    return None


def _union_hours(spans: List[Tuple[datetime, datetime]]) -> float:
    """Hours covered by at least one span (overlaps counted once, gaps not at all)."""
    total, end = 0.0, None
    for a, b in sorted(spans):
        if end is None or a > end:
            total += (b - a).total_seconds()
            end = b
        elif b > end:
            total += (b - end).total_seconds()
            end = b
    return total / 3600


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
            if not isinstance(s, dict) or kit.ident(s.get("name")) is None:
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
            rows.append({"name": s["name"].strip(), "hours": hours, "active_hours": active, "span": (entered, left)})
        if errors:
            return kit.failed(errors)
        lead = _union_hours([r["span"] for r in rows])
        overlap = sum(r["hours"] for r in rows) - lead
        if lead == 0:
            return kit.needs_data("every stage has zero duration", final=None)
        for r in rows:
            r["share"] = round(r["hours"] / lead, 4)
            r["hours"] = round(r["hours"], 2)
            del r["span"]
        slowest = max(rows, key=lambda r: r["share"])            # first of equals
        all_active = all(r["active_hours"] is not None for r in rows)
        active_total = sum(r["active_hours"] for r in rows) if all_active else None
        return {
            "status": "ok", "task_id": task.get("id"), "lead_time_hours": round(lead, 2),
            "overlap_hours": round(max(overlap, 0.0), 2), "stages": rows,
            "bottleneck": slowest["name"], "bottleneck_share": slowest["share"],
            "flow_efficiency": round(active_total / lead, 4) if all_active else None,
            "proposal": f"Look at '{slowest['name']}' first: it held the task for {slowest['share']:.0%} "
                        "of its lead time.",
            "final": "ready_for_approval",
            "method": "elapsed clock hours per stage from the supplied timestamps",
        }
