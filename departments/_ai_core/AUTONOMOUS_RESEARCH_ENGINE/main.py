# ================================================================================

from typing import List, Dict, Any

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
        self.sources: Dict[str, List[Dict[str, Any]]] = {}

    def register_source(self, name: str):
        key = name.lower()
        if key in self.sources:
            return False
        self.sources[key] = []
        return True

    def add_document(self, source: str, data: Dict[str, Any]) -> bool:
        key = source.lower()
        if key not in self.sources:
            return False
        self.sources[key].append(data)
        return True

    def query(self, term: str) -> List[Dict[str, Any]]:
        """
        Simple offline research:
        - keyword matching
        - score = number of matching fields
        """
        term = term.lower()
        ranked = []

        for source, docs in self.sources.items():
            for d in docs:
                score = 0
                for k, v in d.items():
                    if term in str(v).lower():
                        score += 1

                if score > 0:
                    ranked.append({
                        "source": source,
                        "document": d,
                        "score": score
                    })

        ranked.sort(key=lambda x: x["score"], reverse=True)
        return ranked

    def research(self, question: str, **limits) -> Dict[str, Any]:
        """Research a question on the live web. Every sentence of the report cites a source,
        and every finding carries a quote that code has checked is really on that page.
        `limits`: max_subquestions, max_sources, max_rounds."""
        return research(question, **limits).to_dict()

    def summarize(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
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