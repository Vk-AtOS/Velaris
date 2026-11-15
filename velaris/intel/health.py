"""Provider health: one cheap call per enabled provider, with a result that is safe to show (KAN-17, KAN-18).

check() lists the provider's models (GET {base_url}/models for openai_compatible, /api/tags for Ollama): a
call that costs nothing and sends no user data. The result is {ok, latency_s, error} where `error` is a short
fixed code, never the provider's own error text (it can echo a key or an internal host). sweep() checks all
enabled providers and logs/traces the ones that are down; it is run by the API's background jobs.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, List, Optional

from velaris.intel import catalogue, providers, trace
from velaris.intel.errors import LLMError, PolicyRefused, Retryable

logger = logging.getLogger("velaris.intel.health")
TIMEOUT_S = 5.0


def _code(e: Exception) -> str:
    text = str(e)
    if isinstance(e, Retryable):
        return "timeout" if "timed out" in text else "unavailable"
    if "refused" in text or "allow_local" in text:
        return "address_not_allowed"
    if " 401" in text or " 403" in text:
        return "key_rejected"
    return "failed"


def check(provider_id: str, fetch: Optional[Callable[..., List[Dict[str, Any]]]] = None) -> Dict[str, Any]:
    p = providers.get(provider_id)
    if p is None:
        return {"ok": False, "latency_s": 0.0, "error": "no_such_provider"}
    start = time.time()
    try:
        old = catalogue.REFRESH_TIMEOUT_S
        catalogue.REFRESH_TIMEOUT_S = TIMEOUT_S      # same path as the catalogue refresh, with the short timeout
        try:
            n = len(catalogue._remote_models(p, fetch))
        finally:
            catalogue.REFRESH_TIMEOUT_S = old
        return {"ok": True, "latency_s": round(time.time() - start, 3), "error": "", "models": n}
    except (LLMError, PolicyRefused) as e:
        return {"ok": False, "latency_s": round(time.time() - start, 3), "error": _code(e)}


def sweep(fetch: Optional[Callable[..., List[Dict[str, Any]]]] = None) -> Dict[str, Dict[str, Any]]:
    out = {p.id: check(p.id, fetch) for p in providers.list_providers() if p.enabled}
    for pid, r in out.items():
        if not r["ok"]:
            logger.warning("model provider %s is not reachable: %s", pid, r["error"])
            trace.append("providers", "health.down", {"id": pid, "error": r["error"]})
    return out
