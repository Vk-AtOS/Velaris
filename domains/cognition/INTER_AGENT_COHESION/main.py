# ================================================================================

import logging
from typing import Dict, Any, Optional, List
from velaris.agents.MEMORY_FABRIC.main import MemoryFabric

logger = logging.getLogger("INTER_AGENT_COHESION")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - INTER_AGENT_COHESION - %(levelname)s - %(message)s"))
logger.addHandler(handler)

class Cohesion:
    def __init__(self, config: Dict[str, Any] = None):
        self.mem = MemoryFabric()
        self.config = config or {}
        self.version = self.config.get("version", "0.1.0")

    def health_check(self):
        return {"agent": "INTER_AGENT_COHESION", "status": "ok", "version": self.version}

    def link(self, namespace: str, key: str, metadata: Dict[str, Any], ttl: Optional[int] = None):
        return self.mem.put(namespace, key, metadata, ttl=ttl)

    def recall(self, namespace: str, key: str):
        return self.mem.get(namespace, key)

    def list_namespace(self, namespace: str, prefix: Optional[str] = None):
        return self.mem.query(namespace, prefix)

# ================================================================================