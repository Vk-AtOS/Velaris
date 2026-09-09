import logging
from collections import deque
logger = logging.getLogger("SHORTTERM_MEMORY")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - SHORTTERM_MEMORY - %(levelname)s - %(message)s"))
if not logger.handlers:
    logger.addHandler(handler)

class SHORTTERM_MEMORYAgent:
    def __init__(self, capacity: int = 100):
        self.name = "SHORTTERM_MEMORY"
        self.capacity = capacity
        self._dq = deque(maxlen=capacity)
        logger.debug("SHORTTERM_MEMORY initialized")

    def health_check(self):
        return {"agent": self.name, "status": "ok", "version": "0.1.0"}

    def push(self, item):
        self._dq.append(item)
        logger.debug(f"PUSH {item}")

    def recent(self, n: int = 10):
        return list(self._dq)[-n:]
