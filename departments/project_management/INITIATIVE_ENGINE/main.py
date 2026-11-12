"""INITIATIVE_ENGINE: rank proposed initiatives by RICE and keep the register.

propose(context) reads context["initiatives"], each
    {"name", "reach", "impact", "confidence" (0-1), "effort" (> 0, e.g. person-weeks)}
and scores it with the standard RICE formula:

    RICE = reach x impact x confidence / effort

The ranked list is returned (highest first, ties by name) and saved, so the
last ranking survives a restart (`register()`). The inputs are the proposer's
own estimates: the engine orders them, it does not generate initiatives or
judge whether the estimates are right. No initiatives -> `needs_data`.
State: <VELARIS_DATA>/agents/INITIATIVE_ENGINE/register.json (owner-only).
"""
import logging
import time
from typing import Any, Dict, List

from velaris.agentkit import biz_common as kit
from velaris.intel.paths import agent_dir

logger = logging.getLogger("INITIATIVE_ENGINE")
MAX_INITIATIVES = 1000


class InitiativeEngine:
    def __init__(self, name="INITIATIVE_ENGINE"):
        self.name = name
        self._state = kit.JsonState(lambda: agent_dir("INITIATIVE_ENGINE") / "register.json",
                                    {"ranked": [], "ranked_at": None})

    def health_check(self):
        return kit.health(self.name)

    def propose(self, context: dict):
        if not isinstance(context, dict):
            return kit.failed(["context must be an object with 'initiatives'"], idea=None, context=context)
        items = context.get("initiatives")
        if items is None or items == []:
            return kit.needs_data("no initiatives supplied; the engine ranks proposals, it does not invent them",
                                  idea=None, context=context)
        if not isinstance(items, (list, tuple)) or len(items) > MAX_INITIATIVES:
            return kit.failed([f"initiatives must be a list of at most {MAX_INITIATIVES}"], idea=None, context=context)
        errors: List[str] = []
        ranked, names = [], set()
        for i, it in enumerate(items):
            name = kit.text(it.get("name")) if isinstance(it, dict) else None
            reach, impact, confidence, effort = (
                kit.number(it.get(k), lo, hi) if isinstance(it, dict) else None
                for k, lo, hi in (("reach", 0, None), ("impact", 0, None), ("confidence", 0, 1), ("effort", 0, None)))
            if name is None or name in names:
                errors.append(f"initiatives[{i}].name must be a unique non-empty string")
            if None in (reach, impact, confidence, effort) or effort == 0:
                errors.append(f"initiatives[{i}] needs reach >= 0, impact >= 0, confidence 0-1 and effort > 0")
                continue
            names.add(name)
            ranked.append({"name": name, "reach": reach, "impact": impact, "confidence": confidence,
                           "effort": effort, "rice": round(reach * impact * confidence / effort, 4)})
        if errors:
            return kit.failed(errors, idea=None, context=context)
        ranked.sort(key=lambda r: (-r["rice"], r["name"]))
        for position, row in enumerate(ranked, 1):
            row["rank"] = position
        self._state.save({"ranked": ranked, "ranked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
        return {"status": "ok", "idea": ranked[0]["name"], "ranked": ranked, "context": context,
                "method": "RICE = reach x impact x confidence / effort"}

    def register(self) -> Dict[str, Any]:
        """The last saved ranking."""
        data = self._state.load()
        return {"status": "ok" if data["ranked"] else "needs_data", **data}
