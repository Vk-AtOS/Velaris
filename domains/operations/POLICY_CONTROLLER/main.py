import logging
from typing import Dict, Any
logger = logging.getLogger("POLICY_CONTROLLER")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - POLICY_CONTROLLER - %(levelname)s - %(message)s"))
if not logger.handlers:
    logger.addHandler(handler)

class POLICY_CONTROLLERAgent:
    def __init__(self):
        self.name = "POLICY_CONTROLLER"
        self.store = {}
        logger.debug("POLICY_CONTROLLER initialized")

    def health_check(self):
        return {"agent": self.name, "status": "ok", "version": "0.1.0"}

    def put_policy(self, pid: str, policy: Dict[str, Any]):
        self.store[pid] = policy
        logger.debug(f"policy {pid} stored")

    def get_policy(self, pid: str):
        return self.store.get(pid)
