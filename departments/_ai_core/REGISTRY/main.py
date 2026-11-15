# ================================================================================

"""Agent registry: discovers agents from their manifest.json files and loads or creates them by name.

At construction it scans each department folder (or the single base_path folder) one level down for
<AGENT>/manifest.json and indexes it by the manifest "name"; a manifest that is not valid JSON or has no "name" raises.
list_agents() returns the sorted names. get_agent_class(name) imports velaris.agents.<name>.<module> from the manifest
"entrypoint" ("main.py:ClassName") and returns the class; an unknown name or a missing or malformed entrypoint raises
ValueError. create(name, config) instantiates it, passing config only if the constructor takes an argument.
health_all() builds every agent and calls health_check(); a failure becomes {"status": "error", "error": ...} for that agent.
State: in-memory index only, rebuilt on every construction; nothing is written to disk.
"""
import inspect
import os
import pkgutil
import importlib
import logging
from typing import Dict, Any, List, Type

from velaris.agents import department_dirs

logger = logging.getLogger("REGISTRY")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - REGISTRY - %(levelname)s - %(message)s"))
logger.addHandler(handler)


class AgentRegistry:
    """
    Discovers all agent modules under departments/<department>/*
    Loads their entrypoints from manifest.json
    Provides dynamic agent class loading.
    """

    def __init__(self, base_path: str = None):
        # Agents live in departments/<department>/<AGENT>/; base_path overrides with one flat folder.
        self.agent_roots = [base_path] if base_path else [str(d) for d in department_dirs()]
        logger.debug("Agent registry roots: %s", self.agent_roots)
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
        candidates = [(root, name) for root in self.agent_roots for name in sorted(os.listdir(root))]
        for root, name in candidates:
            full = os.path.join(root, name)
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

        entry = self.registry[agent_name]["manifest"].get("entrypoint")
        if not isinstance(entry, str) or ":" not in entry:
            raise ValueError(f"Agent {agent_name} has no entrypoint ('main.py:ClassName') in its manifest")
        module_path, cls_name = entry.split(":")

        module_full = f"velaris.agents.{agent_name}.{module_path.split('/')[-1].replace('.py','')}"
        logger.debug("Loading %s from %s", cls_name, module_full)

        module = importlib.import_module(module_full)
        return getattr(module, cls_name)

    def create(self, agent_name: str, config: Dict[str, Any] = None):
        cls = self.get_agent_class(agent_name)
        params = [p for p in inspect.signature(cls).parameters.values()
                  if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD, p.VAR_POSITIONAL)]
        return cls(config or {}) if params else cls()      # some agents (GST_ENGINE) take no constructor argument

    def health_all(self) -> Dict[str, Any]:
        out = {}
        for name in self.list_agents():
            try:
                inst = self.create(name)
                out[name] = inst.health_check()
            except Exception as e:
                out[name] = {"agent": name, "status": "error", "error": str(e)}
        return out

# ================================================================================