"""Model provider management over HTTP, mounted on the Velaris API app (KAN-18).

  GET    /providers                   every provider (never a key: has_key and the last four characters)
  POST   /providers                   add one (also {"preset": "omniroute"})
  PUT    /providers/{id}              change base_url, models, sensitivity_allowed, enabled, allow_local, free_pool
  POST   /providers/{id}/rotate       {"api_key"}: replace the key
  DELETE /providers/{id}
  POST   /providers/{id}/test         one cheap call (list models); {ok, latency_s, error code}, never the provider's text
  GET    /providers/{id}/models       the catalogue entries
  POST   /providers/{id}/models/refresh
  GET    /providers/usage?days=7      per-day tokens, cost estimate and errors for the caller's organisation

All of it needs the model_admin role (the organisation's owner and admins, mapped by the AetherOS gateway): provider
settings change what every agent of the organisation may do and where its data goes (D7). Authentication and the
organisation check are the app's own (`authed`); each call is traced by `record` with ids and field names only.
"""
from __future__ import annotations

import re
from functools import partial
from typing import Any, Callable, Dict, Tuple

from fastapi import FastAPI, Request

from velaris.core import access, vault
from velaris.intel import catalogue, health, providers, usage

_ID = re.compile(r"[a-z][a-z0-9_-]{0,39}\Z")
_CREATE = {"kind", "base_url", "api_key", "models", "sensitivity_allowed", "enabled", "allow_local", "free_pool"}
_EDIT = {"base_url", "models", "sensitivity_allowed", "enabled", "allow_local", "free_pool"}


def mount(app: FastAPI, *, authed: Callable[..., Any], record: Callable[..., None], in_thread: Callable[..., Any],
          api_error: Any) -> None:
    async def admin(request: Request, action: str) -> Tuple[access.Caller, Dict[str, Any]]:
        caller, body = await authed(request)
        if not access.has_role(caller, access.MODEL_ADMINS):
            record(caller, f"providers.{action}", {"outcome": "denied"})
            raise api_error(403, "access_denied", "managing model providers needs the model_admin role")
        if body is not None and not isinstance(body, dict):
            raise api_error(400, "bad_body", "send a JSON object")
        return caller, body or {}

    def check_id(pid: str) -> str:
        if not _ID.match(pid or ""):
            raise api_error(400, "bad_provider", "unknown provider id")
        return pid

    async def run(caller: access.Caller, action: str, base: Dict[str, Any], fn: Callable[..., Any]) -> Any:
        """Off the event loop. ProviderError text is written for people and never holds a key."""
        try:
            out = await in_thread(fn)
        except providers.ProviderError as e:
            record(caller, f"providers.{action}", {**base, "outcome": "refused"})
            raise api_error(400, "bad_provider", str(e)[:200]) from None
        except vault.VaultKeyError:
            record(caller, f"providers.{action}", {**base, "outcome": "no_vault_key"})
            raise api_error(503, "vault_unavailable", "keys cannot be stored: the server has no encryption key set") from None
        record(caller, f"providers.{action}", {**base, "outcome": "ok"})
        return out

    @app.get("/providers/usage")
    async def providers_usage(request: Request) -> Dict[str, Any]:
        caller, _ = await admin(request, "usage")
        try:
            days = int(request.query_params.get("days", "7"))
        except ValueError:
            raise api_error(400, "bad_days", "days is a number") from None
        return {"days": await run(caller, "usage", {}, partial(usage.daily, days, org=caller.org)),
                "budget": usage.budget_for(caller.org), "month": usage.month_totals(caller.org)}

    @app.get("/providers")
    async def providers_list(request: Request) -> Dict[str, Any]:
        caller, _ = await admin(request, "list")
        rows = await run(caller, "list", {}, providers.list_providers)
        return {"providers": [p.public() for p in rows], "presets": sorted(providers.PRESETS),
                "kinds": list(providers.KINDS), "levels": list(providers.LEVELS)}

    @app.post("/providers")
    async def providers_create(request: Request) -> Dict[str, Any]:
        caller, body = await admin(request, "create")
        pid = check_id(str(body.get("id", "")))
        fields = {k: v for k, v in body.items() if k in _CREATE}
        preset = body.get("preset")
        fn = (partial(providers.from_preset, pid, preset, by=caller.id, **{k: v for k, v in fields.items()
                                                                           if k != "kind"})
              if preset else partial(providers.create, pid, by=caller.id, **{**fields, "kind": fields.get("kind", "")}))
        p = await run(caller, "create", {"id": pid, "fields": sorted(fields)}, fn)
        return {"provider": p.public()}

    @app.put("/providers/{pid}")
    async def providers_update(pid: str, request: Request) -> Dict[str, Any]:
        caller, body = await admin(request, "update")
        pid = check_id(pid)
        fields = {k: v for k, v in body.items() if k in _EDIT}
        p = await run(caller, "update", {"id": pid, "fields": sorted(fields)},
                      partial(providers.update, pid, by=caller.id, **fields))
        return {"provider": p.public()}

    @app.post("/providers/{pid}/rotate")
    async def providers_rotate(pid: str, request: Request) -> Dict[str, Any]:
        caller, body = await admin(request, "rotate")
        pid = check_id(pid)
        p = await run(caller, "rotate", {"id": pid},
                      partial(providers.rotate, pid, str(body.get("api_key", "")), by=caller.id))
        return {"provider": p.public()}

    @app.delete("/providers/{pid}")
    async def providers_delete(pid: str, request: Request) -> Dict[str, Any]:
        caller, _ = await admin(request, "delete")
        pid = check_id(pid)
        if not await run(caller, "delete", {"id": pid}, partial(providers.delete, pid, by=caller.id)):
            raise api_error(404, "not_found", "no such provider")
        return {"deleted": pid}

    @app.post("/providers/{pid}/test")
    async def providers_test(pid: str, request: Request) -> Dict[str, Any]:
        caller, _ = await admin(request, "test")
        pid = check_id(pid)
        return await run(caller, "test", {"id": pid}, partial(health.check, pid))

    @app.get("/providers/{pid}/models")
    async def providers_models(pid: str, request: Request) -> Dict[str, Any]:
        caller, _ = await admin(request, "models")
        pid = check_id(pid)
        return {"models": await run(caller, "models", {"id": pid}, partial(catalogue.query, provider=pid))}

    @app.post("/providers/{pid}/models/refresh")
    async def providers_refresh(pid: str, request: Request) -> Dict[str, Any]:
        caller, _ = await admin(request, "refresh")
        pid = check_id(pid)
        return await run(caller, "refresh", {"id": pid}, partial(catalogue.refresh, pid))
