# ================================================================================

"""Autonomous research engine: ranks documents in registered in-memory sources by keyword match, and delegates live-web research to velaris.intel.research.

AutonomousResearchEngine: register_source(name) creates an empty lowercase-keyed source
(False if it exists); add_document(source, data) appends a dict (False if the source is
unknown); query(term) scores each document by how many of its fields contain the term
(case-insensitive substring) and returns matches best first; summarize(results) joins the
top 3 into one string with a count ("No results", 0 for an empty list); research(question,
**limits) returns velaris.intel.research.research(...).to_dict() and takes max_subquestions,
max_sources, max_rounds.
State: in memory only (velaris.agentkit.memsearch.KeywordStore: bounded, copies in and out), lost on restart;
research() keeps none here.
Failure: bad names or sources return False or empty results; query() of an empty or non-string term returns [];
research() errors propagate from velaris.intel.research.
"""

from typing import List, Dict, Any

from velaris.agentkit.memsearch import KeywordStore
from velaris.intel.research import research


class AutonomousResearchEngine:
    """
    Velaris Autonomous Research Engine (Offline)
    - Accepts research queries
    - Searches across registered offline datasets
    - Performs scoring + ranking
    - Produces structured offline "research summaries"
    """

    def __init__(self):
        self._store = KeywordStore()

    @property
    def sources(self) -> Dict[str, List[Dict[str, Any]]]:
        return self._store.data

    def register_source(self, name: str):
        return self._store.register(name)

    def add_document(self, source: str, data: Dict[str, Any]) -> bool:
        return self._store.add(source, data)

    def query(self, term: str) -> List[Dict[str, Any]]:
        """Offline keyword search: score = number of matching fields, best first."""
        return [{"source": h["collection"], "document": h["record"], "score": h["score"]} for h in self._store.search(term)]

    def research(self, question: str, **limits) -> Dict[str, Any]:
        """Research a question on the live web. Every sentence of the report cites a source,
        and every finding carries a quote that code has checked is really on that page.
        `limits`: max_subquestions, max_sources, max_rounds."""
        return research(question, **limits).to_dict()

    def summarize(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        results = [r for r in results if isinstance(r, dict) and isinstance(r.get("document"), dict)] \
            if isinstance(results, list) else []
        if not results:
            return {"summary": "No results", "count": 0}

        top = results[:3]
        summary_lines = []
        for r in top:
            doc = r["document"]
            parts = []
            for k, v in doc.items():
                parts.append(f"{k}: {v}")
            summary_lines.append("; ".join(parts))

        return {
            "summary": " | ".join(summary_lines),
            "count": len(results)
        }

# ================================================================================