# ================================================================================

import os
import json
from typing import Dict, Any, Optional

from velaris.intel.paths import agent_dir

class SkillpackLoader:
    """
    Velaris Skillpack Loader
    - Loads modular skillpacks (JSON-based)
    - Registers skill functions
    - Enables dynamic capability injection
    """

    def __init__(self):
        # Resolved per instance so VELARIS_DATA is honoured on any machine.
        self.AGENT_DIR = str(agent_dir("SKILLPACK_LOADER"))
        self.SKILL_DIR = os.path.join(self.AGENT_DIR, "skillpacks")
        os.makedirs(self.SKILL_DIR, exist_ok=True)
        self.registry: Dict[str, Dict[str, Any]] = {}

    def load_skillpack(self, name: str, data: Dict[str, Any]) -> bool:
        path = os.path.join(self.SKILL_DIR, f"{name}.json")
        if os.path.exists(path):
            return False
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        self.registry[name] = data
        return True

    def unload_skillpack(self, name: str) -> bool:
        path = os.path.join(self.SKILL_DIR, f"{name}.json")
        if not os.path.exists(path):
            return False
        os.remove(path)
        self.registry.pop(name, None)
        return True

    def get_skillpack(self, name: str) -> Optional[Dict[str, Any]]:
        if name in self.registry:
            return self.registry[name]
        path = os.path.join(self.SKILL_DIR, f"{name}.json")
        if not os.path.exists(path):
            return None
        with open(path, "r") as f:
            data = json.load(f)
            self.registry[name] = data
            return data

    def list_skillpacks(self):
        return list(self.registry.keys())

# ================================================================================