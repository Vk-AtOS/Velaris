# ================================================================================

import json
import os
from typing import Dict, Any, List, Optional

from velaris.agentkit.secure import safe_join
from velaris.agentkit.state import MAX_STATE_BYTES
from velaris.intel.paths import agent_dir, private_dir, read_private, write_private


class SkillpackLoader:
    """
    Velaris Skillpack Loader
    - Loads modular skillpacks (JSON-based; one owner-only file per pack, written atomically)
    - Registers skill functions
    - Enables dynamic capability injection
    - A pack name is a plain file name (no separators, no '..'); the resolved path must stay inside the folder,
      so neither a name nor a symlink can make a write or a delete reach another file
    """

    def __init__(self):
        # Resolved per instance so VELARIS_DATA is honoured on any machine.
        self.AGENT_DIR = str(agent_dir("SKILLPACK_LOADER"))
        self.SKILL_DIR = str(private_dir(os.path.join(self.AGENT_DIR, "skillpacks")))
        self.registry: Dict[str, Dict[str, Any]] = {}

    def _path(self, name: str) -> str:
        if isinstance(name, str) and name.startswith("."):
            raise ValueError("a skillpack name may not start with '.'")
        return str(safe_join(self.SKILL_DIR, name, ".json"))      # ValueError for "../x", "a/b", "", non-text ...

    def load_skillpack(self, name: str, data: Dict[str, Any]) -> bool:
        path = self._path(name)
        if os.path.lexists(path):
            return False
        body = json.dumps(data, indent=2, allow_nan=False)
        if len(body) > MAX_STATE_BYTES:
            raise ValueError("skillpack is too large")
        write_private(path, body, exclusive=True)                 # exclusive: two workers cannot both create it
        self.registry[name] = data
        return True

    def unload_skillpack(self, name: str) -> bool:
        path = self._path(name)
        if not os.path.lexists(path):
            return False
        os.remove(path)
        self.registry.pop(name, None)
        return True

    def get_skillpack(self, name: str) -> Optional[Dict[str, Any]]:
        path = self._path(name)
        if not os.path.exists(path):
            self.registry.pop(name, None)                         # unloaded by another worker
            return None
        data = json.loads(read_private(path))
        self.registry[name] = data
        return data

    def list_skillpacks(self) -> List[str]:
        return sorted(f[:-5] for f in os.listdir(self.SKILL_DIR) if f.endswith(".json") and not f.startswith("."))

# ================================================================================
