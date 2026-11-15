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

class BusinessFunnelDesigner:
    """
    Velaris Business Funnel Designer
    - Generates multi-stage funnels
    - Computes drop-off percentages
    - Suggests optimizations at each step
    """

    def __init__(self):
        self.funnels: List[Dict[str, Any]] = []

    def create_funnel(self, name: str, stages: List[str]) -> Dict[str, Any]:
        funnel = {
            "name": name,
            "stages": stages,
            "metrics": {stage: {"visits": 0, "conversions": 0} for stage in stages}
        }
        self.funnels.append(funnel)
        return funnel

    def record_stage(self, funnel_name: str, stage: str, visits: int, conversions: int) -> bool:
        f = self._find(funnel_name)
        if not f: 
            return False
        if stage not in f["stages"]:
            return False
        f["metrics"][stage]["visits"] += visits
        f["metrics"][stage]["conversions"] += conversions
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

    def _find(self, name: str):
        for f in self.funnels:
            if f["name"] == name:
                return f
        return None

# ================================================================================