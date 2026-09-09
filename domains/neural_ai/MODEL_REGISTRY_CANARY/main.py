# ================================================================================

import os
import json
from typing import Dict, Any, Optional

class ModelRegistryCanary:
    """
    Velaris Model Registry + Canary Deploy System
    - Registers model versions
    - Activates/deactivates models
    - Canary rollout controller (percentage-based)
    - Metadata + checksum tracking
    """

    AGENT_DIR = "/live/agents/MODEL_REGISTRY_CANARY"
    REGISTRY_PATH = os.path.join(AGENT_DIR, "registry.json")

    def __init__(self):
        os.makedirs(self.AGENT_DIR, exist_ok=True)
        if not os.path.exists(self.REGISTRY_PATH):
            with open(self.REGISTRY_PATH, "w") as f:
                f.write("{}")
        self._load_registry()

    def _load_registry(self):
        with open(self.REGISTRY_PATH, "r") as f:
            try:
                self.registry: Dict[str, Any] = json.load(f)
            except:
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