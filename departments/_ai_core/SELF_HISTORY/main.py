import logging
from typing import Dict, Any

from velaris.agentkit.checks import is_json
from velaris.agentkit.state import JsonState

logger = logging.getLogger("SELF_HISTORY")
MAX_EVENTS = 1000     # the newest events are kept; older ones drop off


class SELF_HISTORYAgent:
    def __init__(self):
        self.name = "SELF_HISTORY"
        self._state = JsonState(self.name, "events.json")      # owner-only, shared by workers, survives a restart

    def health_check(self):
        return {"agent": self.name, "status": "ok"}

    @property
    def events(self):
        return list(self._state.load().get("events", []))

    def record(self, event: Dict[str, Any]):
        if not isinstance(event, dict) or not is_json(event):
            logger.warning("SELF_HISTORY refused an event that is not a JSON object")
            return False
        self._state.update(lambda d: d.__setitem__("events", (d.get("events", []) + [event])[-MAX_EVENTS:]))
        return True

    def last(self):
        events = self.events
        return events[-1] if events else {}
