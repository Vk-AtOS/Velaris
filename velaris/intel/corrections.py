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
import re
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("velaris.intel.corrections")
MAX_BLOCK = 4000
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
          timeout: float = 5.0, transport: Optional[httpx.BaseTransport] = None) -> Dict[str, Any]:
    """{"ids": [...], "block": str}; empty when there is nothing relevant or Prime cannot be asked."""
    empty: Dict[str, Any] = {"ids": [], "block": ""}
    try:
        with httpx.Client(base_url=base_url.rstrip("/"), headers={"Authorization": f"Bearer {api_key}"},
                          timeout=timeout, transport=transport) as c:
            r = c.get("/prime/corrections/relevant",
                      params={"agent": agent, "action_type": action_type, "q": query[:2000], "k": k})
        r.raise_for_status()
        body = r.json()
        block = safe_block(body.get("prompt_block"))
        ids = [x["id"] for x in body.get("corrections", []) if isinstance(x, dict) and isinstance(x.get("id"), str)]
        return {"ids": ids[:k], "block": block} if block else empty
    except (httpx.HTTPError, ValueError, KeyError, AttributeError, TypeError) as e:
        logger.warning("corrections for %s/%s unavailable: %s", agent, action_type, type(e).__name__)
        return empty


def with_corrections(prompt: str, block: str) -> str:
    """The prompt followed by the corrections block (nothing added when there is none)."""
    return f"{prompt}\n\n{block}" if block else prompt


def report_outcome(base_url: str, api_key: str, ids: List[str], changed: bool, *, timeout: float = 5.0,
                   transport: Optional[httpx.BaseTransport] = None) -> bool:
    """Tell Prime whether the retrieved corrections changed what the agent proposed. Best effort."""
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
