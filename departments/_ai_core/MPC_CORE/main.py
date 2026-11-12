"""MPC_CORE: clean every source's record (MPC_PREPROC), then merge them (MPC_FUSION).

Cleaning first is what makes the merge meaningful: "1,200" from one system and
1200.0 from another, or "Total Amount" and "total_amount", are the same value
and the same field once cleaned, so they no longer show up as conflicts.
"""
from typing import Any, Dict

from velaris.agentkit.results import health, invalid
from velaris.agents.MPC_FUSION.main import MPC_FUSIONAgent
from velaris.agents.MPC_PREPROC.main import MPC_PREPROCAgent

NAME = "MPC_CORE"


class MPC_COREAgent:
    def __init__(self):
        self.preproc = MPC_PREPROCAgent()
        self.fusion = MPC_FUSIONAgent()

    def health_check(self):
        return health(NAME)

    def run(self, sources: Any, redact: bool = False) -> Dict[str, Any]:
        """sources: [{"source", "record", "trust", "ts"}]. Returns the fusion result plus cleaning stats."""
        if not isinstance(sources, list) or not sources or not all(isinstance(s, dict) for s in sources):
            return invalid("sources must be a non-empty list of objects", record=None)
        cleaned, stats = [], {}
        for s in sources:
            pre = self.preproc.preprocess(s.get("record"), redact=redact)
            if pre["status"] != "ok":
                return invalid(f"source {s.get('source')!r}: {pre['reason']}", record=None)
            cleaned.append({**s, "record": pre["record"]})
            for key, count in pre["stats"].items():
                stats[key] = stats.get(key, 0) + count
        fused = self.fusion.fuse(cleaned)
        return {**fused, "cleaning": stats}
