import logging
from typing import Dict, Any
logger = logging.getLogger("SELF_IDENTITY")
logger.setLevel(logging.DEBUG)
h = logging.StreamHandler()
h.setFormatter(logging.Formatter("%(asctime)s - SELF_IDENTITY - %(levelname)s - %(message)s"))
if not logger.handlers:
    logger.addHandler(h)

class SELF_IDENTITYAgent:
    def __init__(self):
        self.name = "SELF_IDENTITY"
        self.identity = {"name": "Velaris", "model": "1.0-core"}
        logger.debug("SELF_IDENTITY initialized")

    def health_check(self):
        return {"agent": "SELF_IDENTITY", "status": "ok", "identity": self.identity}

    def get_identity(self) -> Dict[str, Any]:
        logger.debug("identity requested")
        return dict(self.identity)

    def set_identity(self, key: str, value: str):
        self.identity[key] = value
        logger.debug(f"identity updated {key}={value}")
        return True
