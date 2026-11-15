# ================================================================================

"""Model registry canary: tracks model versions and their canary rollout percentage.

Models are keyed "name:version" with {active, canary, checksum}. register_model(name, version,
checksum) adds an inactive entry (False if it exists); activate/deactivate(name, version) set
the flag and reset canary to 0; set_canary(name, version, percent) accepts 0..100; get_model
returns the entry or None. Every mutator returns False for an unknown model (or a percent out
of range) instead of raising. Nothing here routes traffic or verifies the checksum.
State: <VELARIS_DATA>/agents/MODEL_REGISTRY_CANARY/registry.json (created on first use); an
unreadable file is logged as a warning and treated as empty.
"""
import logging
import os
import json
from typing import Dict, Any, Optional

from velaris.intel.paths import agent_dir

logger = logging.getLogger("MODEL_REGISTRY_CANARY")

class ModelRegistryCanary:
    """
    Velaris Model Registry + Canary Deploy System
    - Registers model versions
    - Activates/deactivates models
    - Canary rollout controller (percentage-based)
    - Metadata + checksum tracking
    """

    def __init__(self):
        # Resolved per instance so VELARIS_DATA is honoured on any machine.
        self.AGENT_DIR = str(agent_dir("MODEL_REGISTRY_CANARY"))
        self.REGISTRY_PATH = os.path.join(self.AGENT_DIR, "registry.json")
        if not os.path.exists(self.REGISTRY_PATH):
            with open(self.REGISTRY_PATH, "w") as f:
                f.write("{}")
        self._load_registry()

    def _load_registry(self):
        with open(self.REGISTRY_PATH, "r") as f:
            try:
                self.registry: Dict[str, Any] = json.load(f)
            except ValueError as e:
                logger.warning("Model registry %s is unreadable, starting empty: %s", self.REGISTRY_PATH, e)
                self.registry = {}

    def _save_registry(self):
        with open(self.REGISTRY_PATH, "w") as f:
            json.dump(self.registry, f, indent=2)

    def register_model(self, name: str, version: str, checksum: str) -> bool:
        key = f"{name}:{version}"
        if key in self.registry:
            return False
        self.registry[key] = {
            "active": False,
            "canary": 0,
            "checksum": checksum
        }
        self._save_registry()
        return True

    def activate(self, name: str, version: str) -> bool:
        key = f"{name}:{version}"
        if key not in self.registry:
            return False
        self.registry[key]["active"] = True
        self.registry[key]["canary"] = 0
        self._save_registry()
        return True

    def deactivate(self, name: str, version: str) -> bool:
        key = f"{name}:{version}"
        if key not in self.registry:
            return False
        self.registry[key]["active"] = False
        self.registry[key]["canary"] = 0
        self._save_registry()
        return True

    def set_canary(self, name: str, version: str, percent: int) -> bool:
        key = f"{name}:{version}"
        if key not in self.registry:
            return False
        if percent < 0 or percent > 100:
            return False
        self.registry[key]["canary"] = percent
        self._save_registry()
        return True

    def get_model(self, name: str, version: str) -> Optional[Dict[str, Any]]:
        return self.registry.get(f"{name}:{version}")

# ================================================================================