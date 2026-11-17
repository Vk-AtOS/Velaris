"""Step 1, the connector: account validation, TLS-only transports, incremental sync by UIDVALIDITY/UID, size limits, no secrets in output."""
import imaplib
import smtplib
import ssl

import pytest

from velaris.intel import trace
from velaris.mail import connector
from velaris.mail.common import MailError, RelayError
from velaris.mail.connector import ConnectorError, ImapLibTransport, SmtpRelay, sync_account, sync_mailbox, validate_account
from velaris.tests.mail_helpers import ADMIN, ALICE, BOB, make_world, raw_mail

GOOD = {"imap_host": "imap.example.com", "username": "alice@example.com", "secret_name": "mail.alice", "smtp_host": "smtp.example.com"}
PASSWORD = "s3cr3t-p@ss"


class FakeImap:
    """What sync_account needs from a connection; folders = {name: {"validity": n, "msgs": {uid: (raw, seen)}}}."""

    def __init__(self, folders, special=None):
        self.folders, self.special, self.log, self.cur = folders, special or {}, [], None
        self.logged_in = False

    def login(self, user, password):
        self.log.append(("login", user, password))
        if password != PASSWORD:
            raise ConnectorError("login_failed")
        self.logged_in = True

    def list_folders(self):
        return [(n, self.special.get(n, "")) for n in self.folders]

    def select(self, name):
        self.cur = self.folders[name]
        return self.cur["validity"], max(self.cur["msgs"], default=0) + 1

    def search_uids(self, min_uid):
        return [u for u in self.cur["msgs"] if u >= min_uid] or ([max(self.cur["msgs"])] if self.cur["msgs"] else [])   # N:* quirk

    def fetch_meta(self, uid):
        raw, seen = self.cur["msgs"][uid]
        return len(raw), seen

    def fetch_raw(self, uid, max_bytes):
        self.log.append(("fetch", uid))
        return self.cur["msgs"][uid][0]

    def logout(self):
        self.log.append(("logout",))


def account(store, caller=ADMIN, mailbox=None, cfg=None):
    return connector.create_account(store, caller, mailbox["id"], cfg or GOOD)


def row(store, aid):
    return store.one("SELECT * FROM account WHERE id=?", (aid,))


def secrets(name):
    return PASSWORD if name == "mail.alice" else None


def test_account_validation_is_tls_only_and_refuses_local_targets_and_loose_secrets():
    assert validate_account(GOOD).smtp_security == "starttls"
    bad = [{**GOOD, "smtp_security": "none"}, {**GOOD, "smtp_security": "plain"}, {**GOOD, "imap_host": "127.0.0.1"}, {**GOOD, "imap_host": "10.0.0.5"},
           {**GOOD, "imap_host": "localhost"}, {**GOOD, "imap_host": "intranet.internal"}, {**GOOD, "smtp_host": "192.168.1.1"},
           {**GOOD, "secret_name": "root.password"}, {**GOOD, "secret_name": "mail/../x"}, {**GOOD, "imap_port": 0}, {**GOOD, "imap_port": "993"},
           {**GOOD, "ssl": False}, {"imap_host": "imap.example.com"}, {**GOOD, "username": "a\nb"}, "nope"]
    for b in bad:
        with pytest.raises(MailError):
            validate_account(b)


def test_only_a_mail_admin_connects_accounts_so_a_vault_secret_cannot_be_pointed_at_a_users_server():
    store, _, _, _, _, boxes = make_world()
    mb = boxes["alice"]
    with pytest.raises(MailError) as e:
        connector.create_account(store, ALICE, mb["id"], GOOD)                      # the owner is not enough
    assert e.value.status == 403
    a = account(store, mailbox=mb)
    assert a["secret_name"] == "mail.alice" and "password" not in str(a)
    assert connector.list_accounts(store, ALICE, mb["id"])[0]["id"] == a["id"]
    with pytest.raises(MailError):
        connector.list_accounts(store, BOB, mb["id"])
    assert connector.delete_account(store, ADMIN, mb["id"], a["id"]) == {"deleted": True}


def test_sync_is_incremental_dedups_by_message_id_and_resets_on_uidvalidity_change():
    store, _, _, clock, _, boxes = make_world()
    mb = boxes["alice"]
    a = account(store, mailbox=mb)
    imap = FakeImap({"INBOX": {"validity": 7, "msgs": {1: (raw_mail(mid="a@x", subject="one"), False), 2: (raw_mail(mid="b@x", subject="two"), True)}},
                     "Sent Items": {"validity": 3, "msgs": {10: (raw_mail(frm="alice@acme.com", mid="s@x", subject="sent one"), True)}},
                     "Trash": {"validity": 1, "msgs": {1: (raw_mail(mid="t@x"), False)}},
                     "Clients": {"validity": 1, "msgs": {5: (raw_mail(mid="c@x", subject="client"), False)}}},
                    special={"Sent Items": "\\sent"})
    r = sync_account(store, row(store, a["id"]), lambda cfg: imap, secrets)
    assert (r["folders"], r["stored"], r["duplicates"]) == (3, 4, 0)
    assert imap.log[0] == ("login", "alice@example.com", PASSWORD) and imap.log[-1] == ("logout",)
    assert [m["subject"] for m in store.list_messages(ALICE, mb["id"], folder="inbox")["messages"]][::-1] == ["one", "two"]
    assert store.list_messages(ALICE, mb["id"], folder="sent")["total"] == 1 and store.list_messages(ALICE, mb["id"], folder="Clients")["total"] == 1
    assert store.list_messages(ALICE, mb["id"], folder="trash")["total"] == 0                        # server Trash is not mirrored
    assert [m["seen"] for m in store.list_messages(ALICE, mb["id"], folder="inbox")["messages"]][::-1] == [False, True]
    imap.log.clear()
    imap.folders["INBOX"]["msgs"][3] = (raw_mail(mid="c3@x", subject="three"), False)
    r2 = sync_account(store, row(store, a["id"]), lambda cfg: imap, secrets)
    assert (r2["stored"], r2["duplicates"], r2["resets"]) == (1, 0, 0) and [c for c in imap.log if c[0] == "fetch"] == [("fetch", 3)]   # only the new UID
    imap.folders["INBOX"]["validity"] = 8                                                          # the server renumbered the mailbox
    imap.folders["INBOX"]["msgs"] = {1: (raw_mail(mid="a@x", subject="one"), False), 2: (raw_mail(mid="new@x", subject="fresh"), False)}
    r3 = sync_account(store, row(store, a["id"]), lambda cfg: imap, secrets)
    assert (r3["resets"], r3["duplicates"], r3["stored"]) == (1, 1, 1)                             # re-read everything; Message-ID stops the duplicate
    assert store.list_messages(ALICE, mb["id"], folder="inbox")["total"] == 4
    imap.log.clear()
    r4 = sync_account(store, row(store, a["id"]), lambda cfg: imap, secrets)
    assert r4["fetched"] == 0 and not [c for c in imap.log if c[0] == "fetch"]


def test_oversize_messages_are_skipped_without_being_fetched_and_the_run_is_capped():
    store, _, _, _, _, boxes = make_world(settings={"max_message_bytes": 2000})
    mb = boxes["alice"]
    a = account(store, mailbox=mb)
    imap = FakeImap({"INBOX": {"validity": 1, "msgs": {1: (raw_mail(mid="small@x"), False), 2: (raw_mail(mid="big@x", body="x" * 5000), False)}}})
    r = sync_account(store, row(store, a["id"]), lambda cfg: imap, secrets)
    assert (r["stored"], r["skipped_large"]) == (1, 1) and ("fetch", 2) not in imap.log
    imap.folders["INBOX"]["msgs"].update({n: (raw_mail(mid=f"m{n}@x"), False) for n in range(3, 3 + 600)})
    assert sync_account(store, row(store, a["id"]), lambda cfg: imap, secrets)["fetched"] == connector.MAX_PER_RUN


def test_failures_are_codes_never_server_text_or_secrets_and_the_audit_has_no_content():
    store, _, _, _, _, boxes = make_world()
    mb = boxes["alice"]
    a = account(store, mailbox=mb)
    with pytest.raises(ConnectorError) as e:
        sync_account(store, row(store, a["id"]), lambda cfg: FakeImap({}), lambda n: None)
    assert e.value.code == "secret_missing"
    with pytest.raises(ConnectorError) as e:
        sync_account(store, row(store, a["id"]), lambda cfg: FakeImap({}), lambda n: "wrong-password")
    assert e.value.code == "login_failed" and "wrong-password" not in repr(e.value)
    out = sync_mailbox(store, ALICE, mb["id"], lambda cfg: FakeImap({"INBOX": {"validity": 1, "msgs": {1: (raw_mail(subject="Secret plans", mid="z@x"), False)}}}), secrets)
    assert out["synced"]["stored"] == 1 and out["errors"] == []
    blob = str(list(trace.entries()))
    assert PASSWORD not in blob and "Secret plans" not in blob and "imap.example.com" not in blob and "alice@example.com" not in blob
    with pytest.raises(MailError):
        sync_mailbox(store, ALICE, boxes["bob"]["id"], lambda cfg: None, secrets)                      # not your mailbox
    other = store.create_mailbox(ADMIN, "noaccount@acme.com", owner_id="alice")
    with pytest.raises(MailError) as e:
        sync_mailbox(store, ALICE, other["id"], lambda cfg: None, secrets)
    assert e.value.code == "no_account"


# ── the real transports, over stubs of imaplib and smtplib ───────────────────

class StubImapSSL:
    instances = []

    def __init__(self, host, port, ssl_context=None, timeout=None):
        self.args, self.ctx = (host, port, timeout), ssl_context
        self.sent = []
        StubImapSSL.instances.append(self)

    def login(self, u, p):
        if p != PASSWORD:
            raise imaplib.IMAP4.error("AUTHENTICATIONFAILED server text with detail")
        self.sent.append(("login", u))

    def list(self):
        return "OK", [b'(\\HasNoChildren) "/" "INBOX"', b'(\\HasNoChildren \\Sent) "/" "Sent Items"', b'(\\Noselect) "/" "[Gmail]"', b'garbage']

    def select(self, name, readonly=False):
        self.sent.append(("select", name, readonly))
        return "OK", [b"3"]

    def response(self, key):
        return "OK", [{"UIDVALIDITY": b"42", "UIDNEXT": b"9"}[key]]

    def uid(self, cmd, *args):
        self.sent.append((cmd, args))
        if cmd == "SEARCH":
            return "OK", [b"3 4 7"]
        if args[1] == "(RFC822.SIZE FLAGS)":
            return "OK", [b"1 (UID 7 RFC822.SIZE 321 FLAGS (\\Seen))"]
        return "OK", [(b"1 (BODY[] {5}", b"HELLO"), b")"]

    def logout(self):
        self.sent.append("logout")


def test_imaplib_transport_is_tls_with_verification_and_parses_the_protocol():
    StubImapSSL.instances.clear()
    t = ImapLibTransport("imap.example.com", 993, factory=StubImapSSL)
    inst = StubImapSSL.instances[0]
    assert inst.args[:2] == ("imap.example.com", 993) and inst.ctx.verify_mode == ssl.CERT_REQUIRED and inst.ctx.check_hostname
    with pytest.raises(ConnectorError) as e:
        t.login("u", "bad")
    assert e.value.code == "login_failed" and "server text" not in str(e.value)
    t.login("u", PASSWORD)
    assert t.list_folders() == [("INBOX", ""), ("Sent Items", "\\sent")]
    assert t.select('We"ird') == (42, 9) and inst.sent[-1] == ("select", '"We\\"ird"', True)             # read-only, quoted
    assert t.search_uids(3) == [3, 4, 7] and t.fetch_meta(7) == (321, True) and t.fetch_raw(7, 100) == b"HELLO"
    with pytest.raises(ConnectorError):
        t.fetch_raw(7, 3)
    with pytest.raises(ConnectorError):
        t.select("bad\r\nname")


def test_imaplib_transport_never_falls_back_to_plaintext():
    def refuse(*a, **k):
        raise OSError("connection refused")
    with pytest.raises(ConnectorError) as e:
        ImapLibTransport("imap.example.com", factory=refuse)
    assert e.value.code == "connect_failed"
    import inspect
    assert ImapLibTransport.__init__.__kwdefaults__["factory"] is imaplib.IMAP4_SSL                    # the default constructor is the TLS one
    assert "IMAP4(" not in inspect.getsource(connector)


class StubSmtp:
    log = []
    starttls_ok = True

    def __init__(self, host, port, timeout=None, context=None):
        self.kind = "ssl" if context is not None else "plain"
        StubSmtp.log.append(("connect", self.kind, host, port))

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def ehlo(self):
        StubSmtp.log.append(("ehlo",))

    def starttls(self, context=None):
        if not StubSmtp.starttls_ok:
            raise smtplib.SMTPNotSupportedError("STARTTLS extension not supported by server.")
        StubSmtp.log.append(("starttls", context.verify_mode == ssl.CERT_REQUIRED))

    def login(self, u, p):
        if p != PASSWORD:
            raise smtplib.SMTPAuthenticationError(535, b"bad credentials from server")
        StubSmtp.log.append(("login", u))

    def sendmail(self, frm, rcpts, raw):
        StubSmtp.log.append(("sendmail", frm, tuple(rcpts)))
        return {"bad@x.org": (550, b"no such user")} if "bad@x.org" in rcpts else {}


def relay(security, password=PASSWORD):
    return SmtpRelay("smtp.example.com", 587 if security == "starttls" else 465, security, "u", password, ssl_factory=StubSmtp, factory=StubSmtp)


def test_smtp_relay_is_ssl_or_starttls_only_and_never_sends_in_clear():
    StubSmtp.log.clear()
    StubSmtp.starttls_ok = True
    assert relay("starttls").send("a@x.org", ["b@y.org", "bad@x.org"], b"raw") == {"bad@x.org": 550}
    assert [e[0] for e in StubSmtp.log] == ["connect", "ehlo", "starttls", "ehlo", "login", "sendmail"] and ("starttls", True) in StubSmtp.log
    StubSmtp.log.clear()
    relay("ssl").send("a@x.org", ["b@y.org"], b"raw")
    assert StubSmtp.log[0][:2] == ("connect", "ssl") and "starttls" not in [e[0] for e in StubSmtp.log]
    with pytest.raises(ValueError):
        SmtpRelay("smtp.example.com", 25, "none")
    StubSmtp.log.clear()
    StubSmtp.starttls_ok = False
    with pytest.raises(RelayError) as e:
        relay("starttls").send("a@x.org", ["b@y.org"], b"raw")
    assert (e.value.code, e.value.permanent) == ("tls_required", True) and "sendmail" not in [x[0] for x in StubSmtp.log]   # no fallback to plaintext
    StubSmtp.starttls_ok = True
    with pytest.raises(RelayError) as e:
        relay("starttls", password="wrong").send("a@x.org", ["b@y.org"], b"raw")
    assert e.value.code == "auth_failed" and "bad credentials" not in str(e.value) and "wrong" not in str(e.value)


def test_relay_from_env(monkeypatch):
    assert connector.relay_from_env() is None
    monkeypatch.setenv("VELARIS_MAIL_RELAY_HOST", "smtp.example.com")
    monkeypatch.setenv("VELARIS_MAIL_RELAY_USER", "u")
    monkeypatch.setenv("VELARIS_MAIL_RELAY_SECRET", "mail.relay")
    r = connector.relay_from_env(lambda n: "pw" if n == "mail.relay" else None)
    assert (r.host, r.port, r.security, r.username) == ("smtp.example.com", 587, "starttls", "u") and "pw" not in repr(r.__dict__.get("host"))


def test_the_real_vault_is_the_default_secret_source(tmp_path):
    from velaris.agents.SECRETS_VAULT.main import SecretsVault
    SecretsVault().set_secret("mail.vaulted", "from-the-vault")
    assert connector.vault_secret("mail.vaulted") == "from-the-vault" and connector.vault_secret("mail.absent") is None
    with pytest.raises(ConnectorError):
        connector.vault_secret("../escape")


def test_imap_host_resolving_to_an_internal_address_is_refused_before_any_connection(monkeypatch):
    """KAN-69 SV2-03: a public-looking name that resolves inside the network must not get the account password."""
    def no_socket(*a, **k):
        raise AssertionError("connected")
    monkeypatch.setattr(connector.socket, "create_connection", no_socket)
    with pytest.raises(ConnectorError) as e:
        ImapLibTransport("imap.example.com", resolver=lambda h: ["10.0.0.5"])
    assert e.value.code == "blocked_address"


def test_imap_connects_to_the_checked_address_not_to_a_second_lookup(monkeypatch):
    seen = {}

    def fake_connect(addr, timeout=None):
        seen["addr"] = addr
        raise OSError("stop here")
    monkeypatch.setattr(connector.socket, "create_connection", fake_connect)
    with pytest.raises(ConnectorError) as e:
        ImapLibTransport("imap.example.com", 993, resolver=lambda h: ["93.184.216.34"])
    assert e.value.code == "connect_failed" and seen["addr"] == ("93.184.216.34", 993)


def test_a_vault_secret_cannot_be_bound_to_a_second_mailbox():
    store, _, _, _, _, boxes = make_world()
    account(store, mailbox=boxes["alice"])
    with pytest.raises(MailError) as e:
        account(store, mailbox=boxes["bob"])                       # same secret_name, another mailbox
    assert e.value.code == "secret_in_use"
    account(store, mailbox=boxes["alice"])                         # the mailbox that owns it may add another account
