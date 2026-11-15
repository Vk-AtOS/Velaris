# ================================================================================

"""Digital twin XR engine: in-memory store of named twin dicts with diff and merge (no XR or simulation).

create_twin(name, data) (False if it exists), update_twin(name, data) (shallow merge; False if
unknown), get_twin(name) ({} if unknown), diff(a, b) returns the fields that differ as
{field: {"a": ..., "b": ...}}, merge(target, source) copies source fields into target (False if
either is unknown). Names are lower-cased. create_twin keeps the caller's dict, not a copy.
State: a dict in memory only, lost on restart.
"""
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
        self.twins[key] = data
        return True

    def update_twin(self, name: str, data: Dict[str, Any]) -> bool:
        key = name.lower()
        if key not in self.twins:
            return False
        self.twins[key].update(data)
        return True

    def get_twin(self, name: str) -> Dict[str, Any]:
        return self.twins.get(name.lower(), {})

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
        self.twins[t].update(self.twins[s])
        return True

# ================================================================================