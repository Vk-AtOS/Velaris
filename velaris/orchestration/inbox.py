"""The consumer of the EOF queues (defect 13): hands the messages of an agent's inbox to that agent.

EOF_CORE.orchestrate puts ordered steps into EOF_GATEWAY inboxes, and nothing ever read them. `deliver(dst)` is the reader:
for an agent that defines `on_message(message)` it takes the queued messages AS that agent (receive is bound to the agent itself)
and runs `on_message` for each through BackendEngine.run, so the one dispatch path applies. An agent without `on_message` is not
a consumer: its messages stay queued (never dropped) and the answer says so. A message whose handler fails is recorded in the
trace and counted; it is not retried (it was taken), the sender sees it in `failed`.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from velaris.core.access import Caller, acting_as, deployment_org
from velaris.intel import trace

logger = logging.getLogger("velaris.orchestration.inbox")
HANDLER = "on_message"


def deliver(dst: str, *, engine: Any = None, limit: int = 10, org: Optional[str] = None) -> Dict[str, Any]:
    if engine is None:
        from velaris.backend.engine import backend as engine        # loads every agent; deferred
    from velaris.agents.EOF_GATEWAY.main import EOF_GATEWAYAgent
    try:
        cls = engine.agent_class(dst)
    except LookupError:
        return {"delivered": 0, "failed": 0, "consumer": False, "reason": f"no agent named {dst!r}"}
    if not callable(getattr(cls, HANDLER, None)):
        return {"delivered": 0, "failed": 0, "consumer": False, "reason": f"{dst} defines no {HANDLER}; its messages stay queued"}
    me = Caller(id=dst, org=org or deployment_org() or "default", roles=frozenset())
    with acting_as(me):
        got = EOF_GATEWAYAgent().receive(dst, limit)
    delivered = failed = 0
    for message in got.get("messages", []):
        try:
            engine.run(dst, HANDLER, {"message": message}, caller=me)
            delivered += 1
        except Exception as e:  # the handler is agent code; a failure is recorded, the rest still go
            failed += 1
            logger.warning("%s.%s failed for message %s: %s", dst, HANDLER, message.get("id"), type(e).__name__)
            trace.append("inbox", "handler.failed", {"dst": dst, "message": message.get("id"), "error": type(e).__name__})
    return {"delivered": delivered, "failed": failed, "consumer": True, "remaining": got.get("remaining", 0)}
