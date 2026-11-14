"""The chat HTTP surface, mounted by velaris.api.app under /chat. Authenticated like the rest of the API
(signed by the gateway, identity assertion = the user). Errors are {"error": {"code", "message"}}.

  GET    /chat/health                                   liveness, no authentication
  POST   /chat/register                                 -> {queue_id, last_event_id, snapshot}
  GET    /chat/events?queue_id&last_event_id&timeout    long poll -> {events:[...]}
  GET    /chat/events/stream?queue_id&last_event_id&duration   the same stream as Server-Sent Events
  DELETE /chat/queues/{queue_id}
  GET    /chat/channels | /chat/channels/public         joined channels | directory of public ones
  POST   /chat/channels                                 {kind, name?, members?}
  GET|PATCH /chat/channels/{id}                         PATCH {name?, archived?, retention_days?, ai_enabled?}
  POST   /chat/channels/{id}/join | /leave
  POST   /chat/channels/{id}/members                    {user_id}   (also assistants: admins only)
  DELETE /chat/channels/{id}/members/{user_id}
  PUT    /chat/channels/{id}/members/{user_id}/role     {role}
  GET    /chat/channels/{id}/messages?topic&before&after&limit&thread
  POST   /chat/channels/{id}/messages                   {body, topic?, local_id?, reply_to?, attachments?}
  GET    /chat/channels/{id}/topics | /pins
  POST   /chat/channels/{id}/read                       {up_to?}
  PUT    /chat/channels/{id}/draft                      {topic?, body}      GET /chat/drafts
  PATCH|DELETE /chat/messages/{id}                      {body} | soft delete
  GET    /chat/messages/{id}/history | /unfurl
  PUT|DELETE /chat/messages/{id}/reactions/{emoji}
  PUT|DELETE /chat/messages/{id}/pin
  GET    /chat/search?q&channel_id&limit
  POST   /chat/files?name&content_type (raw body)       GET /chat/files/{sha256}
Assistant and admin routes: api_admin.py.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, AsyncIterator, Optional
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse

from velaris.api.auth import Verifier
from velaris.chat.api_admin import add_admin_routes
from velaris.chat.apiutil import ChatRoute, Ctx, fields, query_float, query_int, run
from velaris.chat.assistant import Assistant
from velaris.chat.errors import ChatError
from velaris.chat.events import SSE_KEEPALIVE, sse_frame
from velaris.chat.service import ChatService
from velaris.core.access import Caller
from velaris.intel.llm import LLM

logger = logging.getLogger("velaris.chat.api")
MAX_STREAM_S = 300.0
KEEPALIVE_S = 15.0
POLL_S = 0.25            # how often an open stream looks for new events


def chat_router(verifier: Verifier, org: str, *, service: Optional[ChatService] = None,
                assistant: Optional[Assistant] = None, llm: Optional[LLM] = None) -> APIRouter:
    ctx = Ctx(verifier, org, service=service, assistant=assistant, llm=llm)
    r = APIRouter(prefix="/chat", route_class=ChatRoute)

    def assist(caller: Caller, message_id: int) -> None:
        try:
            ctx.assistant.handle(caller, message_id)
        except Exception as e:      # a background job must not take the server down; the person's message is already saved
            logger.warning("assistant run failed: %s", type(e).__name__)

    @r.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    # ── delivery ──────────────────────────────────────────────────────────────
    @r.post("/register")
    async def register(request: Request) -> Any:
        caller, _, _ = await ctx.authed(request)
        return await run(ctx.svc.register, caller)

    @r.get("/events")
    async def events(request: Request) -> Any:
        caller, _, _ = await ctx.authed(request)
        last = query_int(request, "last_event_id", -1)
        events = await run(ctx.svc.events, caller, request.query_params.get("queue_id"), last,
                           query_float(request, "timeout", 0.0))
        return {"events": events}

    @r.get("/events/stream")
    async def stream(request: Request) -> Any:
        caller, _, _ = await ctx.authed(request)
        qid = request.query_params.get("queue_id")
        acked = query_int(request, "last_event_id", None)
        if acked is None:
            header = request.headers.get("last-event-id", "")
            acked = int(header) if header.lstrip("-").isdigit() else -1
        duration = min(max(query_float(request, "duration", 55.0), 0.05), MAX_STREAM_S)
        await run(ctx.svc.events, caller, qid, acked, 0.0, acked)        # a bad queue is a JSON error, not a broken stream

        async def frames() -> AsyncIterator[bytes]:
            # An async generator: between polls the stream awaits a sleep and holds NO worker thread. (A sync
            # generator parked a thread for the whole stream, so ~40 open streams starved every other request.)
            end, cursor = time.monotonic() + duration, acked
            beat = float("-inf")        # the first idle poll sends a heartbeat at once, then one per KEEPALIVE_S
            while (left := end - time.monotonic()) > 0:
                try:
                    batch = await run(ctx.svc.events, caller, qid, cursor, 0.0, acked)
                except ChatError as e:
                    yield sse_frame({"id": cursor + 1, "type": "error", "code": e.code})
                    return
                if not batch and time.monotonic() - beat >= KEEPALIVE_S:
                    beat = time.monotonic()
                    yield SSE_KEEPALIVE
                for ev in batch:
                    yield sse_frame(ev)
                    cursor = ev["id"]
                if not batch:
                    await asyncio.sleep(min(POLL_S, max(left, 0.0)))
        return StreamingResponse(frames(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @r.delete("/queues/{queue_id}")
    async def drop_queue(queue_id: str, request: Request) -> Any:
        caller, _, _ = await ctx.authed(request)
        return {"deleted": await run(ctx.svc.drop_queue, caller, queue_id)}

    # ── channels and members ──────────────────────────────────────────────────
    @r.get("/channels")
    async def channels(request: Request) -> Any:
        caller, _, _ = await ctx.authed(request)
        return {"channels": await run(ctx.svc.list_channels, caller)}

    @r.get("/channels/public")
    async def public(request: Request) -> Any:
        caller, _, _ = await ctx.authed(request)
        return {"channels": await run(ctx.svc.list_public, caller)}

    @r.post("/channels")
    async def create_channel(request: Request) -> Any:
        caller, body, _ = await ctx.authed(request)
        f = fields(body, {"kind": True, "name": False, "members": False})
        out = await run(ctx.svc.create_channel, caller, f["kind"], f.get("name"), f.get("members", []))
        return JSONResponse(out, status_code=201 if out.get("created") else 200)

    @r.get("/channels/{channel_id}")
    async def get_channel(channel_id: int, request: Request) -> Any:
        caller, _, _ = await ctx.authed(request)
        return await run(ctx.svc.get_channel, caller, channel_id)

    @r.patch("/channels/{channel_id}")
    async def update_channel(channel_id: int, request: Request) -> Any:
        caller, body, _ = await ctx.authed(request)
        return await run(ctx.svc.update_channel, caller, channel_id, body)

    @r.post("/channels/{channel_id}/join")
    async def join(channel_id: int, request: Request) -> Any:
        caller, _, _ = await ctx.authed(request)
        return await run(ctx.svc.join, caller, channel_id)

    @r.post("/channels/{channel_id}/leave")
    async def leave(channel_id: int, request: Request) -> Any:
        caller, _, _ = await ctx.authed(request)
        await run(ctx.svc.leave, caller, channel_id)
        return {"left": True}

    @r.post("/channels/{channel_id}/members")
    async def add_member(channel_id: int, request: Request) -> Any:
        caller, body, _ = await ctx.authed(request)
        return await run(ctx.svc.add_member, caller, channel_id, fields(body, {"user_id": True})["user_id"])

    @r.delete("/channels/{channel_id}/members/{user_id}")
    async def remove_member(channel_id: int, user_id: str, request: Request) -> Any:
        caller, _, _ = await ctx.authed(request)
        await run(ctx.svc.remove_member, caller, channel_id, user_id)
        return {"removed": True}

    @r.put("/channels/{channel_id}/members/{user_id}/role")
    async def set_role(channel_id: int, user_id: str, request: Request) -> Any:
        caller, body, _ = await ctx.authed(request)
        return await run(ctx.svc.set_role, caller, channel_id, user_id, fields(body, {"role": True})["role"])

    # ── messages ──────────────────────────────────────────────────────────────
    @r.get("/channels/{channel_id}/messages")
    async def history(channel_id: int, request: Request) -> Any:
        caller, _, _ = await ctx.authed(request)
        return await run(ctx.svc.history, caller, channel_id, topic=request.query_params.get("topic"),
                         before=query_int(request, "before"), after=query_int(request, "after"),
                         limit=query_int(request, "limit", 50), thread=query_int(request, "thread"))

    @r.post("/channels/{channel_id}/messages")
    async def post_message(channel_id: int, request: Request, tasks: BackgroundTasks) -> Any:
        caller, body, _ = await ctx.authed(request)
        f = fields(body, {"body": True, "topic": False, "local_id": False, "reply_to": False, "attachments": False})
        msg = await run(ctx.svc.post, caller, channel_id, f["body"], topic=f.get("topic"), local_id=f.get("local_id"),
                        reply_to=f.get("reply_to"), attachments=f.get("attachments", []))
        if msg.pop("duplicate", False):
            return JSONResponse({"message": msg, "duplicate": True}, status_code=200)
        tasks.add_task(assist, caller, msg["id"])
        return JSONResponse({"message": msg}, status_code=201)

    @r.get("/channels/{channel_id}/topics")
    async def topics(channel_id: int, request: Request) -> Any:
        caller, _, _ = await ctx.authed(request)
        return {"topics": await run(ctx.svc.topics, caller, channel_id)}

    @r.get("/channels/{channel_id}/pins")
    async def pins(channel_id: int, request: Request) -> Any:
        caller, _, _ = await ctx.authed(request)
        return {"messages": await run(ctx.svc.pins, caller, channel_id)}

    @r.post("/channels/{channel_id}/read")
    async def mark_read(channel_id: int, request: Request) -> Any:
        caller, body, _ = await ctx.authed(request)
        return {"last_read_id": await run(ctx.svc.mark_read, caller, channel_id, fields(body, {"up_to": False}).get("up_to"))}

    @r.put("/channels/{channel_id}/draft")
    async def set_draft(channel_id: int, request: Request) -> Any:
        caller, body, _ = await ctx.authed(request)
        f = fields(body, {"body": True, "topic": False})
        await run(ctx.svc.set_draft, caller, channel_id, f.get("topic"), f["body"])
        return {"saved": True}

    @r.get("/drafts")
    async def drafts(request: Request) -> Any:
        caller, _, _ = await ctx.authed(request)
        return {"drafts": await run(ctx.svc.drafts, caller)}

    @r.patch("/messages/{message_id}")
    async def edit(message_id: int, request: Request) -> Any:
        caller, body, _ = await ctx.authed(request)
        return {"message": await run(ctx.svc.edit, caller, message_id, fields(body, {"body": True})["body"])}

    @r.delete("/messages/{message_id}")
    async def delete(message_id: int, request: Request) -> Any:
        caller, _, _ = await ctx.authed(request)
        await run(ctx.svc.delete, caller, message_id)
        return {"deleted": True}

    @r.get("/messages/{message_id}/history")
    async def edit_history(message_id: int, request: Request) -> Any:
        caller, _, _ = await ctx.authed(request)
        return {"versions": await run(ctx.svc.edit_history, caller, message_id)}

    @r.get("/messages/{message_id}/unfurl")
    async def unfurl(message_id: int, request: Request) -> Any:
        caller, _, _ = await ctx.authed(request)
        return {"links": await run(ctx.svc.unfurl, caller, message_id)}

    @r.put("/messages/{message_id}/reactions/{emoji}")
    async def react(message_id: int, emoji: str, request: Request) -> Any:
        caller, _, _ = await ctx.authed(request)
        await run(ctx.svc.react, caller, message_id, emoji, True)
        return {"ok": True}

    @r.delete("/messages/{message_id}/reactions/{emoji}")
    async def unreact(message_id: int, emoji: str, request: Request) -> Any:
        caller, _, _ = await ctx.authed(request)
        await run(ctx.svc.react, caller, message_id, emoji, False)
        return {"ok": True}

    @r.put("/messages/{message_id}/pin")
    async def pin(message_id: int, request: Request) -> Any:
        caller, _, _ = await ctx.authed(request)
        await run(ctx.svc.pin, caller, message_id, True)
        return {"pinned": True}

    @r.delete("/messages/{message_id}/pin")
    async def unpin(message_id: int, request: Request) -> Any:
        caller, _, _ = await ctx.authed(request)
        await run(ctx.svc.pin, caller, message_id, False)
        return {"pinned": False}

    @r.get("/search")
    async def search(request: Request) -> Any:
        caller, _, _ = await ctx.authed(request)
        return {"messages": await run(ctx.svc.search, caller, request.query_params.get("q"),
                                      channel_id=query_int(request, "channel_id"), limit=query_int(request, "limit", 20))}

    # ── files ─────────────────────────────────────────────────────────────────
    @r.post("/files")
    async def upload(request: Request) -> Any:
        limit = ctx.svc.limits.max_file_bytes
        caller, _, data = await ctx.authed(request, max_body=limit, parse=False)
        out = await run(ctx.svc.upload, caller, request.query_params.get("name"),
                        request.query_params.get("content_type") or request.headers.get("content-type"), data)
        return JSONResponse(out, status_code=201)

    @r.get("/files/{digest}")
    async def download(digest: str, request: Request) -> Response:
        caller, _, _ = await ctx.authed(request)
        meta, data = await run(ctx.svc.download, caller, digest)
        return Response(data, media_type=meta["content_type"], headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(meta['name'])}",
            "X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store",
            "Content-Security-Policy": "default-src 'none'; sandbox"})

    add_admin_routes(r, ctx)
    return r

