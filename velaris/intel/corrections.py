"""Correction memory, agent side (KAN-24): what the agent's approvers changed before, put in its prompt.

The corrections live in Prime (AetherOS), next to the approvals they come from, per organisation and
pseudonymised. Before an agent proposes an action it asks Prime for the few most relevant corrections of its own
(same agent, same action type) and adds them to the prompt as QUOTED DATA, never as instructions.

Defence in depth: Prime already quotes and caps the block, and this module checks it again before use. A block
that is too long, has a fence other than its own, or holds control characters is dropped whole. Corrections are
advisory: if Prime cannot be asked, the agent goes on without them (and the failure is logged), it never blocks.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

import httpx

logger = logging.getLogger("velaris.intel.corrections")
MAX_BLOCK = 4000
LOOKUP_TIMEOUT_S = 1.0      # the wait for Prime on every model call (router.complete): a slow or down Prime costs at most this
ALSO_MAX = 5                # other proposer names sent with a lookup (AetherOS GET /prime/corrections/relevant, `also`)
_FENCE = "```"
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def safe_block(block: Any) -> str:
    """The block if it is shaped as Prime builds it, else ''."""
    if not isinstance(block, str) or not block or len(block) > MAX_BLOCK or _CONTROL.search(block):
        return ""
    if block.count(_FENCE) != 2 or not block.rstrip().endswith(_FENCE) or f"{_FENCE}corrections\n" not in block:
        return ""
    return block


def fetch(base_url: str, api_key: str, agent: str, action_type: str, query: str = "", *, k: int = 3,
          also: Sequence[str] = (), timeout: float = 5.0, transport: Optional[httpx.BaseTransport] = None) -> Dict[str, Any]:
    """{"ids": [...], "block": str}; empty when there is nothing relevant or Prime cannot be asked.

    `also` are other names the same proposer is filed under (e.g. the tools a flow uses): Prime looks them up too, up to
    ALSO_MAX of them."""
    empty: Dict[str, Any] = {"ids": [], "block": ""}
    params: Dict[str, Any] = {"agent": agent, "action_type": action_type, "q": query[:2000], "k": k}
    names = [str(a)[:128] for a in also if a][:ALSO_MAX]
    if names:
        params["also"] = names                                  # repeated query parameter: also=a&also=b
    try:
        with httpx.Client(base_url=base_url.rstrip("/"), headers={"Authorization": f"Bearer {api_key}"},
                          timeout=timeout, transport=transport) as c:
            r = c.get("/prime/corrections/relevant", params=params)
        r.raise_for_status()
        body = r.json()
        block = safe_block(body.get("prompt_block"))
        ids = [x["id"] for x in body.get("corrections", []) if isinstance(x, dict) and isinstance(x.get("id"), str)]
        return {"ids": ids[:k], "block": block} if block else empty
    except httpx.TimeoutException:
        logger.warning("corrections for %s/%s: Prime did not answer within %gs, continuing without them",
                       agent, action_type, timeout)
        return empty
    except (httpx.HTTPError, ValueError, KeyError, AttributeError, TypeError) as e:
        logger.warning("corrections for %s/%s unavailable: %s", agent, action_type, type(e).__name__)
        return empty


def for_purpose(purpose: str, query: str = "", key: Optional[Tuple[str, str]] = None,
                also: Sequence[str] = ()) -> Dict[str, Any]:
    """The corrections for a model call labelled `purpose` ("AGENT.action", or just "agent"); router.complete, the one place
    every model call passes, calls this. `key` is (agent, action_type) when Prime files the caller's proposals under other
    names than its purpose; `also` are further names it may be filed under. Empty when Prime is not configured
    (VELARIS_PRIME_URL and VELARIS_PRIME_API_KEY) or cannot be asked."""
    url, key_ = os.environ.get("VELARIS_PRIME_URL", ""), os.environ.get("VELARIS_PRIME_API_KEY", "")
    if not (url and key_ and (purpose or key)):
        return {"ids": [], "block": ""}
    agent, _, action = purpose.partition(".")
    agent, action = key or (agent, action or "model")
    return fetch(url, key_, agent, action, query, also=also, timeout=LOOKUP_TIMEOUT_S)


def with_corrections(prompt: str, block: str) -> str:
    """The prompt followed by the corrections block (nothing added when there is none)."""
    return f"{prompt}\n\n{block}" if block else prompt


def report_outcome(base_url: str, api_key: str, ids: List[str], changed: bool, *, timeout: float = 5.0,
                   transport: Optional[httpx.BaseTransport] = None) -> bool:
    """Tell Prime that these corrections were in the prompt of a proposal, and whether they changed its outcome. Best effort.

    `changed` is what the approver then did with that proposal: True when it was approved as proposed (what was corrected
    before did not have to be corrected again), False when it was rejected again."""
    if not ids:
        return False
    try:
        with httpx.Client(base_url=base_url.rstrip("/"), headers={"Authorization": f"Bearer {api_key}"},
                          timeout=timeout, transport=transport) as c:
            c.post("/prime/corrections/outcome", json={"ids": ids, "changed": changed}).raise_for_status()
        return True
    except httpx.HTTPError as e:
        logger.warning("could not report the correction outcome: %s", type(e).__name__)
        return False


def outcome(ids: Sequence[str], changed: bool) -> bool:
    """report_outcome to the Prime of this deployment (the same environment for_purpose reads). False when there is nothing to
    report or nowhere to report it. Flow calls this when the proposal that carried `ids` is decided."""
    url, key = os.environ.get("VELARIS_PRIME_URL", ""), os.environ.get("VELARIS_PRIME_API_KEY", "")
    return bool(url and key and ids) and report_outcome(url, key, list(ids), changed)
