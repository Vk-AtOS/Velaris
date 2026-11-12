"""EAC_AUDIT: the compliance family's view of the audit trail.

It does not keep a log of its own. record() appends to the hash-chained trace
in velaris.intel.trace (actions are prefixed "eac."), find() reads those
entries back, verify() walks the whole chain and reports the first altered,
removed or reordered entry. Text values are masked for secrets and personal
identifiers before they are written.
"""
import logging
from typing import Any, Dict, Optional

from velaris.agentkit.aicore_b_common import fail, health, ident, invalid, jsonable, number
from velaris.intel import guard, trace

logger = logging.getLogger("EAC_AUDIT")
NAME = "EAC_AUDIT"
PREFIX = "eac."


def _masked(value: Any) -> Any:
    if isinstance(value, str):
        return guard.redact(value)[0]
    if isinstance(value, dict):
        return {k: _masked(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_masked(v) for v in value]
    return value


class EAC_AUDITAgent:
    def health_check(self):
        return health(NAME)

    def record(self, event: str, details: Optional[Dict[str, Any]] = None, actor: str = "EAC") -> Dict[str, Any]:
        """Append one audit event. Returns its hash, or a failure the caller must treat as "not recorded"."""
        if ident(event, 80) is None or ident(actor, 80) is None:
            return invalid("event and actor must be non-empty strings")
        details = {} if details is None else details
        if not isinstance(details, dict) or not jsonable(details):
            return invalid("details must be a JSON object")
        try:
            entry = trace.append(actor.strip(), PREFIX + event.strip(), _masked(details))
        except OSError as e:
            logger.warning("EAC_AUDIT could not write the trace: %s", e)
            return fail("storage_error", "the audit entry could not be written")
        return {"status": "ok", "hash": entry["hash"], "ts": entry["ts"]}

    def find(self, event: Optional[str] = None, actor: Optional[str] = None,
             since: Optional[float] = None, limit: int = 100) -> Dict[str, Any]:
        """Audit events, oldest first, filtered by event name, actor and time."""
        if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
            return invalid("limit must be a positive integer", events=[])
        if since is not None and number(since) is None:
            return invalid("since must be a timestamp", events=[])
        found = [e for e in trace.entries()
                 if e["action"].startswith(PREFIX)
                 and (event is None or e["action"] == PREFIX + event)
                 and (actor is None or e["actor"] == actor)
                 and (since is None or e["ts"] >= since)]
        return {"status": "ok", "events": found[-limit:], "total": len(found)}

    def summary(self) -> Dict[str, Any]:
        """How many audit events of each kind exist."""
        counts: Dict[str, int] = {}
        for e in trace.entries():
            if e["action"].startswith(PREFIX):
                name = e["action"][len(PREFIX):]
                counts[name] = counts.get(name, 0) + 1
        return {"status": "ok", "counts": counts, "total": sum(counts.values())}

    def verify(self) -> Dict[str, Any]:
        """Check the chain. intact False means the trail was tampered with (see broken_at)."""
        result = trace.verify()
        return {"status": "ok" if result["ok"] else "tampered", "intact": result["ok"],
                "entries": result["entries"], "broken_at": result["broken_at"], "reason": result["reason"]}
