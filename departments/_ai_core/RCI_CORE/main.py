"""RCI_CORE: the way events get into the running context, and the way the context is read.

ingest(topic, event) screens the event before it is stored: text that looks
like an attempt to instruct a model is refused (velaris.intel.guard.scan),
and secrets and personal identifiers in text values are masked. What passes
is appended to the topic through RCI_STREAM. context(topic) returns the
bounded context built by RCI_CONTEXT.
"""
from typing import Any, Dict, Iterator

from velaris.agentkit.aicore_b_common import fail, health, invalid
from velaris.agents.RCI_CONTEXT.main import RCI_CONTEXTAgent
from velaris.agents.RCI_STREAM.main import RCI_STREAMAgent
from velaris.intel import guard

NAME = "RCI_CORE"


def _strings(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from _strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)


def _masked(value: Any, counts: Dict[str, int]) -> Any:
    if isinstance(value, str):
        text, found = guard.redact(value)
        for kind, n in found.items():
            counts[kind] = counts.get(kind, 0) + n
        return text
    if isinstance(value, dict):
        return {k: _masked(v, counts) for k, v in value.items()}
    if isinstance(value, list):
        return [_masked(v, counts) for v in value]
    return value


class RCI_COREAgent:
    def __init__(self):
        self.stream = RCI_STREAMAgent()
        self.contexts = RCI_CONTEXTAgent()

    def health_check(self):
        return health(NAME)

    def ingest(self, topic: str, event: Dict[str, Any]) -> Dict[str, Any]:
        """Screen, mask and store one event. Returns its offset, or why it was refused."""
        if not isinstance(event, dict) or not event:
            return invalid("event must be a non-empty object")
        scan = guard.scan("\n".join(_strings(event)), source=f"rci:{topic}")
        if scan.level in ("high", "block"):
            return fail("blocked", "the event contains text that looks like instructions to a model",
                        findings=[f["rule"] for f in scan.findings])
        redacted: Dict[str, int] = {}
        stored = self.stream.publish(topic, _masked(event, redacted))
        return {**stored, "redacted": redacted} if stored["status"] == "ok" else stored

    def context(self, topic: str, **options: Any) -> Dict[str, Any]:
        """The current context of a topic (see RCI_CONTEXT.build for the options)."""
        return self.contexts.snapshot(topic, **options)
