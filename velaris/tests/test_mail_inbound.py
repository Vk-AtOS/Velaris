"""Inbound: the SMTP state machine (no open relay, limits), SPF / DKIM / DMARC fixtures, spam rules, the delivery pipeline."""
import base64
import hashlib

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from velaris.mail import dkim, spam
from velaris.mail.dnsauth import UnavailableResolver, authentication_results, check_dmarc, check_spf, org_domain
from velaris.mail.mime import parse_message
from velaris.mail.smtp import Envelope, SmtpSession
from velaris.tests.mail_helpers import ALICE, FakeResolver, make_world, raw_mail


# ── the state machine ────────────────────────────────────────────────────────

def session(max_size=1000, got=None, rcpt=None, **kw):
    got = got if got is not None else []
    check = rcpt or (lambda a: "ok" if a.endswith("@acme.com") else "relay")
    return SmtpSession(hostname="mx.acme.com", peer_ip="203.0.113.5", rcpt_check=check, max_size=max_size,
                       on_message=lambda e: (got.append(e) or (250, "2.0.0 queued")), **kw), got


def say(s, *lines):
    out = []
    for ln in lines:
        out += s.feed(ln if isinstance(ln, bytes) else ln.encode() + b"\r\n")
    return [o.decode().strip() for o in out]


def test_happy_path_with_chunked_input_dot_stuffing_and_quit():
    s, got = session()
    assert s.greeting().startswith(b"220 mx.acme.com")
    r = say(s, "EHLO client.ext.org", "MAIL FROM:<a@ext.org> SIZE=100", "RCPT TO:<b@acme.com>", "DATA")
    assert r[0].startswith("250-mx.acme.com") and "250 2.1.0 ok" in r and r[-1].startswith("354")
    out = []
    for chunk in (b"Subject: x\r\n\r\n..hidden dot\r\nbo", b"dy\r\n.\r", b"\nQUIT\r\n"):
        out += s.feed(chunk)
    assert out[0] == b"250 2.0.0 queued\r\n" and out[1].startswith(b"221") and s.closed
    assert got[0].data == b"Subject: x\r\n\r\n.hidden dot\r\nbody\r\n" and got[0].rcpts == ["b@acme.com"] and got[0].mail_from == "a@ext.org"


def test_no_open_relay_and_recipient_validation():
    s, got = session(rcpt=lambda a: {"b@acme.com": "ok", "gone@acme.com": "nouser", "full@acme.com": "full"}.get(a, "relay"))
    say(s, "HELO x.org", "MAIL FROM:<a@ext.org>")
    assert say(s, "RCPT TO:<victim@gmail.com>")[0].startswith("550 5.7.1")
    assert say(s, "RCPT TO:<gone@acme.com>")[0].startswith("550 5.1.1")
    assert say(s, "RCPT TO:<full@acme.com>")[0].startswith("452")
    assert say(s, "DATA")[0].startswith("503")                              # no accepted recipient: no DATA
    assert say(s, "RCPT TO:<b@acme.com>")[0].startswith("250") and say(s, "RCPT TO:<b@acme.com>")[0].startswith("250")
    assert say(s, "RCPT TO:<x@acme.com> SIZE=1")[0].startswith("501")
    say(s, "DATA", "Subject: x", "", "hi", ".")
    assert len(got) == 1 and got[0].rcpts == ["b@acme.com"]
    for verb in ("VRFY b@acme.com", "EXPN list", "AUTH PLAIN AAAA", "STARTTLS"):
        assert say(s, verb)[0].startswith("502")                           # no harvesting, no auth, no relay path


def test_sequence_errors_syntax_and_error_budget():
    s, _ = session(max_errors=100)
    assert say(s, "MAIL FROM:<a@ext.org>")[0].startswith("503")             # before HELO
    say(s, "EHLO x.org")
    assert say(s, "RCPT TO:<b@acme.com>")[0].startswith("503")              # before MAIL
    assert say(s, "MAIL FROM:a@ext.org")[0].startswith("501")
    assert say(s, "MAIL FROM:<not valid>")[0].startswith("501")
    assert say(s, "MAIL FROM:<a@ext.org> SMTPUTF8")[0].startswith("555")
    assert say(s, "MAIL FROM:<>")[0].startswith("250")                      # null sender (bounces) is legal
    assert say(s, "MAIL FROM:<a@ext.org>")[0].startswith("503")             # nested transaction
    assert say(s, "RSET")[0].startswith("250") and say(s, "MAIL FROM:<a@ext.org>")[0].startswith("250")
    assert say(s, "NOOP")[0].startswith("250") and say(s, "WHAT")[0].startswith("500")
    tight, _ = session(max_errors=3)
    out = say(tight, "WHAT", "WHAT", "WHAT")
    assert out[-1].startswith("421") and tight.closed                       # too many errors: closed


def test_size_limits_declared_and_actual():
    s, got = session(max_size=200)
    say(s, "EHLO x.org")
    assert say(s, "MAIL FROM:<a@ext.org> SIZE=5000")[0].startswith("552")
    say(s, "MAIL FROM:<a@ext.org>", "RCPT TO:<b@acme.com>", "DATA")
    out = []
    for _ in range(20):
        out += s.feed(b"x" * 100 + b"\r\n")                                 # far over 200 bytes; only a window is kept
    out += s.feed(b".\r\n")
    assert out[-1].startswith(b"552") and got == []
    assert say(s, "MAIL FROM:<a@ext.org>")[0].startswith("250")             # and the session is usable again


def test_bare_lf_never_terminates_data_and_long_lines_are_refused():
    s, got = session()
    say(s, "EHLO x.org", "MAIL FROM:<a@ext.org>", "RCPT TO:<b@acme.com>", "DATA")
    out = s.feed(b"Subject: x\r\n\r\nbody\n.\nMAIL FROM:<evil@x.org>\r\nRCPT TO:<c@acme.com>\r\n")
    assert out == [] and got == []                                          # smuggled commands are just message text
    s.feed(b"\r\n.\r\n")
    assert b"MAIL FROM:<evil@x.org>" in got[0].data and got[0].rcpts == ["b@acme.com"]
    s2, _ = session()
    assert s2.feed(b"A" * 5000)[0].startswith(b"500")


def test_delivery_failure_is_a_temporary_reply():
    def boom(env):
        raise RuntimeError("db down")
    s = SmtpSession(hostname="h", peer_ip="1.1.1.1", rcpt_check=lambda a: "ok", max_size=1000, on_message=boom)
    say(s, "EHLO x.org", "MAIL FROM:<a@ext.org>", "RCPT TO:<b@acme.com>", "DATA")
    assert s.feed(b"x\r\n.\r\n")[0].startswith(b"451")


# ── SPF ──────────────────────────────────────────────────────────────────────

def spf(zone, ip="192.0.2.10", frm="u@ext.org", helo="mail.ext.org", **kw):
    return check_spf(FakeResolver(txt=zone, **kw), ip, frm, helo)


@pytest.mark.parametrize("zone,ip,expected", [
    ({"ext.org": ["v=spf1 ip4:192.0.2.0/24 -all"]}, "192.0.2.10", "pass"),
    ({"ext.org": ["v=spf1 ip4:192.0.2.0/24 -all"]}, "198.51.100.1", "fail"),
    ({"ext.org": ["v=spf1 ip4:192.0.2.0/24 ~all"]}, "198.51.100.1", "softfail"),
    ({"ext.org": ["v=spf1 ?all"]}, "198.51.100.1", "neutral"),
    ({"ext.org": ["v=spf1 ip4:192.0.2.0/24"]}, "198.51.100.1", "neutral"),
    ({"ext.org": ["unrelated"]}, "192.0.2.10", "none"),
    ({"ext.org": ["v=spf1 ip6:2001:db8::/32 -all"]}, "2001:db8::5", "pass"),
    ({"ext.org": ["v=spf1 include:_spf.big.com -all"], "_spf.big.com": ["v=spf1 ip4:192.0.2.0/24 -all"]}, "192.0.2.10", "pass"),
    ({"ext.org": ["v=spf1 include:_spf.big.com -all"], "_spf.big.com": ["v=spf1 ip4:10.0.0.0/8 -all"]}, "192.0.2.10", "fail"),
    ({"ext.org": ["v=spf1 include:gone.example -all"]}, "192.0.2.10", "permerror"),
    ({"ext.org": ["v=spf1 redirect=_spf.other.com"], "_spf.other.com": ["v=spf1 ip4:192.0.2.10 -all"]}, "192.0.2.10", "pass"),
    ({"ext.org": ["v=spf1 exists:%{i}.bl.ext.org -all"], "192.0.2.10.bl.ext.org": ["x"]}, "192.0.2.10", "fail"),     # exists needs an A record, not TXT
    ({"ext.org": ["v=spf1 a:%{d}.hosts.ext.org -all"]}, "192.0.2.10", "fail"),
    ({"ext.org": ["v=spf1 -all", "v=spf1 +all"]}, "192.0.2.10", "permerror"),
    ({"ext.org": ["v=spf1 bogus:x -all"]}, "192.0.2.10", "permerror"),
])
def test_spf_results(zone, ip, expected):
    assert spf(zone, ip).result == expected


def test_spf_a_mx_exists_macros_and_limits():
    z = {"ext.org": ["v=spf1 a mx:mx.ext.org exists:%{l}.%{d}.q.ext.org -all"]}
    assert spf(z, "192.0.2.10", a={"ext.org": ["192.0.2.10"]}).result == "pass"
    assert spf(z, "192.0.2.20", mx={"mx.ext.org": ["m1.ext.org"]}, a={"m1.ext.org": ["192.0.2.20"]}).result == "pass"
    assert spf(z, "192.0.2.30", a={"u.ext.org.q.ext.org": ["127.0.0.2"]}).result == "pass"       # %{l}.%{d} -> u.ext.org
    assert spf({"ext.org": ["v=spf1 a/24 -all"]}, "192.0.2.77", a={"ext.org": ["192.0.2.1"]}).result == "pass"
    ten = " ".join(f"include:i{n}.ext.org" for n in range(11))
    zone = {"ext.org": [f"v=spf1 {ten} -all"], **{f"i{n}.ext.org": ["v=spf1 ?all"] for n in range(11)}}
    assert spf(zone).result == "permerror"                                                         # more than 10 lookups
    assert spf({"ext.org": ["v=spf1 a:v1.ext.org a:v2.ext.org a:v3.ext.org -all"]}).result == "permerror"   # three void lookups
    assert spf({"ext.org": ["v=spf1 a -all"]}, down=("ext.org",)).result == "temperror"
    assert spf({"ext.org": ["v=spf1 -all"]}, ip="not-an-ip").result == "none"
    assert spf({"mail.ext.org": ["v=spf1 -all"]}, frm="", helo="mail.ext.org").result == "fail"     # null sender: check HELO
    assert check_spf(UnavailableResolver(), "192.0.2.1", "u@ext.org", "h.org").result == "temperror"


# ── DKIM ─────────────────────────────────────────────────────────────────────

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
SIGNED_RAW = dkim.sign(raw_mail(frm="u@ext.org", to="alice@acme.com", mid="signed@ext.org", body="line one\r\n\r\nline  two  "), KEY, "ext.org", "s1", now=1_800_000_000)
DNS_KEY = {"s1._domainkey.ext.org": [dkim.dns_record(KEY)]}


def test_rfc6376_canonicalisation_examples():
    headers, body = dkim.split_message(b" A: X\r\nB : Y\t\r\n\tZ  \r\n\r\n C \r\nD \t E\r\n\r\n\r\n".lstrip(b" "))
    hd = [("A", " X"), ("B ", " Y\t\r\n\tZ  ")]
    assert "".join(dkim.canon_header(n, v, True) for n, v in hd) == "a:X\r\nb:Y Z\r\n"
    assert "".join(dkim.canon_header(n, v, False) for n, v in hd) == "A: X\r\nB : Y\t\r\n\tZ  \r\n"
    assert dkim.canon_body(b" C \r\nD \t E\r\n\r\n\r\n", True) == b" C\r\nD E\r\n"
    assert dkim.canon_body(b" C \r\nD \t E\r\n\r\n\r\n", False) == b" C \r\nD \t E\r\n"
    assert dkim.canon_body(b"", False) == b"\r\n" and dkim.canon_body(b"\r\n\r\n", True) == b""
    assert headers and body is not None


def test_dkim_sign_verify_roundtrip_and_tampering():
    r = FakeResolver(txt=DNS_KEY)
    assert dkim.verify_all(SIGNED_RAW, r, now=1_800_000_100)[0].result == "pass"
    assert dkim.verify_all(SIGNED_RAW.replace(b"line one", b"line ONE"), r)[0].reason == "body hash did not verify"
    assert dkim.verify_all(SIGNED_RAW.replace(b"Subject: hello", b"Subject: hellp"), r)[0].result == "fail"
    assert dkim.verify_all(raw_mail(), r)[0].result == "none"
    assert dkim.verify_all(SIGNED_RAW, FakeResolver())[0].result == "permerror"                 # key not published
    assert dkim.verify_all(SIGNED_RAW, FakeResolver(txt={"s1._domainkey.ext.org": ["v=DKIM1; k=rsa; p="]}))[0].reason == "the key was revoked"
    assert dkim.verify_all(SIGNED_RAW, FakeResolver(down=("s1._domainkey.ext.org",)))[0].result == "temperror"
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    assert dkim.verify_all(SIGNED_RAW, FakeResolver(txt={"s1._domainkey.ext.org": [dkim.dns_record(other)]}))[0].result == "fail"


def test_dkim_expiry_weak_algorithm_and_missing_from_signature():
    r = FakeResolver(txt=DNS_KEY)
    expired = SIGNED_RAW.replace(b"s=s1; t=1800000000;", b"s=s1; t=1800000000; x=1800000050;")
    assert dkim.verify_all(expired, r, now=1_800_000_100)[0].reason == "signature expired"
    sha1 = SIGNED_RAW.replace(b"a=rsa-sha256", b"a=rsa-sha1")
    assert dkim.verify_all(sha1, r)[0].reason == "unsupported algorithm"
    nofrom = SIGNED_RAW.replace(b"h=from:", b"h=")
    assert dkim.verify_all(nofrom, r)[0].result == "permerror"


def test_dkim_ed25519_sha256():
    ed = Ed25519PrivateKey.generate()
    pub = base64.b64encode(ed.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)).decode()
    raw = raw_mail(frm="u@ext.org")
    headers, body = dkim.split_message(raw)
    bh = base64.b64encode(hashlib.sha256(dkim.canon_body(body, True)).digest()).decode()
    value = f" v=1; a=ed25519-sha256; c=relaxed/relaxed; d=ext.org; s=ed; h=from:subject; bh={bh}; b="
    data = "".join(dkim.canon_header(n, v, True) for n, v in dkim._select(headers, ["from", "subject"])) + dkim.canon_header("DKIM-Signature", value, True).rstrip("\r\n")
    sig = base64.b64encode(ed.sign(hashlib.sha256(data.encode()).digest())).decode()
    signed = b"DKIM-Signature:" + (value + sig).encode() + b"\r\n" + raw
    r = FakeResolver(txt={"ed._domainkey.ext.org": [f"v=DKIM1; k=ed25519; p={pub}"]})
    assert dkim.verify_all(signed, r)[0].result == "pass"
    assert dkim.verify_all(signed.replace(b"hello", b"hellx"), r)[0].result == "fail"


# ── DMARC ────────────────────────────────────────────────────────────────────

def dmarc(zone, spf_result="pass", spf_domain="ext.org", dk=("pass", "ext.org"), frm="ext.org"):
    from velaris.mail.dnsauth import SpfResult
    from velaris.mail.dkim import DkimResult
    return check_dmarc(FakeResolver(txt=zone), frm, SpfResult(spf_result, spf_domain), [DkimResult(dk[0], dk[1])] if dk else [])


def test_dmarc_alignment_policy_and_inheritance():
    rec = {"_dmarc.ext.org": ["v=DMARC1; p=reject; sp=quarantine"]}
    assert dmarc(rec).result == "pass"
    assert dmarc(rec, spf_result="fail", dk=("pass", "ext.org")).result == "pass"                 # DKIM alone is enough
    r = dmarc(rec, spf_result="fail", dk=("fail", "ext.org"))
    assert (r.result, r.policy) == ("fail", "reject")
    assert dmarc(rec, spf_result="pass", spf_domain="bounce.other.net", dk=None).result == "fail"  # SPF passed, not aligned
    assert dmarc(rec, spf_result="pass", spf_domain="mail.ext.org", dk=None).result == "pass"      # relaxed alignment
    strict = {"_dmarc.ext.org": ["v=DMARC1; p=none; aspf=s"]}
    assert dmarc(strict, spf_result="pass", spf_domain="mail.ext.org", dk=None).result == "fail"
    sub = dmarc(rec, spf_result="fail", dk=None, frm="news.ext.org")                               # falls back to the org domain; sp applies
    assert (sub.result, sub.policy) == ("fail", "quarantine")
    assert dmarc({}).result == "none"
    assert check_dmarc(FakeResolver(down=("_dmarc.ext.org",)), "ext.org", None, []).result == "temperror"
    assert dmarc({"_dmarc.ext.org": ["v=DMARC1; p=bogus"]}).result == "none"                       # unusable record
    assert org_domain("a.b.example.co.uk") == "example.co.uk" and org_domain("x.acme.com") == "acme.com"


def test_authentication_results_header_is_structured_and_clean():
    from velaris.mail.dnsauth import DmarcResult, SpfResult
    ar = authentication_results("mx.acme.com", SpfResult("pass"), "u@ext.org;evil=1\r\n", [], DmarcResult("fail", "reject"), "ext.org")
    assert "\r" not in ar and "\n" not in ar and ar.startswith("mx.acme.com; spf=pass") and "dkim=none" in ar and "policy.dmarc=reject" in ar


# ── spam and the pipeline ────────────────────────────────────────────────────

def test_spam_rules_are_listed_with_weights():
    p = parse_message(raw_mail(subject="ACT NOW YOU HAVE WON", body="click here http://1.2.3.4/x", frm="Boss <ceo@bank.com>",
                               extra="Reply-To: crook@evil.test\r\n"))
    total, report = spam.score(p, {"spf": "fail", "dmarc": "fail", "dkim": []})
    names = {r["rule"] for r in report}
    assert {"spf_fail", "dmarc_fail", "spam_phrases", "ip_address_link", "reply_to_differs", "shouting_subject"} <= names and total >= 5
    assert spam.score(parse_message(raw_mail()), {"spf": "pass", "dmarc": "pass", "dkim": []})[0] == 0
    exe = parse_message(b"From: a@x.com\r\nMIME-Version: 1.0\r\nContent-Type: multipart/mixed; boundary=B\r\n\r\n--B\r\nContent-Type: text/plain\r\n\r\nt\r\n"
                        b'--B\r\nContent-Type: application/octet-stream\r\nContent-Disposition: attachment; filename="invoice.exe"\r\n\r\nMZ\r\n--B--\r\n')
    assert ("executable_attachment", 4.0) in [(r["rule"], r["weight"]) for r in spam.score(exe, {})[1]]


def deliver(ib, raw, rcpt="alice@acme.com", ip="192.0.2.10", mail_from="x@ext.org"):
    return ib.deliver(Envelope("mail.ext.org", ip, mail_from, [rcpt], raw))


GOOD_DNS = dict(txt={"ext.org": ["v=spf1 ip4:192.0.2.0/24 -all"], "_dmarc.ext.org": ["v=DMARC1; p=reject"], **DNS_KEY})


def test_pipeline_delivers_with_authentication_results_and_quarantines_failures():
    store, _, ib, _, _, boxes = make_world(resolver=FakeResolver(**GOOD_DNS))
    mb = boxes["alice"]
    assert deliver(ib, raw_mail(frm="x@ext.org"))[0] == 250
    msg = store.list_messages(ALICE, mb["id"])["messages"][0]
    full = store.get_message(ALICE, mb["id"], msg["id"])
    assert "spf=pass" in full["auth_results"] and "dmarc=pass" in full["auth_results"] and msg["folder_role"] == "inbox"
    assert deliver(ib, raw_mail(frm="x@ext.org", mid="spoof@ext.org"), ip="198.51.100.9")[0] == 250          # fails SPF and DMARC with p=reject
    q = store.list_messages(ALICE, mb["id"], folder="quarantine")["messages"]
    assert len(q) == 1 and q[0]["spam_score"] >= 5
    assert any(r["rule"] == "dmarc_fail" for r in store.get_message(ALICE, mb["id"], q[0]["id"])["spam_report"])
    assert deliver(ib, SIGNED_RAW, ip="203.0.113.9")[0] == 250     # DKIM-aligned, SPF-failing: passes DMARC
    assert store.list_messages(ALICE, mb["id"])["total"] == 2
    assert deliver(ib, raw_mail(mid="m1@ext.org"))[0] == 250 and store.list_messages(ALICE, mb["id"])["total"] == 2   # redelivery: no duplicate


def test_pipeline_without_a_resolver_passes_nothing_and_rejects_loops_and_unknowns():
    store, _, ib, _, _, boxes = make_world(resolver=UnavailableResolver())
    assert deliver(ib, raw_mail())[0] == 250
    row = store.list_messages(ALICE, boxes["alice"]["id"])["messages"][0]
    assert "spf=temperror" in store.get_message(ALICE, boxes["alice"]["id"], row["id"])["auth_results"]
    assert deliver(ib, raw_mail(), rcpt="nobody@acme.com")[0] == 550
    hops = "".join(f"Received: from h{i} by h{i + 1}\r\n" for i in range(40))
    assert deliver(ib, raw_mail(mid="loop@x", extra=hops))[0] == 554


def test_end_to_end_through_the_state_machine_and_quota(monkeypatch):
    monkeypatch.setenv("VELARIS_ORG", "acme")
    store, _, ib, _, _, boxes = make_world()
    s = ib.session("192.0.2.10")
    out = []
    for ln in (b"EHLO c.ext.org\r\n", b"MAIL FROM:<x@ext.org>\r\n", b"RCPT TO:<alice@acme.com>\r\n", b"RCPT TO:<x@gmail.com>\r\n", b"DATA\r\n", raw_mail() + b".\r\n"):
        out += s.feed(ln)
    text = b"".join(out)
    assert b"550 5.7.1" in text and text.rstrip().endswith(b"250 2.0.0 queued")
    store.run("UPDATE mailbox SET quota_bytes=1 WHERE id=?", (boxes["alice"]["id"],))
    assert ib.rcpt_check("alice@acme.com") == "full" and ib.rcpt_check("zed@acme.com") == "nouser" and ib.rcpt_check("a@other.org") == "relay"
    assert deliver(ib, raw_mail(mid="q@x"))[0] == 552


def test_listener_handler_speaks_smtp_over_in_memory_streams_and_nothing_starts_on_import():
    import asyncio
    import velaris.mail.inbound as inbound
    assert not hasattr(inbound, "_server") and inbound.main.__module__ == "velaris.mail.inbound"          # nothing is bound at import
    store, _, ib, _, _, boxes = make_world()

    class Writer:
        def __init__(self):
            self.out, self.closed = b"", False

        def write(self, b):
            self.out += b

        async def drain(self):
            pass

        def close(self):
            self.closed = True

        def get_extra_info(self, name):
            return ("192.0.2.77", 5555)

    async def run():
        r = asyncio.StreamReader()
        r.feed_data(b"EHLO c.ext.org\r\nMAIL FROM:<x@ext.org>\r\nRCPT TO:<alice@acme.com>\r\nDATA\r\n" + raw_mail() + b".\r\nQUIT\r\n")
        r.feed_eof()
        w = Writer()
        await inbound._handle(r, w, ib, "mx.acme.com", 5.0)
        return w

    w = asyncio.run(run())
    assert w.out.startswith(b"220 mx.acme.com") and b"250 2.0.0 queued" in w.out and b"221" in w.out and w.closed
    assert store.list_messages(ALICE, boxes["alice"]["id"])["total"] == 1
