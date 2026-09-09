# ================================================================================

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