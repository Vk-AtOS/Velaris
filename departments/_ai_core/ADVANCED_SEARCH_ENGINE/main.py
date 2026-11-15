# ================================================================================

"""Advanced search engine: keyword search over in-memory datasets, plus live web search and page reading.

AdvancedSearchEngine.register_dataset(name) creates an empty dataset (False if it exists);
add_record(dataset, record) appends a dict (False if the dataset is unknown); names are
lower-cased. search(keyword) is a case-insensitive substring match that scores each record
by the number of fields containing the keyword and returns hits best first; datasets_list()
names the datasets. web_search(query, limit=8) and read_page(url) delegate to velaris.intel.web
(read_page returns a dict whose 'error' key is set for a blocked or unreadable page).
State: in memory only, lost on restart (velaris.agentkit.memsearch.KeywordStore: bounded, records are copied in and
out). A bad name or record returns False; an empty or non-string keyword finds nothing.
"""
from velaris.agentkit.memsearch import KeywordStore
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
        self._store = KeywordStore()

    @property
    def datasets(self) -> Dict[str, List[Dict[str, Any]]]:
        return self._store.data

    def register_dataset(self, name: str) -> bool:
        return self._store.register(name)

    def add_record(self, dataset: str, record: Dict[str, Any]) -> bool:
        return self._store.add(dataset, record)

    def search(self, keyword: str) -> List[Dict[str, Any]]:
        return [{"dataset": h["collection"], "record": h["record"], "score": h["score"]} for h in self._store.search(keyword)]

    def datasets_list(self) -> List[str]:
        return self._store.names()

    def web_search(self, query: str, limit: int = 8) -> List[Dict[str, str]]:
        """Live web search (public search APIs; results screened by the guard)."""
        return web.search(query, limit=limit)

    def read_page(self, url: str) -> Dict[str, Any]:
        """One web page as clean markdown. Check 'error': a blocked or unreadable page has no text."""
        return web.scrape(url).to_dict()

# ================================================================================