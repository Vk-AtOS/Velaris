# ================================================================================

import copy
from typing import Dict, Any


class DigitalTwinXREngine:
    """
    Velaris Digital Twin / XR Engine (Offline Simulation)
    - Maintains abstract digital-twin state models
    - Allows updating and querying XR-friendly state data
    - Provides diff and merge operations
    """

    def __init__(self):
        self.twins: Dict[str, Dict[str, Any]] = {}

    def create_twin(self, name: str, data: Dict[str, Any]) -> bool:
        key = name.lower()
        if key in self.twins:
            return False
        self.twins[key] = copy.deepcopy(data)       # never keep the caller's own dict
        return True

    def update_twin(self, name: str, data: Dict[str, Any]) -> bool:
        key = name.lower()
        if key not in self.twins:
            return False
        self.twins[key].update(copy.deepcopy(data))
        return True

    def get_twin(self, name: str) -> Dict[str, Any]:
        return copy.deepcopy(self.twins.get(name.lower(), {}))    # a copy: callers cannot edit the twin in place

    def diff(self, a: str, b: str) -> Dict[str, Any]:
        """
        Compares two digital twins and returns differing fields.
        """
        ta = self.get_twin(a)
        tb = self.get_twin(b)
        keys = set(ta.keys()) | set(tb.keys())
        out = {}
        for k in keys:
            if ta.get(k) != tb.get(k):
                out[k] = {"a": ta.get(k), "b": tb.get(k)}
        return out

    def merge(self, target: str, source: str) -> bool:
        """
        Merge source twin fields into target twin.
        """
        t = target.lower()
        s = source.lower()
        if t not in self.twins or s not in self.twins:
            return False
        self.twins[t].update(copy.deepcopy(self.twins[s]))
        return True

# ================================================================================