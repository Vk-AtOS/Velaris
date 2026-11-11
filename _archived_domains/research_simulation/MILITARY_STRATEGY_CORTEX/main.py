# ================================================================================

from typing import Dict, List


class MilitaryStrategyCortex:
    """
    Velaris Military Strategy Cortex (Offline)
    --- STRICTLY NON-OPERATIONAL & NON-REAL-WORLD ---
    This module performs *abstract, fictional simulations only*.
    No real-world actions, advice, or planning.

    Features:
    - Abstract unit strength comparisons
    - Turn-based fictional scenario evaluation
    - Risk scores inside a toy model
    """

    def __init__(self):
        self.units: Dict[str, Dict[str, int]] = {}
        self.history: List[Dict[str, str]] = []

    def register_unit(self, name: str, attack: int, defense: int) -> bool:
        key = name.lower()
        if key in self.units:
            return False
        self.units[key] = {
            "attack": attack,
            "defense": defense
        }
        return True

    def strength(self, name: str) -> int:
        key = name.lower()
        if key not in self.units:
            return 0
        u = self.units[key]
        return (u["attack"] * 2) + u["defense"]

    def compare(self, a: str, b: str) -> str:
        sa = self.strength(a)
        sb = self.strength(b)

        if sa == 0 or sb == 0:
            return "UNKNOWN"

        if sa > sb:
            result = f"{a} advantage"
        elif sb > sa:
            result = f"{b} advantage"
        else:
            result = "balanced"

        self.history.append({"a": a, "b": b, "result": result})
        return result

    def risk_index(self, a: str, b: str) -> int:
        """
        Fictional risk calculation:
        - High difference in strength → high risk
        - Balanced → medium risk
        """
        sa = self.strength(a)
        sb = self.strength(b)

        if sa == 0 or sb == 0:
            return 50

        diff = abs(sa - sb)

        if diff > 40:
            return 90
        if diff > 20:
            return 70
        return 50

    def history_log(self) -> List[Dict[str, str]]:
        return list(self.history)

# ================================================================================