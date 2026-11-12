"""DOMAIN_SCOUT: find public sources about a sales vertical the company is considering.

"Domain" in the DOMAIN_* agents means a sales vertical: an industry the company
sells to (healthcare, logistics, textiles ...). scout() turns a named vertical
and region into a few search queries, runs them through the guarded web search
and returns the results with their URLs and the query that found each.

It returns sources to read, not conclusions: no market size, no ranking, and
nothing that the search did not return. No vertical -> `needs_data`.
"""
import logging
from typing import Any, Callable, Dict, Optional

from velaris.agentkit import biz_common as kit
from velaris.agentkit import biz_outside

logger = logging.getLogger("DOMAIN_SCOUT")
QUERY_TEMPLATES = ("{vertical} industry {region} companies",
                   "{vertical} {region} IT services outsourcing",
                   "{vertical} {region} industry association")


class DOMAIN_SCOUTAgent:
    def __init__(self):
        self.name = "DOMAIN_SCOUT"

    def health_check(self):
        return kit.health("DOMAIN_SCOUT")

    def scout(self, vertical: Any, region: str = "", search_fn: Optional[Callable] = None,
              limit: int = 8) -> Dict[str, Any]:
        if vertical is None or vertical == "":
            return kit.needs_data("no vertical named; the scout does not pick industries itself", results=[])
        v = kit.ident(vertical, 100)
        if v is None or not isinstance(region, str) or len(region) > 100:
            return kit.failed(["vertical must be a short non-empty string and region a short string"])
        queries = [" ".join(t.format(vertical=v, region=region.strip()).split()) for t in QUERY_TEMPLATES]
        got = biz_outside.sourced_search(queries, search_fn=search_fn, limit=limit)
        got.update(vertical=v, region=region.strip())
        return got
