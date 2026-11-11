import logging
import time

logger = logging.getLogger("AEGIS")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - AEGIS - %(levelname)s - %(message)s"))
logger.addHandler(handler)

class AegisAgent:
    def __init__(self, config=None):
        self.config = config or {}
        self.rate_limit = self.config.get("rate_limit", 5)  # max events
        self.window_seconds = self.config.get("window_seconds", 10)
        self.threat_scores = {}
        self.events = {}

    def health_check(self):
        status = {"agent": "AEGIS", "status": "ok", "version": "0.1.0"}
        logger.debug("Health: %s", status)
        return status

    def record_event(self, source):
        now = time.time()
        self.events.setdefault(source, [])
        self.events[source] = [t for t in self.events[source] if now - t <= self.window_seconds]
        self.events[source].append(now)
        logger.debug("Record event: source=%s count=%s", source, len(self.events[source]))

    def is_rate_limited(self, source):
        now = time.time()
        self.events.setdefault(source, [])
        window_events = [t for t in self.events[source] if now - t <= self.window_seconds]
        limited = len(window_events) > self.rate_limit
        logger.debug("Rate limit check: source=%s limited=%s count=%s",
                     source, limited, len(window_events))
        return limited

    def adjust_threat(self, source, delta):
        self.threat_scores[source] = self.threat_scores.get(source, 0) + delta
        logger.debug("Threat adjust: source=%s score=%s", source, self.threat_scores[source])
        return self.threat_scores[source]

    def get_threat(self, source):
        return self.threat_scores.get(source, 0)
