"""QUALITY_CONTROL_ENGINE: a batch checked against a u-chart and explicit disposition rules.

Control chart (defects per unit, the right chart for defect counts on samples of varying size):
  u      = total defects in the batch / sample size
  u-bar  = total defects / total units over the history batches (the baseline)
  limits = u-bar +/- 3 x sqrt(u-bar / n) for this batch's n; the lower limit is floored at 0
  rule 1   the point is beyond a 3-sigma limit
  rule 2   8 points in a row (this batch and the 7 before it) on one side of u-bar
The chart needs at least MIN_HISTORY earlier batches; fewer -> chart is `needs_data`.
With fewer than 20 the limits are flagged provisional.

Disposition, first rule that applies (the result names it):
  D1 hold         any critical defect
  D2 hold         a regulatory flag is raised (safety, traceability or documentation)
  D3 investigate  the chart signals above the centre line (rule 1 high, or rule 2 high)
  D4 accept       none of the above
inspection_rigour and process_stability have no defined unit and are not used.
"""
import logging
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from velaris.agentkit import biz_common as kit

logger = logging.getLogger("QUALITY_CONTROL_ENGINE")
MIN_HISTORY = 8
SETTLED_HISTORY = 20
RUN_LENGTH = 8
DISPOSITION_RULES = {
    "D1": "hold: a critical defect was found",
    "D2": "hold: a regulatory flag is raised",
    "D3": "investigate: the control chart signals a rise in defects per unit",
    "D4": "accept: no rule applies",
}


@dataclass
class QCInput:
    batch_id: str
    sample_size: int
    defects_found: Dict[str, int]
    inspection_rigour: float
    process_stability: float
    regulatory_flags: Dict[str, bool]


class QualityControlEngine:
    MAX_SAMPLE = 100000
    MAX_DEFECT = 100000
    DEFECT_WEIGHT = {"cosmetic": 0, "minor": 0, "major": 0, "critical": 0}                        # recognised classes
    REG_WEIGHT = {"documentation_issue": 0, "traceability_gap": 0, "safety_nonconformance": 0}   # recognised flags

    def health_check(self) -> Dict[str, Any]:
        return kit.health("QUALITY_CONTROL_ENGINE")

    def validate(self, q: QCInput) -> List[str]:
        e = kit.dataclass_errors(q, ["sample_size", "inspection_rigour", "process_stability"],
                                 ["defects_found", "regulatory_flags"])
        if kit.ident(getattr(q, "batch_id", None), 64) is None:
            e.append("batch_id invalid")
        if e:
            return e
        if q.sample_size <= 0 or q.sample_size > self.MAX_SAMPLE:
            e.append("sample_size invalid")
        for k, count in q.defects_found.items():
            if k not in self.DEFECT_WEIGHT:
                e.append(f"unsupported defect {k}")
            elif kit.number(count, 0, self.MAX_DEFECT) is None:
                e.append(f"invalid defect count {k}")
        if not 0 < q.inspection_rigour <= 1.0:
            e.append("inspection_rigour invalid")
        if not 0 < q.process_stability <= 1.0:
            e.append("process_stability invalid")
        e += [f"unsupported regulatory flag {k}" for k in q.regulatory_flags if k not in self.REG_WEIGHT]
        return e

    def _chart(self, u: float, n: float, history: List[Dict[str, float]]) -> Dict[str, Any]:
        if len(history) < MIN_HISTORY:
            return {"status": "needs_data",
                    "reason": f"{len(history)} earlier batch(es) supplied; the chart needs at least {MIN_HISTORY}"}
        centre = sum(h["defects"] for h in history) / sum(h["sample_size"] for h in history)
        spread = 3 * math.sqrt(centre / n)
        ucl, lcl = centre + spread, max(0.0, centre - spread)
        recent = [h["defects"] / h["sample_size"] for h in history[-(RUN_LENGTH - 1):]] + [u]
        signals = []
        if u > ucl:
            signals.append({"rule": 1, "side": "high", "detail": f"u {u:.4f} above the upper limit {ucl:.4f}"})
        elif u < lcl:
            signals.append({"rule": 1, "side": "low", "detail": f"u {u:.4f} below the lower limit {lcl:.4f}"})
        for side, test in (("high", lambda x: x > centre), ("low", lambda x: x < centre)):
            if len(recent) == RUN_LENGTH and all(test(x) for x in recent):
                signals.append({"rule": 2, "side": side,
                                "detail": f"{RUN_LENGTH} points in a row on the {side} side of {centre:.4f}"})
        return {"status": "ok", "centre_line": round(centre, 6), "ucl": round(ucl, 6), "lcl": round(lcl, 6),
                "in_control": not signals, "signals": signals, "history_batches": len(history),
                "limits_provisional": len(history) < SETTLED_HISTORY}

    def assess(self, q: QCInput, history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        err = self.validate(q)
        rows: List[Dict[str, float]] = []
        if history is not None and not isinstance(history, (list, tuple)):
            err.append("history must be a list of {'sample_size', 'defects'}")
        for i, h in enumerate(history if isinstance(history, (list, tuple)) else []):
            n = kit.number(h.get("sample_size"), 1, self.MAX_SAMPLE) if isinstance(h, dict) else None
            d = kit.number(h.get("defects"), 0) if isinstance(h, dict) else None
            if n is None or d is None:
                err.append(f"history[{i}] needs a positive sample_size and non-negative defects")
            else:
                rows.append({"sample_size": n, "defects": d})
        if err:
            return kit.failed(err)
        total = sum(q.defects_found.values())
        u = total / q.sample_size
        chart = self._chart(u, q.sample_size, rows)
        raised = sorted(k for k, on in q.regulatory_flags.items() if on)
        rising = chart["status"] == "ok" and any(s["side"] == "high" for s in chart["signals"])
        if q.defects_found.get("critical", 0) > 0:
            rule, why = "D1", f"{q.defects_found['critical']} critical defect(s)"
        elif raised:
            rule, why = "D2", f"flag(s): {', '.join(raised)}"
        elif rising:
            rule, why = "D3", "; ".join(s["detail"] for s in chart["signals"] if s["side"] == "high")
        else:
            rule, why = "D4", "no rule applies"
        return {
            "status": "ok", "batch_id": q.batch_id, "sample_size": q.sample_size, "defects_total": total,
            "defects_per_unit": round(u, 6), "defects_by_class": dict(q.defects_found),
            "control_chart": chart, "disposition": DISPOSITION_RULES[rule].split(":")[0],
            "deciding_rule": rule, "deciding_reason": why, "rules": DISPOSITION_RULES,
            "inputs_not_used": ["inspection_rigour", "process_stability"],
            "method": "u-chart with 3-sigma limits from the history baseline; run rule of 8",
        }
