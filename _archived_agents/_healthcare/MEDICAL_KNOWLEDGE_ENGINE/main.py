# ================================================================================

from typing import Dict, List


class MedicalKnowledgeEngine:
    """
    Velaris Medical Knowledge Engine (Offline)
    - Stores medical facts locally
    - Keyword search + direct lookup
    - Case-insensitive duplicate protection
    """

    def __init__(self):
        self.entries: Dict[str, str] = {}

    def add_entry(self, condition: str, description: str) -> bool:
        key = condition.lower()
        if key in self.entries:
            return False
        self.entries[key] = description
        return True

    def update_entry(self, condition: str, description: str) -> bool:
        key = condition.lower()
        if key not in self.entries:
            return False
        self.entries[key] = description
        return True

    def lookup(self, term: str) -> str:
        return self.entries.get(term.lower(), "NOT_FOUND")

    def search(self, keyword: str) -> List[str]:
        keyword = keyword.lower()
        return [
            k for k, v in self.entries.items()
            if keyword in k or keyword in v.lower()
        ]

# ================================================================================