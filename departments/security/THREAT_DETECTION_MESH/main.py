# ================================================================================

"""Threat detection mesh: rule-based event scorer that counts matches against registered signatures; not machine learning.

ThreatDetectionMesh: add_signature(name, pattern) registers a {key: value} pattern (False
if the name exists); record_event(event) stores an event; score_event(event) adds 10 for
every signature key whose value equals the event's value; detect(event) returns {event,
score, level} with level HIGH (score >= 20), MEDIUM (>= 10) or LOW; summary() rates all
recorded events.
State: in memory only (self.signatures, self.events), lost on restart; events grow without
bound.
Failure: no match gives score 0 / LOW; non-dict events raise TypeError or AttributeError.
"""

from typing import Dict, Any, List


class ThreatDetectionMesh:
    """
    Velaris Threat Detection Mesh
    - Detects anomalies in component behavior
    - Maintains a threat signature database
    - Scores incoming events for threat likelihood
    """

    def __init__(self):
        self.signatures: List[Dict[str, Any]] = []
        self.events: List[Dict[str, Any]] = []

    def add_signature(self, name: str, pattern: Dict[str, Any]) -> bool:
        """Register a threat pattern."""
        for s in self.signatures:
            if s["name"] == name:
                return False
        self.signatures.append({"name": name, "pattern": pattern})
        return True

    def record_event(self, event: Dict[str, Any]):
        """Record an observed event."""
        self.events.append(event)

    def score_event(self, event: Dict[str, Any]) -> int:
        """
        Score event severity by matching keys/values against signatures.
        Higher score = more suspicious.
        """
        score = 0
        for sig in self.signatures:
            pat = sig["pattern"]
            for k, v in pat.items():
                if k in event and event[k] == v:
                    score += 10
        return score

    def detect(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Return threat rating for a single event."""
        score = self.score_event(event)
        if score >= 20:
            level = "HIGH"
        elif score >= 10:
            level = "MEDIUM"
        else:
            level = "LOW"

        return {"event": event, "score": score, "level": level}

    def summary(self) -> Dict[str, Any]:
        """Summarize all events with threat scoring."""
        out = []
        for e in self.events:
            out.append(self.detect(e))
        return {"count": len(out), "results": out}

# ================================================================================