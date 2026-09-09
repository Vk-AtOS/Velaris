import os
import pkgutil
import importlib
import logging
from typing import Dict, Any, List, Type

logger = logging.getLogger("REGISTRY")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - REGISTRY - %(levelname)s - %(message)s"))
logger.addHandler(handler)


class AgentRegistry:
    """
    Discovers all agent modules under live/agents/*
    Loads their entrypoints from manifest.json
    Provides dynamic agent class loading.
    """

    def __init__(self, base_path: str = None):
        self.base_path = base_path or os.path.dirname(os.path.abspath(__file__)) + "/.."
        self.agents_path = os.path.abspath(os.path.join(self.base_path, "..", "agents"))
        logger.debug("Agent registry path: %s", self.agents_path)
        self.registry = self._discover()

    def health_check(self):
        status = {"agent": "REGISTRY", "status": "ok", "count": len(self.registry)}
        logger.debug("Health: %s", status)
        return status

    ############################################################
    # INTERNAL DISCOVERY
    ############################################################
    def _discover(self) -> Dict[str, Dict[str, Any]]:
        registry = {}
        for name in os.listdir(self.agents_path):
            full = os.path.join(self.agents_path, name)
            if not os.path.isdir(full):
                continue
            manifest_path = os.path.join(full, "manifest.json")
            if not os.path.exists(manifest_path):
                continue

            import json
            with open(manifest_path, "r") as f:
                manifest = json.load(f)

            registry[manifest["name"]] = {
                "path": full,
                "manifest": manifest
            }

        logger.debug("Discovered agents: %s", list(registry.keys()))
        return registry

    ############################################################
    # PUBLIC METHODS
    ############################################################
    def list_agents(self) -> List[str]:
        return sorted(self.registry.keys())

    def get_agent_class(self, agent_name: str) -> Type:
        if agent_name not in self.registry:
            raise ValueError(f"Agent not found: {agent_name}")

        entry = self.registry[agent_name]["manifest"]["entrypoint"]
        module_path, cls_name = entry.split(":")

        module_full = f"velaris.agents.{agent_name}.{module_path.split('/')[-1].replace('.py','')}"
        logger.debug("Loading %s from %s", cls_name, module_full)

        module = importlib.import_module(module_full)
        return getattr(module, cls_name)

    def create(self, agent_name: str, config: Dict[str, Any] = None):
        cls = self.get_agent_class(agent_name)
        return cls(config or {})

    def health_all(self) -> Dict[str, Any]:
        out = {}
        for name in self.list_agents():
            try:
                inst = self.create(name)
                out[name] = inst.health_check()
            except Exception as e:
                out[name] = {"agent": name, "status": "error", "error": str(e)}
        return out
