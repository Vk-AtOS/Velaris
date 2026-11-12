"""The assistant as a participant. It is a member of a channel like anyone else, and that membership is
all the permission it has. It never acts: it answers, drafts, or proposes, and a proposal is a
one-step run in velaris.intel.flow that waits for a named person other than the requester.

  Trigger     a message from a person that @[assistant:name]-mentions it in a channel it belongs to, or
              any message from a person in a direct conversation with it. Nothing else reaches it.
  Reads       the last few messages of the topic (or direct conversation). Each is screened by
              guard.scan(); one that reads like instructions is withheld; the rest are redacted
              (secrets, personal identifiers) and fenced with guard.wrap() so the model is told they
              are data. The request itself is screened too; a blocked request is not sent anywhere.
  Replies     answer: posted in the channel as the assistant (same limits and rate bucket as a person).
              draft ("draft ..." in the request): stored for the requester only, posted under THEIR
              name only if they confirm. propose: the model may name one registered tool; code checks
              the arguments, and the step waits for approval by the channel's owners/admins or a
              chat_admin, never the requester (four eyes). The approval names the call by its hash.
  Switches    the channel's ai_enabled flag and the organisation's `ai_enabled` setting, checked on
              every trigger and again when an approved step is about to run.
  Trace       who it acted for, channel and message ids, hashes of what it wrote. Never the text.
  No model    without a configured model it says nothing and tells only the requester: not_configured.
"""
from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from functools import partial
from typing import Any, Callable, Dict, List, Optional

from velaris.chat.core import sha
from velaris.chat.errors import ChatError
from velaris.chat.policy import CHAT_ADMIN, is_assistant, strip_mention
from velaris.chat.service import ChatService
from velaris.core.access import Caller
from velaris.intel import guard
from velaris.intel.flow import Flow, FlowError, Tool
from velaris.intel.llm import LLM, LLMError, extract_json

CONTEXT_MESSAGES = 20
_MODEL_ENV = ("VELARIS_MODEL", "ANTHROPIC_API_KEY", "AWS_BEARER_TOKEN_BEDROCK", "OLLAMA_MODEL")
WITHHELD = "[message withheld: it read like instructions to an AI]"


def llm_from_env() -> Optional[LLM]:
    """A real gateway only when the deployment configured a model; otherwise None (not_configured)."""
    return LLM() if any(os.environ.get(k) for k in _MODEL_ENV) else None


@dataclass
class ChatTool:
    """An action the assistant may propose. `check` validates and normalises the arguments for this requester
    (raise ChatError/ValueError to refuse); `run` performs it as the requester, only after approval."""
    name: str
    description: str
    params: Dict[str, str]
    check: Callable[[ChatService, Caller, Dict[str, Any]], Dict[str, Any]]
    run: Callable[[ChatService, Caller, Dict[str, Any]], Any]


def _check_post(svc: ChatService, who: Caller, args: Dict[str, Any]) -> Dict[str, Any]:
    cid, body = args.get("channel_id"), args.get("body")
    if not isinstance(cid, int) or isinstance(cid, bool) or not isinstance(body, str) or not body.strip():
        raise ValueError("channel_id (number) and body (text) are required")
    svc._require(who, svc._channel(who, cid), "post")          # the requester must be able to post there now
    return {"channel_id": cid, "body": body[:svc.limits.max_body], "topic": args.get("topic") or "general"}


def _run_post(svc: ChatService, who: Caller, args: Dict[str, Any]) -> Dict[str, Any]:
    msg = svc.post(who, args["channel_id"], args["body"], topic=args.get("topic"), ai_assisted=True)
    return {"posted_message_id": msg["id"], "channel_id": msg["channel_id"]}


POST_MESSAGE = ChatTool("post_message", "Post a message in another channel, as the requester",
                        {"channel_id": "number", "body": "text", "topic": "optional topic"}, _check_post, _run_post)


class Assistant:
    def __init__(self, svc: ChatService, *, llm: Optional[LLM] = None, tools: Optional[List[ChatTool]] = None,
                 flow_path: Optional[str] = None) -> None:
        self.svc, self.llm = svc, llm
        self.tools = {t.name: t for t in (tools if tools is not None else [POST_MESSAGE])}
        self.flow_path = flow_path or str(svc.store.path.parent / "chat_flow.db")

    # ── triggers ──────────────────────────────────────────────────────────────
    def handle(self, caller: Caller, message_id: int) -> List[Dict[str, Any]]:
        """Called after a person's message was committed. One outcome dict per assistant addressed."""
        svc = self.svc
        row = svc.store.message(caller.org, message_id)
        if row is None or row["sender"] != caller.id or row["deleted_at"] is not None or is_assistant(row["sender"]):
            return []
        ch = svc.store.channel(caller.org, row["channel_id"])
        if ch is None:
            return []
        members = svc.store.member_ids(ch["id"])
        named = set(json.loads(row["mentions"]))
        targets = [m for m in members if m in svc.assistants and (m in named or ch["kind"] == "direct")]
        return [self._run(caller, ch, row, a) for a in targets]

    def _notice(self, caller: Caller, ch: Any, row: Any, assistant: str, code: str) -> Dict[str, Any]:
        self.svc._audit("assistant.notice", assistant, caller.org, for_user=caller.id, channel=ch["id"],
                        message=row["id"], code=code)
        self.svc.hub.emit([caller.id], {"type": "assistant_notice", "channel_id": ch["id"], "message_id": row["id"],
                                        "assistant": assistant, "code": code}, org=caller.org)
        return {"assistant": assistant, "status": code}

    def _run(self, caller: Caller, ch: Any, row: Any, assistant: str) -> Dict[str, Any]:
        svc = self.svc
        if not svc.org_setting(caller.org, "ai_enabled") or not ch["ai_enabled"]:
            return self._notice(caller, ch, row, assistant, "disabled")
        if self.llm is None:
            return self._notice(caller, ch, row, assistant, "not_configured")
        request = strip_mention(row["body"], assistant) or "Summarise the recent messages."
        if guard.scan(request, source="chat.request").blocked:
            return self._notice(caller, ch, row, assistant, "blocked")
        prompt = self._prompt(caller, ch, row, assistant, request)
        try:
            reply = self.llm.complete(prompt, max_tokens=800, temperature=0.2, purpose="chat.assistant").text
        except LLMError:
            return self._notice(caller, ch, row, assistant, "model_error")
        try:
            data = extract_json(reply)
        except LLMError:
            data = None
        text, proposal = (str(data.get("text") or ""), data.get("propose")) if isinstance(data, dict) else (reply, None)
        text = guard.redact(text)[0].strip()[:svc.limits.max_body]
        out: Dict[str, Any] = {"assistant": assistant, "status": "empty"}
        if text:
            out = self._deliver(caller, ch, row, assistant, text, draft=request.lower().startswith("draft"))
        if isinstance(proposal, dict) and proposal:
            out["proposal"] = self._propose(caller, ch, row, assistant, proposal)
        elif not text:
            return self._notice(caller, ch, row, assistant, "empty")
        return out

    def _prompt(self, caller: Caller, ch: Any, row: Any, assistant: str, request: str) -> str:
        svc = self.svc
        where, args = "channel_id=? AND id<? AND deleted_at IS NULL AND erased=0", [ch["id"], row["id"]]
        if ch["kind"] in ("public", "private"):
            where, args = where + " AND topic=?", [*args, row["topic"]]
        rows = svc.store.all(f"SELECT id, sender, body FROM messages WHERE {where} ORDER BY id DESC LIMIT ?",
                             [*args, CONTEXT_MESSAGES])[::-1]
        lines = []
        for r in rows:
            blocked = guard.scan(r["body"], source=f"chat.message.{r['id']}").blocked
            lines.append(f"[{r['id']}] {r['sender']}: {WITHHELD if blocked else guard.redact(r['body'])[0]}")
        preamble, block = guard.wrap("\n".join(lines) or "(no earlier messages)",
                                     label="recent chat messages written by colleagues")
        tools = "\n".join(f"- {t.name}({', '.join(f'{k}: {v}' for k, v in t.params.items())}): {t.description}"
                          for t in self.tools.values()) or "(none)"
        return (f"You are {assistant}, an assistant inside company chat, working for {caller.id}. You can only reply with text "
                "or suggest one action; you cannot do anything yourself, and a suggested action waits for a person's approval.\n"
                f"{preamble}\n\n{block}\n\nRequest from {caller.id}: {guard.redact(request)[0]}\n\n"
                f"Actions you may suggest:\n{tools}\n\n"
                'Reply with JSON only: {"text": "<your reply>", "propose": null or {"tool": "<name>", "args": {...}}}. '
                "If you do not know, say so; do not invent facts.")

    # ── outcomes ──────────────────────────────────────────────────────────────
    def _deliver(self, caller: Caller, ch: Any, row: Any, assistant: str, text: str, *, draft: bool) -> Dict[str, Any]:
        svc = self.svc
        if not draft:
            try:
                msg = svc.post_as_assistant(caller.org, assistant, ch["id"], text, topic=row["topic"], reply_to=row["id"],
                                            for_user=caller.id)
            except ChatError as e:
                return self._notice(caller, ch, row, assistant, "post_refused:" + e.code)
            svc._audit("assistant.answer", assistant, caller.org, for_user=caller.id, channel=ch["id"], message=row["id"],
                       reply=msg["id"], reply_sha256=sha(text))
            return {"assistant": assistant, "status": "answered", "message_id": msg["id"]}
        draft_id = uuid.uuid4().hex
        with svc._write() as db:
            db.execute("INSERT INTO ai_drafts VALUES(?,?,?,?,?,?,?,?,?,?)", (draft_id, caller.org, ch["id"], row["topic"],
                       caller.id, assistant, text, "pending", svc.clock(), row["id"]))
            svc._audit("assistant.draft", assistant, caller.org, for_user=caller.id, channel=ch["id"], message=row["id"],
                       draft=draft_id, draft_sha256=sha(text))
            svc._notify([caller.id], {"type": "assistant_draft", "op": "new", "channel_id": ch["id"], "draft_id": draft_id,
                                      "topic": row["topic"], "body": text, "assistant": assistant}, caller.org)
        return {"assistant": assistant, "status": "draft", "draft_id": draft_id}

    def drafts(self, caller: Caller) -> List[Dict[str, Any]]:
        caller = self.svc._enter(caller)
        rows = self.svc.store.all("SELECT * FROM ai_drafts WHERE org=? AND requester=? AND status='pending' ORDER BY created_at",
                                  (caller.org, caller.id))
        return [{"draft_id": r["id"], "channel_id": r["channel_id"], "topic": r["topic"], "body": r["body"],
                 "assistant": r["assistant"]} for r in rows]

    def _draft(self, caller: Caller, draft_id: Any) -> Any:
        row = self.svc.store.one("SELECT * FROM ai_drafts WHERE id=? AND org=? AND requester=? AND status='pending'",
                                 (draft_id, caller.org, caller.id)) if isinstance(draft_id, str) else None
        if row is None:
            raise ChatError(404, "no_such_draft", "no such draft")             # other people's drafts do not exist for you
        return row

    def confirm_draft(self, caller: Caller, draft_id: Any, body: Optional[str] = None) -> Dict[str, Any]:
        """Post the draft under the requester's own name (optionally edited first). Their limits, their policy."""
        svc = self.svc
        caller = svc._enter(caller)
        row = self._draft(caller, draft_id)
        msg = svc.post(caller, row["channel_id"], row["body"] if body is None else body, topic=row["topic"], ai_assisted=True)
        with svc._write() as db:
            db.execute("UPDATE ai_drafts SET status='confirmed' WHERE id=?", (row["id"],))
            svc._audit("assistant.draft_confirmed", row["assistant"], caller.org, for_user=caller.id, draft=row["id"],
                       message=msg["id"])
        return msg

    def discard_draft(self, caller: Caller, draft_id: Any) -> None:
        svc = self.svc
        caller = svc._enter(caller)
        row = self._draft(caller, draft_id)
        with svc._write() as db:
            db.execute("UPDATE ai_drafts SET status='discarded' WHERE id=?", (row["id"],))
            svc._audit("assistant.draft_discarded", row["assistant"], caller.org, for_user=caller.id, draft=row["id"])

    # ── proposals: the approval path ──────────────────────────────────────────
    def _flow(self, who: Caller) -> Flow:
        tools = [Tool(t.name, partial(self._execute, t, who), t.description, dict(t.params), needs_approval=True)
                 for t in self.tools.values()]
        return Flow(tools, llm=self.llm, path=self.flow_path)

    def _execute(self, tool: ChatTool, who: Caller, **args: Any) -> Any:
        return tool.run(self.svc, who, args)

    def _propose(self, caller: Caller, ch: Any, row: Any, assistant: str, proposal: Dict[str, Any]) -> Dict[str, Any]:
        svc = self.svc
        tool, args = self.tools.get(str(proposal.get("tool"))), proposal.get("args", {})
        if tool is None or not isinstance(args, dict) or set(args) - set(tool.params):
            return {"status": self._notice(caller, ch, row, assistant, "invalid_proposal")["status"]}
        try:
            args = tool.check(svc, caller, args)
        except (ChatError, ValueError):
            return {"status": self._notice(caller, ch, row, assistant, "invalid_proposal")["status"]}
        approvers = [r["user_id"] for r in svc.store.all(
            "SELECT user_id FROM members WHERE channel_id=? AND user_id<>? AND (role IN ('owner','admin') OR ?)",
            (ch["id"], caller.id, int(ch["kind"] in ("direct", "group"))))
            if not is_assistant(r["user_id"])]
        meta = {"caller": {"id": caller.id, "org": caller.org, "roles": sorted(caller.roles)}, "assistant": assistant,
                "channel": ch["id"], "message": row["id"]}
        result = self._flow(caller).call(tool.name, args, actor=caller.id, meta=meta)
        with svc._write() as db:
            db.execute("INSERT INTO ai_proposals VALUES(?,?,?,?,?,?,?,?,?,?,?,?,NULL)", (
                result.run_id, caller.org, ch["id"], caller.id, json.dumps(sorted(caller.roles)), assistant, tool.name,
                result.pending["call_hash"], json.dumps(approvers), "pending", svc.clock(), row["id"]))
            svc._audit("assistant.propose", assistant, caller.org, for_user=caller.id, channel=ch["id"], message=row["id"],
                       run=result.run_id, tool=tool.name, call_hash=result.pending["call_hash"], approvers=approvers)
            svc._notify([caller.id, *approvers], {"type": "assistant_proposal", "op": "new", "channel_id": ch["id"],
                        "run_id": result.run_id, "tool": tool.name, "args": args, "call_hash": result.pending["call_hash"],
                        "requester": caller.id, "approvers": approvers}, caller.org)
        return {"status": "waiting_approval", "run_id": result.run_id, "call_hash": result.pending["call_hash"]}

    def proposals(self, caller: Caller) -> List[Dict[str, Any]]:
        """Pending proposals the caller made or may decide."""
        caller = self.svc._enter(caller)
        out = []
        for r in self.svc.store.all("SELECT * FROM ai_proposals WHERE org=? AND status='pending' ORDER BY created_at", (caller.org,)):
            approvers = json.loads(r["approvers"])
            if caller.id != r["requester"] and caller.id not in approvers and CHAT_ADMIN not in caller.roles:
                continue
            start = self._flow(caller).history(r["run_id"])[0]
            out.append({"run_id": r["run_id"], "channel_id": r["channel_id"], "tool": r["tool"], "args": start["direct"]["args"],
                        "call_hash": r["call_hash"], "requester": r["requester"], "approvers": approvers,
                        "assistant": r["assistant"]})
        return out

    def decide(self, caller: Caller, run_id: Any, call_hash: Any, approve: Any, note: str = "") -> Dict[str, Any]:
        svc = self.svc
        caller = svc._enter(caller)
        row = svc.store.one("SELECT * FROM ai_proposals WHERE run_id=? AND org=?", (run_id, caller.org)) if isinstance(run_id, str) else None
        if row is None or not isinstance(call_hash, str) or not isinstance(approve, bool) or not isinstance(note, str):
            raise ChatError(404, "no_such_proposal", "no such proposal")
        approvers = json.loads(row["approvers"])
        if row["requester"] == caller.id:
            svc._denied(caller, "proposal.decide", "four eyes", row["channel_id"])
            raise ChatError(403, "four_eyes", "an action must be approved by someone other than the person it is for")
        if caller.id not in approvers and CHAT_ADMIN not in caller.roles:
            svc._denied(caller, "proposal.decide", "not an approver", row["channel_id"])
            raise ChatError(404, "no_such_proposal", "no such proposal")
        if row["status"] != "pending":
            raise ChatError(409, "not_waiting", "this proposal was already decided")
        ch = svc.store.channel(caller.org, row["channel_id"])
        if approve and (not svc.org_setting(caller.org, "ai_enabled") or ch is None or not ch["ai_enabled"]):
            raise ChatError(409, "assistant_disabled", "the assistant is switched off here, so this cannot run")
        requester = Caller(id=row["requester"], org=row["org"], roles=frozenset(json.loads(row["requester_roles"])))
        flow = self._flow(requester)
        try:
            flow.decide(run_id, call_hash, approve=approve, by=caller.id, note=note[:500])
        except FlowError:
            raise ChatError(409, "not_waiting", "the proposal is not waiting for that step") from None
        final = flow.history(run_id)[-1]
        status = "rejected" if not approve else ("approved" if final.get("ok") else "failed")
        with svc._write() as db:
            db.execute("UPDATE ai_proposals SET status=?, decided_by=? WHERE run_id=?", (status, caller.id, run_id))
            svc._audit("assistant.decide", row["assistant"], caller.org, for_user=row["requester"], decided_by=caller.id,
                       run=run_id, call_hash=call_hash, approve=approve, outcome=status)
            svc._notify([row["requester"], *approvers, caller.id], {"type": "assistant_proposal", "op": "decided",
                        "channel_id": row["channel_id"], "run_id": run_id, "status": status, "decided_by": caller.id},
                        caller.org)
        return {"run_id": run_id, "status": status}
