"""Document library agent: a company's files, searchable and answerable with citations.

Thin wrapper over velaris.intel.docs, where the logic and its tests live.
"""
from typing import Any, Dict, List

from velaris.intel.docs import DocStore


class DocumentLibrary:
    def __init__(self) -> None:
        self._store = None       # opened on first use

    def _docs(self) -> DocStore:
        if self._store is None:
            self._store = DocStore()
        return self._store

    def health_check(self) -> Dict[str, Any]:
        return {"agent": "DOCUMENT_LIBRARY", "status": "ok"}

    def ingest(self, name: str, data: bytes, scope: str) -> Dict[str, Any]:
        return self._docs().ingest(name, data, scope=scope)

    def search(self, query: str, scope: str, k: int = 6) -> List[Dict[str, Any]]:
        return [p.to_dict() for p in self._docs().search(query, scope=scope, k=k)]

    def ask(self, question: str, scope: str) -> Dict[str, Any]:
        return self._docs().ask(question, scope=scope)
