"""Organisation settings, delegation, aliases, quotas, legal hold, retention, export and erasure.

A mixin for MailStore. "Administration" means the mail_admin role; an owner may also export or erase
their own mailbox (data-principal rights under India's DPDP Act). An administrator never reads mail
through these calls except export, which is audited. Erasure refuses while any legal hold applies.
"""
from __future__ import annotations

import re
import secrets
import sqlite3
from typing import Any, Dict, List, Optional

from velaris.core.access import Caller
from velaris.mail.common import DnsError, MailError, audit, uid
from velaris.mail.mime import valid_address
from velaris.mail.db import dumps, loads
from velaris.mail.legal_export import LegalExportMixin

MB = 1024 * 1024
DOMAIN = re.compile(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}\Z")
RIGHTS = ("read", "send", "manage", "approve")
DEFAULTS: Dict[str, Any] = {
    "local_domains": [],            # domains this deployment hosts mail for (inbound accepts only these)
    "allowlisted_domains": [],      # other domains internal mail may go to without a second approver
    "dkim_domains": [], "dkim_selector": "velaris",
    "max_recipients": 5,            # more than this (to+cc+bcc) needs a second person
    "undo_window_s": 30, "max_message_bytes": 25 * MB, "max_attachment_bytes": 10 * MB, "default_quota_bytes": 1024 * MB,
    "retention_days": 0, "trash_retention_days": 30, "spam_retention_days": 30,
    "spam_threshold": 5.0, "autoreply_external": False,
    "legal_export": False,          # true: a mail_admin may export a mailbox with a second approver (legal hold); off: owner only
}
_INT = {"max_recipients": (1, 500), "undo_window_s": (0, 300), "max_message_bytes": (1024, 100 * MB),
        "max_attachment_bytes": (0, 100 * MB), "default_quota_bytes": (MB, 1024 * 1024 * MB), "retention_days": (0, 36500),
        "trash_retention_days": (1, 3650), "spam_retention_days": (1, 3650)}
_DOMAINS = ("local_domains", "allowlisted_domains", "dkim_domains")


def _is_admin(caller: Caller) -> bool:
    return "mail_admin" in caller.roles


class AdminMixin(LegalExportMixin):
    # ── org settings ─────────────────────────────────────────────────────────
    def org_settings(self, org: str) -> Dict[str, Any]:
        r = self.one("SELECT data FROM org_settings WHERE org=?", (org,))      # type: ignore[attr-defined]
        return {**DEFAULTS, **loads(r["data"] if r else None, {})}

    def set_org_settings(self, caller: Caller, patch: Dict[str, Any]) -> Dict[str, Any]:
        who = self._who(caller)                                                # type: ignore[attr-defined]
        if not _is_admin(who):
            raise MailError("forbidden", "changing mail settings needs the mail_admin role", 403)
        if not isinstance(patch, dict) or not patch or set(patch) - set(DEFAULTS):
            raise MailError("bad_request", "send known settings only: " + ", ".join(sorted(DEFAULTS)))
        clean: Dict[str, Any] = {}
        for k, v in patch.items():
            if k in _DOMAINS:
                if k != "allowlisted_domains" and isinstance(v, list) and set(d.lower() for d in v if isinstance(d, str)) - self.verified_domains(who.org):
                    raise MailError("domain_unverified", f"{k} may only hold domains this organisation has verified; claim and verify them first")
                if not isinstance(v, list) or len(v) > 200 or not all(isinstance(d, str) and DOMAIN.match(d.lower()) for d in v):
                    raise MailError("bad_request", f"{k} is a list of up to 200 domain names")
                clean[k] = sorted({d.lower() for d in v})
            elif k in _INT:
                lo, hi = _INT[k]
                if not (isinstance(v, int) and not isinstance(v, bool) and lo <= v <= hi):
                    raise MailError("bad_request", f"{k} is a whole number from {lo} to {hi}")
                clean[k] = v
            elif k == "spam_threshold":
                if not (isinstance(v, (int, float)) and not isinstance(v, bool) and 1 <= v <= 100):
                    raise MailError("bad_request", "spam_threshold is a number from 1 to 100")
                clean[k] = float(v)
            elif k == "dkim_selector":
                if not (isinstance(v, str) and re.fullmatch(r"[a-z0-9][a-z0-9-]{0,30}", v)):
                    raise MailError("bad_request", "dkim_selector is 1-31 letters, digits or hyphens")
                clean[k] = v
            else:                                                              # autoreply_external, legal_export
                if not isinstance(v, bool):
                    raise MailError("bad_request", f"{k} is true or false")
                clean[k] = v
        new = {**loads((self.one("SELECT data FROM org_settings WHERE org=?", (who.org,)) or {"data": None})["data"], {}), **clean}  # type: ignore[attr-defined]
        self.run("INSERT INTO org_settings(org, data) VALUES (?,?) ON CONFLICT(org) DO UPDATE SET data=excluded.data",  # type: ignore[attr-defined]
                 (who.org, dumps(new)))
        audit("settings.update", who.id, who.org, keys=sorted(clean))
        return self.org_settings(who.org)

    # ── domain ownership ─────────────────────────────────────────────────────
    def verified_domains(self, org: str) -> set:
        return {r["domain"] for r in self.q("SELECT domain FROM domain WHERE org=? AND verified=1", (org,))}    # type: ignore[attr-defined]

    def claim_domain(self, caller: Caller, domain: str) -> Dict[str, Any]:
        """Start proving this organisation owns `domain`: publish TXT velaris-verify=<token> at _velaris.<domain>, then verify_domain()."""
        who = self._who(caller)                                                # type: ignore[attr-defined]
        if not _is_admin(who):
            raise MailError("forbidden", "claiming a domain needs the mail_admin role", 403)
        d = (domain or "").strip().lower() if isinstance(domain, str) else ""
        if not DOMAIN.match(d):
            raise MailError("bad_request", "not a valid domain name")
        if self.one("SELECT 1 FROM domain WHERE domain=? AND verified=1 AND org<>?", (d, who.org)):    # type: ignore[attr-defined]
            raise MailError("domain_taken", "that domain belongs to another organisation on this deployment", 409)
        with self.tx() as c:                                                   # type: ignore[attr-defined]
            c.execute("INSERT OR IGNORE INTO domain(domain, org, token, verified, created) VALUES (?,?,?,0,?)", (d, who.org, secrets.token_hex(16), self.clock()))  # type: ignore[attr-defined]
        audit("domain.claim", who.id, who.org, domain=d)
        return self.domain_view(who.org, d)

    def domain_view(self, org: str, d: str) -> Dict[str, Any]:
        r = self.one("SELECT * FROM domain WHERE domain=? AND org=?", (d, org))      # type: ignore[attr-defined]
        if r is None:
            raise MailError("not_found", "no such claim", 404)
        return {"domain": d, "status": "verified" if r["verified"] else "pending", "record": {"name": f"_velaris.{d}", "type": "TXT", "value": f"velaris-verify={r['token']}"}}

    def domains(self, caller: Caller) -> List[Dict[str, Any]]:
        who = self._who(caller)                                                # type: ignore[attr-defined]
        return [self.domain_view(who.org, r["domain"]) for r in self.q("SELECT domain FROM domain WHERE org=? ORDER BY domain", (who.org,))]   # type: ignore[attr-defined]

    def verify_domain(self, caller: Caller, domain: str, resolver: Any) -> Dict[str, Any]:
        who = self._who(caller)                                                # type: ignore[attr-defined]
        if not _is_admin(who):
            raise MailError("forbidden", "verifying a domain needs the mail_admin role", 403)
        d = (domain or "").strip().lower() if isinstance(domain, str) else ""
        row = self.one("SELECT * FROM domain WHERE domain=? AND org=?", (d, who.org))   # type: ignore[attr-defined]
        if row is None:
            raise MailError("not_claimed", "claim the domain first", 409)
        if not row["verified"]:
            try:
                found = [t.strip() for t in resolver.txt(f"_velaris.{d}")]
            except DnsError:
                raise MailError("dns_unavailable", "the DNS check could not be completed; try again", 503) from None
            if f"velaris-verify={row['token']}" in found:
                try:
                    self.run("UPDATE domain SET verified=1 WHERE domain=? AND org=?", (d, who.org))   # type: ignore[attr-defined]
                except sqlite3.IntegrityError:
                    raise MailError("domain_taken", "that domain was verified by another organisation first", 409) from None
                audit("domain.verified", who.id, who.org, domain=d)
        return self.domain_view(who.org, d)

    def require_verified_address(self, org: str, address: str) -> None:
        if address.rsplit("@", 1)[-1] not in self.verified_domains(org) or address.rsplit("@", 1)[-1] not in self.org_settings(org)["local_domains"]:   # type: ignore[attr-defined]
            raise MailError("domain_unverified", "the address is not in a verified local domain of this organisation")

    # ── per-mailbox settings: signature and vacation responder ───────────────
    def get_mailbox_settings(self, caller: Caller, mailbox_id: str) -> Dict[str, Any]:
        mb, _ = self.access(caller, mailbox_id, "read")                        # type: ignore[attr-defined]
        return {"signature": mb["signature"], "vacation": loads(mb["vacation"], {})}

    def set_mailbox_settings(self, caller: Caller, mailbox_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
        mb, _ = self.access(caller, mailbox_id, "manage")                      # type: ignore[attr-defined]
        if not isinstance(patch, dict) or not patch or set(patch) - {"signature", "vacation"}:
            raise MailError("bad_request", "send signature and/or vacation")
        if "signature" in patch:
            sig = patch["signature"]
            if not isinstance(sig, str) or len(sig) > 2000:
                raise MailError("bad_request", "a signature is text of at most 2000 characters")
            self.run("UPDATE mailbox SET signature=? WHERE id=?", (sig, mb["id"]))     # type: ignore[attr-defined]
        if "vacation" in patch:
            v = patch["vacation"]
            ok = (isinstance(v, dict) and not set(v) - {"enabled", "subject", "body", "start", "end", "window_days"}
                  and isinstance(v.get("enabled", False), bool) and isinstance(v.get("subject", ""), str) and len(v.get("subject", "")) <= 200
                  and isinstance(v.get("body", ""), str) and len(v.get("body", "")) <= 2000
                  and all(v.get(k) is None or (isinstance(v[k], (int, float)) and not isinstance(v[k], bool)) for k in ("start", "end"))
                  and (v.get("window_days") is None or (isinstance(v["window_days"], int) and 1 <= v["window_days"] <= 30)))
            if not ok or (v.get("enabled") and not v.get("body")):
                raise MailError("bad_request", "vacation: enabled, subject, body (required when enabled), start, end, window_days 1-30")
            self.run("UPDATE mailbox SET vacation=? WHERE id=?", (dumps(v), mb["id"]))   # type: ignore[attr-defined]
        audit("mailbox.settings", caller.id, caller.org, mailbox=mb["id"], keys=sorted(patch))
        return self.get_mailbox_settings(caller, mailbox_id)

    # ── aliases and delegation ───────────────────────────────────────────────
    def add_alias(self, caller: Caller, mailbox_id: str, address: str) -> List[str]:
        who = self._who(caller)                                                # type: ignore[attr-defined]
        if not _is_admin(who):
            raise MailError("forbidden", "aliases need the mail_admin role", 403)
        mb, _ = self.access(caller, mailbox_id, "admin")                       # type: ignore[attr-defined]
        a = (address or "").strip().lower()
        if not valid_address(a):
            raise MailError("bad_request", "not a valid address")
        self.require_verified_address(who.org, a)
        with self.tx() as c:                                                   # type: ignore[attr-defined]
            if c.execute("SELECT 1 FROM mailbox WHERE address=? UNION SELECT 1 FROM alias WHERE address=?", (a, a)).fetchone():
                raise MailError("exists", "that address is already in use", 409)
            c.execute("INSERT INTO alias(address, mailbox_id, org) VALUES (?,?,?)", (a, mb["id"], mb["org"]))
        audit("alias.add", who.id, who.org, mailbox=mb["id"], alias=a)
        return [r["address"] for r in self.q("SELECT address FROM alias WHERE mailbox_id=?", (mb["id"],))]   # type: ignore[attr-defined]

    def own_addresses(self, mailbox_id: str) -> List[str]:
        mb = self.one("SELECT address FROM mailbox WHERE id=?", (mailbox_id,))  # type: ignore[attr-defined]
        return ([mb["address"]] if mb else []) + [r["address"] for r in self.q("SELECT address FROM alias WHERE mailbox_id=?", (mailbox_id,))]  # type: ignore[attr-defined]

    def _owner_only(self, caller: Caller, mailbox_id: str) -> Any:
        """Delegation is the owner's to give. Not an administrator, not a delegate (so it cannot be chained)."""
        mb, via = self.access(caller, mailbox_id, "admin")                     # type: ignore[attr-defined]
        if via["via"] != "owner":
            audit("delegate.refused", caller.id, caller.org, mailbox=mb["id"], via=via["via"])
            raise MailError("forbidden", "only the mailbox owner can grant or change delegation", 403)
        return mb

    def set_delegate(self, caller: Caller, mailbox_id: str, user_id: str, rights: List[str]) -> Dict[str, Any]:
        mb = self._owner_only(caller, mailbox_id)
        if not (isinstance(rights, list) and rights and set(rights) <= set(RIGHTS) and isinstance(user_id, str)
                and 0 < len(user_id) <= 200) or user_id == mb["owner_id"]:
            raise MailError("bad_request", "send a user_id (not the owner) and rights from: " + ", ".join(RIGHTS))
        gid = uid()
        with self.tx() as c:                                                   # type: ignore[attr-defined]
            c.execute("INSERT INTO delegation(id, mailbox_id, org, user_id, rights, granted_by, created, revoked) VALUES (?,?,?,?,?,?,?,0) "
                      "ON CONFLICT(mailbox_id, user_id) DO UPDATE SET rights=excluded.rights, granted_by=excluded.granted_by, "
                      "created=excluded.created, revoked=0", (gid, mb["id"], mb["org"], user_id, ",".join(sorted(set(rights))), caller.id, self.clock()))  # type: ignore[attr-defined]
        audit("delegate.set", caller.id, caller.org, mailbox=mb["id"], delegate=user_id, rights=sorted(set(rights)))
        return {"user_id": user_id, "rights": sorted(set(rights))}

    def remove_delegate(self, caller: Caller, mailbox_id: str, user_id: str) -> Dict[str, Any]:
        mb = self._owner_only(caller, mailbox_id)
        n = self.run("UPDATE delegation SET revoked=1 WHERE mailbox_id=? AND user_id=? AND revoked=0", (mb["id"], str(user_id)))  # type: ignore[attr-defined]
        if not n:
            raise MailError("not_found", "no such delegate", 404)
        audit("delegate.remove", caller.id, caller.org, mailbox=mb["id"], delegate=user_id)
        return {"removed": True}

    def delegates(self, caller: Caller, mailbox_id: str) -> List[Dict[str, Any]]:
        mb, _ = self.access(caller, mailbox_id, "admin")                       # type: ignore[attr-defined]
        return [{"user_id": r["user_id"], "rights": r["rights"].split(","), "granted_by": r["granted_by"]}
                for r in self.q("SELECT * FROM delegation WHERE mailbox_id=? AND revoked=0", (mb["id"],))]   # type: ignore[attr-defined]

    def can_approve(self, caller: Caller, mailbox_id: str) -> bool:
        """Who may approve a second-person send from this mailbox: mail_approver / mail_admin roles, or a delegate holding 'approve'."""
        if caller.roles & {"mail_approver", "mail_admin"}:
            return True
        d = self.one("SELECT 1 FROM delegation WHERE mailbox_id=? AND user_id=? AND revoked=0 AND (',' || rights || ',') LIKE '%,approve,%'",  # type: ignore[attr-defined]
                     (mailbox_id, caller.id))
        return d is not None

    # ── quota, hold, retention ───────────────────────────────────────────────
    def set_quota(self, caller: Caller, mailbox_id: str, quota_bytes: int) -> Dict[str, Any]:
        who = self._who(caller)                                                # type: ignore[attr-defined]
        mb, _ = self.access(caller, mailbox_id, "admin")                       # type: ignore[attr-defined]
        if not _is_admin(who):
            raise MailError("forbidden", "changing a quota needs the mail_admin role", 403)
        if not (isinstance(quota_bytes, int) and not isinstance(quota_bytes, bool) and MB <= quota_bytes <= 1024 * 1024 * MB):
            raise MailError("bad_request", "quota is 1 MiB to 1 PiB")
        self.run("UPDATE mailbox SET quota_bytes=? WHERE id=?", (quota_bytes, mb["id"]))   # type: ignore[attr-defined]
        audit("quota.set", who.id, who.org, mailbox=mb["id"], quota=quota_bytes)
        return {"quota_bytes": quota_bytes}

    def set_hold(self, caller: Caller, mailbox_id: str, on: bool, message_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """Legal hold on a whole mailbox, or on listed messages. A held message is never purged, retained away or erased."""
        who = self._who(caller)                                                # type: ignore[attr-defined]
        mb, _ = self.access(caller, mailbox_id, "admin")                       # type: ignore[attr-defined]
        if not _is_admin(who):
            raise MailError("forbidden", "legal hold needs the mail_admin role", 403)
        if not isinstance(on, bool):
            raise MailError("bad_request", "on is true or false")
        if message_ids is None:
            self.run("UPDATE mailbox SET legal_hold=? WHERE id=?", (int(on), mb["id"]))   # type: ignore[attr-defined]
            n = -1
        else:
            if not isinstance(message_ids, list) or len(message_ids) > 1000:
                raise MailError("bad_request", "message_ids is a list of up to 1000 ids")
            n = 0
            with self.tx() as c:                                               # type: ignore[attr-defined]
                for m in message_ids:
                    n += c.execute("UPDATE message SET hold=? WHERE id=? AND mailbox_id=?", (int(on), str(m), mb["id"])).rowcount
        audit("hold.set", who.id, who.org, mailbox=mb["id"], on=on, messages=n)
        return {"legal_hold": on, "messages_changed": n}

    def retention_run(self, caller: Caller, dry_run: bool = False) -> Dict[str, int]:
        """Remove mail past its retention period (never held items). dry_run counts what would go and removes nothing."""
        who = self._who(caller)                                                # type: ignore[attr-defined]
        if not _is_admin(who):
            raise MailError("forbidden", "retention needs the mail_admin role", 403)
        s, now = self.org_settings(who.org), self.clock()                      # type: ignore[attr-defined]
        base = "m.org=? AND m.hold=0 AND m.mailbox_id NOT IN (SELECT id FROM mailbox WHERE legal_hold=1) "
        sets = [("trash", base + "AND m.deleted_at IS NOT NULL AND m.deleted_at<?", (who.org, now - s["trash_retention_days"] * 86400)),
                ("spam", base + "AND m.folder_id IN (SELECT id FROM folder WHERE role IN ('spam','quarantine')) AND m.received_ts<?",
                 (who.org, now - s["spam_retention_days"] * 86400))]
        if s["retention_days"]:
            sets.append(("age", base + "AND m.draft=0 AND m.received_ts<?", (who.org, now - s["retention_days"] * 86400)))
        out = {}
        for name, cond, args in sets:
            ids = [r["id"] for r in self.q(f"SELECT m.id FROM message m WHERE {cond}", args)]   # type: ignore[attr-defined]
            out[name] = len(ids) if dry_run else self.purge(ids)               # type: ignore[attr-defined]
        audit("retention.preview" if dry_run else "retention.run", who.id, who.org, **out)
        return out

    # ── DPDP: export and erasure ─────────────────────────────────────────────
    def export_mailbox(self, caller: Caller, mailbox_id: str, limit: int = 20000, *, legal_request: str = "") -> Dict[str, Any]:
        mb, via = self.access(caller, mailbox_id, "admin")                     # type: ignore[attr-defined]
        if via["via"] == "admin":                  # an administrator manages mailboxes but does not read other people's mail (SV2-02)
            self.use_legal_export(caller, mb, legal_request)                   # type: ignore[attr-defined]
        rows = self.q("SELECT * FROM message WHERE mailbox_id=? ORDER BY received_ts LIMIT ?", (mb["id"], limit + 1))   # type: ignore[attr-defined]
        audit("mailbox.export", caller.id, caller.org, mailbox=mb["id"], via=via["via"], messages=min(len(rows), limit))
        return {"mailbox": self.mailbox_dict(mb), "settings": {"signature": mb["signature"], "vacation": loads(mb["vacation"], {})},   # type: ignore[attr-defined]
                "rules": [{"name": r["name"], "conditions": loads(r["conditions"], []), "actions": loads(r["actions"], [])}
                          for r in self.q("SELECT * FROM rule WHERE mailbox_id=?", (mb["id"],))],   # type: ignore[attr-defined]
                "messages": [self._full(r) for r in rows[:limit]], "truncated": len(rows) > limit}   # type: ignore[attr-defined]

    def erase_mailbox(self, caller: Caller, mailbox_id: str) -> Dict[str, Any]:
        mb, via = self.access(caller, mailbox_id, "admin")                     # type: ignore[attr-defined]
        if mb["legal_hold"] or self.one("SELECT 1 FROM message WHERE mailbox_id=? AND hold=1 LIMIT 1", (mb["id"],)):   # type: ignore[attr-defined]
            audit("mailbox.erase.refused", caller.id, caller.org, mailbox=mb["id"], reason="legal_hold")
            raise MailError("legal_hold", "the mailbox is under legal hold, so it cannot be erased", 409)
        n = self.purge([r["id"] for r in self.q("SELECT id FROM message WHERE mailbox_id=?", (mb["id"],))])   # type: ignore[attr-defined]
        with self.tx() as c:                                                   # type: ignore[attr-defined]
            for t in ("rule", "account", "submission", "autoreply_log", "delegation", "alias", "folder", "thread"):
                c.execute(f"DELETE FROM {t} WHERE mailbox_id=?", (mb["id"],))
            c.execute("DELETE FROM mailbox WHERE id=?", (mb["id"],))
        audit("mailbox.erase", caller.id, caller.org, mailbox=mb["id"], via=via["via"], messages=n)
        return {"erased": True, "messages": n}
