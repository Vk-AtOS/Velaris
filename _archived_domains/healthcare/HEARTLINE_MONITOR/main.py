# ================================================================================

import time
from typing import Dict


class HeartlineMonitor:
    """
    Velaris Heartline Monitor
    - Tracks heartbeat signals for all agents/modules
    - Detects stalls, delays, missing heartbeats
    - Computes stability health score
    """

    def __init__(self):
        self.beats: Dict[str, float] = {}

    def beat(self, component: str):
        """Record a heartbeat timestamp for a component."""
        self.beats[component] = time.time()

    def last_seen(self, component: str) -> float:
        """Return last heartbeat timestamp, or 0 if never."""
        return self.beats.get(component, 0)

    def is_alive(self, component: str, timeout: float = 5.0) -> bool:
        """Check if the component is alive within given timeout."""
        ts = self.last_seen(component)
        if ts == 0:
            return False
        return (time.time() - ts) <= timeout

    def health_score(self) -> float:
        """
        Compute a health score from 0–100.
        More recent/active beats = higher score.
        """
        if not self.beats:
            return 0.0
        now = time.time()
        delays = [now - ts for ts in self.beats.values()]
        avg_delay = sum(delays) / len(delays)
        score = max(0.0, 100 - (avg_delay * 10))
        return min(score, 100.0)

# ================================================================================