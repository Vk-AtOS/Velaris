"""Bridge from the memory agents to the long-term fact store (velaris.intel.memory).

The memory agents keep their own working data (recent items, episodes, node
registry, export index) and hand anything worth keeping for good to MemoryStore,
which owns fact extraction, deduplication, supersession, scopes and time travel.
Nothing of that is re-implemented here.
"""
from __future__ import annotations

import logging
import sqlite3
from typing import Any, Dict, List, Optional

from velaris.agentkit.infra_store import fail, invalid, ok
from velaris.intel.llm import LLM
from velaris.intel.memory import MemoryStore

logger = logging.getLogger("velaris.agentkit.infra")
MAX_TEXT = 8000      # MemoryStore reads this much of one text when extracting facts


def is_scope(scope: Any) -> bool:
    return isinstance(scope, str) and 0 < len(scope) <= 200 and scope == scope.strip()


def remember(llm: Optional[LLM], texts: List[str], scope: str, source: str) -> Dict[str, Any]:
    """Store the durable facts in `texts` under `scope`. Returns counts of what MemoryStore did."""
    if not is_scope(scope):
        return invalid("scope must be a non-empty string")
    texts = [t.strip() for t in texts if isinstance(t, str) and t.strip()]
    if not texts:
        return {"status": "nothing_to_store", "facts": [], "counts": {}}
    facts: List[Dict[str, Any]] = []
    try:
        store = MemoryStore(llm)
        batch, size = [], 0
        for text in texts + [None]:                     # None flushes the last batch
            if text is None or size + len(text) > MAX_TEXT:
                if batch:
                    facts += store.remember("\n".join(batch), scope=scope, source=source)
                batch, size = [], 0
            if text is not None:
                batch.append(text[:MAX_TEXT])
                size += len(text) + 1
    except (sqlite3.Error, OSError) as e:
        logger.warning("long-term memory unavailable: %s", e)
        return fail("error", f"long-term memory unavailable: {type(e).__name__}")
    counts: Dict[str, int] = {}
    for f in facts:
        counts[f["action"]] = counts.get(f["action"], 0) + 1
    if counts.get("REFUSED"):
        return fail("refused", "the text was blocked by the guard and not stored", facts=facts, counts=counts)
    return ok(facts=facts, counts=counts)
