"""MPC_FUSION: merges records about the same thing from several sources into one, field by field.

Each source is {"source": name, "record": {...}, "trust": 0..1 (default 0.5),
"ts": when it was read (default 0)}. For every field: if all sources that have
it agree, that value is used. If they disagree the winner is the value from
the most trusted source, then the most recent, then the value most sources
hold, then the first source by name; the disagreement is listed in
"conflicts" with every candidate, so a person can overrule it. "provenance"
says which source each fused value came from.
"""
import json
from typing import Any, Dict, List

from velaris.agentkit.aicore_b_common import health, ident, invalid, number

NAME = "MPC_FUSION"


def _same(a: Any, b: Any) -> bool:
    return json.dumps(a, sort_keys=True, default=str) == json.dumps(b, sort_keys=True, default=str)


class MPC_FUSIONAgent:
    def health_check(self):
        return health(NAME)

    def fuse(self, sources: Any) -> Dict[str, Any]:
        """Returns record, provenance, conflicts and agreement (share of fields with no conflict)."""
        if not isinstance(sources, list) or not sources:
            return invalid("sources must be a non-empty list", record=None)
        clean: List[Dict[str, Any]] = []
        for s in sources:
            if not isinstance(s, dict) or ident(s.get("source")) is None or not isinstance(s.get("record"), dict):
                return invalid("each source needs 'source' (a name) and 'record' (an object)", record=None)
            trust, ts = number(s.get("trust", 0.5)), number(s.get("ts", 0))
            if trust is None or not 0 <= trust <= 1 or ts is None:
                return invalid(f"source {s['source']!r}: trust must be 0..1 and ts a number", record=None)
            clean.append({"source": s["source"].strip(), "record": s["record"], "trust": trust, "ts": ts})
        if len({s["source"] for s in clean}) != len(clean):
            return invalid("source names must be distinct", record=None)

        record: Dict[str, Any] = {}
        provenance: Dict[str, str] = {}
        conflicts: List[Dict[str, Any]] = []
        fields = sorted({f for s in clean for f in s["record"]})
        for field in fields:
            holders = [s for s in clean if s["record"].get(field) is not None]
            if not holders:
                continue

            def support(s):
                return sum(1 for o in holders if _same(o["record"][field], s["record"][field]))
            best = min(holders, key=lambda s: (-s["trust"], -s["ts"], -support(s), s["source"]))
            record[field], provenance[field] = best["record"][field], best["source"]
            if any(not _same(s["record"][field], best["record"][field]) for s in holders):
                conflicts.append({"field": field, "chosen": best["record"][field], "chosen_from": best["source"],
                                  "candidates": [{"source": s["source"], "value": s["record"][field],
                                                  "trust": s["trust"], "ts": s["ts"]} for s in holders]})
        agreement = round(1 - len(conflicts) / len(record), 3) if record else None
        return {"status": "ok", "record": record, "provenance": provenance, "conflicts": conflicts,
                "agreement": agreement, "sources": len(clean)}
