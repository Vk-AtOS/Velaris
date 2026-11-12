"""Outside information for the business agents: web search and cited research.

Both go through velaris.intel (guarded fetch, quote-verified findings). An agent
that needs facts about the market, competitors or the economy gets them here
with their sources, or gets an honest non-ok status. Nothing is made up.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional

from velaris.agentkit import biz_common as kit
from velaris.intel import research as research_mod
from velaris.intel import web
from velaris.intel.llm import LLM
from velaris.intel.web_fetch import FetchError

logger = logging.getLogger("velaris.agentkit.biz_outside")

MAX_QUERIES = 10


def cited_research(question: Any, *, llm: Optional[LLM] = None, search_fn: Optional[Callable] = None,
                   fetcher: Any = None, scope_note: str = "", **limits: int) -> Dict[str, Any]:
    """Research a question on the web; every finding carries a quote checked against its page.

    status: ok (at least one verified finding), no_findings, not_configured, failed.
    `limits`: max_subquestions, max_sources, max_rounds.
    """
    q = kit.text(question, 500)
    if q is None:
        return kit.failed(["question must be a non-empty string of at most 500 characters"])
    bad = [k for k, v in limits.items() if k not in ("max_subquestions", "max_sources", "max_rounds")
           or isinstance(v, bool) or not isinstance(v, int) or not 1 <= v <= 20]
    if bad:
        return kit.failed([f"invalid limit: {k}" for k in bad])
    if llm is None and not kit.model_available():
        return kit.not_configured("research needs a language model to read pages; none is configured",
                                  question=q, report="", sources=[])
    kwargs: Dict[str, Any] = dict(limits, llm=llm, fetcher=fetcher, scope_note=scope_note)
    if search_fn is not None:
        kwargs["search_fn"] = search_fn
    res = research_mod.research(q, **kwargs).to_dict()
    res["status"] = "ok" if res["learnings"] else "no_findings"
    return res


def sourced_search(queries: Any, *, search_fn: Optional[Callable] = None, limit: int = 8) -> Dict[str, Any]:
    """Run each query through the guarded web search. Results are de-duplicated by URL and
    each records the queries that found it. status: ok, no_results, needs_data, failed."""
    if isinstance(queries, str):
        queries = [queries]
    if not isinstance(queries, (list, tuple)):
        return kit.failed(["queries must be a string or a list of strings"])
    if not queries:
        return kit.needs_data("no search queries supplied", results=[])
    clean = [kit.text(q, 300) for q in queries]
    if None in clean or len(clean) > MAX_QUERIES:
        return kit.failed([f"queries must be 1 to {MAX_QUERIES} non-empty strings of at most 300 characters"])
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 50:
        return kit.failed(["limit must be a whole number from 1 to 50"])
    found: Dict[str, Dict[str, Any]] = {}
    errors: List[str] = []
    for q in clean:
        try:
            hits = (search_fn or web.search)(q, limit=limit)
        except (FetchError, OSError, ValueError) as e:
            logger.warning("search failed for %r: %s", q, e)
            errors.append(f"{q}: {type(e).__name__}")
            continue
        for h in hits:
            url = h.get("url") if isinstance(h, dict) else None
            if not isinstance(url, str) or not url.startswith(("http://", "https://")):
                continue
            row = found.setdefault(url, {"url": url, "title": str(h.get("title", ""))[:300],
                                         "snippet": str(h.get("snippet", ""))[:500], "found_by": []})
            row["found_by"].append(q)
    return {"status": "ok" if found else "no_results", "results": list(found.values()),
            "queries": clean, "search_errors": errors}
