"""Provider registry: the model providers an organisation has configured (KAN-11).

A record is {id, kind, base_url, models[], sensitivity_allowed[], enabled, allow_local, free_pool}
plus an API key that is encrypted at rest (velaris.core.vault, AES-256-GCM, the purpose names the
provider id so a sealed key cannot be moved to another record). Rules:

  * A key is never returned by any function here except `credentials()`, which only the model
    gateway calls. Everything else shows `key_last4`. A key never reaches the trace or a log.
  * Saving or rotating a key needs the vault master key; without it the call raises VaultKeyError
    and nothing is stored (fail closed). Records without a key (a local Ollama) need none.
  * The default for `sensitivity_allowed` is ["public"]: a provider must be told what it may see.
    A `free_pool` provider (OmniRoute and other aggregators that route to free tiers) can never be
    allowed "restricted"; the registry refuses to store that combination.
  * Plain JSON under VELARIS_DATA (metadata only), cross-process locked, atomic, schema_version 1
    (velaris.agentkit.state.JsonState); at most MAX_PROVIDERS records.

The gateway (velaris/intel/llm.py) resolves "<id>:<model>" names through this registry; the three
built-in names anthropic, bedrock and ollama keep reading their keys from the environment.
"""
from __future__ import annotations

import base64
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence
from urllib.parse import urlsplit

from velaris.agentkit.state import JsonState
from velaris.core import vault
from velaris.intel import trace

KINDS = ("openai_compatible", "anthropic", "bedrock", "ollama")
LEVELS = ("public", "internal", "restricted")
BUILTIN_IDS = frozenset({"anthropic", "bedrock", "ollama", "fake"})
MAX_PROVIDERS = 50
MAX_MODELS = 200
_ID = re.compile(r"[a-z][a-z0-9_-]{0,39}\Z")
_MODEL = re.compile(r"[\w.:/@+-]{1,120}\Z")

# Ready-made records. OmniRoute pools many providers' free tiers: its retention and training terms
# vary, so restricted data never goes there and it carries the "free pool" badge.
PRESETS: Dict[str, Dict[str, Any]] = {
    "omniroute": {"kind": "openai_compatible", "base_url": "http://localhost:20128/v1",
                  "sensitivity_allowed": ["public", "internal"], "allow_local": True, "free_pool": True},
}


class ProviderError(ValueError):
    """A provider record was refused. The message never contains a key."""


@dataclass(frozen=True)
class Provider:
    id: str
    kind: str
    base_url: str = ""
    models: Sequence[str] = ()
    sensitivity_allowed: Sequence[str] = ("public",)
    enabled: bool = True
    allow_local: bool = False
    free_pool: bool = False
    key_last4: str = ""
    has_key: bool = False
    created_at: float = 0.0
    updated_at: float = 0.0
    rotated_at: float = 0.0
    _sealed: str = field(default="", repr=False, compare=False)    # never shown; only credentials() opens it

    def public(self) -> Dict[str, Any]:
        return {"id": self.id, "kind": self.kind, "base_url": self.base_url, "models": list(self.models),
                "sensitivity_allowed": list(self.sensitivity_allowed), "enabled": self.enabled,
                "allow_local": self.allow_local, "free_pool": self.free_pool, "has_key": self.has_key,
                "key_last4": self.key_last4, "created_at": self.created_at, "updated_at": self.updated_at,
                "rotated_at": self.rotated_at}

    def accepts(self, level: str) -> bool:
        return self.enabled and level in self.sensitivity_allowed


def _state() -> JsonState:
    return JsonState("llm_providers", "providers.json", {"providers": {}}, version=1)


def _purpose(provider_id: str) -> str:
    return f"provider-key:{provider_id}"


def _seal(provider_id: str, key: str) -> str:
    return base64.b64encode(vault.seal_bytes(key.encode("utf-8"), _purpose(provider_id))).decode("ascii")


def _check_key(key: str) -> str:
    if not isinstance(key, str) or not (8 <= len(key.strip()) <= 4096) or any(c in key for c in "\r\n\x00"):
        raise ProviderError("the API key looks wrong (8 to 4096 characters, one line)")
    return key.strip()


def _check_url(kind: str, base_url: str) -> str:
    base_url = (base_url or "").strip().rstrip("/")
    if not base_url:
        if kind == "openai_compatible":
            raise ProviderError("base_url is required for openai_compatible")
        return ""
    parts = urlsplit(base_url)
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password \
            or parts.query or parts.fragment:
        raise ProviderError("base_url must be an http(s) URL without credentials, query or fragment")
    return base_url


def _check_levels(levels: Sequence[str]) -> List[str]:
    bad = [x for x in levels if x not in LEVELS]
    if bad or not isinstance(levels, (list, tuple)):
        raise ProviderError(f"sensitivity_allowed holds only {', '.join(LEVELS)}")
    return sorted(set(levels), key=LEVELS.index)


def _check_models(models: Sequence[str]) -> List[str]:
    if not isinstance(models, (list, tuple)) or len(models) > MAX_MODELS or not all(
            isinstance(m, str) and _MODEL.match(m) for m in models):
        raise ProviderError(f"models is a list of at most {MAX_MODELS} model names")
    return list(dict.fromkeys(models))


def _record(kind: str, base_url: str, models: Sequence[str], levels: Sequence[str], enabled: bool,
            allow_local: bool, free_pool: bool) -> Dict[str, Any]:
    if kind not in KINDS:
        raise ProviderError(f"kind must be one of {', '.join(KINDS)}")
    levels = _check_levels(levels)
    if free_pool and "restricted" in levels:
        raise ProviderError("a free-pool provider can never be allowed restricted data")
    return {"kind": kind, "base_url": _check_url(kind, base_url), "models": _check_models(models),
            "sensitivity_allowed": levels, "enabled": bool(enabled), "allow_local": bool(allow_local),
            "free_pool": bool(free_pool)}


def _from_row(pid: str, row: Dict[str, Any]) -> Provider:
    return Provider(id=pid, kind=row["kind"], base_url=row.get("base_url", ""),
                    models=tuple(row.get("models", ())),
                    sensitivity_allowed=tuple(row.get("sensitivity_allowed", ("public",))),
                    enabled=row.get("enabled", True), allow_local=row.get("allow_local", False),
                    free_pool=row.get("free_pool", False), key_last4=row.get("key_last4", ""),
                    has_key=bool(row.get("sealed_key")), created_at=row.get("created_at", 0.0),
                    updated_at=row.get("updated_at", 0.0), rotated_at=row.get("rotated_at", 0.0),
                    _sealed=row.get("sealed_key", ""))


def create(provider_id: str, *, kind: str, base_url: str = "", api_key: Optional[str] = None,
           models: Sequence[str] = (), sensitivity_allowed: Sequence[str] = ("public",),
           enabled: bool = True, allow_local: bool = False, free_pool: bool = False,
           by: str = "") -> Provider:
    if not _ID.match(provider_id or "") or provider_id in BUILTIN_IDS:
        raise ProviderError("id is 1-40 lowercase letters, digits, - or _, and not a built-in name")
    row = _record(kind, base_url, models, sensitivity_allowed, enabled, allow_local, free_pool)
    if api_key is not None:
        key = _check_key(api_key)
        row.update(sealed_key=_seal(provider_id, key), key_last4=key[-4:])   # VaultKeyError here: nothing stored
    row.update(created_at=time.time(), updated_at=time.time(), rotated_at=0.0)

    def add(d: Dict[str, Any]) -> None:
        if provider_id in d["providers"]:
            raise ProviderError(f"provider '{provider_id}' already exists")
        if len(d["providers"]) >= MAX_PROVIDERS:
            raise ProviderError(f"at most {MAX_PROVIDERS} providers")
        d["providers"][provider_id] = row
    _state().update(add)
    trace.append("providers", "create", {"id": provider_id, "kind": kind, "by": by, "has_key": api_key is not None,
                                         "sensitivity_allowed": row["sensitivity_allowed"]})
    return _from_row(provider_id, row)


def from_preset(provider_id: str, preset: str, *, api_key: Optional[str] = None, by: str = "",
                **overrides: Any) -> Provider:
    if preset not in PRESETS:
        raise ProviderError(f"unknown preset '{preset}'")
    return create(provider_id, api_key=api_key, by=by, **{**PRESETS[preset], **overrides})


def get(provider_id: str) -> Optional[Provider]:
    row = _state().load()["providers"].get(provider_id)
    return _from_row(provider_id, row) if row else None


def list_providers() -> List[Provider]:
    return [_from_row(k, v) for k, v in sorted(_state().load()["providers"].items())]


def update(provider_id: str, *, by: str = "", **changes: Any) -> Provider:
    """Change base_url, models, sensitivity_allowed, enabled, allow_local or free_pool. Not the key (see rotate)."""
    allowed = {"base_url", "models", "sensitivity_allowed", "enabled", "allow_local", "free_pool"}
    if set(changes) - allowed:
        raise ProviderError(f"cannot change: {', '.join(sorted(set(changes) - allowed))}")

    def edit(d: Dict[str, Any]) -> Dict[str, Any]:
        row = d["providers"].get(provider_id)
        if row is None:
            raise ProviderError(f"no provider '{provider_id}'")
        new = _record(row["kind"], changes.get("base_url", row.get("base_url", "")),
                      changes.get("models", row.get("models", ())),
                      changes.get("sensitivity_allowed", row.get("sensitivity_allowed", ("public",))),
                      changes.get("enabled", row.get("enabled", True)),
                      changes.get("allow_local", row.get("allow_local", False)),
                      changes.get("free_pool", row.get("free_pool", False)))
        row.update(new, updated_at=time.time())
        return row
    row = _state().update(edit)
    trace.append("providers", "update", {"id": provider_id, "by": by, "fields": sorted(changes)})
    return _from_row(provider_id, row)


def rotate(provider_id: str, new_key: str, *, by: str = "") -> Provider:
    """Replace the key. The old one is gone from disk as soon as the file is written."""
    key = _check_key(new_key)
    sealed = _seal(provider_id, key)

    def swap(d: Dict[str, Any]) -> Dict[str, Any]:
        row = d["providers"].get(provider_id)
        if row is None:
            raise ProviderError(f"no provider '{provider_id}'")
        row.update(sealed_key=sealed, key_last4=key[-4:], rotated_at=time.time(), updated_at=time.time())
        return row
    row = _state().update(swap)
    trace.append("providers", "rotate", {"id": provider_id, "by": by})
    return _from_row(provider_id, row)


def delete(provider_id: str, *, by: str = "") -> bool:
    gone = _state().update(lambda d: d["providers"].pop(provider_id, None)) is not None
    if gone:
        trace.append("providers", "delete", {"id": provider_id, "by": by})
    return gone


def credentials(provider_id: str) -> Optional[str]:
    """The plaintext key, for the model gateway only. None if the provider has none."""
    p = get(provider_id)
    if p is None or not p._sealed:
        return None
    return vault.open_bytes(base64.b64decode(p._sealed), _purpose(provider_id)).decode("utf-8")
