"""/integrations/atlassian/...: each person connects their own Atlassian account (OAuth 2.0 3LO, KAN-73). Signed like every API call.

  GET    /integrations/atlassian/status      {configured, connected, site, scope}
  POST   /integrations/atlassian/connect     -> {"authorize_url"}: send the person's browser there (the AetherOS UI does)
  GET    /integrations/atlassian/callback    ?code=&state=  the consent page redirects back through AetherOS to here, as the same person
  DELETE /integrations/atlassian             the person disconnects (their tokens are forgotten)
  POST   /integrations/atlassian/revoke      {"user_id"}  hr_admin or governance_admin: offboarding
Errors are {"error": {"code", "message"}} with codes only (never tokens or Atlassian's text).
"""
from __future__ import annotations

from typing import Any, Callable, Optional

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from velaris.core.atlassian_oauth import OAuth, OAuthError

REVOKERS = frozenset({"hr_admin", "governance_admin"})
_STATUS = {"not_configured": 503, "state_invalid": 400, "exchange_failed": 400, "busy": 429, "network": 502, "blocked": 502,
           "bad_response": 502, "redirect_refused": 502}


def mount_atlassian(app: FastAPI, authed: Callable, record: Callable, in_thread: Callable, oauth: Optional[OAuth] = None) -> OAuth:
    oa = oauth or OAuth()

    def err(code: str, status: int, message: str = "") -> JSONResponse:
        return JSONResponse({"error": {"code": code, "message": message or code.replace("_", " ")}}, status_code=status)

    async def guarded(request: Request, op: str, fn: Callable[[Any, Any], Any], *, roles: Optional[frozenset] = None) -> JSONResponse:
        caller, body = await authed(request)
        record(caller, f"atlassian.{op}", {})
        if roles is not None and not caller.roles & roles:
            return err("forbidden", 403, "this needs an HR or governance administrator")
        try:
            return JSONResponse(await in_thread(lambda: fn(caller, body)))
        except OAuthError as e:
            return err(e.code, _STATUS.get(e.code, 400))

    @app.get("/integrations/atlassian/status")
    async def status(request: Request) -> JSONResponse:
        return await guarded(request, "status", lambda c, b: oa.status(c))

    @app.post("/integrations/atlassian/connect")
    async def connect(request: Request) -> JSONResponse:
        return await guarded(request, "connect", lambda c, b: {"authorize_url": oa.authorize_url(c)})

    @app.get("/integrations/atlassian/callback")
    async def callback(request: Request) -> JSONResponse:
        q = request.query_params
        return await guarded(request, "callback", lambda c, b: oa.exchange(c, q.get("code"), q.get("state")))

    @app.delete("/integrations/atlassian")
    async def disconnect(request: Request) -> JSONResponse:
        return await guarded(request, "disconnect", lambda c, b: {"disconnected": oa.revoke_user(c.org, c.id, by=c.id)})

    @app.post("/integrations/atlassian/revoke")
    async def revoke(request: Request) -> JSONResponse:
        def go(c: Any, b: Any) -> Any:
            uid = b.get("user_id") if isinstance(b, dict) else None
            if not isinstance(uid, str) or not 0 < len(uid) <= 200:
                raise OAuthError("state_invalid")
            return {"revoked": oa.revoke_user(c.org, uid, by=c.id)}
        return await guarded(request, "revoke", go, roles=REVOKERS)
    return oa
