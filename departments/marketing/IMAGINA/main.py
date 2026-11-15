"""Imagina: template generator for ideation prompts (stub-level, no model).

imagine(seed) returns config["depth"] (default 2) strings "<seed> - vision layer N";
scenario(topic) returns a dict with fixed possibility and risk sentences; visual_map(nodes)
returns the nodes and a chain of consecutive pairs as connections. Keeps no state; no input
validation (a non-list nodes value raises).
"""
import logging
from typing import List, Dict, Any

logger = logging.getLogger("IMAGINA")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - IMAGINA - %(levelname)s - %(message)s"))
logger.addHandler(handler)

class ImaginaAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.depth = self.config.get("depth", 2)
        self.version = self.config.get("version", "0.1.0")

    def health_check(self):
        status = {"agent": "IMAGINA", "status": "ok", "version": self.version}
        logger.debug("Health: %s", status)
        return status

    def imagine(self, seed: str) -> List[str]:
        """
        Produce layered imaginative variations from a seed.
        """
        outputs = [f"{seed} - vision layer {i+1}" for i in range(self.depth)]
        logger.debug("Imagine seed=%s -> %s", seed, outputs)
        return outputs

    def scenario(self, topic: str) -> Dict[str, Any]:
        """
        Build a simple hypothetical scenario structure.
        """
        sc = {
            "topic": topic,
            "possibility": f"A possible evolution of {topic}",
            "risk": f"A risk scenario for {topic}"
        }
        logger.debug("Scenario=%s", sc)
        return sc

    def visual_map(self, nodes: List[str]) -> Dict[str, Any]:
        """
        Construct a minimal visual node map.
        """
        m = {
            "nodes": nodes,
            "connections": [(nodes[i], nodes[i+1]) for i in range(len(nodes)-1)]
        }
        logger.debug("Visual map=%s", m)
        return m
