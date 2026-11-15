"""The assistant as a participant. It is a member of a channel like anyone else, and that membership is
all the permission it has. It never acts: it answers, drafts, or proposes, and a proposal is a
one-step run in velaris.intel.flow that runs only with two keys: the requester's and a second person's.

  Trigger     a message from a person that @[assistant:name]-mentions it in a channel it belongs to, or
              any message from a person in a direct conversation with it. Nothing else reaches it.
  Reads       the last few messages of the topic (or direct conversation). Each is screened by
              guard.scan(); one that reads like instructions is withheld; the rest are redacted
              (secrets, personal identifiers) and fenced with guard.wrap() so the model is told they
              are data. The request itself is screened too; a blocked request is not sent anywhere.
  Replies     answer: posted in the channel as the assistant (same limits and rate bucket as a person).
              draft ("draft ..." in the request): stored for the requester only, posted under THEIR
              name only if they confirm. propose: the model may name one registered tool; code checks
              the arguments. The step runs as the requester, so it needs BOTH keys, each naming the call hash:
                1. the requester confirms it:  POST /chat/assistant/proposals/{run_id}/confirm {call_hash}
                   (once; a different or old hash is refused), and
                2. a second person approves it: POST /chat/assistant/proposals/{run_id}/decide, refused
                   with `requester_not_confirmed` until key 1 is turned. Either side may reject at any time.
              Who may be the second person: channel owners/admins (public/private channels only) and
              chat_admins who have used chat, minus the requester and minus anyone who wrote a message in
              the context the model read (their ids are kept on the proposal, never their text; AI text keeps its own authors,
              also through a confirmed draft or an approved run). If some AI text lost its provenance the set is unknown
              (`*`): only a chat_admin who has not posted in the topic lately may approve. In direct
              and group conversations only chat_admins qualify. Nobody left: status `no_eligible_approver`
              and the requester gets an assistant_notice. Proposals from before this rule: `needs_reconfirm`.
  Events      assistant_proposal op=confirm goes to the requester only (the "confirm this" card). Approvers
              get op=new only after the requester confirmed. op=decided ends it.
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
from typing import Any, Callable, Dict, List, Optional, Sequence

from velaris.chat.core import sha
from velaris.chat.errors import ChatError
from velaris.chat.policy import CHAT_ADMIN, is_assistant, strip_mention
from velaris.chat.service import ChatService
from velaris.core.access import Caller
from velaris.intel import guard
from velaris.intel.flow import Flow, FlowError, Tool, call_hash
from velaris.intel.llm import LLM, LLMError, extract_json

CONTEXT_MESSAGES = 20
_MODEL_ENV = ("VELARIS_MODEL", "ANTHROPIC_API_KEY", "AWS_BEARER_TOKEN_BEDROCK", "OLLAMA_MODEL")
UNKNOWN = "*"        # in a context-author set: some AI text's provenance is lost, so who steered it is unknown
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
    msg = svc.post(who, args["channel_id"], args["body"], topic=args.get("topic"), ai_assisted=True,
                   context_authors=[*args.get("context_authors", [UNKNOWN]), who.id])
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

    def _still_allowed(self, caller: Caller, channel_id: int, assistant: str, *actions: str) -> Optional[Any]:
        """The channel as it is NOW if the requester may still do `actions` there, the assistant is still a member and
        the switches are still on; else None. The work runs in the background, so nothing stored is trusted."""
        svc = self.svc
        ch = svc.store.channel(caller.org, channel_id)
        if ch is None or not ch["ai_enabled"] or not svc.org_setting(caller.org, "ai_enabled") \
                or svc.store.role(ch["id"], assistant) is None:
            return None
        try:
            for action in actions:
                svc._require(caller, ch, action)
        except ChatError:
            return None
        return ch

    def _refused(self, caller: Caller, ch: Any, row: Any, assistant: str) -> Dict[str, Any]:
        """Access was lost between the request and the work: do nothing, tell nobody, leave a trace."""
        self.svc._audit("assistant.notice", assistant, caller.org, for_user=caller.id, channel=ch["id"], message=row["id"],
                        code="no_longer_allowed")
        return {"assistant": assistant, "status": "no_longer_allowed"}

    def _run(self, caller: Caller, ch: Any, row: Any, assistant: str) -> Dict[str, Any]:
        svc = self.svc
        if not svc.org_setting(caller.org, "ai_enabled") or not ch["ai_enabled"]:
            return self._notice(caller, ch, row, assistant, "disabled")
        if self._still_allowed(caller, ch["id"], assistant, "view") is None:
            return self._refused(caller, ch, row, assistant)
        if self.llm is None:
            return self._notice(caller, ch, row, assistant, "not_configured")
        request = strip_mention(row["body"], assistant) or "Summarise the recent messages."
        if guard.scan(request, source="chat.request").blocked:
            return self._notice(caller, ch, row, assistant, "blocked")
        prompt, authors = self._prompt(caller, ch, row, assistant, request)
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
            out = self._deliver(caller, ch, row, assistant, text, authors, draft=request.lower().startswith("draft"))
        if isinstance(proposal, dict) and proposal:
            out["proposal"] = self._propose(caller, ch, row, assistant, proposal, authors)
        elif not text:
            return self._notice(caller, ch, row, assistant, "empty")
        return out

    def _prompt(self, caller: Caller, ch: Any, row: Any, assistant: str, request: str) -> tuple:
        """The prompt, and the ids of everyone who wrote a message in the context window (withheld ones too)."""
        rows, authors = self._closure(ch, row["topic"], row["id"])
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
                "If you do not know, say so; do not invent facts."), authors

    def _closure(self, ch: Any, topic: str, before_id: int) -> tuple:
        """The window before `before_id` and its full author set: its senders plus, for AI text, whoever that text was
        built from. AI text with no recorded provenance makes the set UNKNOWN; it is never guessed from neighbours."""
        rows = self._window(ch, topic, before_id, "id, sender, body, ai_assisted, context_authors", True)
        found = {r["sender"] for r in rows if not is_assistant(r["sender"])}
        for r in rows:
            if r["ai_assisted"]:
                found.update(json.loads(r["context_authors"]) if r["context_authors"] else {UNKNOWN})
        return rows, sorted(u for u in found if not is_assistant(u))

    def _window(self, ch: Any, topic: str, before_id: int, cols: str, live_only: bool) -> List[Any]:
        """The CONTEXT_MESSAGES messages before `before_id` in the channel (this topic, for named channels), oldest first."""
        where, args = "channel_id=? AND id<?", [ch["id"], before_id]
        if live_only:
            where += " AND deleted_at IS NULL AND erased=0"
        if ch["kind"] in ("public", "private"):
            where, args = where + " AND topic=?", [*args, topic]
        return self.svc.store.all(f"SELECT {cols} FROM messages WHERE {where} ORDER BY id DESC LIMIT ?",
                                  [*args, CONTEXT_MESSAGES])[::-1]

    # ── outcomes ──────────────────────────────────────────────────────────────
    def _deliver(self, caller: Caller, ch: Any, row: Any, assistant: str, text: str, authors: List[str], *,
                 draft: bool) -> Dict[str, Any]:
        svc = self.svc
        if self._still_allowed(caller, ch["id"], assistant, "view", *(() if draft else ("post",))) is None:
            return self._refused(caller, ch, row, assistant)             # access changed while the model was thinking
        if not draft:
            try:
                msg = svc.post_as_assistant(caller.org, assistant, ch["id"], text, topic=row["topic"], reply_to=row["id"],
                                            for_user=caller.id, context_authors=[*authors, caller.id])
            except ChatError as e:
                return self._notice(caller, ch, row, assistant, "post_refused:" + e.code)
            svc._audit("assistant.answer", assistant, caller.org, for_user=caller.id, channel=ch["id"], message=row["id"],
                       reply=msg["id"], reply_sha256=sha(text))
            return {"assistant": assistant, "status": "answered", "message_id": msg["id"]}
        draft_id = uuid.uuid4().hex
        with svc._write() as db:
            db.execute("INSERT INTO ai_drafts VALUES(?,?,?,?,?,?,?,?,?,?,?)", (draft_id, caller.org, ch["id"], row["topic"],
                       caller.id, assistant, text, "pending", svc.clock(), row["id"], json.dumps(sorted({*authors, caller.id}))))
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

    def _draft_authors(self, caller: Caller, row: Any) -> List[str]:
        """Who steered the draft, as recorded when it was written. A draft from before the column existed has no
        record, and rebuilding one from the live window would miss deleted or erased messages and anything edited
        since, so it is unknown (fail closed)."""
        if row["context_authors"] is not None:
            return json.loads(row["context_authors"])
        return [UNKNOWN]

    def confirm_draft(self, caller: Caller, draft_id: Any, body: Optional[str] = None) -> Dict[str, Any]:
        """Post the draft under the requester's own name (optionally edited first). Their limits, their policy."""
        svc = self.svc
        caller = svc._enter(caller)
        row = self._draft(caller, draft_id)
        msg = svc.post(caller, row["channel_id"], row["body"] if body is None else body, topic=row["topic"], ai_assisted=True,
                       context_authors=[*self._draft_authors(caller, row), caller.id])   # the editor counts too
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
    def _flow(self, who: Caller, authors: Sequence[str] = (UNKNOWN,)) -> Flow:
        tools = [Tool(t.name, partial(self._execute, t, who, list(authors)), t.description, dict(t.params), needs_approval=True)
                 for t in self.tools.values()]
        return Flow(tools, llm=self.llm, path=self.flow_path)

    def _execute(self, tool: ChatTool, who: Caller, authors: List[str], **args: Any) -> Any:
        """Runs an approved step. The proposal's authors ride along (set here, never by the model: _propose refuses
        any argument a tool does not declare) so what the step posts keeps its provenance."""
        return tool.run(self.svc, who, {**args, "context_authors": authors})

    def _approvers(self, ch: Any, requester: str, authors: List[str]) -> List[str]:
        """Who may be the second key: owners/admins (named channels only) and known chat_admins, never the
        requester and never anyone who wrote text the model read."""
        named = [] if ch["kind"] in ("direct", "group") else [r["user_id"] for r in self.svc.store.all(
            "SELECT user_id FROM members WHERE channel_id=? AND role IN ('owner','admin')", (ch["id"],))]
        if UNKNOWN in authors:               # provenance lost: only a chat_admin outside the recent posters may be the second key
            named = []
        pool = [*named, *self.svc.chat_admins(ch["org"])]    # admins: last verified request carried the role
        return list(dict.fromkeys(u for u in pool if u != requester and u not in authors and not is_assistant(u)))

    def _recent_posters(self, ch: Any, topic: str) -> List[str]:
        """Belt and braces: anyone who posted in this topic lately may have steered the model, whatever the window held."""
        since = self.svc.clock() - self.svc.org_setting(ch["org"], "approver_exclude_hours") * 3600
        return [r["sender"] for r in self.svc.store.all(
            "SELECT DISTINCT sender FROM messages WHERE channel_id=? AND topic=? AND created_at>=?", (ch["id"], topic, since))
            if not is_assistant(r["sender"])]

    def _may_decide(self, caller: Caller, row: Any, ch: Any) -> bool:
        """Live check (membership and roles as they are now) of the same rule _approvers applies."""
        if caller.id == row["requester"] or caller.id in json.loads(row["context_authors"]):
            return False
        if CHAT_ADMIN in caller.roles:
            return True
        return UNKNOWN not in json.loads(row["context_authors"]) and ch is not None and ch["kind"] not in ("direct", "group") and self.svc.store.role(ch["id"], caller.id) in ("owner", "admin")

    def _propose(self, caller: Caller, ch: Any, row: Any, assistant: str, proposal: Dict[str, Any],
                 authors: List[str]) -> Dict[str, Any]:
        svc = self.svc
        if self._still_allowed(caller, ch["id"], assistant, "view") is None:
            return {"status": self._refused(caller, ch, row, assistant)["status"]}
        tool, args = self.tools.get(str(proposal.get("tool"))), proposal.get("args", {})
        if tool is None or not isinstance(args, dict) or set(args) - set(tool.params):
            return {"status": self._notice(caller, ch, row, assistant, "invalid_proposal")["status"]}
        try:
            args = tool.check(svc, caller, args)
        except (ChatError, ValueError):
            return {"status": self._notice(caller, ch, row, assistant, "invalid_proposal")["status"]}
        authors = sorted({*authors, *self._recent_posters(ch, row["topic"])})
        approvers = self._approvers(ch, caller.id, authors)
        if not approvers:                       # fail closed: no second key exists, so no run is even started
            run_id, chash, status = uuid.uuid4().hex, call_hash(tool.name, args), "no_eligible_approver"
        else:
            meta = {"caller": {"id": caller.id, "org": caller.org, "roles": sorted(caller.roles)}, "assistant": assistant,
                    "channel": ch["id"], "message": row["id"]}
            result = self._flow(caller).call(tool.name, args, actor=caller.id, meta=meta)
            run_id, chash, status = result.run_id, result.pending["call_hash"], "pending"
        with svc._write() as db:
            db.execute("INSERT INTO ai_proposals(run_id, org, channel_id, requester, requester_roles, assistant, tool, "
                       "call_hash, approvers, status, created_at, source_message_id, context_authors) "
                       "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                run_id, caller.org, ch["id"], caller.id, json.dumps(sorted(caller.roles)), assistant, tool.name,
                chash, json.dumps(approvers), status, svc.clock(), row["id"], json.dumps(authors)))
            svc._audit("assistant.propose", assistant, caller.org, for_user=caller.id, channel=ch["id"], message=row["id"],
                       run=run_id, tool=tool.name, call_hash=chash, approvers=approvers, status=status)
            if status == "pending":
                svc._notify([caller.id], {"type": "assistant_proposal", "op": "confirm", "channel_id": ch["id"],
                            "run_id": run_id, "tool": tool.name, "args": args, "call_hash": chash,
                            "requester": caller.id}, caller.org)
        if status != "pending":
            self._notice(caller, ch, row, assistant, status)
            return {"status": status, "run_id": run_id, "call_hash": chash}
        return {"status": "waiting_approval", "run_id": run_id, "call_hash": chash}

    def proposals(self, caller: Caller) -> List[Dict[str, Any]]:
        """Pending proposals the caller made, or may decide (approvers see them only once the requester confirmed)."""
        caller = self.svc._enter(caller)
        out = []
        for r in self.svc.store.all("SELECT * FROM ai_proposals WHERE org=? AND status='pending' ORDER BY created_at", (caller.org,)):
            if caller.id != r["requester"] and not (r["requester_confirmed"] and self._may_decide(
                    caller, r, self.svc.store.channel(caller.org, r["channel_id"]))):
                continue
            start = self._flow(caller).history(r["run_id"])[0]
            out.append({"run_id": r["run_id"], "channel_id": r["channel_id"], "tool": r["tool"], "args": start["direct"]["args"],
                        "call_hash": r["call_hash"], "requester": r["requester"], "approvers": json.loads(r["approvers"]),
                        "assistant": r["assistant"], "requester_confirmed": bool(r["requester_confirmed"]),
                    "provenance_unknown": UNKNOWN in json.loads(r["context_authors"])})
        return out

    def _proposal(self, caller: Caller, run_id: Any) -> Any:
        row = self.svc.store.one("SELECT * FROM ai_proposals WHERE run_id=? AND org=?", (run_id, caller.org)) if isinstance(run_id, str) else None
        if row is None:
            raise ChatError(404, "no_such_proposal", "no such proposal")
        return row

    def confirm_proposal(self, caller: Caller, run_id: Any, call_hash: Any) -> Dict[str, Any]:
        """Key one: the requester agrees to this exact call. Single use; only now do approvers hear of it."""
        svc = self.svc
        caller = svc._enter(caller)
        row = self._proposal(caller, run_id)
        if row["requester"] != caller.id:
            svc._denied(caller, "proposal.confirm", "not the requester", row["channel_id"])
            raise ChatError(404, "no_such_proposal", "no such proposal")
        if row["status"] != "pending":
            raise ChatError(409, "not_waiting", "this proposal is no longer waiting")
        if row["requester_confirmed"]:
            raise ChatError(409, "already_confirmed", "this proposal was already confirmed")
        if not isinstance(call_hash, str) or call_hash != row["call_hash"]:
            raise ChatError(409, "hash_mismatch", "that is not the call this proposal now holds")
        ch = svc.store.channel(caller.org, row["channel_id"])
        if not svc.org_setting(caller.org, "ai_enabled") or ch is None or not ch["ai_enabled"]:
            raise ChatError(409, "assistant_disabled", "the assistant is switched off here, so this cannot run")
        start = self._flow(caller).history(run_id)[0]
        still = set(self._approvers(ch, row["requester"], json.loads(row["context_authors"])))   # as of now, not as stored
        approvers = [u for u in json.loads(row["approvers"]) if u in still]
        inside = [u for u in approvers if svc.store.role(ch["id"], u) is not None]
        outside = [u for u in approvers if u not in inside]
        with svc._write() as db:
            if db.execute("UPDATE ai_proposals SET requester_confirmed=1, confirmed_hash=?, confirmed_at=? WHERE run_id=? "
                          "AND status='pending' AND requester_confirmed=0", (call_hash, svc.clock(), run_id)).rowcount != 1:
                raise ChatError(409, "already_confirmed", "this proposal was already confirmed")
            svc._audit("assistant.proposal_confirmed", row["assistant"], caller.org, for_user=caller.id, run=run_id,
                       call_hash=call_hash, notified=approvers)
            svc._notify(outside, {"type": "assistant_proposal", "op": "waiting", "run_id": run_id}, caller.org)   # no details
            svc._notify(inside, {"type": "assistant_proposal", "op": "new", "channel_id": row["channel_id"],
                        "run_id": run_id, "tool": row["tool"], "args": start["direct"]["args"], "call_hash": call_hash,
                        "requester": caller.id, "approvers": approvers}, caller.org)
        return {"run_id": run_id, "status": "confirmed", "call_hash": call_hash}

    def decide(self, caller: Caller, run_id: Any, call_hash: Any, approve: Any, note: str = "") -> Dict[str, Any]:
        """Key two (approve=True, a different eligible person) or a rejection by either side."""
        svc = self.svc
        caller = svc._enter(caller)
        if not isinstance(call_hash, str) or not isinstance(approve, bool) or not isinstance(note, str):
            raise ChatError(404, "no_such_proposal", "no such proposal")
        row = self._proposal(caller, run_id)
        ch = svc.store.channel(caller.org, row["channel_id"])
        if row["requester"] == caller.id:
            if approve:
                svc._denied(caller, "proposal.decide", "four eyes", row["channel_id"])
                raise ChatError(403, "four_eyes", "an action must be approved by someone other than the person it is for")
        elif not self._may_decide(caller, row, ch):
            svc._denied(caller, "proposal.decide", "not an eligible approver", row["channel_id"])
            raise ChatError(404, "no_such_proposal", "no such proposal")
        if row["status"] != "pending":
            raise ChatError(409, "not_waiting", "this proposal was already decided")
        if approve:
            if not row["requester_confirmed"] or not (call_hash == row["call_hash"] == row["confirmed_hash"]):
                raise ChatError(409, "requester_not_confirmed", "the requester has not confirmed this exact call yet")
            if not svc.org_setting(caller.org, "ai_enabled") or ch is None or not ch["ai_enabled"]:
                raise ChatError(409, "assistant_disabled", "the assistant is switched off here, so this cannot run")
        requester = Caller(id=row["requester"], org=row["org"], roles=frozenset(json.loads(row["requester_roles"])))
        flow = self._flow(requester, json.loads(row["context_authors"]))
        try:
            flow.decide(run_id, call_hash, approve=approve, by=caller.id, note=note[:500])
        except FlowError:
            raise ChatError(409, "not_waiting", "the proposal is not waiting for that step") from None
        final = flow.history(run_id)[-1]
        status = "rejected" if not approve else ("approved" if final.get("ok") else "failed")
        seen = [row["requester"], caller.id, *(json.loads(row["approvers"]) if row["requester_confirmed"] else [])]
        with svc._write() as db:
            db.execute("UPDATE ai_proposals SET status=?, decided_by=? WHERE run_id=?", (status, caller.id, run_id))
            svc._audit("assistant.decide", row["assistant"], caller.org, for_user=row["requester"], decided_by=caller.id,
                       run=run_id, call_hash=call_hash, approve=approve, outcome=status)
            svc._notify(seen, {"type": "assistant_proposal", "op": "decided", "channel_id": row["channel_id"],
                        "run_id": run_id, "status": status, "decided_by": caller.id}, caller.org)
        return {"run_id": run_id, "status": status}
