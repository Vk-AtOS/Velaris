"""Assistant and admin/compliance routes (added to the chat router by api.py).

  GET  /chat/assistant/drafts                         the requester's pending drafts
  POST /chat/assistant/drafts/{id}/confirm            {body?} -> posts under the requester's own name
  POST /chat/assistant/drafts/{id}/discard
  GET  /chat/assistant/proposals                      pending proposals the caller made or may decide
  POST /chat/assistant/proposals/{run_id}/decide      {call_hash, approve, note?}   (not the requester)
  Channel kill switch: PATCH /chat/channels/{id} {"ai_enabled": false}; add/remove the assistant: members routes.

  chat_admin only:
  GET|PUT /chat/admin/settings                        {retention_days, purge_grace_days, ai_enabled, unfurl_hosts}
  PUT  /chat/admin/channels/{id}/hold                 {hold: bool}
  GET  /chat/admin/channels/{id}/export
  POST /chat/admin/sweep                              apply retention now
  POST /chat/admin/messages/{id}/erase
  GET  /chat/admin/users/{user_id}/export | POST /chat/admin/users/{user_id}/erase
  Any user: GET /chat/me/export (their own data).
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request

from velaris.chat.apiutil import Ctx, fields, run


def add_admin_routes(r: APIRouter, ctx: Ctx) -> None:
    @r.get("/assistant/drafts")
    async def drafts(request: Request) -> Any:
        caller, _, _ = await ctx.authed(request)
        return {"drafts": await run(ctx.assistant.drafts, caller)}

    @r.post("/assistant/drafts/{draft_id}/confirm")
    async def confirm(draft_id: str, request: Request) -> Any:
        caller, body, _ = await ctx.authed(request)
        return {"message": await run(ctx.assistant.confirm_draft, caller, draft_id, fields(body, {"body": False}).get("body"))}

    @r.post("/assistant/drafts/{draft_id}/discard")
    async def discard(draft_id: str, request: Request) -> Any:
        caller, _, _ = await ctx.authed(request)
        await run(ctx.assistant.discard_draft, caller, draft_id)
        return {"discarded": True}

    @r.get("/assistant/proposals")
    async def proposals(request: Request) -> Any:
        caller, _, _ = await ctx.authed(request)
        return {"proposals": await run(ctx.assistant.proposals, caller)}

    @r.post("/assistant/proposals/{run_id}/decide")
    async def decide(run_id: str, request: Request) -> Any:
        caller, body, _ = await ctx.authed(request)
        f = fields(body, {"call_hash": True, "approve": True, "note": False})
        return await run(ctx.assistant.decide, caller, run_id, f["call_hash"], f["approve"], f.get("note", ""))

    @r.get("/admin/settings")
    async def get_settings(request: Request) -> Any:
        caller, _, _ = await ctx.authed(request)
        return await run(ctx.svc.org_settings, caller)

    @r.put("/admin/settings")
    async def put_settings(request: Request) -> Any:
        caller, body, _ = await ctx.authed(request)
        return await run(ctx.svc.set_org_settings, caller, body)

    @r.put("/admin/channels/{channel_id}/hold")
    async def hold(channel_id: int, request: Request) -> Any:
        caller, body, _ = await ctx.authed(request)
        return await run(ctx.svc.set_legal_hold, caller, channel_id, fields(body, {"hold": True})["hold"])

    @r.get("/admin/channels/{channel_id}/export")
    async def export_channel(channel_id: int, request: Request) -> Any:
        caller, _, _ = await ctx.authed(request)
        return await run(ctx.svc.export_channel, caller, channel_id)

    @r.post("/admin/sweep")
    async def sweep(request: Request) -> Any:
        caller, _, _ = await ctx.authed(request)
        await run(ctx.svc._admin, caller, "sweep")
        return await run(ctx.svc.sweep, caller.org, by=caller.id)

    @r.post("/admin/messages/{message_id}/erase")
    async def erase_message(message_id: int, request: Request) -> Any:
        caller, _, _ = await ctx.authed(request)
        await run(ctx.svc.erase_message, caller, message_id)
        return {"erased": True}

    @r.get("/admin/users/{user_id}/export")
    async def export_user(user_id: str, request: Request) -> Any:
        caller, _, _ = await ctx.authed(request)
        return await run(ctx.svc.export_user, caller, user_id)

    @r.post("/admin/users/{user_id}/erase")
    async def erase_user(user_id: str, request: Request) -> Any:
        caller, _, _ = await ctx.authed(request)
        return await run(ctx.svc.erase_user, caller, user_id)

    @r.get("/me/export")
    async def export_me(request: Request) -> Any:
        caller, _, _ = await ctx.authed(request)
        return await run(ctx.svc.export_user, caller, None)
