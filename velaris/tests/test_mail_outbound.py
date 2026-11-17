"""Outbound: drafts, the undo-send timeline (injected clock), the approval matrix, four eyes, DKIM, relay."""
import base64

import pytest

from velaris.core.access import Caller
from velaris.mail import dkim, drafts
from velaris.mail.common import MailError, RelayError
from velaris.mail.mime import parse_message
from velaris.mail.outbound import requirements
from velaris.tests.mail_helpers import ADMIN, ALICE, BOB, CAROL, FakeResolver, make_world

B64 = base64.b64encode(b"%PDF-1.4 fake").decode()


def draft(store, caller, mb, to=("bob@acme.com",), **kw):
    return drafts.create_draft(store, caller, mb["id"], {"to": list(to), "subject": "Plan", "text": "see you at 3", **kw})["id"]


def test_internal_human_mail_goes_straight_through_the_undo_window():
    store, ob, _, clock, relay, boxes = make_world()
    d = draft(store, ALICE, boxes["alice"], cc=[])
    t0 = clock()
    sub = ob.submit(ALICE, boxes["alice"]["id"], d)
    assert (sub["state"], sub["undoStatus"], sub["sendAt"], sub["requires_approval"], sub["canCancel"]) == ("approved", "pending", t0 + 30, False, True)
    clock.advance(29)
    assert ob.process_due() == [] and store.list_messages(BOB, boxes["bob"]["id"])["total"] == 0
    clock.advance(1)
    assert [r["result"] for r in ob.process_due()] == ["sent"]
    assert relay.sent == []                                                  # internal: never touched the relay
    got = store.list_messages(BOB, boxes["bob"]["id"])["messages"]
    assert got[0]["subject"] == "Plan" and got[0]["from"] == "alice@acme.com"
    sent = store.list_messages(ALICE, boxes["alice"]["id"], folder="sent")["messages"]
    assert len(sent) == 1 and not sent[0]["draft"] and store.list_messages(ALICE, boxes["alice"]["id"], folder="drafts")["total"] == 0
    after = ob.get(ALICE, sub["id"])
    assert (after["state"], after["undoStatus"], after["canCancel"]) == ("sent", "final", False)
    with pytest.raises(MailError) as e:
        ob.cancel(ALICE, sub["id"])
    assert e.value.code == "cannot_unsend"


def test_undo_send_cancels_inside_the_window_and_nothing_is_sent():
    store, ob, _, clock, relay, boxes = make_world()
    d = draft(store, ALICE, boxes["alice"])
    sub = ob.submit(ALICE, boxes["alice"]["id"], d)
    clock.advance(10)
    out = ob.cancel(ALICE, sub["id"])
    assert (out["state"], out["undoStatus"]) == ("canceled", "canceled")
    clock.advance(600)
    assert ob.process_due() == [] and store.list_messages(BOB, boxes["bob"]["id"])["total"] == 0
    assert store.list_messages(ALICE, boxes["alice"]["id"], folder="drafts")["total"] == 1          # the draft is still there to edit
    assert ob.submit(ALICE, boxes["alice"]["id"], d)["state"] == "approved"                          # and can be sent again


def test_cancel_after_send_at_is_too_late_even_if_the_worker_has_not_run_yet():
    store, ob, _, clock, _, boxes = make_world(settings={"undo_window_s": 5})
    sub = ob.submit(ALICE, boxes["alice"]["id"], draft(store, ALICE, boxes["alice"]))
    clock.advance(5)
    with pytest.raises(MailError) as e:
        ob.cancel(ALICE, sub["id"])
    assert e.value.code == "cannot_unsend"
    assert [r["result"] for r in ob.process_due()] == ["sent"]


def test_a_draft_cannot_be_edited_or_submitted_twice_while_it_is_being_sent():
    store, ob, _, clock, _, boxes = make_world()
    mb = boxes["alice"]
    d = draft(store, ALICE, mb)
    ob.submit(ALICE, mb["id"], d)
    with pytest.raises(MailError) as e:
        drafts.update_draft(store, ALICE, mb["id"], d, {"text": "changed"})
    assert e.value.code == "locked"
    with pytest.raises(MailError) as e:
        ob.submit(ALICE, mb["id"], d)
    assert e.value.code == "already_submitted"
    with pytest.raises(MailError):
        drafts.delete_draft(store, ALICE, mb["id"], d)


@pytest.mark.parametrize("rcpts,atts,origin,expected", [
    (["bob@acme.com"], 0, "human", []),
    (["bob@acme.com", "friend@partner.com"], 0, "human", []),                  # partner.com is on the allowlist in make_world below
    (["bob@acme.com", "x@unknown.org"], 0, "human", ["external_recipient"]),
    (["bob@acme.com"], 1, "human", ["attachment"]),
    (["bob@acme.com"], 0, "assistant", ["assistant_draft"]),
    (["bob@acme.com"], 0, "rule_forward", ["forward_rule"]),
    ([f"u{i}@acme.com" for i in range(6)], 0, "human", ["many_recipients"]),
    ([f"u{i}@acme.com" for i in range(5)], 0, "human", []),                    # exactly N is fine
    (["x@unknown.org"] * 1 + [f"u{i}@acme.com" for i in range(6)], 2, "assistant", ["external_recipient", "attachment", "assistant_draft", "many_recipients"]),
    (["Bob@ACME.com"], 0, "human", []),
    (["bob@acme.com.evil.org"], 0, "human", ["external_recipient"]),           # look-alike domains are external
])
def test_approval_requirements_matrix(rcpts, atts, origin, expected):
    s = {"local_domains": ["acme.com"], "allowlisted_domains": ["partner.com"], "max_recipients": 5}
    assert requirements(s, origin=origin, recipients=[r.lower() for r in rcpts], n_attachments=atts) == expected


def test_external_mail_needs_a_second_person_and_the_window_starts_at_approval():
    store, ob, _, clock, relay, boxes = make_world()
    mb = boxes["alice"]
    sub = ob.submit(ALICE, mb["id"], draft(store, ALICE, mb, to=["client@ext.org"]))
    assert sub["state"] == "awaiting_approval" and sub["sendAt"] is None and [r["code"] for r in sub["reasons"]] == ["external_recipient"]
    clock.advance(3600)
    assert ob.process_due() == [] and relay.sent == []
    assert ob.pending_approvals(ALICE) == []                                  # the submitter never sees it as theirs to approve
    pend = ob.pending_approvals(CAROL)
    assert pend[0]["preview"]["to"] == ["client@ext.org"] and pend[0]["preview"]["text"].startswith("see you")
    with pytest.raises(MailError) as e:
        ob.decide(ALICE, sub["id"], approve=True, payload_hash_seen=sub["payload_hash"])
    assert e.value.code in ("four_eyes", "forbidden")
    alice_admin = Caller("alice", "acme", frozenset({"mail_admin"}))
    with pytest.raises(MailError) as e:
        ob.decide(alice_admin, sub["id"], approve=True, payload_hash_seen=sub["payload_hash"])   # an approver role does not let you approve your own send
    assert e.value.code == "four_eyes"
    with pytest.raises(MailError) as e:
        ob.decide(BOB, sub["id"], approve=True, payload_hash_seen=sub["payload_hash"])           # not an approver
    assert e.value.code == "forbidden"
    with pytest.raises(MailError) as e:
        ob.decide(CAROL, sub["id"], approve=True, payload_hash_seen="0" * 64)
    assert e.value.code == "hash_mismatch"
    t = clock()
    ok = ob.decide(CAROL, sub["id"], approve=True, payload_hash_seen=sub["payload_hash"], note="ok")
    assert (ok["state"], ok["approved_by"], ok["sendAt"], ok["canCancel"]) == ("approved", "carol", t + 30, True)
    clock.advance(31)
    assert [r["result"] for r in ob.process_due()] == ["sent"]
    assert relay.sent[0]["rcpts"] == ["client@ext.org"] and relay.sent[0]["from"] == "alice@acme.com"


def test_rejection_and_cancel_while_awaiting_approval():
    store, ob, _, clock, relay, boxes = make_world()
    mb = boxes["alice"]
    s1 = ob.submit(ALICE, mb["id"], draft(store, ALICE, mb, to=["a@ext.org"]))
    out = ob.decide(CAROL, s1["id"], approve=False, payload_hash_seen=s1["payload_hash"], note="no")
    assert (out["state"], out["undoStatus"]) == ("rejected", "canceled")
    s2 = ob.submit(ALICE, mb["id"], draft(store, ALICE, mb, to=["b@ext.org"]))
    assert ob.cancel(ALICE, s2["id"])["state"] == "canceled"
    clock.advance(999)
    assert ob.process_due() == [] and relay.sent == []


def test_content_changed_after_approval_is_never_sent():
    store, ob, _, clock, relay, boxes = make_world()
    mb = boxes["alice"]
    d = draft(store, ALICE, mb, to=["client@ext.org"])
    sub = ob.submit(ALICE, mb["id"], d)
    ob.decide(CAROL, sub["id"], approve=True, payload_hash_seen=sub["payload_hash"])
    from velaris.core import fieldseal
    from velaris.mail.db import SEAL
    store.run("UPDATE message SET body_text=? WHERE id=?", (fieldseal.seal("send the money to a new account", SEAL), d))   # tampering behind the API
    clock.advance(31)
    assert ob.process_due()[0] == {"id": sub["id"], "result": "failed", "code": "content_changed"}
    assert relay.sent == []


def test_attachments_and_assistant_drafts_need_approval_even_internally():
    store, ob, _, clock, relay, boxes = make_world()
    mb = boxes["alice"]
    s = ob.submit(ALICE, mb["id"], draft(store, ALICE, mb, attachments=[{"name": "r.pdf", "data_b64": B64, "content_type": "application/pdf"}]))
    assert [r["code"] for r in s["reasons"]] == ["attachment"]
    ad = drafts.create_assistant_draft(store, ALICE, mb["id"], to=["bob@acme.com"], subject="Re: hi", text="Sure.")
    s2 = ob.submit(ALICE, mb["id"], ad["id"])
    assert s2["state"] == "awaiting_approval" and [r["code"] for r in s2["reasons"]] == ["assistant_draft"]
    # a person editing the assistant's draft does not launder it
    ob.cancel(ALICE, s2["id"])
    drafts.update_draft(store, ALICE, mb["id"], ad["id"], {"text": "I rewrote this myself"})
    assert store.row(mb["id"], ad["id"])["origin"] == "assistant"
    assert ob.submit(ALICE, mb["id"], ad["id"])["state"] == "awaiting_approval"
    ob.decide(CAROL, s["id"], approve=True, payload_hash_seen=s["payload_hash"])
    clock.advance(31)
    ob.process_due()
    got = store.get_message(BOB, boxes["bob"]["id"], store.list_messages(BOB, boxes["bob"]["id"])["messages"][0]["id"])
    assert got["attachment_list"][0]["name"] == "r.pdf"


def test_delegate_acts_as_themselves_with_the_grant_recorded():
    store, ob, _, clock, _, boxes = make_world()
    mb = boxes["alice"]
    with pytest.raises(MailError):
        ob.submit(BOB, mb["id"], draft(store, ALICE, mb))
    store.set_delegate(ALICE, mb["id"], "bob", ["send"])
    d = drafts.create_draft(store, BOB, mb["id"], {"to": ["carol@acme.com"], "subject": "from the shared desk", "text": "hi"})["id"]
    sub = ob.submit(BOB, mb["id"], d)
    assert sub["submitted_by"] == "bob" and sub["on_behalf_of"] == "alice" and sub["grant"]
    store.create_mailbox(ADMIN, "carol@acme.com", owner_id="carol")
    clock.advance(31)
    ob.process_due()
    carol_box = [m for m in store.mailboxes_for(CAROL)][0]
    raw_row = store.list_messages(CAROL, carol_box["id"])["messages"][0]
    assert raw_row["from"] == "alice@acme.com"
    assert store.get_message(CAROL, carol_box["id"], raw_row["id"])["headers"].get("sender") == "bob@acme.com"     # who really sent it is visible


def test_relay_dkim_bcc_and_retry_behaviour():
    store, ob, _, clock, relay, boxes = make_world(settings={"dkim_domains": ["acme.com"], "allowlisted_domains": []})
    mb = boxes["alice"]
    sub = ob.submit(ALICE, mb["id"], draft(store, ALICE, mb, to=["client@ext.org"], bcc=["audit@ext.org"]))
    ob.decide(CAROL, sub["id"], approve=True, payload_hash_seen=sub["payload_hash"])
    clock.advance(31)
    relay.fail = RelayError("smtp_451", False)
    assert ob.process_due()[0]["result"] == "retry"
    assert ob.get(ALICE, sub["id"])["state"] == "approved" and ob.process_due() == []          # waits for its back-off
    relay.fail = None
    clock.advance(61)
    assert ob.process_due()[0]["result"] == "sent"
    sent = relay.sent[0]
    assert sorted(sent["rcpts"]) == ["audit@ext.org", "client@ext.org"] and b"audit@ext.org" not in sent["raw"].split(b"\r\n\r\n")[0]     # Bcc is envelope only
    key = dkim.load_or_create_key("velaris")
    assert dkim.verify_all(sent["raw"], FakeResolver(txt={"velaris._domainkey.acme.com": [dkim.dns_record(key)]}))[0].result == "pass"
    assert store.org_settings("acme")["dkim_selector"] == "velaris"
    assert parse_message(sent["raw"]).from_addr == "alice@acme.com"


def test_permanent_failure_missing_relay_and_unconfigured_dkim():
    store, ob, _, clock, relay, boxes = make_world(relay=None)
    ob.relay = None
    mb = boxes["alice"]
    sub = ob.submit(ALICE, mb["id"], draft(store, ALICE, mb, to=["x@acme.org"]))
    ob.decide(CAROL, sub["id"], approve=True, payload_hash_seen=sub["payload_hash"])
    clock.advance(31)
    assert ob.process_due()[0]["code"] == "relay_not_configured" and ob.get(ALICE, sub["id"])["state"] == "failed"
    ob.relay = type("R", (), {"send": lambda self, *a: (_ for _ in ()).throw(RelayError("smtp_550", True))})()
    d2 = draft(store, ALICE, mb, to=["x@acme.org"])
    s2 = ob.submit(ALICE, mb["id"], d2)
    ob.decide(CAROL, s2["id"], approve=True, payload_hash_seen=s2["payload_hash"])
    clock.advance(31)
    assert ob.process_due()[0] == {"id": s2["id"], "result": "failed", "code": "smtp_550"}


def test_draft_validation_from_address_headers_and_size():
    store, ob, _, _, _, boxes = make_world()
    mb = boxes["alice"]
    for bad in ({"to": ["bob@acme.com"], "subject": "x\r\nBcc: e@x.com"}, {"to": ["not an address"]}, {"to": ["bob@acme.com"], "from_address": "ceo@acme.com"},
                {"to": ["bob@acme.com"], "attachments": [{"name": "a", "data_b64": "!!!"}]}, {"to": [f"u{i}@x.org" for i in range(501)]},
                {"to": ["bob@acme.com"], "attachments": [{"name": "a", "data_b64": base64.b64encode(b"x" * 11_000_000).decode()}]}):
        with pytest.raises(MailError):
            drafts.create_draft(store, ALICE, mb["id"], {"subject": "s", "text": "t", **bad})
    with pytest.raises(MailError):
        ob.submit(ALICE, mb["id"], drafts.create_draft(store, ALICE, mb["id"], {"subject": "no one to send to", "text": "t"})["id"])
    store.set_mailbox_settings(ALICE, mb["id"], {"signature": "Alice, Ops"})
    d = drafts.create_draft(store, ALICE, mb["id"], {"to": ["bob@acme.com"], "subject": "s", "text": "body"})
    assert d["body_text"].endswith("\n\n-- \nAlice, Ops")
    store.add_alias(ADMIN, mb["id"], "ops@acme.com")
    assert drafts.create_draft(store, ALICE, mb["id"], {"to": ["bob@acme.com"], "from_address": "ops@acme.com", "subject": "s", "text": "t"})["from"] == "ops@acme.com"


def test_reply_sets_threading_headers_and_marks_original_answered():
    store, ob, ib, clock, _, boxes = make_world()
    mb = boxes["alice"]
    from velaris.tests.mail_helpers import raw_mail
    from velaris.mail.smtp import Envelope
    ib.deliver(Envelope("h.org", "192.0.2.1", "bob@acme.com", ["alice@acme.com"], raw_mail(frm="bob@acme.com", subject="Question", mid="q1@x")))
    orig = store.list_messages(ALICE, mb["id"])["messages"][0]
    d = drafts.create_draft(store, ALICE, mb["id"], {"to": ["bob@acme.com"], "text": "answer", "in_reply_to_id": orig["id"]})
    assert d["subject"] == "Re: Question" and d["in_reply_to"] == "q1@x" and d["references"] == ["q1@x"]
    sub = ob.submit(ALICE, mb["id"], d["id"])
    clock.advance(31)
    ob.process_due()
    assert store.get_message(ALICE, mb["id"], orig["id"])["answered"] and store.row(mb["id"], d["id"])["thread_id"] == store.row(mb["id"], orig["id"])["thread_id"] and sub


class FakeGate:
    def __init__(self):
        self.state, self.by = "pending", "prime-approver"

    def submit(self, run_id, pending, meta):
        return {"state": "pending", "call_hash": pending["call_hash"], "decided_by": "", "note": "", "run_id": run_id}

    def check(self, record):
        return {**record, "state": self.state, "decided_by": self.by}


def test_with_a_gate_the_decision_comes_from_the_gate_and_four_eyes_still_holds():
    gate = FakeGate()
    store, ob, _, clock, relay, boxes = make_world()
    ob.gate = gate
    mb = boxes["alice"]
    sub = ob.submit(ALICE, mb["id"], draft(store, ALICE, mb, to=["x@ext.org"]))
    with pytest.raises(MailError) as e:
        ob.decide(CAROL, sub["id"], approve=True, payload_hash_seen=sub["payload_hash"])
    assert e.value.code == "decided_in_prime"
    assert ob.get(ALICE, sub["id"])["state"] == "awaiting_approval"
    gate.state = "approved"
    assert ob.get(ALICE, sub["id"])["state"] == "approved" and ob.get(ALICE, sub["id"])["approved_by"] == "prime-approver"
    other = ob.submit(ALICE, mb["id"], draft(store, ALICE, mb, to=["y@ext.org"]))
    gate.by = "alice"                                                         # the gate names the submitter as approver: refused here too
    out = ob.get(ALICE, other["id"])
    assert out["state"] == "rejected" and out["error"] == "four_eyes"


def test_audit_trail_holds_ids_and_hashes_never_addresses_or_subjects():
    from velaris.intel import trace
    store, ob, _, clock, _, boxes = make_world()
    mb = boxes["alice"]
    sub = ob.submit(ALICE, mb["id"], draft(store, ALICE, mb, to=["client@ext.org"]))
    ob.decide(CAROL, sub["id"], approve=True, payload_hash_seen=sub["payload_hash"])
    clock.advance(31)
    ob.process_due()
    mail = [e for e in trace.entries() if e["actor"] == "mail"]
    blob = str(mail)
    for secret in ("client@ext.org", "alice@acme.com", "Plan", "see you at 3"):
        assert secret not in blob
    assert {"submission.create", "submission.approved", "submission.sent"} <= {e["action"] for e in mail} and trace.verify()["ok"]


def test_other_organisations_cannot_see_cancel_or_decide_a_submission():
    store, ob, _, clock, relay, boxes = make_world()
    mb = boxes["alice"]
    sub = ob.submit(ALICE, mb["id"], draft(store, ALICE, mb, to=["client@ext.org"]))
    outsiders = [Caller("alice", "evilcorp"), Caller("carol", "evilcorp", frozenset({"mail_approver", "mail_admin"}))]
    for who in outsiders:
        for call in (lambda: ob.get(who, sub["id"]), lambda: ob.cancel(who, sub["id"]),
                     lambda: ob.decide(who, sub["id"], approve=True, payload_hash_seen=sub["payload_hash"]),
                     lambda: ob.submit(who, mb["id"], "x"), lambda: ob.list_submissions(who, mb["id"])):
            with pytest.raises(MailError) as e:
                call()
            assert e.value.status == 404
        assert ob.pending_approvals(who) == []
    assert ob.get(ALICE, sub["id"])["state"] == "awaiting_approval" and store.one("SELECT org FROM submission")["org"] == "acme"


DSN = (b"From: MAILER-DAEMON@mx.remote.org\r\nTo: alice@acme.com\r\nSubject: Undelivered Mail Returned to Sender\r\nMessage-ID: <dsn-%MID%-%ACTION%@mx.remote.org>\r\n"
       b"MIME-Version: 1.0\r\nContent-Type: multipart/report; report-type=delivery-status; boundary=\"B\"\r\n\r\n"
       b"--B\r\nContent-Type: text/plain\r\n\r\nYour message could not be delivered.\r\n"
       b"--B\r\nContent-Type: message/delivery-status\r\n\r\nReporting-MTA: dns; mx.remote.org\r\n\r\n"
       b"Final-Recipient: rfc822; carl@remote.org\r\nAction: %ACTION%\r\nStatus: %STATUS%\r\nDiagnostic-Code: smtp; 550 secret server text\r\n\r\n"
       b"--B\r\nContent-Type: text/rfc822-headers\r\n\r\nMessage-ID: <%MID%>\r\nSubject: Plan\r\n\r\n--B--\r\n")


def _dsn(mid, action="failed", status="5.1.1"):
    return DSN.replace(b"%MID%", mid.encode()).replace(b"%ACTION%", action.encode()).replace(b"%STATUS%", status.encode())


def test_a_permanent_bounce_marks_the_submission_and_a_delay_or_stranger_does_not():
    """KAN-71: a message the relay accepted but the remote server later refused stayed 'sent' for ever."""
    from velaris.mail import dsn
    from velaris.mail.smtp import Envelope
    store, ob, ib, clock, relay, boxes = make_world(settings={"allowlisted_domains": ["remote.org"]})
    mb = boxes["alice"]
    d = draft(store, ALICE, mb, to=("carl@remote.org",))
    sub = ob.submit(ALICE, mb["id"], d)
    assert sub["state"] == "awaiting_approval" or sub["state"] == "approved"
    clock.advance(31)
    ob.process_due()
    s = ob.get(ALICE, sub["id"])
    assert s["state"] == "sent"
    mid = store.row(mb["id"], d)["message_id"]
    assert dsn.parse_dsn(_dsn(mid)) == {"action": "failed", "status": "5.1.1", "recipient": "carl@remote.org", "original_message_id": mid}
    assert dsn.parse_dsn(b"From: a@b.c\r\n\r\nplain mail") is None and dsn.parse_dsn(b"\xff\x00garbage") is None
    for raw in (_dsn(mid, "delayed", "4.4.1"), _dsn("someone-elses@x.org")):                 # temporary, or not ours: nothing changes
        ib.deliver(Envelope("mx.remote.org", "192.0.2.9", "MAILER-DAEMON@mx.remote.org", ["alice@acme.com"], raw))
    assert ob.get(ALICE, sub["id"])["state"] == "sent"
    code, _ = ib.deliver(Envelope("mx.remote.org", "192.0.2.9", "MAILER-DAEMON@mx.remote.org", ["alice@acme.com"], _dsn(mid)))
    assert code == 250
    after = ob.get(ALICE, sub["id"])
    assert after["state"] == "bounced" and after["error"] == "dsn_5.1.1" and "secret server text" not in str(after)
