"""KAN-71: the mail connector against a REAL mailbox. Skipped unless these are set (nothing here runs in CI without them):

  VELARIS_TEST_ADDRESS         the test mailbox's address (From and To of the test mails; use a throw-away one)
  VELARIS_TEST_SMTP_HOST / _PORT (587) / _SECURITY (starttls|ssl) / _USER / _PASS
  VELARIS_TEST_IMAP_HOST / _PORT (993) / _USER / _PASS
  VELARIS_TEST_DNS_DOMAIN + VELARIS_TEST_DNS_TOKEN   optional: a domain whose TXT record _velaris.<domain> you set to the token

Run:  VELARIS_TEST_ADDRESS=... python3.11 -m pytest -q velaris/tests/test_mail_live.py -s
The same steps, as a runbook with a printed report, are in tools/mail_e2e.py. Each test sends 1-2 messages and waits up to
VELARIS_TEST_WAIT_S (default 120) for delivery. They exercise: send through the relay, receive through IMAP, undo-send,
bounce (a DSN for a message to a non-existent user of the same domain), and domain TXT verification with the real resolver.
"""
import os
import secrets
import time

import pytest

from velaris.mail import connector, dsn
from velaris.mail.inbound import dnspython_resolver

ADDR = os.environ.get("VELARIS_TEST_ADDRESS", "")
HAVE_MAIL = all(os.environ.get(k) for k in ("VELARIS_TEST_ADDRESS", "VELARIS_TEST_SMTP_HOST", "VELARIS_TEST_SMTP_USER", "VELARIS_TEST_SMTP_PASS",
                                             "VELARIS_TEST_IMAP_HOST", "VELARIS_TEST_IMAP_USER", "VELARIS_TEST_IMAP_PASS"))
pytestmark = pytest.mark.skipif(not HAVE_MAIL, reason="needs a real test mailbox (see this module's docstring)")
WAIT = float(os.environ.get("VELARIS_TEST_WAIT_S", "120"))


def relay():
    return connector.SmtpRelay(os.environ["VELARIS_TEST_SMTP_HOST"], int(os.environ.get("VELARIS_TEST_SMTP_PORT", "587")),
                               os.environ.get("VELARIS_TEST_SMTP_SECURITY", "starttls"), os.environ["VELARIS_TEST_SMTP_USER"],
                               os.environ["VELARIS_TEST_SMTP_PASS"])


def imap():
    t = connector.ImapLibTransport(os.environ["VELARIS_TEST_IMAP_HOST"], int(os.environ.get("VELARIS_TEST_IMAP_PORT", "993")))
    t.login(os.environ["VELARIS_TEST_IMAP_USER"], os.environ["VELARIS_TEST_IMAP_PASS"])
    return t


def raw_mail(marker: str, to: str = ADDR) -> bytes:
    return (f"From: {ADDR}\r\nTo: {to}\r\nSubject: velaris live test {marker}\r\nMessage-ID: <{marker}@velaris.test>\r\n"
            f"Date: {time.strftime('%a, %d %b %Y %H:%M:%S +0000', time.gmtime())}\r\n\r\nlive test {marker}\r\n").encode()


def wait_for(predicate, what: str):
    deadline = time.monotonic() + WAIT
    while time.monotonic() < deadline:
        found = predicate()
        if found:
            return found
        time.sleep(5)
    pytest.fail(f"{what} did not arrive within {WAIT:.0f}s")


def inbox_messages():
    t = imap()
    try:
        t.select("INBOX")
        return [t.fetch_raw(u, 2_000_000) for u in t.search_uids(1)[-50:]]
    finally:
        t.logout()


def test_send_through_the_relay_and_receive_through_imap():
    marker = secrets.token_hex(6)
    assert relay().send(ADDR, [ADDR], raw_mail(marker)) == {}                       # nothing refused
    wait_for(lambda: [m for m in inbox_messages() if marker.encode() in m], "the test message")


def test_a_bounce_comes_back_as_a_dsn_we_can_read():
    marker = secrets.token_hex(6)
    bad = f"no-such-user-{marker}@{ADDR.rsplit('@', 1)[1]}"
    try:
        refused = relay().send(ADDR, [bad], raw_mail(marker, bad))
    except Exception as e:                              # a relay may refuse a non-existent local user at once: that is also a bounce
        pytest.skip(f"the relay refused the recipient immediately ({type(e).__name__}); try a domain whose server accepts then bounces")
    if refused:
        pytest.skip("the relay refused the recipient immediately; try a domain whose server accepts then bounces")
    found = wait_for(lambda: [d for d in map(dsn.parse_dsn, inbox_messages()) if d and d["original_message_id"] == f"{marker}@velaris.test"], "the bounce")
    assert found[0]["action"] == "failed" and found[0]["status"].startswith("5")


def test_undo_send_inside_the_window_sends_nothing_and_a_later_send_arrives():
    from velaris.tests.mail_helpers import ALICE, Clock, make_world
    from velaris.mail import drafts
    clock = Clock()
    store, ob, _, clock, _, boxes = make_world(clock=clock, relay=relay(), settings={"allowlisted_domains": [ADDR.rsplit("@", 1)[1]]})
    mb = boxes["alice"]
    marker = secrets.token_hex(6)
    d = drafts.create_draft(store, ALICE, mb["id"], {"to": [ADDR], "subject": f"velaris undo {marker}", "text": marker})["id"]
    sub = ob.submit(ALICE, mb["id"], d)
    clock.advance(5)
    ob.cancel(ALICE, sub["id"])
    clock.advance(600)
    ob.process_due()
    time.sleep(30)
    assert not [m for m in inbox_messages() if marker.encode() in m]               # cancelled inside the window: never left
    sub = ob.submit(ALICE, mb["id"], d)
    clock.advance(31)
    assert [r["result"] for r in ob.process_due()] == ["sent"]
    wait_for(lambda: [m for m in inbox_messages() if marker.encode() in m], "the message sent after the undo window")


@pytest.mark.skipif(not (os.environ.get("VELARIS_TEST_DNS_DOMAIN") and os.environ.get("VELARIS_TEST_DNS_TOKEN")), reason="needs a domain with the TXT record set")
def test_domain_txt_verification_with_the_real_resolver():
    domain, token = os.environ["VELARIS_TEST_DNS_DOMAIN"], os.environ["VELARIS_TEST_DNS_TOKEN"]
    assert token in dnspython_resolver().txt(f"_velaris.{domain}")
