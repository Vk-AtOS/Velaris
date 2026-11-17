# ================================================================================

"""Agent registry: discovers agents from their manifest.json files and loads or creates them by name.

At construction it scans each department folder (or the single base_path folder) one level down for
<AGENT>/manifest.json and indexes it by the manifest "name"; a manifest that is not valid JSON or has no "name" raises.
list_agents() returns the sorted names. get_agent_class(name) imports velaris.agents.<name>.<module> from the manifest
"entrypoint" ("main.py:ClassName") and returns the class; an unknown name or a missing or malformed entrypoint raises
ValueError. create(name, config) instantiates it, passing config only to a constructor whose first parameter is named "config";
any other constructor is called with its own defaults, and one with required arguments raises ValueError.
health(name) / health_all() build the agent and call its health_check() or health() (else a module-level one); an
agent with none is reported as {"status": "no_health_method"}, and a failure becomes {"status": "error", "error": ...}.
State: in-memory index only, rebuilt on every construction; nothing is written to disk.
"""
import inspect
import os
import importlib
import logging
from typing import Dict, Any, List, Type

from velaris.agents import department_dirs
from velaris.agents.health import default_health

logger = logging.getLogger("REGISTRY")


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
        """Build the agent. `config` is passed only to a constructor whose first parameter is named `config`;
        any other constructor is called with its own defaults (its first parameter is not a config dict: giving
        it {} silently changed ALK_EVO's thresholds and AAE_POLICY's rules). A constructor with required
        arguments of its own cannot be built here and raises ValueError."""
        cls = self.get_agent_class(agent_name)
        params = [p for p in inspect.signature(cls).parameters.values()
                  if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)]
        if params and params[0].name == "config":
            return cls(config or {})
        if any(p.default is p.empty for p in params):
            raise ValueError(f"Agent {agent_name} needs constructor arguments the registry cannot supply")
        return cls()

    def health(self, agent_name: str) -> Dict[str, Any]:
        """Health of one agent: its instance health_check()/health(), else a module-level health_check()/health(),
        else {"status": "no_health_method"} (never a fabricated "ok"). Construction failure is reported as an error."""
        try:
            inst = self.create(agent_name)
        except Exception as e:
            logger.warning("health: cannot build %s: %s", agent_name, e)
            return {"agent": agent_name, "status": "error", "error": str(e)}
        try:
            return default_health(agent_name, inst, importlib.import_module(type(inst).__module__))
        except Exception as e:
            logger.warning("health of %s failed: %s", agent_name, e)
            return {"agent": agent_name, "status": "error", "error": str(e)}

    def health_all(self) -> Dict[str, Any]:
        return {name: self.health(name) for name in self.list_agents()}

# ================================================================================