# ================================================================================

"""Digital twin / XR engine: named in-memory state dicts with update, diff and merge (no XR rendering, no device link).

create_twin(name, data) (False if the name exists), update_twin(name, data) (merges top-level keys; False if unknown),
get_twin(name) (a copy; {} if unknown), diff(a, b) returns {field: {"a": value, "b": value}} for every field that
differs, treating an unknown twin as empty, and merge(target, source) copies the source's fields over the target's
(False if either is unknown). Names are case-insensitive. Data is deep-copied in and out, so callers cannot edit a twin
in place.
State: a dict in memory only, lost on restart. Failure: a non-string name raises AttributeError; no caller check is made.
"""
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