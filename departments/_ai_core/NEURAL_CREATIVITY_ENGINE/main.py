# ================================================================================

"""Neural creativity engine: a rule-based random combiner of idea pools; it is not an ML model.

NeuralCreativityEngine: add_to_pool(pool, item) adds to "objects", "actions" or "styles"
(pool name is lower-cased; False for an unknown pool or a duplicate item); generate()
picks one random item from each pool and returns object, action, style and a concept
string "<object> performing <action> in <style> style"; pool_list() returns copies of
the pools.
State: in memory only (self.pools), lost on restart; output is random, not seeded.
Failure: generate() returns {"error": "pool_empty:<pool>"} if any pool is empty; a
non-string pool name raises AttributeError.
"""

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