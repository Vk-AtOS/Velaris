"""The autonomy policy table over HTTP (VEL-14), mounted on the Velaris API app.

  GET /autonomy                 {"modes": {class: mode}, "money_limit", "classes", "allowed_modes", "locked"}
  PUT /autonomy/{class}         {"mode": "auto" | "auto_notify" | "approval" | "forbidden"}: change one class

Governance admin (the organisation's owner/admin as mapped by the AetherOS gateway) only: the table decides which actions
run without a person. A class in `locked` refuses auto modes (400): loosening those is decided in code. Every call is
traced by `record` (class and mode only), and an accepted change is also written by autonomy.set_mode, stored in
<VELARIS_DATA>/agents/orchestration/autonomy.json.
"""
from __future__ import annotations

from functools import partial
from typing import Any, Callable, Dict, Tuple

from fastapi import FastAPI, Request

from velaris.core import access
from velaris.orchestration import autonomy


def mount(app: FastAPI, *, authed: Callable[..., Any], record: Callable[..., None], in_thread: Callable[..., Any],
          api_error: Any) -> None:
    async def admin(request: Request, action: str) -> Tuple[access.Caller, Dict[str, Any]]:
        caller, body = await authed(request)
        if not access.has_role(caller, access.GOVERNANCE_ADMINS):
            record(caller, f"autonomy.{action}", {"outcome": "denied"})
            raise api_error(403, "access_denied", "the autonomy table needs the governance_admin role")
        if body is not None and not isinstance(body, dict):
            raise api_error(400, "bad_body", "send a JSON object")
        return caller, body or {}

    def change(caller: access.Caller, cls: str, mode: str) -> None:
        with access.acting_as(caller):
            autonomy.set_mode(cls, mode, by=caller.id)

    @app.get("/autonomy")
    async def autonomy_get(request: Request) -> Dict[str, Any]:
        caller, _ = await admin(request, "read")
        record(caller, "autonomy.read", {"outcome": "ok"})
        t = autonomy.table()
        return {**t, "classes": list(autonomy.CLASSES), "allowed_modes": list(autonomy.MODES),
                "locked": sorted(autonomy.LOCKED)}

    @app.put("/autonomy/{cls}")
    async def autonomy_put(cls: str, request: Request) -> Dict[str, Any]:
        caller, body = await admin(request, "set")
        mode = body.get("mode")
        if cls not in autonomy.CLASSES or not isinstance(mode, str) or mode not in autonomy.MODES:
            record(caller, "autonomy.set", {"class": cls[:40], "outcome": "bad_request"})
            raise api_error(400, "bad_autonomy", "use a known action class and a mode from allowed_modes")
        if cls in autonomy.LOCKED and mode in ("auto", "auto_notify"):
            record(caller, "autonomy.set", {"class": cls, "mode": mode, "outcome": "locked"})
            raise api_error(400, "locked_class", f"'{cls}' always needs a human; it cannot be set to {mode}")
        await in_thread(partial(change, caller, cls, mode))
        record(caller, "autonomy.set", {"class": cls, "mode": mode, "outcome": "ok"})
        return {"class": cls, "mode": mode, "modes": autonomy.table()["modes"]}
