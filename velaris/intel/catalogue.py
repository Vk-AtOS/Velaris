"""Model catalogue (KAN-13): what each configured model can do and what it costs.

An entry per "provider:model": context_window, supports_tools / supports_json / supports_vision,
languages_note, price_in_per_mtok / price_out_per_mtok (USD per million tokens), source
("manual" or "discovered"). Rules:

  * Prices and capabilities are CONFIGURATION. Nothing is guessed: whatever is unknown stays None
    and cost_estimate() then says None ("unknown"), never 0.
  * refresh(provider_id) lists the provider's models (GET {base_url}/models for openai_compatible,
    /api/tags for Ollama; other kinds keep their configured list), adds new ones with only what the
    provider itself reports, and NEVER overwrites a field somebody configured by hand. A model the
    provider no longer lists is marked listed=False, not deleted. A failed refresh keeps the old
    catalogue and records the error and a failure count per provider.
  * query() answers questions such as "which models can call tools and have at least 32k context?"
    and can be limited to what a sensitivity level may use (velaris.intel.policy).

Stored as JSON under VELARIS_DATA (schema_version 1, cross-process locked).
"""
from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional

import httpx

from velaris.agentkit.state import JsonState
from velaris.intel import openai_compat, policy, providers
from velaris.intel.errors import LLMError

FIELDS = ("context_window", "supports_tools", "supports_json", "supports_vision", "languages_note",
          "price_in_per_mtok", "price_out_per_mtok")
_NUMBERS = ("context_window", "price_in_per_mtok", "price_out_per_mtok")
_FLAGS = ("supports_tools", "supports_json", "supports_vision")
MAX_ENTRIES = 5000
REFRESH_TIMEOUT_S = 15.0


def _state() -> JsonState:
    return JsonState("llm_catalogue", "catalogue.json", {"models": {}, "refresh": {}}, version=1)


def _clean(fields: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for k, v in fields.items():
        if k not in FIELDS:
            raise ValueError(f"unknown catalogue field '{k}'")
        if v is None:
            out[k] = None
        elif k in _NUMBERS:
            if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0:
                raise ValueError(f"{k} must be a number of at least 0, or None for unknown")
            out[k] = v
        elif k in _FLAGS:
            if not isinstance(v, bool):
                raise ValueError(f"{k} must be true, false or None for unknown")
            out[k] = v
        else:
            out[k] = str(v)[:300]
    return out


def _blank(provider: str, model: str) -> Dict[str, Any]:
    return {"provider": provider, "model": model, **{f: None for f in FIELDS}, "source": "manual",
            "listed": True, "manual_fields": [], "updated_at": 0.0}


def configure(provider: str, model: str, **fields: Any) -> Dict[str, Any]:
    """Set fields by hand (they then survive every refresh). Unmentioned fields are left as they are."""
    clean = _clean(fields)

    def put(d: Dict[str, Any]) -> Dict[str, Any]:
        key = f"{provider}:{model}"
        if key not in d["models"] and len(d["models"]) >= MAX_ENTRIES:
            raise ValueError(f"at most {MAX_ENTRIES} catalogue entries")
        e = d["models"].setdefault(key, _blank(provider, model))
        e.update(clean, updated_at=time.time())
        e["manual_fields"] = sorted(set(e["manual_fields"]) | set(clean))
        return e
    return _state().update(put)


def get(name: str) -> Optional[Dict[str, Any]]:
    return _state().load()["models"].get(name)


def query(*, tools: Optional[bool] = None, json_mode: Optional[bool] = None, vision: Optional[bool] = None,
          min_context: Optional[int] = None, provider: Optional[str] = None,
          sensitivity: Optional[str] = None) -> List[Dict[str, Any]]:
    """Entries that satisfy every given condition. A condition on an unknown (None) value does not match."""
    out = []
    for e in _state().load()["models"].values():
        if not e.get("listed", True) or (provider and e["provider"] != provider):
            continue
        if tools is not None and e["supports_tools"] is not tools:
            continue
        if json_mode is not None and e["supports_json"] is not json_mode:
            continue
        if vision is not None and e["supports_vision"] is not vision:
            continue
        if min_context is not None and not (e["context_window"] and e["context_window"] >= min_context):
            continue
        if sensitivity is not None and not policy.permits(e["provider"], policy.effective(sensitivity)):
            continue
        out.append(e)
    return sorted(out, key=lambda e: (e["provider"], e["model"]))


def cost_estimate(name: str, tokens_in: int, tokens_out: int) -> Optional[float]:
    """USD for this many tokens, or None when either price is unknown."""
    e = get(name)
    if not e or e["price_in_per_mtok"] is None or e["price_out_per_mtok"] is None:
        return None
    return (tokens_in * e["price_in_per_mtok"] + tokens_out * e["price_out_per_mtok"]) / 1_000_000


def _discovered(raw: Dict[str, Any]) -> Dict[str, Any]:
    """What a provider's own model list tells us (OpenRouter-style fields); the rest stays unknown."""
    found: Dict[str, Any] = {}
    ctx = raw.get("context_length") or raw.get("context_window")
    if isinstance(ctx, int) and not isinstance(ctx, bool) and ctx > 0:
        found["context_window"] = ctx
    params = raw.get("supported_parameters")
    if isinstance(params, list):
        found["supports_tools"] = "tools" in params
    pricing = raw.get("pricing")
    if isinstance(pricing, dict):
        for src, dst in (("prompt", "price_in_per_mtok"), ("completion", "price_out_per_mtok")):
            try:
                found[dst] = float(pricing[src]) * 1_000_000
            except (KeyError, TypeError, ValueError):
                pass
    return found


def _remote_models(p: providers.Provider, fetch: Optional[Callable[..., List[Dict[str, Any]]]]) -> List[Dict[str, Any]]:
    if p.kind == "openai_compatible":
        return (fetch or openai_compat.list_models)(p.base_url, providers.credentials(p.id),
                                                    allow_local=p.allow_local, timeout=REFRESH_TIMEOUT_S)
    if p.kind == "ollama":
        url = (p.base_url or "http://127.0.0.1:11434").rstrip("/") + "/api/tags"
        try:
            r = httpx.get(url, timeout=REFRESH_TIMEOUT_S)
            r.raise_for_status()
            return [{"id": m["name"]} for m in r.json().get("models", [])]
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as e:
            raise LLMError(f"model list of '{p.id}' failed: {type(e).__name__}") from e
    return [{"id": m} for m in p.models]      # anthropic, bedrock: no list endpoint is used; the configured list is the catalogue


def refresh(provider_id: str, fetch: Optional[Callable[..., List[Dict[str, Any]]]] = None) -> Dict[str, Any]:
    """Update the catalogue from one provider. Never raises: returns {"ok", "added", "unlisted", "error"}."""
    p = providers.get(provider_id)
    if p is None or not p.enabled:
        return {"ok": False, "added": 0, "unlisted": 0, "error": "no such enabled provider"}
    try:
        remote = _remote_models(p, fetch)
        error = ""
    except LLMError as e:
        remote, error = [], str(e)[:200]

    def apply(d: Dict[str, Any]) -> Dict[str, int]:
        status = d["refresh"].setdefault(provider_id, {"failures": 0})
        if error:
            status.update(ok=False, error=error, failures=status["failures"] + 1, at=time.time())
            return {"added": 0, "unlisted": 0}
        status.update(ok=True, error="", failures=0, at=time.time())
        seen, added = set(), 0
        for raw in remote[:MAX_ENTRIES]:
            key = f"{provider_id}:{raw['id']}"
            seen.add(key)
            if key not in d["models"]:
                if len(d["models"]) >= MAX_ENTRIES:
                    break
                d["models"][key] = {**_blank(provider_id, raw["id"]), "source": "discovered"}
                added += 1
            e = d["models"][key]
            e["listed"] = True
            for f, v in _discovered(raw).items():
                if f not in e["manual_fields"]:          # a hand-set value always wins
                    e[f] = v
            e["updated_at"] = time.time()
        unlisted = 0
        for key, e in d["models"].items():
            if e["provider"] == provider_id and key not in seen and e.get("listed", True):
                e["listed"] = False
                unlisted += 1
        return {"added": added, "unlisted": unlisted}
    out = _state().update(apply)
    return {"ok": not error, "error": error, **out}


def refresh_all(fetch: Optional[Callable[..., List[Dict[str, Any]]]] = None) -> Dict[str, Dict[str, Any]]:
    """The refresh job: every enabled provider, one failure never stops the others."""
    return {p.id: refresh(p.id, fetch) for p in providers.list_providers() if p.enabled}


def refresh_status() -> Dict[str, Any]:
    return _state().load()["refresh"]
