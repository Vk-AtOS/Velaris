import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("MEMORY_MESH")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - MEMORY_MESH - %(levelname)s - %(message)s"))
if not logger.handlers:
    logger.addHandler(handler)


class MemoryAgentBase:
    """
    Base class used by MEMORY_MESH & other mesh-like memory components.
    The previous scaffold required a `name` parameter. We now make it optional
    so subclasses can be instantiated with zero arguments.
    """

    def __init__(self, name: str = "MEMORY_MESH"):
        self.name = name
        self._nodes: Dict[str, dict] = {}
        logger.debug(f"{self.name} initialized.")

    def health_check(self):
        return {"agent": self.name, "status": "ok", "version": "0.1.0"}

    def register_node(self, node_id: str, meta: dict):
        self._nodes[node_id] = meta
        logger.debug(f"{self.name} registered node {node_id}")

    def nodes(self):
        return dict(self._nodes)


class MEMORY_MESHAgent(MemoryAgentBase):
    """
    No params required. Inherits default name "MEMORY_MESH".
    """

    def __init__(self):
        super().__init__("MEMORY_MESH")

