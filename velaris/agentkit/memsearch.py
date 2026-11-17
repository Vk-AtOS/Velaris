"""A small in-memory keyword store shared by ADVANCED_SEARCH_ENGINE and AUTONOMOUS_RESEARCH_ENGINE.

Named collections of dict records; search(term) is a case-insensitive substring match scored by the number of fields
that contain the term, best first. Names are text (lower-cased), a record is a dict of at most MAX_FIELDS fields,
a collection holds at most MAX_RECORDS records and the store at most MAX_COLLECTIONS collections. An empty or
non-text term finds nothing (an empty string would otherwise match every record). Records are copied in, and hits are
copies, so a caller cannot change what is stored. Nothing is persisted.
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List

MAX_COLLECTIONS = 100
MAX_RECORDS = 10_000
MAX_FIELDS = 100


class KeywordStore:
    def __init__(self) -> None:
        self.data: Dict[str, List[Dict[str, Any]]] = {}

    def register(self, name: Any) -> bool:
        """False for a bad name, a name already registered or a full store."""
        if not isinstance(name, str) or not name.strip() or len(name) > 120:
            return False
        key = name.lower()
        if key in self.data or len(self.data) >= MAX_COLLECTIONS:
            return False
        self.data[key] = []
        return True

    def add(self, name: Any, record: Any) -> bool:
        key = name.lower() if isinstance(name, str) else None
        if key not in self.data or not isinstance(record, dict) or len(record) > MAX_FIELDS \
                or len(self.data[key]) >= MAX_RECORDS:
            return False
        self.data[key].append(copy.deepcopy(record))
        return True

    def search(self, term: Any) -> List[Dict[str, Any]]:
        if not isinstance(term, str) or not term.strip():
            return []
        term = term.lower()
        hits = []
        for name, records in self.data.items():
            for r in records:
                score = sum(1 for v in r.values() if term in str(v).lower())
                if score:
                    hits.append({"collection": name, "record": copy.deepcopy(r), "score": score})
        hits.sort(key=lambda h: -h["score"])          # stable: equal scores keep insertion order
        return hits

    def names(self) -> List[str]:
        return list(self.data)
