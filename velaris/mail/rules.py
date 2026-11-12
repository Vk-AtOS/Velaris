"""Per-user rules, the vacation responder and auto-reply loop protection.

A rule is a list of conditions (all must hold; velaris.agentkit.conditions list-form semantics, so a missing
field never matches) and a list of actions. Text fields are compared lower-case, so write values lower-case.
Condition fields: from, from_domain, to, cc, subject, body, has_attachment, size, list_id, spam_score, spf, dmarc.
Actions: move{folder} (not Trash, Drafts or Sent), label{label}, flag, mark_read, stop, auto_reply{subject, body},
forward{to[1..5]}. Forwarding NEVER happens by itself: it creates a draft and a submission that waits for a
second person (outbound.requirements: forward_rule). A rule never deletes and never sends on its own.

Auto-replies (rule or vacation) are suppressed for: Auto-Submitted other than "no", Precedence bulk/junk/list,
List-Id/List-Unsubscribe, X-Auto-Response-Suppress, an empty or null Return-Path, system-like senders
(mailer-daemon, noreply, ...), the mailbox's own addresses, mail not addressed to the mailbox in To/Cc, a sender
already answered inside the window (vacation: window_days, default 7; rule: 1 day), and more than 200 a day.
Everything we send as an auto-reply carries Auto-Submitted: auto-replied, so two responders cannot loop.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from velaris.agentkit import conditions
from velaris.core.access import Caller
from velaris.mail.common import MailError, audit, h12, uid
from velaris.mail.db import dumps, loads
from velaris.mail.mime import Parsed, domain_of, valid_address
from velaris.mail.store import MailStore

FIELDS = frozenset("from from_domain to cc subject body has_attachment size list_id spam_score spf dmarc".split())
ACTIONS = frozenset("move label flag mark_read stop auto_reply forward".split())
MAX_RULES, MAX_CONDITIONS, MAX_ACTIONS, DAILY_CAP = 50, 10, 8, 200
_SYSTEM = re.compile(r"(mailer-daemon|postmaster|no-?reply|do-?not-?reply|bounces?|notifications?)([._+-]|\Z)", re.I)


def record_of(row: Any, n_attachments: int) -> Dict[str, Any]:
    """What conditions look at: lower-cased text, so matching is case-insensitive."""
    h = loads(row["headers"], {})
    ar = row["auth_results"] or ""
    m = lambda k: (re.search(rf"\b{k}=(\w+)", ar) or [None, ""])[1]       # noqa: E731
    return {"from": row["from_addr"].lower(), "from_domain": domain_of(row["from_addr"]), "to": " ".join(loads(row["to_addrs"], [])).lower(),
            "cc": " ".join(loads(row["cc_addrs"], [])).lower(), "subject": row["subject"].lower(), "body": (row["body_text"] or "")[:20000].lower(),
            "has_attachment": n_attachments > 0, "size": row["size"], "list_id": h.get("list-id", "").lower(), "spam_score": row["spam_score"],
            "spf": m("spf"), "dmarc": m("dmarc")}


def validate_rule(store: MailStore, mb: Any, d: Any) -> Dict[str, Any]:
    if not isinstance(d, dict) or set(d) - {"name", "enabled", "conditions", "actions", "position"}:
        raise MailError("bad_rule", "a rule has name, enabled, conditions, actions")
    name, conds, acts = d.get("name"), d.get("conditions", []), d.get("actions")
    if not (isinstance(name, str) and 0 < len(name) <= 100) or not isinstance(conds, list) or len(conds) > MAX_CONDITIONS \
            or not isinstance(acts, list) or not 0 < len(acts) <= MAX_ACTIONS:
        raise MailError("bad_rule", f"name 1-100 characters, up to {MAX_CONDITIONS} conditions, 1-{MAX_ACTIONS} actions")
    clean_c = []
    for c in conds:
        err = conditions.condition_error(c)
        if err or c.get("field") not in FIELDS:
            raise MailError("bad_rule", "a condition is not valid: " + (err or "unknown field; use " + ", ".join(sorted(FIELDS))))
        v = c.get("value")
        if conditions.op_of(c) != "matches":
            v = v.lower() if isinstance(v, str) else [x.lower() if isinstance(x, str) else x for x in v] if isinstance(v, list) else v
        if len(dumps(v)) > 500:
            raise MailError("bad_rule", "a condition value is too long")
        clean_c.append({k: (v if k == "value" else val) for k, val in c.items() if k in ("field", "op", "value")})
    clean_a = []
    for a in acts:
        t = a.get("type") if isinstance(a, dict) else None
        if t not in ACTIONS:
            raise MailError("bad_rule", "unknown action; use " + ", ".join(sorted(ACTIONS)))
        if t == "move":
            f = a.get("folder")
            row = store.one("SELECT role FROM folder WHERE mailbox_id=? AND (id=? OR name=? COLLATE NOCASE)", (mb["id"], str(f), str(f)))
            if row is None or row["role"] in ("trash", "drafts", "sent"):
                raise MailError("bad_rule", "move needs an existing folder that is not Trash, Drafts or Sent")
            clean_a.append({"type": t, "folder": str(f)})
        elif t == "label":
            if not (isinstance(a.get("label"), str) and 0 < len(a["label"]) <= 50):
                raise MailError("bad_rule", "label needs a label of 1-50 characters")
            clean_a.append({"type": t, "label": a["label"]})
        elif t == "forward":
            to = a.get("to")
            if not (isinstance(to, list) and 0 < len(to) <= 5 and all(isinstance(x, str) and valid_address(x.lower()) for x in to)):
                raise MailError("bad_rule", "forward needs 1-5 valid addresses")
            clean_a.append({"type": t, "to": [x.lower() for x in to]})
        elif t == "auto_reply":
            if not (isinstance(a.get("subject", ""), str) and len(a.get("subject", "")) <= 200 and isinstance(a.get("body"), str) and 0 < len(a["body"]) <= 2000):
                raise MailError("bad_rule", "auto_reply needs a body of 1-2000 characters and an optional subject")
            clean_a.append({"type": t, "subject": a.get("subject") or "Automatic reply", "body": a["body"]})
        else:
            clean_a.append({"type": t})
    pos = d.get("position", 0)
    if not isinstance(pos, int) or isinstance(pos, bool) or not 0 <= pos <= 1000 or not isinstance(d.get("enabled", True), bool):
        raise MailError("bad_rule", "position is 0-1000 and enabled is true or false")
    return {"name": name, "enabled": d.get("enabled", True), "conditions": clean_c, "actions": clean_a, "position": pos}


def _view(r: Any) -> Dict[str, Any]:
    return {"id": r["id"], "name": r["name"], "enabled": bool(r["enabled"]), "position": r["position"],
            "conditions": loads(r["conditions"], []), "actions": loads(r["actions"], [])}


def list_rules(store: MailStore, caller: Caller, mailbox_id: str) -> List[Dict[str, Any]]:
    mb, _ = store.access(caller, mailbox_id, "manage")
    return [_view(r) for r in store.q("SELECT * FROM rule WHERE mailbox_id=? ORDER BY position, created", (mb["id"],))]


def create_rule(store: MailStore, caller: Caller, mailbox_id: str, d: Any) -> Dict[str, Any]:
    mb, _ = store.access(caller, mailbox_id, "manage")
    v = validate_rule(store, mb, d)
    if store.one("SELECT COUNT(*) AS n FROM rule WHERE mailbox_id=?", (mb["id"],))["n"] >= MAX_RULES:
        raise MailError("limit", "too many rules", 409)
    rid = uid()
    store.run("INSERT INTO rule(id, mailbox_id, org, name, enabled, position, conditions, actions, created_by, created) VALUES (?,?,?,?,?,?,?,?,?,?)",
              (rid, mb["id"], mb["org"], v["name"], int(v["enabled"]), v["position"], dumps(v["conditions"]), dumps(v["actions"]), caller.id, store.clock()))
    audit("rule.create", caller.id, caller.org, mailbox=mb["id"], rule=rid, actions=[a["type"] for a in v["actions"]])
    return _view(store.one("SELECT * FROM rule WHERE id=?", (rid,)))


def update_rule(store: MailStore, caller: Caller, mailbox_id: str, rule_id: str, d: Any) -> Dict[str, Any]:
    mb, _ = store.access(caller, mailbox_id, "manage")
    if store.one("SELECT 1 FROM rule WHERE id=? AND mailbox_id=?", (rule_id, mb["id"])) is None:
        raise MailError("not_found", "no such rule", 404)
    v = validate_rule(store, mb, d)
    store.run("UPDATE rule SET name=?, enabled=?, position=?, conditions=?, actions=? WHERE id=?",
              (v["name"], int(v["enabled"]), v["position"], dumps(v["conditions"]), dumps(v["actions"]), rule_id))
    audit("rule.update", caller.id, caller.org, mailbox=mb["id"], rule=rule_id, actions=[a["type"] for a in v["actions"]])
    return _view(store.one("SELECT * FROM rule WHERE id=?", (rule_id,)))


def delete_rule(store: MailStore, caller: Caller, mailbox_id: str, rule_id: str) -> Dict[str, Any]:
    mb, _ = store.access(caller, mailbox_id, "manage")
    if not store.run("DELETE FROM rule WHERE id=? AND mailbox_id=?", (rule_id, mb["id"])):
        raise MailError("not_found", "no such rule", 404)
    audit("rule.delete", caller.id, caller.org, mailbox=mb["id"], rule=rule_id)
    return {"deleted": True}


def matches(rule_conditions: List[Dict[str, Any]], record: Dict[str, Any]) -> bool:
    return all(conditions.holds(c, record) for c in rule_conditions)


def dry_run(store: MailStore, caller: Caller, mailbox_id: str, d: Any, limit: int = 100) -> Dict[str, Any]:
    """What a rule WOULD do to the latest messages. Changes nothing, sends nothing."""
    mb, _ = store.access(caller, mailbox_id, "manage")
    v = validate_rule(store, mb, d)
    hits = []
    for r in store.q("SELECT * FROM message WHERE mailbox_id=? AND draft=0 AND deleted_at IS NULL ORDER BY received_ts DESC LIMIT ?", (mb["id"], max(1, min(limit, 500)))):
        n = store.one("SELECT COUNT(*) AS n FROM attachment WHERE message_pk=? AND inline=0", (r["id"],))["n"]
        if matches(v["conditions"], record_of(r, n)):
            hits.append(r["id"])
    return {"checked_latest": limit, "would_match": hits, "would_do": [a["type"] for a in v["actions"]],
            "forward_needs_second_approver": any(a["type"] == "forward" for a in v["actions"])}


# ── auto-reply protection ────────────────────────────────────────────────────

def may_auto_reply(store: MailStore, mb: Any, row: Any, kind: str, window_days: float) -> bool:
    sender, h = row["from_addr"], loads(row["headers"], {})
    if not sender or _SYSTEM.match(sender.split("@")[0]) or sender in store.own_addresses(mb["id"]):
        return False
    if h.get("auto-submitted", "no").strip().lower() != "no" or h.get("precedence", "").strip().lower() in ("bulk", "junk", "list", "auto_reply"):
        return False
    if any(k in h for k in ("list-id", "list-unsubscribe", "x-auto-response-suppress")) or ("return-path" in h and h["return-path"].strip() in ("", "<>")):
        return False
    if not set(store.own_addresses(mb["id"])) & set(loads(row["to_addrs"], []) + loads(row["cc_addrs"], [])):
        return False
    now = store.clock()
    key = h12(kind + ":" + sender)
    if store.one("SELECT 1 FROM autoreply_log WHERE mailbox_id=? AND sender_hash=? AND ts>?", (mb["id"], key, now - window_days * 86400)):
        return False
    if store.one("SELECT COUNT(*) AS n FROM autoreply_log WHERE mailbox_id=? AND ts>?", (mb["id"], now - 86400))["n"] >= DAILY_CAP:
        return False
    store.run("INSERT INTO autoreply_log(mailbox_id, sender_hash, ts) VALUES (?,?,?)", (mb["id"], key, now))
    return True


def apply_inbound(store: MailStore, outbound: Any, mb: Any, pk: str) -> List[Dict[str, Any]]:
    """Run the mailbox's rules and vacation responder on a message just delivered to the inbox."""
    row = store.row(mb["id"], pk)
    n_att = store.one("SELECT COUNT(*) AS n FROM attachment WHERE message_pk=? AND inline=0", (pk,))["n"]
    rec, effects = record_of(row, n_att), []
    stopped = False
    for r in store.q("SELECT * FROM rule WHERE mailbox_id=? AND enabled=1 ORDER BY position, created", (mb["id"],)):
        if stopped or not matches(loads(r["conditions"], []), rec):
            continue
        for a in loads(r["actions"], []):
            t = a["type"]
            if t == "move":
                store.mutate(mb["id"], pk, folder=a["folder"])
            elif t == "label":
                store.mutate(mb["id"], pk, add_labels=[a["label"]])
            elif t == "flag":
                store.mutate(mb["id"], pk, flagged=True)
            elif t == "mark_read":
                store.mutate(mb["id"], pk, seen=True)
            elif t == "stop":
                stopped = True
                break
            elif t == "forward":
                sid = outbound.propose_forward(mb, pk, a["to"], r["id"]) if outbound is not None else None
                effects.append({"rule": r["id"], "action": "forward", "outcome": "pending_approval" if sid else "skipped"})
                continue
            elif t == "auto_reply":
                ok = outbound is not None and may_auto_reply(store, mb, row, "rule:" + r["id"], 1)
                sid = outbound.send_auto_reply(mb, _as_parsed(row), a["subject"], a["body"], "rule") if ok else None
                effects.append({"rule": r["id"], "action": "auto_reply", "outcome": "queued" if sid else "skipped"})
                continue
            effects.append({"rule": r["id"], "action": t, "outcome": "done"})
    v = loads(mb["vacation"], {})
    now = store.clock()
    if (v.get("enabled") and outbound is not None and (v.get("start") is None or now >= v["start"]) and (v.get("end") is None or now <= v["end"])
            and may_auto_reply(store, mb, row, "vacation", v.get("window_days") or 7)):
        sid = outbound.send_auto_reply(mb, _as_parsed(row), v.get("subject") or "Automatic reply", v["body"], "vacation")
        effects.append({"rule": "vacation", "action": "auto_reply", "outcome": "queued" if sid else "skipped"})
    if effects:
        audit("rules.applied", "rules", mb["org"], mailbox=mb["id"], message=pk, actions=[f"{e['action']}:{e['outcome']}" for e in effects])
    return effects


def _as_parsed(row: Any) -> Any:
    return Parsed(message_id=row["message_id"], from_addr=row["from_addr"], references=loads(row["refs"], []), subject=row["subject"])
