"""EOF_GATEWAY: a durable message hand-off between agents.

route(src, dst, payload) checks the message and appends it to the
destination's inbox (one owner-only file per destination under this agent's
state directory); receive(dst) returns the messages not yet taken. It delivers
to an inbox and nothing more: it does not call the destination agent.

Checks, all deterministic: both ends are agents that exist, the payload is a
JSON object within a size limit, and no text in it looks like an attempt to
instruct a model (velaris.intel.guard). Every decision is written to the
trace without the payload.
"""
import json
import logging
import time
from typing import Any, Dict, Iterator

from velaris.agentkit.aicore_b_common import (JsonState, append_line, fail, health, ident, invalid, jsonable,
                                              known_agents, new_id, peek_dir, read_lines)
from velaris.intel import guard, trace
from velaris.intel.paths import agent_dir

logger = logging.getLogger("EOF_GATEWAY")
NAME = "EOF_GATEWAY"
MAX_PAYLOAD_BYTES = 64 * 1024


def _strings(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)


class EOF_GATEWAYAgent:
    def __init__(self):
        self._cursors = JsonState(NAME, "cursors.json")     # {dst: messages already received}

    def health_check(self):
        return health(NAME)

    def route(self, src: str, dst: str, payload: dict) -> Dict[str, Any]:
        """Queue `payload` for `dst`. Returns routed True/False with a status and reason."""
        base = {"routed": False, "src": src, "dst": dst}
        src_id, dst_id = ident(src, 80), ident(dst, 80)
        if src_id is None or dst_id is None:
            return {**base, **invalid("src and dst must be agent names")}
        if not isinstance(payload, dict) or not jsonable(payload):
            return {**base, **invalid("payload must be a JSON object")}
        size = len(json.dumps(payload).encode())
        if size > MAX_PAYLOAD_BYTES:
            return {**base, **invalid(f"payload is {size} bytes; the limit is {MAX_PAYLOAD_BYTES}")}
        agents = known_agents()
        unknown = [a for a in (src_id, dst_id) if a not in agents]
        if unknown:
            return {**base, **fail("unknown_agent", f"no such agent: {', '.join(unknown)}")}
        if src_id == dst_id:
            return {**base, **invalid("src and dst are the same agent")}
        scan = guard.scan("\n".join(_strings(payload)), source=f"gateway:{src_id}->{dst_id}")
        if scan.level in ("high", "block"):
            trace.append(NAME, "route.refused", {"src": src_id, "dst": dst_id,
                                                  "rules": [f["rule"] for f in scan.findings]})
            return {**base, **fail("blocked", "payload text looks like instructions to a model",
                                   findings=[f["rule"] for f in scan.findings])}
        message = {"id": new_id("msg"), "ts": time.time(), "src": src_id, "dst": dst_id, "payload": payload}
        try:
            append_line(agent_dir(NAME) / f"inbox_{dst_id}.jsonl", message)
            entry = trace.append(NAME, "route", {"id": message["id"], "src": src_id, "dst": dst_id, "bytes": size})
        except OSError as e:
            logger.warning("EOF_GATEWAY could not queue a message for %s: %s", dst_id, e)
            return {**base, **fail("storage_error", "the message could not be stored")}
        return {**base, "routed": True, "status": "ok", "message_id": message["id"], "trace_hash": entry["hash"]}

    def receive(self, dst: str, limit: int = 10) -> Dict[str, Any]:
        """Messages queued for `dst` that were not returned before, oldest first."""
        dst_id = ident(dst, 80)
        if dst_id is None or not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
            return invalid("dst must be an agent name and limit a positive integer", messages=[])
        queued = read_lines(peek_dir(NAME) / f"inbox_{dst_id}.jsonl")
        taken = int(self._cursors.load().get(dst_id, 0))
        batch = queued[taken:taken + limit]
        if batch:
            self._cursors.update(lambda c: c.__setitem__(dst_id, taken + len(batch)))
        return {"status": "ok", "messages": batch, "remaining": len(queued) - taken - len(batch)}
