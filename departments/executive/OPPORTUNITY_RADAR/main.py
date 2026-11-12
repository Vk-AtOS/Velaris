"""OPPORTUNITY_RADAR: watch the web for new mentions of the things the caller is looking for.

run({"queries": [...], "keywords": [...]?, "limit": 8}):
  * every query goes through the guarded web search (velaris.intel.web.search);
  * results are de-duplicated and compared with the URLs already seen on earlier runs,
    so `new` holds only what has not been reported before;
  * each result lists which supplied keywords appear in its title or snippet.

The radar reports what the search returned, with its URL. It does not judge
whether something is a good opportunity and invents nothing: no queries ->
`needs_data`; a search that returns nothing -> `no_results`.
State: <VELARIS_DATA>/agents/OPPORTUNITY_RADAR/seen.json (owner-only).
"""
import logging
import time
from typing import Any, Callable, Dict, List, Optional

from velaris.agentkit import biz_common as kit
from velaris.agentkit import biz_outside
from velaris.intel.paths import agent_dir

logger = logging.getLogger("OPPORTUNITY_RADAR")
MAX_SEEN = 20_000


class OpportunityRadarAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.version = (config or {}).get("version", kit.VERSION)
        self._state = kit.JsonState(lambda: agent_dir("OPPORTUNITY_RADAR") / "seen.json", {"seen": {}})

    def health_check(self) -> Dict[str, Any]:
        return {"agent": "OPPORTUNITY_RADAR", "status": "ok", "version": self.version}

    def run(self, payload: Dict[str, Any], search_fn: Optional[Callable] = None) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            return kit.failed(["payload must be an object"])
        keywords = payload.get("keywords", [])
        if not isinstance(keywords, (list, tuple)) or len(keywords) > 50 \
                or any(kit.text(k, 100) is None for k in keywords):
            return kit.failed(["keywords must be a list of at most 50 short strings"])
        got = biz_outside.sourced_search(payload.get("queries", []), search_fn=search_fn,
                                         limit=payload.get("limit", 8))
        if got["status"] not in ("ok", "no_results"):
            return got
        data = self._state.load()
        seen: Dict[str, str] = data["seen"]
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        new: List[Dict[str, Any]] = []
        for r in got["results"]:
            r["keywords_matched"] = [k for k in keywords if kit.has_term(k, f"{r['title']} {r['snippet']}")]
            r["first_seen"] = seen.get(r["url"], now)
            if r["url"] not in seen and len(seen) < MAX_SEEN:
                seen[r["url"]] = now
                new.append(r)
        if new:
            self._state.save(data)
        return {"status": got["status"], "new": new, "seen_before": len(got["results"]) - len(new),
                "results": got["results"], "queries": got["queries"], "search_errors": got["search_errors"],
                "note": "Search results as returned, with their URLs. Whether any is worth pursuing is a human call."}
