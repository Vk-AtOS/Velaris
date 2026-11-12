"""STRATEGIC_INTEL: a cited research brief on a strategic question.

run({"question": "...", "scope": "..."?, "max_sources": n?, ...}) hands the question to
velaris.intel.research: it searches, reads pages through the guarded fetcher, keeps only
findings whose quote is really on the page, and writes a report in which every sentence
cites its source. The agent adds no knowledge of its own.

status: ok (verified findings), no_findings (nothing verifiable was found, and the report
says so), not_configured (no language model), failed (bad input).
"""
import logging
from typing import Any, Callable, Dict, Optional

from velaris.agentkit import biz_common as kit
from velaris.agentkit import biz_outside

logger = logging.getLogger("STRATEGIC_INTEL")
LIMITS = ("max_subquestions", "max_sources", "max_rounds")


class StrategicIntelAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.version = (config or {}).get("version", kit.VERSION)

    def health_check(self) -> Dict[str, Any]:
        return {"agent": "STRATEGIC_INTEL", "status": "ok", "version": self.version}

    def run(self, payload: Dict[str, Any], llm: Any = None, search_fn: Optional[Callable] = None,
            fetcher: Any = None) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            return kit.failed(["payload must be an object with a 'question'"])
        scope = payload.get("scope", "")
        if not isinstance(scope, str) or len(scope) > 500:
            return kit.failed(["scope must be a string of at most 500 characters"])
        limits = {k: payload[k] for k in LIMITS if k in payload}
        return biz_outside.cited_research(payload.get("question"), llm=llm, search_fn=search_fn,
                                          fetcher=fetcher, scope_note=scope, **limits)
