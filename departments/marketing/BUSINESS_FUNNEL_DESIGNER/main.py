# ================================================================================

"""Business funnel designer: multi-stage conversion funnels with drop-off analysis.
BusinessFunnelDesigner.create_funnel(name, stages) adds a funnel with zeroed visits and conversions
per stage and returns it. record_stage(funnel_name, stage, visits, conversions) adds to a stage's
counters and returns True, or False for an unknown funnel or stage. analyze(funnel_name) returns
{stage: {"conversion_rate", "drop_off"}} where the rate is conversions/visits in percent and drop_off
is the percent fall in conversions from the previous stage; {} for an unknown funnel. It does not
suggest optimizations; it only computes these figures.
State: in-memory list only, nothing persisted. Failure: no input validation; duplicate funnel names
are allowed and the first match wins.
"""
from typing import Dict, Any, List

from velaris.agentkit.checks import is_name

MAX_COUNT = 10 ** 12


def _count(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= MAX_COUNT


class BusinessFunnelDesigner:
    """
    Velaris Business Funnel Designer
    - Generates multi-stage funnels
    - Computes drop-off percentages
    - Suggests optimizations at each step (suggest_optimizations)
    """

    def __init__(self):
        self.funnels: List[Dict[str, Any]] = []

    def create_funnel(self, name: str, stages: List[str]) -> Dict[str, Any]:
        if not is_name(name) or not isinstance(stages, list) or not stages or len(set(stages)) != len(stages) \
                or not all(is_name(s) for s in stages):
            raise ValueError("a funnel needs a name and a list of distinct stage names")
        funnel = {
            "name": name,
            "stages": stages,
            "metrics": {stage: {"visits": 0, "conversions": 0} for stage in stages}
        }
        self.funnels.append(funnel)
        return funnel

    def record_stage(self, funnel_name: str, stage: str, visits: int, conversions: int) -> bool:
        """False for an unknown funnel/stage, a negative or non-integer count, or more conversions than visits
        (neither this call nor the running total may break that)."""
        f = self._find(funnel_name)
        if not f or stage not in f["stages"] or not _count(visits) or not _count(conversions):
            return False
        m = f["metrics"][stage]
        if m["conversions"] + conversions > m["visits"] + visits:
            return False
        m["visits"] += visits
        m["conversions"] += conversions
        return True

    def analyze(self, funnel_name: str) -> Dict[str, Any]:
        f = self._find(funnel_name)
        if not f:
            return {}
        analysis = {}
        prev_conv = None
        for stage in f["stages"]:
            m = f["metrics"][stage]
            visits = m["visits"]
            conv = m["conversions"]
            rate = (conv / visits) * 100 if visits > 0 else 0
            if prev_conv is None:
                drop = 0
            else:
                drop = ((prev_conv - conv) / prev_conv * 100) if prev_conv > 0 else 0
            analysis[stage] = {"conversion_rate": rate, "drop_off": drop}
            prev_conv = conv
        return analysis

    def suggest_optimizations(self, funnel_name: str, threshold: float = 50.0) -> List[Dict[str, Any]]:
        """Stages whose drop-off from the previous stage is at least `threshold` percent, worst first.
        Observations for a person to weigh: the numbers say where people leave, not why."""
        analysis = self.analyze(funnel_name)
        rows = [{"stage": s, "drop_off": a["drop_off"], "conversion_rate": a["conversion_rate"],
                 "suggestion": f"Review the step into '{s}': {a['drop_off']:.0f}% of the previous stage did not continue"}
                for s, a in analysis.items() if a["drop_off"] >= threshold]
        return sorted(rows, key=lambda r: r["drop_off"], reverse=True)

    def _find(self, name: str):
        for f in self.funnels:
            if f["name"] == name:
                return f
        return None

# ================================================================================
