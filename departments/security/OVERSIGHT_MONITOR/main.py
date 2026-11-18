"""Oversight monitor: a minimal in-memory log of oversight entries (stub-level).

record(entry) appends any dict; last() returns the latest entry or {} when empty;
health_check() reports status ok. It raises no alerts, validates nothing and has no size
limit. State: a list in memory only, lost on restart.
"""
import logging
from typing import Dict, Any, List
logger = logging.getLogger("OVERSIGHT_MONITOR")

class OVERSIGHT_MONITORAgent:
    def __init__(self):
        self.name = "OVERSIGHT_MONITOR"
        self.logs: List[Dict[str, Any]] = []
        logger.debug("OVERSIGHT_MONITOR initialized")

    def health_check(self):
        return {"agent": self.name, "status": "ok", "version": "0.1.0"}

    def record(self, entry: Dict[str, Any]):
        self.logs.append(entry)
        logger.debug("recorded oversight entry")

    def last(self):
        return self.logs[-1] if self.logs else {}
