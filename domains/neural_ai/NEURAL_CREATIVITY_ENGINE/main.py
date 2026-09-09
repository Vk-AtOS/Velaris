# ================================================================================

from typing import List, Dict


class NeuralCreativityEngine:
    """
    Velaris Neural Creativity Engine (Offline)
    - NOT an ML model. Rule-based combinatorial creativity engine.
    - Creates unique idea blends from predefined idea pools.
    """

    def __init__(self):
        self.pools: Dict[str, List[str]] = {
            "objects": [],
            "actions": [],
            "styles": []
        }

    def add_to_pool(self, pool: str, item: str) -> bool:
        pool = pool.lower()
        if pool not in self.pools:
            return False
        if item in self.pools[pool]:
            return False
        self.pools[pool].append(item)
        return True

    def generate(self) -> Dict[str, str]:
        """
        Combines one random element from each pool.
        """
        import random

        for k, items in self.pools.items():
            if not items:
                return {"error": f"pool_empty:{k}"}

        obj = random.choice(self.pools["objects"])
        act = random.choice(self.pools["actions"])
        sty = random.choice(self.pools["styles"])

        blend = f"{obj} performing {act} in {sty} style"
        return {
            "object": obj,
            "action": act,
            "style": sty,
            "concept": blend
        }

    def pool_list(self) -> Dict[str, List[str]]:
        return {k: list(v) for k, v in self.pools.items()}

# ================================================================================