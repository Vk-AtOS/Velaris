"""Sending: submissions with approval and undo-send, in the shape of JMAP's EmailSubmission (RFC 8621).

A draft becomes a submission. `undo_status` is pending (can still be cancelled), final (handed on) or
canceled. The path:

  submit() -> requirements(...) empty   -> state approved, send_at = now + undo window      (internal, human, no attachment)
           -> requirements non-empty    -> state awaiting_approval, one velaris.intel.flow step "MAIL.send_approved"
                                           that a SECOND person decides (or AetherOS Prime, when a gate is set);
                                           on approval -> approved, send_at = approval + undo window
  cancel()  while pending and before send_at -> canceled; later -> cannot_unsend
  process_due() claims approved submissions whose send_at has passed, rebuilds the MIME from the draft,
                checks it still has the approved payload hash, DKIM-signs, delivers local recipients into their
                mailboxes and the rest through the injected relay.

No model is involved anywhere in this module, and nothing here is reachable from the assistant.
Approval requirements (any one is enough to need a second person):

  external_recipient   a recipient domain is not in local_domains or allowlisted_domains
  attachment           the message has an attachment
  assistant_draft      the draft was written by the assistant
  forward_rule         the message was proposed by a forwarding rule
  many_recipients      more than max_recipients (to+cc+bcc)
"""
from __future__ import annotations

import argparse
import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Sequence

from velaris.core.access import Caller
from velaris.intel.flow import Flow, FlowError, Tool
from velaris.intel.paths import data_dir, private_dir
from velaris.mail import dkim
from velaris.mail.common import Clock, MailError, RelayError, audit, uid
from velaris.mail.db import dumps, loads
from velaris.mail.connector import relay_from_env
from velaris.mail.drafts import EXTRA_HEADERS, active_submission, payload_hash
from velaris.mail.mime import Attachment, Parsed, build_message, domain_of, parse_message
from velaris.mail.store import MailStore

logger = logging.getLogger("velaris.mail.outbound")

REASONS = {
    "external_recipient": "a recipient is outside the organisation's allowed domains",
    "attachment": "the message has an attachment",
    "assistant_draft": "the assistant drafted this message",
    "forward_rule": "a forwarding rule proposed this message",
    "many_recipients": "the message has many recipients",
}
MAX_ATTEMPTS = 4
STUCK_AFTER_S = 900.0        # a submission in "sending" this long was abandoned by a crashed worker
_TOOL = "MAIL.send_approved"


def requirements(settings: Dict[str, Any], *, origin: str, recipients: Sequence[str], n_attachments: int) -> List[str]:
    internal = set(settings["local_domains"]) | set(settings["allowlisted_domains"])
    out = []
    if any(domain_of(r) not in internal for r in recipients):
        out.append("external_recipient")
    if n_attachments:
        out.append("attachment")
    if origin == "assistant":
        out.append("assistant_draft")
    if origin == "rule_forward":
        out.append("forward_rule")
    if len(recipients) > settings["max_recipients"]:
        out.append("many_recipients")
    return out


def _flow_caller(id_: str, org: str) -> Dict[str, Any]:
    return {"id": id_, "org": org, "roles": [], "employee_id": None}


class Outbound:
    def __init__(self, store: MailStore, *, relay: Any = None, gate: Any = None, flow_path: Optional[str] = None,
                 clock: Optional[Clock] = None, local_delivery: Optional[Callable[[Any, bytes, str], Any]] = None) -> None:
        self.store, self.relay, self.gate = store, relay, gate
        self.clock = clock or store.clock
        self.flow_path = flow_path or str(private_dir(data_dir() / "mail") / "flow.db")
        self.local_delivery = local_delivery
        self._flow_obj: Optional[Flow] = None
        self._flow_lock = threading.RLock()

    # ── approval flow ────────────────────────────────────────────────────────
    def _flow(self) -> Flow:
        """One Flow (one sqlite connection) shared by all threads; every use holds self._flow_lock."""
        if self._flow_obj is None or self._flow_obj.gate is not self.gate:
            tool = Tool(_TOOL, lambda submission_id, payload_hash: "approved", "Send an approved email",
                        {"submission_id": "id", "payload_hash": "sha256 of the message to be sent"}, needs_approval=True, idempotent=True)
            self._flow_obj = Flow([tool], path=self.flow_path, gate=self.gate)
        return self._flow_obj

    def view(self, s: Any) -> Dict[str, Any]:
        now = self.clock()
        pending = s["undo_status"] == "pending" and (s["state"] == "awaiting_approval" or (s["state"] == "approved" and now < (s["send_at"] or 0)))
        return {"id": s["id"], "draft_id": s["draft_id"], "mailbox_id": s["mailbox_id"], "state": s["state"], "undoStatus": s["undo_status"],
                "sendAt": s["send_at"], "canCancel": pending, "origin": s["origin"], "submitted_by": s["actor_id"], "on_behalf_of": s["on_behalf_of"],
                "grant": s["grant_id"], "requires_approval": bool(loads(s["reasons"], [])),
                "reasons": [{"code": r, "text": REASONS.get(r, r)} for r in loads(s["reasons"], [])], "payload_hash": s["payload_hash"],
                "approved_by": s["approved_by"], "approved_at": s["approved_at"], "sent_at": s["sent_at"], "error": s["error"], "created": s["created"]}

    def _row(self, sub_id: str, org: str) -> Any:
        s = self.store.one("SELECT * FROM submission WHERE id=? AND org=?", (str(sub_id), org))
        if s is None:
            raise MailError("not_found", "no such submission", 404)
        return s

    def _create(self, mb: Any, draft: Any, actor: str, grant: str, origin: str, direct: bool = False) -> Any:
        s = self.store.org_settings(mb["org"])
        to = loads(draft["to_addrs"], []) + loads(draft["cc_addrs"], []) + loads(draft["bcc_addrs"], [])
        if not to:
            raise MailError("no_recipients", "the message has no recipients")
        reasons = [] if direct else requirements(s, origin=draft["origin"] or origin, recipients=to,
                                                 n_attachments=self.store.one("SELECT COUNT(*) AS n FROM attachment WHERE message_pk=?", (draft["id"],))["n"])
        now, sid, ph = self.clock(), uid(), payload_hash(self.store, draft)
        self.store.run("UPDATE message SET message_id=? WHERE id=?", (f"{uid()}@{domain_of(draft['from_addr']) or 'localhost'}", draft["id"]))
        state, send_at, undo = ("awaiting_approval", None, "pending") if reasons else ("approved", now + (0 if direct else s["undo_window_s"]),
                                                                                       "final" if direct else "pending")
        run_id = ""
        if reasons:
            with self._flow_lock:
                res = self._flow().call(_TOOL, {"submission_id": sid, "payload_hash": ph}, actor=actor,
                                        meta={"caller": _flow_caller(mb["owner_id"] if actor.startswith(("rule:", "auto:")) else actor, mb["org"])})
            run_id = res.run_id
        self.store.run("INSERT INTO submission(id, org, mailbox_id, draft_id, actor_id, on_behalf_of, grant_id, origin, state, undo_status, created, "
                       "send_at, reasons, payload_hash, flow_run_id, approved_by, approved_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                       (sid, mb["org"], mb["id"], draft["id"], actor, mb["owner_id"], grant, draft["origin"] or origin, state, undo, now, send_at,
                        dumps(reasons), ph, run_id, "" if reasons else ("policy" if not direct else "owner-rule"), None if reasons else now))
        audit("submission.create", actor, mb["org"], mailbox=mb["id"], submission=sid, draft=draft["id"], state=state, reasons=reasons,
              origin=draft["origin"] or origin, grant=grant, hash=ph)
        return self.store.one("SELECT * FROM submission WHERE id=?", (sid,))

    def submit(self, caller: Caller, mailbox_id: str, draft_id: str) -> Dict[str, Any]:
        mb, via = self.store.access(caller, mailbox_id, "send")
        draft = self.store.one("SELECT * FROM message WHERE id=? AND mailbox_id=? AND draft=1", (str(draft_id), mb["id"]))
        if draft is None:
            raise MailError("not_found", "no such draft", 404)
        if active_submission(self.store, draft["id"]):
            raise MailError("already_submitted", "this draft is already being sent", 409)
        return self.view(self._create(mb, draft, caller.id, via["grant"], "human"))

    def propose_forward(self, mb: Any, message_pk: str, to: Sequence[str], rule_id: str) -> Optional[str]:
        """A rule's forward: a draft plus a submission that always waits for a person. Returns the submission id."""
        orig = self.store.row(mb["id"], message_pk)
        if "x-velaris-forwarded" in loads(orig["headers"], {}) or "auto-submitted" in loads(orig["headers"], {}):
            return None                                                     # never forward a forward or a machine's mail
        text = (f"---------- Forwarded message ----------\nFrom: {orig['from_addr']}\nSubject: {orig['subject']}\n\n"
                + (orig["body_text"] or "")[:200_000])
        p = Parsed(from_addr=mb["address"], to=list(to), subject="Fwd: " + orig["subject"], text=text, size=len(text),
                   headers={"x-velaris-forwarded": "1"})
        pk = self.store.save_draft(mb["id"], p, origin="rule_forward", sent_by=f"rule:{rule_id}")
        return self._create(mb, self.store.one("SELECT * FROM message WHERE id=?", (pk,)), f"rule:{rule_id}", "", "rule_forward")["id"]

    def send_auto_reply(self, mb: Any, orig: Any, subject: str, body: str, kind: str) -> Optional[str]:
        """An automatic reply (vacation, auto-reply rule): fixed text the mailbox owner wrote, no undo window."""
        s = self.store.org_settings(mb["org"])
        to = orig.from_addr
        if not s["autoreply_external"] and domain_of(to) not in set(s["local_domains"]) | set(s["allowlisted_domains"]):
            return None
        p = Parsed(from_addr=mb["address"], to=[to], subject=subject, text=body, size=len(body), in_reply_to=orig.message_id,
                   references=[*orig.references, orig.message_id][-20:],
                   headers={"auto-submitted": "auto-replied", "precedence": "bulk", "x-auto-response-suppress": "All"})
        pk = self.store.save_draft(mb["id"], p, origin="auto_reply", sent_by=f"auto:{kind}")
        return self._create(mb, self.store.one("SELECT * FROM message WHERE id=?", (pk,)), f"auto:{kind}", "", "auto_reply", direct=True)["id"]

    # ── deciding and cancelling ──────────────────────────────────────────────
    def refresh(self, s: Any) -> Any:
        """Move an awaiting submission on if its approval has been decided (here, or by the gate)."""
        if s["state"] != "awaiting_approval" or not s["flow_run_id"]:
            return s
        with self._flow_lock:
            flow = self._flow()
            try:
                flow.resume(s["flow_run_id"])
            except FlowError:
                return s
            dec = next((e for e in reversed(flow.history(s["flow_run_id"])) if e["kind"] == "decision"), None)
        if dec is None:
            return s
        by, now = str(dec.get("by") or ""), self.clock()
        if dec["approve"] and by and by != s["actor_id"]:
            n = self.store.run("UPDATE submission SET state='approved', approved_by=?, approved_at=?, send_at=? WHERE id=? AND state='awaiting_approval'",
                               (by, now, now + self.store.org_settings(s["org"])["undo_window_s"], s["id"]))
            if n:
                audit("submission.approved", by, s["org"], submission=s["id"], mailbox=s["mailbox_id"], hash=s["payload_hash"])
        else:                                                               # rejected, or approved by the submitter: refused
            n = self.store.run("UPDATE submission SET state='rejected', undo_status='canceled', approved_by=?, error=? WHERE id=? AND state='awaiting_approval'",
                               (by, "rejected" if not dec["approve"] else "four_eyes", s["id"]))
            if n:
                audit("submission.rejected", by or "gate", s["org"], submission=s["id"], mailbox=s["mailbox_id"])
        return self._row(s["id"], s["org"])

    def get(self, caller: Caller, sub_id: str) -> Dict[str, Any]:
        s = self._row(sub_id, self.store._who(caller).org)
        self.store.access(caller, s["mailbox_id"], "read")
        return self.view(self.refresh(s))

    def list_submissions(self, caller: Caller, mailbox_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        mb, _ = self.store.access(caller, mailbox_id, "read")
        rows = self.store.q("SELECT * FROM submission WHERE mailbox_id=? ORDER BY created DESC LIMIT ?", (mb["id"], max(1, min(limit, 200))))
        return [self.view(self.refresh(r)) for r in rows]

    def preview(self, s: Any) -> Dict[str, Any]:
        d = self.store.one("SELECT * FROM message WHERE id=?", (s["draft_id"],))
        if d is None:
            return {}
        atts = [{"name": a["name"], "sha256": a["sha256"], "size": a["size"]} for a in self.store.q("SELECT * FROM attachment WHERE message_pk=?", (d["id"],))]
        return {"from": d["from_addr"], "to": loads(d["to_addrs"], []), "cc": loads(d["cc_addrs"], []), "bcc": loads(d["bcc_addrs"], []),
                "subject": d["subject"], "text": d["body_text"][:20000], "attachments": atts}

    def pending_approvals(self, caller: Caller, limit: int = 100) -> List[Dict[str, Any]]:
        who = self.store._who(caller)
        out = []
        for s in self.store.q("SELECT * FROM submission WHERE org=? AND state='awaiting_approval' ORDER BY created LIMIT 500", (who.org,)):
            s = self.refresh(s)
            if s["state"] == "awaiting_approval" and s["actor_id"] != who.id and self.store.can_approve(who, s["mailbox_id"]):
                out.append({**self.view(s), "preview": self.preview(s)})
        return out[:limit]

    def decide(self, caller: Caller, sub_id: str, *, approve: bool, payload_hash_seen: str, note: str = "") -> Dict[str, Any]:
        who = self.store._who(caller)
        s = self.refresh(self._row(sub_id, who.org))
        if s["state"] != "awaiting_approval":
            raise MailError("not_waiting", "this submission is not waiting for a decision", 409)
        if not self.store.can_approve(who, s["mailbox_id"]):
            raise MailError("forbidden", "you may not decide sends from this mailbox", 403)
        if s["actor_id"] == who.id:
            audit("submission.decide.refused", who.id, who.org, submission=s["id"], reason="four_eyes")
            raise MailError("four_eyes", "a message must be approved by someone other than the person who submitted it", 403)
        if payload_hash_seen != s["payload_hash"]:
            raise MailError("hash_mismatch", "the decision names a different message than the one waiting", 409)
        if self.gate is not None:
            raise MailError("decided_in_prime", "sends from this deployment are approved in AetherOS Prime", 409)
        with self._flow_lock:
            flow = self._flow()
            pending = flow.resume(s["flow_run_id"]).pending
            if not pending:
                raise MailError("not_waiting", "this submission is not waiting for a decision", 409)
            try:
                flow.decide(s["flow_run_id"], pending["call_hash"], approve=bool(approve), by=who.id, note=str(note)[:500])
            except FlowError:
                raise MailError("not_waiting", "this submission is not waiting for a decision", 409) from None
        return self.view(self.refresh(self._row(s["id"], who.org)))

    def cancel(self, caller: Caller, sub_id: str) -> Dict[str, Any]:
        who = self.store._who(caller)
        s = self._row(sub_id, who.org)
        self.store.access(caller, s["mailbox_id"], "send")
        s = self.refresh(s)
        now = self.clock()
        if s["undo_status"] != "pending" or (s["state"] == "approved" and now >= (s["send_at"] or 0)):
            audit("submission.cancel.refused", who.id, who.org, submission=s["id"], state=s["state"])
            raise MailError("cannot_unsend", "the message has already been handed on", 409)
        n = self.store.run("UPDATE submission SET state='canceled', undo_status='canceled', canceled_by=? WHERE id=? AND undo_status='pending' "
                           "AND state IN ('awaiting_approval','approved')", (who.id, s["id"]))
        if not n:
            raise MailError("cannot_unsend", "the message has already been handed on", 409)
        audit("submission.cancel", who.id, who.org, submission=s["id"], mailbox=s["mailbox_id"])
        return self.view(self._row(s["id"], who.org))

    # ── the worker ───────────────────────────────────────────────────────────
    def recover_stuck(self, now: float) -> int:
        """Submissions left in 'sending' by a crash go back to the queue (state 'approved') so they are retried; at
        MAX_ATTEMPTS they fail instead. A retry can in rare cases deliver twice (crash after the relay accepted); the
        Message-ID is the same, so receivers drop the duplicate."""
        cutoff = now - STUCK_AFTER_S
        n = self.store.run("UPDATE submission SET state='failed', error='gave_up_after_crash' WHERE state='sending' AND send_at<=? AND attempts>=?",
                           (cutoff, MAX_ATTEMPTS))
        n += self.store.run("UPDATE submission SET state='approved', send_at=?, error='retry_after_crash' WHERE state='sending' AND send_at<=?",
                            (now, cutoff))
        return n

    def process_due(self, limit: int = 50) -> List[Dict[str, Any]]:
        now = self.clock()
        self.recover_stuck(now)
        out = []
        for s in self.store.q("SELECT * FROM submission WHERE state='approved' AND send_at<=? ORDER BY send_at LIMIT ?", (now, limit)):
            out.append(self._send(s, now))
        return [o for o in out if o]

    def _fail(self, s: Any, code: str, permanent: bool, now: float) -> Dict[str, Any]:
        if permanent or s["attempts"] >= MAX_ATTEMPTS:
            self.store.run("UPDATE submission SET state='failed', error=? WHERE id=?", (code, s["id"]))
        else:
            self.store.run("UPDATE submission SET state='approved', send_at=?, error=? WHERE id=?", (now + 60 * 2 ** (s["attempts"] - 1), code, s["id"]))
        audit("submission.failed", s["actor_id"], s["org"], submission=s["id"], code=code, permanent=permanent)
        return {"id": s["id"], "result": "failed" if permanent else "retry", "code": code}

    def _send(self, s: Any, now: float) -> Optional[Dict[str, Any]]:
        if not self.store.run("UPDATE submission SET state='sending', undo_status='final', attempts=attempts+1, send_at=? WHERE id=? AND state='approved' AND send_at<=?",
                              (now, s["id"], now)):
            return None                                                     # another worker has it
        s = self._row(s["id"], s["org"])
        d = self.store.one("SELECT * FROM message WHERE id=? AND draft=1", (s["draft_id"],))
        if d is None:
            return self._fail(s, "draft_missing", True, now)
        if payload_hash(self.store, d) != s["payload_hash"]:
            return self._fail(s, "content_changed", True, now)              # not what was approved: never sent
        mb = self.store.one("SELECT * FROM mailbox WHERE id=?", (s["mailbox_id"],))
        settings = self.store.org_settings(s["org"])
        atts = [Attachment(a["name"], a["content_type"], a["size"], a["sha256"], self.store.get_blob(a["sha256"]), a["content_id"], bool(a["inline"]))
                for a in self.store.q("SELECT * FROM attachment WHERE message_pk=?", (d["id"],))]
        sender = ""
        if s["actor_id"] != mb["owner_id"] and not s["actor_id"].startswith(("rule:", "auto:")):
            me = self.store.one("SELECT address FROM mailbox WHERE org=? AND owner_id=? AND kind='personal' LIMIT 1", (s["org"], s["actor_id"]))
            sender = me["address"] if me else ""
        extra = {"-".join(w.capitalize() for w in k.split("-")): v for k, v in loads(d["headers"], {}).items() if k in EXTRA_HEADERS}
        try:
            raw = build_message(from_addr=d["from_addr"], to=loads(d["to_addrs"], []), cc=loads(d["cc_addrs"], []), subject=d["subject"],
                                text=d["body_text"], html=d["body_html"], attachments=atts, message_id=d["message_id"], in_reply_to=d["in_reply_to"],
                                references=loads(d["refs"], []), extra=extra, sender=sender, now=now)
        except MailError:
            return self._fail(s, "cannot_build", True, now)
        if domain_of(d["from_addr"]) in settings["dkim_domains"] and domain_of(d["from_addr"]) in self.store.verified_domains(s["org"]):
            try:
                raw = dkim.sign(raw, dkim.load_or_create_key(settings["dkim_selector"]), domain_of(d["from_addr"]), settings["dkim_selector"], now=now)
            except (OSError, ValueError) as e:
                logger.warning("dkim signing failed: %s", type(e).__name__)
                return self._fail(s, "dkim_unavailable", False, now)
        rcpts = [*loads(d["to_addrs"], []), *loads(d["cc_addrs"], []), *loads(d["bcc_addrs"], [])]
        external = []
        for r in rcpts:
            lm = self.store.deliverable_mailbox(r)
            if lm is None:
                external.append(r)
            elif self.local_delivery is not None:
                self.local_delivery(lm, raw, d["from_addr"])
            else:
                self.store.deliver(lm["id"], parse_message(raw, fallback_ts=now), auth_results="internal", source="inbound")
        refused = 0
        if external:
            if self.relay is None:
                return self._fail(s, "relay_not_configured", True, now)
            try:
                bad = self.relay.send(d["from_addr"], external, raw)
                refused = len(bad or {})
            except RelayError as e:
                return self._fail(s, e.code[:60], e.permanent, now)
        self.store.mark_sent(d["id"], d["message_id"], s["actor_id"], now)
        self.store.run("UPDATE submission SET state='sent', sent_at=?, refused=?, error='' WHERE id=?", (now, refused, s["id"]))
        if d["in_reply_to"]:
            for r in self.store.q("SELECT id FROM message WHERE mailbox_id=? AND message_id=? AND draft=0", (mb["id"], d["in_reply_to"])):
                self.store.mutate(mb["id"], r["id"], answered=True)
        audit("submission.sent", s["actor_id"], s["org"], submission=s["id"], mailbox=mb["id"], local=len(rcpts) - len(external),
              external=len(external), refused=refused, hash=s["payload_hash"], approved_by=s["approved_by"])
        return {"id": s["id"], "result": "sent"}


def main() -> None:     # pragma: no cover  (a long-running worker; python3.11 -m velaris.mail.outbound)
    ap = argparse.ArgumentParser(description="Hand approved, undo-window-expired mail to the relay.")
    ap.add_argument("--loop", type=float, default=0.0, help="repeat every N seconds (default: run once)")
    args = ap.parse_args()
    out = Outbound(MailStore(), relay=relay_from_env())
    while True:
        res = out.process_due()
        print(f"processed {len(res)} submissions")
        if not args.loop:
            break
        time.sleep(args.loop)


if __name__ == "__main__":      # pragma: no cover
    main()
