# ================================================================================

from typing import Dict, Any, List


class GeoCivilizationEngine:
    """
    Velaris Geo-Civilization Engine (Offline)
    - Stores simplified geopolitical and civilization datasets
    - Allows relationship mapping between regions
    - Provides rule-based risk and cooperation scoring
    """

    def __init__(self):
        self.regions: Dict[str, Dict[str, Any]] = {}
        self.relations: Dict[str, Dict[str, str]] = {}  # regionA -> regionB -> relation_type

    def add_region(self, name: str, population: int, economy: str) -> bool:
        key = name.lower()
        if key in self.regions:
            return False
        self.regions[key] = {
            "population": population,
            "economy": economy
        }
        self.relations[key] = {}
        return True

    def update_region(self, name: str, population: int = None, economy: str = None) -> bool:
        key = name.lower()
        if key not in self.regions:
            return False
        if population is not None:
            self.regions[key]["population"] = population
        if economy is not None:
            self.regions[key]["economy"] = economy
        return True

    def link_regions(self, a: str, b: str, relation: str) -> bool:
        a = a.lower()
        b = b.lower()
        if a not in self.regions or b not in self.regions:
            return False
        self.relations[a][b] = relation
        return True

    def get_relation(self, a: str, b: str) -> str:
        a = a.lower()
        b = b.lower()
        return self.relations.get(a, {}).get(b, "NONE")

    def cooperation_score(self, a: str, b: str) -> int:
        """
        Simple rule-based scoring:
        alliance → 90
        trade → 70
        neutral → 50
        tension → 25
        conflict → 5
        """
        rel = self.get_relation(a, b)
        mapping = {
            "alliance": 90,
            "trade": 70,
            "neutral": 50,
            "tension": 25,
            "conflict": 5,
        }
        return mapping.get(rel, 50)

    def risk_score(self, a: str, b: str) -> int:
        """
        Reverse risk scoring: conflict high risk, alliance low risk.
        """
        rel = self.get_relation(a, b)
        mapping = {
            "alliance": 10,
            "trade": 30,
            "neutral": 50,
            "tension": 70,
            "conflict": 90,
        }
        return mapping.get(rel, 50)

    def search_region(self, keyword: str) -> List[str]:
        keyword = keyword.lower()
        return [r for r, data in self.regions.items() if keyword in r or keyword in data["economy"].lower()]

# ================================================================================