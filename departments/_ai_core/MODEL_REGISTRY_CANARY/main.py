# ================================================================================

import logging
import os
import json
from typing import Dict, Any, Optional

from velaris.agentkit.state import JsonState
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
        # Owner-only, atomic, locked across workers. A file that cannot be parsed is set aside (kept), never overwritten.
        self._state = JsonState("MODEL_REGISTRY_CANARY", path=self.REGISTRY_PATH)

    @property
    def registry(self) -> Dict[str, Any]:
        return self._state.load().get("models", {})

    def _change(self, name: str, version: str, fn) -> bool:
        key = f"{name}:{version}"

        def go(d):
            model = d.setdefault("models", {}).get(key)
            return False if model is None else fn(model)
        return bool(self._state.update(go))

    def register_model(self, name: str, version: str, checksum: str) -> bool:
        key = f"{name}:{version}"

        def add(d):
            models = d.setdefault("models", {})
            if key in models:
                return False
            models[key] = {"active": False, "canary": 0, "checksum": checksum}
            return True
        return bool(self._state.update(add))

    def activate(self, name: str, version: str) -> bool:
        return self._change(name, version, lambda m: m.update(active=True, canary=0) or True)

    def deactivate(self, name: str, version: str) -> bool:
        return self._change(name, version, lambda m: m.update(active=False, canary=0) or True)

    def set_canary(self, name: str, version: str, percent: int) -> bool:
        """Whole percent 0..100. Booleans, floats and text are refused (a string used to raise TypeError)."""
        if isinstance(percent, bool) or not isinstance(percent, int) or not 0 <= percent <= 100:
            return False
        return self._change(name, version, lambda m: m.update(canary=percent) or True)

    def get_model(self, name: str, version: str) -> Optional[Dict[str, Any]]:
        return self.registry.get(f"{name}:{version}")

# ================================================================================