"""Step 1: connect an existing mailbox. IMAP in (TLS only), SMTP submission out (SSL or STARTTLS only).

Standard library only (imaplib, smtplib, ssl). Credentials are never in config or logs: an account names a
SECRETS_VAULT secret ("mail.<something>") and the password is fetched at the moment of use. All network
I/O goes through transports built by an injected factory, so tests use fakes and never open a socket.

Transport interface (what sync_account needs from an IMAP connection):
    login(username, password)             list_folders() -> [(name, special_use)]
    select(name) -> (uidvalidity, uidnext)   search_uids(min_uid) -> [uid]
    fetch_meta(uid) -> (size, seen)        fetch_raw(uid, max_bytes) -> bytes        logout()

Incremental sync per folder is by UIDVALIDITY and UID: if UIDVALIDITY changed the folder is read again from
the start (Message-ID dedup stops duplicates); otherwise only UIDs above the last one stored are fetched.
Messages over the size limit are skipped and counted, never fetched. Folders synced: inbox, sent, archive
and custom ones; Trash, Spam and Drafts on the server are not mirrored.

Limits (ponytail): IMAP folder names are used as the server sends them (modified UTF-7 is not decoded);
flags are mirrored once (seen at first sight), not kept in step afterwards.
"""
from __future__ import annotations

import imaplib
import ipaddress
import os
import re
import smtplib
import ssl
from dataclasses import asdict, dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from velaris.agents.SECRETS_VAULT.main import SecretsVault
from velaris.core.access import Caller
from velaris.mail.common import Clock, MailError, RelayError, audit, uid
from velaris.mail.db import dumps, loads
from velaris.mail.mime import parse_message
from velaris.mail.store import MailStore

MAX_FOLDERS, MAX_PER_RUN = 50, 500
_HOST = re.compile(r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}\Z")
_SECRET = re.compile(r"mail\.[A-Za-z0-9_][A-Za-z0-9_.-]{0,100}\Z")
_SPECIAL = {"\\sent": "sent", "\\drafts": "drafts", "\\trash": "trash", "\\junk": "spam", "\\archive": "archive", "\\all": "archive"}
_NAMES = {"inbox": "inbox", "sent": "sent", "sent items": "sent", "sent mail": "sent", "drafts": "drafts", "trash": "trash",
          "deleted items": "trash", "junk": "spam", "spam": "spam", "junk email": "spam", "archive": "archive"}


class ConnectorError(Exception):
    """A connector failure. `code` is safe to show; it never contains server text or a credential."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class AccountConfig:
    imap_host: str
    username: str
    secret_name: str
    imap_port: int = 993
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_security: str = "starttls"


def _host_ok(h: Any) -> bool:
    if not isinstance(h, str) or not _HOST.match(h) or h.lower().endswith((".local", ".internal", ".localhost")) or h.lower() == "localhost":
        return False
    return True


def validate_account(d: Any) -> AccountConfig:
    """Raise MailError unless `d` is a usable, TLS-only configuration that does not point at this machine's network."""
    allowed = {"imap_host", "imap_port", "username", "secret_name", "smtp_host", "smtp_port", "smtp_security"}
    if not isinstance(d, dict) or set(d) - allowed or not {"imap_host", "username", "secret_name"} <= set(d):
        raise MailError("bad_request", "send imap_host, username, secret_name and optionally imap_port, smtp_host, smtp_port, smtp_security")
    for host in (d["imap_host"], d.get("smtp_host") or "example.com"):
        try:
            ipaddress.ip_address(host)
            raise MailError("bad_host", "use a host name, not an address")
        except ValueError:
            pass
        if not _host_ok(host):
            raise MailError("bad_host", "the host name is not allowed")
    ports = (d.get("imap_port", 993), d.get("smtp_port", 587))
    if not all(isinstance(p, int) and not isinstance(p, bool) and 1 <= p <= 65535 for p in ports):
        raise MailError("bad_request", "ports are whole numbers from 1 to 65535")
    if d.get("smtp_security", "starttls") not in ("ssl", "starttls"):
        raise MailError("insecure_transport", "SMTP must use ssl or starttls; plaintext is not supported")
    if not (isinstance(d["username"], str) and 0 < len(d["username"]) <= 254 and not re.search(r"[\x00-\x1f]", d["username"])):
        raise MailError("bad_request", "username is not valid")
    if not (isinstance(d["secret_name"], str) and _SECRET.match(d["secret_name"])):
        raise MailError("bad_secret", "secret_name must be a SECRETS_VAULT name starting with 'mail.'")
    return AccountConfig(d["imap_host"].lower(), d["username"], d["secret_name"], ports[0], (d.get("smtp_host") or "").lower(),
                         ports[1], d.get("smtp_security", "starttls"))


def vault_secret(name: str) -> Optional[str]:
    """The default secret source: the SECRETS_VAULT agent. Raises ConnectorError if the vault cannot answer."""
    try:
        return SecretsVault().get_secret(name)
    except (ValueError, OSError):
        raise ConnectorError("secret_unavailable") from None


# ── real transports (not used by tests, except through stubs of imaplib/smtplib) ──────────────

def _q(name: str) -> str:
    if re.search(r"[\x00\r\n]", name):
        raise ConnectorError("bad_folder_name")
    return '"' + name.replace("\\", "\\\\").replace('"', '\\"') + '"'


class ImapLibTransport:
    """imaplib over TLS with certificate and host name checks. There is no plaintext constructor."""

    def __init__(self, host: str, port: int = 993, *, timeout: float = 30.0, factory: Any = imaplib.IMAP4_SSL,
                 context: Optional[ssl.SSLContext] = None) -> None:
        try:
            self._c = factory(host, port, ssl_context=context or ssl.create_default_context(), timeout=timeout)
        except (imaplib.IMAP4.error, OSError):
            raise ConnectorError("connect_failed") from None

    def _do(self, fn: Callable[[], Any]) -> Any:
        try:
            typ, data = fn()
        except (imaplib.IMAP4.error, OSError, ValueError, TypeError):
            raise ConnectorError("imap_error") from None
        if typ != "OK":
            raise ConnectorError("imap_refused")
        return data

    def login(self, username: str, password: str) -> None:
        try:
            self._c.login(username, password)
        except (imaplib.IMAP4.error, OSError):
            raise ConnectorError("login_failed") from None

    def list_folders(self) -> List[Tuple[str, str]]:
        out = []
        for line in self._do(self._c.list) or []:
            m = re.match(rb'\((?P<f>[^)]*)\)\s+(?:"[^"]*"|NIL)\s+(?P<n>.+)\Z', line if isinstance(line, bytes) else b"")
            if not m:
                continue
            flags = m.group("f").decode("ascii", "replace").lower().split()
            name = m.group("n").decode("utf-8", "replace").strip()
            name = name[1:-1].replace('\\"', '"').replace("\\\\", "\\") if name.startswith('"') else name
            if "\\noselect" not in flags and name:
                out.append((name, next((f for f in flags if f in _SPECIAL), "")))
        return out

    def _resp(self, key: str) -> int:
        data = self._do(lambda: self._c.response(key))
        try:
            return int(data[0])
        except (TypeError, ValueError, IndexError):
            raise ConnectorError("imap_error") from None

    def select(self, name: str) -> Tuple[int, int]:
        self._do(lambda: self._c.select(_q(name), readonly=True))
        return self._resp("UIDVALIDITY"), self._resp("UIDNEXT")

    def search_uids(self, min_uid: int) -> List[int]:
        data = self._do(lambda: self._c.uid("SEARCH", None, "UID", f"{int(min_uid)}:*"))
        return [int(x) for x in (data[0] or b"").split() if x.isdigit()]

    def fetch_meta(self, uid_: int) -> Tuple[int, bool]:
        data = self._do(lambda: self._c.uid("FETCH", str(int(uid_)), "(RFC822.SIZE FLAGS)"))
        text = (data[0] if isinstance(data[0], bytes) else b"").decode("ascii", "replace")
        m = re.search(r"RFC822\.SIZE (\d+)", text)
        if not m:
            raise ConnectorError("imap_error")
        return int(m.group(1)), "\\Seen" in text

    def fetch_raw(self, uid_: int, max_bytes: int) -> bytes:
        data = self._do(lambda: self._c.uid("FETCH", str(int(uid_)), "(BODY.PEEK[])"))
        raw = next((d[1] for d in data if isinstance(d, tuple) and isinstance(d[1], bytes)), None)
        if raw is None or len(raw) > max_bytes:
            raise ConnectorError("imap_error")
        return raw

    def logout(self) -> None:
        try:
            self._c.logout()
        except (imaplib.IMAP4.error, OSError):
            pass


class SmtpRelay:
    """Submission over SSL (implicit) or STARTTLS. If STARTTLS is not offered the send fails; it never falls back to plaintext."""

    def __init__(self, host: str, port: int, security: str, username: str = "", password: str = "", *, timeout: float = 30.0,
                 context: Optional[ssl.SSLContext] = None, ssl_factory: Any = smtplib.SMTP_SSL, factory: Any = smtplib.SMTP) -> None:
        if security not in ("ssl", "starttls"):
            raise ValueError("SMTP security must be ssl or starttls")
        self.host, self.port, self.security, self.username, self._password = host, port, security, username, password
        self.timeout, self.context, self.ssl_factory, self.factory = timeout, context or ssl.create_default_context(), ssl_factory, factory

    def send(self, mail_from: str, rcpts: List[str], raw: bytes) -> Dict[str, int]:
        """Returns {recipient: code} for recipients the server refused; raises RelayError on failure."""
        try:
            if self.security == "ssl":
                conn = self.ssl_factory(self.host, self.port, timeout=self.timeout, context=self.context)
            else:
                conn = self.factory(self.host, self.port, timeout=self.timeout)
            with conn:
                if self.security == "starttls":
                    conn.ehlo()
                    conn.starttls(context=self.context)
                    conn.ehlo()
                if self.username:
                    conn.login(self.username, self._password)
                refused = conn.sendmail(mail_from, rcpts, raw)
        except smtplib.SMTPNotSupportedError:
            raise RelayError("tls_required", True) from None
        except smtplib.SMTPAuthenticationError:
            raise RelayError("auth_failed", True) from None
        except smtplib.SMTPRecipientsRefused:
            raise RelayError("recipients_refused", True) from None
        except smtplib.SMTPResponseException as e:
            raise RelayError(f"smtp_{e.smtp_code}", 500 <= e.smtp_code < 600) from None
        except (smtplib.SMTPException, OSError, ssl.SSLError):
            raise RelayError("relay_unreachable", False) from None
        return {r: int(v[0]) for r, v in (refused or {}).items()}


def relay_from_env(secrets: Callable[[str], Optional[str]] = vault_secret) -> Optional[SmtpRelay]:
    """The deployment's outbound relay from VELARIS_MAIL_RELAY_HOST/PORT/SECURITY/USER/SECRET, or None when unset."""
    host = os.environ.get("VELARIS_MAIL_RELAY_HOST", "").strip()
    if not host:
        return None
    user, secret = os.environ.get("VELARIS_MAIL_RELAY_USER", ""), os.environ.get("VELARIS_MAIL_RELAY_SECRET", "")
    pw = (secrets(secret) if secret else "") or ""
    return SmtpRelay(host, int(os.environ.get("VELARIS_MAIL_RELAY_PORT", "587")), os.environ.get("VELARIS_MAIL_RELAY_SECURITY", "starttls"), user, pw)


# ── accounts and sync ────────────────────────────────────────────────────────

def role_for(name: str, special: str) -> str:
    return _SPECIAL.get(special) or _NAMES.get(name.strip().lower(), "custom")


def create_account(store: MailStore, caller: Caller, mailbox_id: str, d: Any) -> Dict[str, Any]:
    """Only a mail_admin connects accounts: the host is chosen by them, so a user cannot point a vault secret at a server of their own."""
    who = store._who(caller)
    if "mail_admin" not in who.roles:
        raise MailError("forbidden", "connecting an account needs the mail_admin role", 403)
    mb, _ = store.access(caller, mailbox_id, "admin")
    cfg = validate_account(d)
    aid = uid()
    store.run("INSERT INTO account(id, mailbox_id, org, config, created_by, created) VALUES (?,?,?,?,?,?)",
              (aid, mb["id"], mb["org"], dumps(asdict(cfg)), who.id, store.clock()))
    audit("account.create", who.id, who.org, mailbox=mb["id"], account=aid, secret=cfg.secret_name)
    return {"id": aid, **asdict(cfg)}


def list_accounts(store: MailStore, caller: Caller, mailbox_id: str) -> List[Dict[str, Any]]:
    mb, _ = store.access(caller, mailbox_id, "manage")
    return [{"id": r["id"], **loads(r["config"], {}), "folders": len(loads(r["state"], {}).get("folders", {}))}
            for r in store.q("SELECT * FROM account WHERE mailbox_id=?", (mb["id"],))]


def delete_account(store: MailStore, caller: Caller, mailbox_id: str, account_id: str) -> Dict[str, Any]:
    mb, _ = store.access(caller, mailbox_id, "admin")
    if not store.run("DELETE FROM account WHERE id=? AND mailbox_id=?", (account_id, mb["id"])):
        raise MailError("not_found", "no such account", 404)
    audit("account.delete", caller.id, caller.org, mailbox=mb["id"], account=account_id)
    return {"deleted": True}


def sync_account(store: MailStore, acct: Any, imap_factory: Callable[[AccountConfig], Any],
                 secrets: Callable[[str], Optional[str]] = vault_secret, *, clock: Optional[Clock] = None) -> Dict[str, int]:
    """Fetch what is new in one account. Returns counts; raises ConnectorError(code) when the account cannot be read."""
    now = (clock or store.clock)()
    cfg = AccountConfig(**loads(acct["config"], {}))
    max_size = store.org_settings(acct["org"])["max_message_bytes"]
    state = loads(acct["state"], {})
    state.setdefault("folders", {})
    res = {"folders": 0, "fetched": 0, "stored": 0, "duplicates": 0, "skipped_large": 0, "resets": 0}
    password = secrets(cfg.secret_name)
    if not password:
        raise ConnectorError("secret_missing")
    imap = imap_factory(cfg)
    try:
        imap.login(cfg.username, password)
        budget = MAX_PER_RUN
        for name, special in imap.list_folders()[:MAX_FOLDERS]:
            role = role_for(name, special)
            if role in ("trash", "spam", "drafts") or budget <= 0:
                continue
            res["folders"] += 1
            validity, _next = imap.select(name)
            st = state["folders"].get(name, {})
            if st and st.get("uidvalidity") != validity:
                res["resets"] += 1
            last = st.get("last_uid", 0) if st.get("uidvalidity") == validity else 0
            for u in sorted(x for x in imap.search_uids(last + 1) if x > last)[:budget]:
                budget -= 1
                size, seen = imap.fetch_meta(u)
                last = u
                if size > max_size:
                    res["skipped_large"] += 1
                    continue
                p = parse_message(imap.fetch_raw(u, max_size), max_attachment=store.org_settings(acct["org"])["max_attachment_bytes"], fallback_ts=now)
                res["fetched"] += 1
                when = p.date_ts if p.date_ts and p.date_ts <= now else now
                if store.deliver(acct["mailbox_id"], p, folder_role=role, folder_name=name if role == "custom" else "",
                                 source="connector", seen=seen, received=when):
                    res["stored"] += 1
                else:
                    res["duplicates"] += 1
            state["folders"][name] = {"uidvalidity": validity, "last_uid": last}
            store.run("UPDATE account SET state=? WHERE id=?", (dumps(state), acct["id"]))
    except MailError as e:
        raise ConnectorError(e.code) from None
    finally:
        imap.logout()
    return res


def sync_mailbox(store: MailStore, caller: Caller, mailbox_id: str, imap_factory: Callable[[AccountConfig], Any],
                 secrets: Callable[[str], Optional[str]] = vault_secret) -> Dict[str, Any]:
    mb, _ = store.access(caller, mailbox_id, "send")
    accounts = store.q("SELECT * FROM account WHERE mailbox_id=?", (mb["id"],))
    if not accounts:
        raise MailError("no_account", "this mailbox has no connected account", 409)
    total: Dict[str, int] = {}
    errors = []
    for a in accounts:
        try:
            for k, v in sync_account(store, a, imap_factory, secrets).items():
                total[k] = total.get(k, 0) + v
        except ConnectorError as e:
            errors.append(e.code)
    audit("connector.sync", caller.id, caller.org, mailbox=mb["id"], accounts=len(accounts), errors=errors, **total)
    return {"synced": total, "errors": errors}
