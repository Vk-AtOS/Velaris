"""EOF_GATEWAY: a durable message hand-off between agents.

route(dst, payload, via=None) checks the message and appends it to the
destination's inbox (one owner-only file per destination under this agent's
state directory); receive(dst) returns the messages not yet taken. It delivers
to an inbox and nothing more: it does not call the destination agent.

Who sent it is never a free-text argument. Every message records:
  on_behalf_of   the current caller (velaris.core.access); routing without one is refused.
  src            the agent that sent it when an agent routes for a person: that agent
                 passes itself (`via=self`) and its name is read from where its class is
                 defined (departments/<dept>/<AGENT>/main.py), so it cannot claim another
                 agent's name. A direct call (no `via`) sends as the caller: src is the
                 caller's id.
  sender         "agent" or "caller", saying which of the two src is.
Limit: in-process code can construct any agent and route through it; what it cannot do
is make the message say it came from an agent it did not use, or from someone other
than the authenticated caller.

Checks, all deterministic: both ends are agents that exist, the payload is a
JSON object within a size limit, and no text in it looks like an attempt to
instruct a model (velaris.intel.guard). Every decision is written to the
trace without the payload.

receive(dst) is bound to the caller (velaris.core.access): only the agent whose
name is `dst` may take its messages, and `dst` must be a known agent name (no path
separators), so it can never name a file outside this agent's directory.
"""
import inspect
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

from velaris.agentkit.checks import ident, is_json, known_agents, new_id
from velaris.agentkit.results import fail, health, invalid
from velaris.agentkit.state import append_line, JsonState, peek_dir, read_lines
from velaris.agents import DEPARTMENTS_DIR
from velaris.core.access import check_caller
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


def agent_name(obj: Any) -> Optional[str]:
    """The agent an object belongs to, from the file its class is defined in; None if it is not an agent."""
    try:
        path = Path(inspect.getfile(type(obj))).resolve()
    except (TypeError, OSError):
        return None
    if path.name != "main.py" or path.parent.parent.parent != DEPARTMENTS_DIR.resolve():
        return None
    return path.parent.name


class EOF_GATEWAYAgent:
    def __init__(self):
        self._cursors = JsonState(NAME, "cursors.json")     # {dst: messages already received}

    def health_check(self):
        return health(NAME)

    def route(self, dst: str, payload: dict, *, via: Any = None) -> Dict[str, Any]:
        """Queue `payload` for `dst` as the current caller, through agent `via` if given (see the module docstring)."""
        base = {"routed": False, "src": None, "dst": dst}
        dst_id = ident(dst, 80)
        if dst_id is None:
            return {**base, **invalid("dst must be an agent name")}
        sender = None if via is None else agent_name(via)
        if via is not None and sender is None:
            return {**base, **invalid("via must be the agent object that is sending, not a name")}
        caller, refused = check_caller(NAME, "route", {"dst": dst_id, "via": sender})
        if refused:
            return {**base, **refused}
        src_id = sender or caller.id
        base["src"] = src_id
        if not isinstance(payload, dict) or not is_json(payload):
            return {**base, **invalid("payload must be a JSON object")}
        size = len(json.dumps(payload).encode())
        if size > MAX_PAYLOAD_BYTES:
            return {**base, **invalid(f"payload is {size} bytes; the limit is {MAX_PAYLOAD_BYTES}")}
        agents = known_agents()
        unknown = [a for a in ((sender, dst_id) if sender else (dst_id,)) if a not in agents]
        if unknown:
            return {**base, **fail("unknown_agent", f"no such agent: {', '.join(unknown)}")}
        if src_id == dst_id:
            return {**base, **invalid("src and dst are the same agent")}
        try:
            scan = guard.scan("\n".join(_strings(payload)), source=f"gateway:{src_id}->{dst_id}")
        except (OSError, ValueError, TypeError) as e:       # the scan is traced; no trace, no delivery
            logger.warning("EOF_GATEWAY could not scan and trace a payload: %s", e)
            return {**base, **fail("storage_error", "the message could not be checked and recorded")}
        if scan.level in ("high", "block"):
            try:
                trace.append(NAME, "route.refused", {"src": src_id, "dst": dst_id,
                                                      "rules": [f["rule"] for f in scan.findings]})
            except (OSError, ValueError, TypeError) as e:
                logger.warning("EOF_GATEWAY could not trace a refusal: %s", e)
            return {**base, **fail("blocked", "payload text looks like instructions to a model",
                                   findings=[f["rule"] for f in scan.findings])}
        message = {"id": new_id("msg"), "ts": time.time(), "src": src_id, "sender": "agent" if sender else "caller",
                   "on_behalf_of": caller.id, "dst": dst_id, "payload": payload}
        try:
            append_line(agent_dir(NAME) / f"inbox_{dst_id}.jsonl", message)
            entry = trace.append(NAME, "route", {"id": message["id"], "src": src_id, "sender": message["sender"],
                                                 "on_behalf_of": caller.id, "dst": dst_id, "bytes": size})
        except (OSError, ValueError, TypeError) as e:
            logger.warning("EOF_GATEWAY could not queue a message for %s: %s", dst_id, e)
            return {**base, **fail("storage_error", "the message could not be stored")}
        return {**base, "routed": True, "status": "ok", "message_id": message["id"], "trace_hash": entry["hash"]}

    def receive(self, dst: str, limit: int = 10) -> Dict[str, Any]:
        """Messages queued for `dst` that were not returned before, oldest first. Only `dst` itself may ask."""
        dst_id = ident(dst, 80)
        if dst_id is None or not dst_id.isidentifier() or not isinstance(limit, int) or isinstance(limit, bool) \
                or limit < 1:
            return invalid("dst must be an agent name and limit a positive integer", messages=[])
        if dst_id not in known_agents():
            return fail("unknown_agent", f"no such agent: {dst_id}", messages=[])
        _, refused = check_caller(NAME, "receive", {"dst": dst_id}, roles=frozenset(), also=dst_id)
        if refused:
            return {**refused, "messages": []}
        queued = read_lines(peek_dir(NAME) / f"inbox_{dst_id}.jsonl")
        taken = int(self._cursors.load().get(dst_id, 0))
        batch = queued[taken:taken + limit]
        if batch:
            self._cursors.update(lambda c: c.__setitem__(dst_id, taken + len(batch)))
        return {"status": "ok", "messages": batch, "remaining": len(queued) - taken - len(batch)}
