# ================================================================================

from velaris.intel import web
from typing import Dict, List, Any


class AdvancedSearchEngine:
    """
    Velaris Advanced Search Engine (Offline)
    - Keyword search across multiple datasets
    - Weighted scoring
    - Multi-index registry
    """

    def __init__(self):
        self.datasets: Dict[str, List[Dict[str, Any]]] = {}

    def register_dataset(self, name: str) -> bool:
        key = name.lower()
        if key in self.datasets:
            return False
        self.datasets[key] = []
        return True

    def add_record(self, dataset: str, record: Dict[str, Any]) -> bool:
        key = dataset.lower()
        if key not in self.datasets:
            return False
        self.datasets[key].append(record)
        return True

    def search(self, keyword: str) -> List[Dict[str, Any]]:
        keyword = keyword.lower()
        results = []
        for ds_name, records in self.datasets.items():
            for r in records:
                score = 0
                for k, v in r.items():
                    v_str = str(v).lower()
                    if keyword in v_str:
                        score += 1
                if score > 0:
                    results.append({"dataset": ds_name, "record": r, "score": score})

        # sort by descending score
        results.sort(key=lambda x: x["score"], reverse=True)
        return results

    def datasets_list(self) -> List[str]:
        return list(self.datasets.keys())

    def web_search(self, query: str, limit: int = 8) -> List[Dict[str, str]]:
        """Live web search (public search APIs; results screened by the guard)."""
        return web.search(query, limit=limit)

    def read_page(self, url: str) -> Dict[str, Any]:
        """One web page as clean markdown. Check 'error': a blocked or unreadable page has no text."""
        return web.scrape(url).to_dict()

# ================================================================================