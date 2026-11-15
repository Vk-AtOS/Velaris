"""Rules: validation, actions, forwarding that needs approval, vacation and auto-reply loop protection."""
import pytest

from velaris.mail import rules
from velaris.mail.common import MailError
from velaris.mail.smtp import Envelope
from velaris.tests.mail_helpers import ALICE, BOB, CAROL, make_world, raw_mail


def receive(ib, rcpt="alice@acme.com", **kw):
    kw.setdefault("to", rcpt)
    return ib.deliver(Envelope("h.ext.org", "192.0.2.1", kw.get("frm", "x@ext.org"), [rcpt], raw_mail(**kw)))


def inbox(store, caller, mb, folder="inbox"):
    return store.list_messages(caller, mb["id"], folder=folder)["messages"]


def test_rule_validation_refuses_unsafe_or_malformed_rules():
    store, _, _, _, _, boxes = make_world()
    mb = boxes["alice"]
    ok = {"name": "r", "conditions": [{"field": "subject", "op": "contains", "value": "invoice"}], "actions": [{"type": "flag"}]}
    assert rules.create_rule(store, ALICE, mb["id"], ok)["name"] == "r"
    bad = [{**ok, "name": ""}, {**ok, "actions": []}, {**ok, "actions": [{"type": "delete"}]}, {**ok, "actions": [{"type": "move", "folder": "Trash"}]},
           {**ok, "actions": [{"type": "move", "folder": "Nowhere"}]}, {**ok, "conditions": [{"field": "password", "op": "==", "value": "x"}]},
           {**ok, "conditions": [{"field": "subject", "op": "matches", "value": "(a+)+$"}]}, {**ok, "conditions": [{"field": "size", "op": ">", "value": "big"}]},
           {**ok, "actions": [{"type": "forward", "to": ["not an address"]}]}, {**ok, "actions": [{"type": "forward", "to": ["a@x.org"] * 6}]},
           {**ok, "extra": 1}, {**ok, "conditions": [{"field": "subject", "op": "contains", "value": "x" * 600}]}, "nonsense"]
    for b in bad:
        with pytest.raises(MailError):
            rules.create_rule(store, ALICE, mb["id"], b)
    with pytest.raises(MailError):
        rules.list_rules(store, BOB, mb["id"])                                    # someone else's rules are not visible


def test_move_label_flag_mark_read_stop_case_insensitive_and_missing_fields_do_not_match():
    store, _, ib, _, _, boxes = make_world()
    mb = boxes["alice"]
    store.create_folder(ALICE, mb["id"], "Invoices")
    rules.create_rule(store, ALICE, mb["id"], {"name": "inv", "position": 1, "conditions": [{"field": "subject", "op": "contains", "value": "INVOICE"},
                      {"field": "from_domain", "op": "==", "value": "Billing.Example.COM"}],
                      "actions": [{"type": "label", "label": "finance"}, {"type": "flag"}, {"type": "mark_read"}, {"type": "move", "folder": "Invoices"}, {"type": "stop"}]})
    rules.create_rule(store, ALICE, mb["id"], {"name": "later", "position": 2, "conditions": [], "actions": [{"type": "label", "label": "never"}]})
    rules.create_rule(store, ALICE, mb["id"], {"name": "list", "position": 0, "conditions": [{"field": "list_id", "op": "contains", "value": "news"}],
                      "actions": [{"type": "label", "label": "news"}]})
    receive(ib, subject="Your Invoice #42", frm="ar@billing.example.com", mid="i1@x")
    m = store.list_messages(ALICE, mb["id"], folder="Invoices")["messages"][0]
    assert m["labels"] == ["finance"] and m["flagged"] and m["seen"]                  # stop: the later rule did not run
    receive(ib, subject="Hello", mid="i2@x")
    plain = inbox(store, ALICE, mb)[0]
    assert plain["labels"] == ["never"]                                               # no list-id header: the "news" rule did not match
    assert rules.dry_run(store, ALICE, mb["id"], {"name": "t", "conditions": [{"field": "subject", "op": "contains", "value": "hello"}], "actions": [{"type": "flag"}]})["would_match"] == [plain["id"]]
    assert not store.get_message(ALICE, mb["id"], plain["id"])["flagged"]             # a dry run changes nothing


def test_forwarding_always_waits_for_a_second_person_and_never_forwards_machines_or_forwards():
    store, ob, ib, clock, relay, boxes = make_world(settings={"allowlisted_domains": ["partner.com"]})
    mb = boxes["alice"]
    rules.create_rule(store, ALICE, mb["id"], {"name": "fwd", "conditions": [{"field": "subject", "op": "contains", "value": "contract"}],
                                               "actions": [{"type": "forward", "to": ["partner@partner.com"]}]})
    receive(ib, subject="New contract", mid="c1@x", body="terms")
    subs = ob.list_submissions(ALICE, mb["id"])
    assert len(subs) == 1 and subs[0]["state"] == "awaiting_approval" and subs[0]["origin"] == "rule_forward"
    assert [r["code"] for r in subs[0]["reasons"]] == ["forward_rule"] and subs[0]["submitted_by"].startswith("rule:")
    clock.advance(86400 * 3)
    assert ob.process_due() == [] and relay.sent == []                                  # no amount of waiting sends it
    pend = ob.pending_approvals(CAROL)[0]
    assert pend["preview"]["to"] == ["partner@partner.com"] and "Forwarded message" in pend["preview"]["text"] and "terms" in pend["preview"]["text"]
    approved = ob.decide(CAROL, subs[0]["id"], approve=True, payload_hash_seen=subs[0]["payload_hash"])
    assert approved["state"] == "approved"
    clock.advance(31)
    ob.process_due()
    assert relay.sent[0]["rcpts"] == ["partner@partner.com"] and b"X-Velaris-Forwarded" in relay.sent[0]["raw"]
    receive(ib, subject="New contract again", mid="c2@x", extra="Auto-Submitted: auto-generated\r\n")
    receive(ib, subject="Fwd contract", mid="c3@x", extra="X-Velaris-Forwarded: 1\r\n")
    assert len(ob.list_submissions(ALICE, mb["id"])) == 1                               # machine mail and already-forwarded mail are not forwarded


def test_forward_rule_with_internal_target_still_needs_approval():
    store, ob, ib, _, relay, boxes = make_world()
    rules.create_rule(store, ALICE, boxes["alice"]["id"], {"name": "f", "conditions": [], "actions": [{"type": "forward", "to": ["bob@acme.com"]}]})
    receive(ib, mid="f1@x")
    assert ob.list_submissions(ALICE, boxes["alice"]["id"])[0]["state"] == "awaiting_approval" and relay.sent == []


@pytest.mark.parametrize("extra,frm,to", [
    ("Auto-Submitted: auto-generated\r\n", "x@ext.org", "alice@acme.com"),
    ("Auto-Submitted: auto-replied\r\n", "x@ext.org", "alice@acme.com"),
    ("Precedence: bulk\r\n", "x@ext.org", "alice@acme.com"),
    ("Precedence: list\r\n", "x@ext.org", "alice@acme.com"),
    ("List-Id: <news.ext.org>\r\n", "x@ext.org", "alice@acme.com"),
    ("List-Unsubscribe: <mailto:u@ext.org>\r\n", "x@ext.org", "alice@acme.com"),
    ("X-Auto-Response-Suppress: All\r\n", "x@ext.org", "alice@acme.com"),
    ("Return-Path: <>\r\n", "x@ext.org", "alice@acme.com"),
    ("", "noreply@ext.org", "alice@acme.com"),
    ("", "mailer-daemon@ext.org", "alice@acme.com"),
    ("", "alice@acme.com", "alice@acme.com"),                                          # from myself
    ("", "x@ext.org", "someone-else@acme.com, bob@acme.com"),                           # not addressed to me: a Bcc or a list
])
def test_vacation_loop_protection_suppresses(extra, frm, to):
    store, ob, ib, clock, relay, boxes = make_world()
    store.set_mailbox_settings(ALICE, boxes["alice"]["id"], {"vacation": {"enabled": True, "body": "away until Monday"}})
    ib.deliver(Envelope("h.org", "192.0.2.1", frm, ["alice@acme.com"], raw_mail(frm=frm, to=to, extra=extra)))
    clock.advance(60)
    ob.process_due()
    assert relay.sent == [] and ob.list_submissions(ALICE, boxes["alice"]["id"]) == []


def test_vacation_replies_once_per_sender_per_window_and_marks_itself_automatic():
    store, ob, ib, clock, relay, boxes = make_world(settings={"autoreply_external": True})
    mb = boxes["alice"]
    store.set_mailbox_settings(ALICE, mb["id"], {"vacation": {"enabled": True, "subject": "Out of office", "body": "away until Monday", "window_days": 7,
                                                              "start": clock() - 10, "end": clock() + 30 * 86400}})
    receive(ib, mid="v1@x")
    clock.advance(31)                                                                   # the undo window passes
    ob.process_due()
    assert len(relay.sent) == 1
    raw = relay.sent[0]["raw"]
    assert b"Auto-Submitted: auto-replied" in raw and b"Precedence: bulk" in raw and b"In-Reply-To: <v1@x>" in raw
    assert relay.sent[0]["rcpts"] == ["x@ext.org"]
    receive(ib, mid="v2@x")
    clock.advance(31)                                                                   # the undo window passes
    ob.process_due()
    assert len(relay.sent) == 1                                                         # same sender inside the window
    receive(ib, mid="v3@x", frm="other@ext.org")
    clock.advance(31)                                                                   # the undo window passes
    ob.process_due()
    assert len(relay.sent) == 2                                                         # a different sender gets one
    clock.advance(8 * 86400)
    receive(ib, mid="v4@x")
    clock.advance(31)                                                                   # the undo window passes
    ob.process_due()
    assert len(relay.sent) == 3                                                         # window over
    store.set_mailbox_settings(ALICE, mb["id"], {"vacation": {"enabled": True, "body": "x", "end": clock() - 1}})
    receive(ib, mid="v5@x", frm="late@ext.org")
    clock.advance(31)                                                                   # the undo window passes
    ob.process_due()
    assert len(relay.sent) == 3                                                         # past its end date


def test_two_responders_cannot_loop_and_external_auto_replies_can_be_turned_off():
    store, ob, ib, clock, relay, boxes = make_world(settings={"autoreply_external": False})
    for who, caller in (("alice", ALICE), ("bob", BOB)):
        store.set_mailbox_settings(caller, boxes[who]["id"], {"vacation": {"enabled": True, "body": f"{who} is away"}})
    ib.deliver(Envelope("h.org", "192.0.2.1", "bob@acme.com", ["alice@acme.com"], raw_mail(frm="bob@acme.com", to="alice@acme.com", mid="p1@x")))
    for _ in range(5):                                                                  # let any ping-pong run
        clock.advance(60)
        ob.process_due()
    assert store.list_messages(BOB, boxes["bob"]["id"])["total"] == 1                   # alice answered bob once
    assert ob.list_submissions(BOB, boxes["bob"]["id"]) == []                           # bob never answered the answer
    receive(ib, mid="e1@x")
    ob.process_due()
    assert relay.sent == []                                                             # org setting: no automatic mail to outside domains


def test_auto_reply_rule_has_its_own_daily_window():
    store, ob, ib, clock, relay, boxes = make_world(settings={"autoreply_external": True})
    mb = boxes["alice"]
    rules.create_rule(store, ALICE, mb["id"], {"name": "ack", "conditions": [{"field": "subject", "op": "contains", "value": "support"}],
                                               "actions": [{"type": "auto_reply", "subject": "Got it", "body": "We will reply soon."}]})
    receive(ib, subject="support needed", mid="a1@x")
    receive(ib, subject="support again", mid="a2@x")
    clock.advance(31)
    ob.process_due()
    assert len(relay.sent) == 1
    clock.advance(86400 + 1)
    receive(ib, subject="support third", mid="a3@x")
    clock.advance(31)
    ob.process_due()
    assert len(relay.sent) == 2


def test_auto_reply_waits_out_the_undo_window_can_be_cancelled_and_external_needs_the_admin_setting():
    """KAN-108: an auto-reply is no longer sent at once with no way back, and outside domains need autoreply_external."""
    store, ob, ib, clock, relay, boxes = make_world(settings={"autoreply_external": True})
    mb = boxes["alice"]
    store.set_mailbox_settings(ALICE, mb["id"], {"vacation": {"enabled": True, "body": "away until Monday"}})
    receive(ib, mid="u1@x")
    ob.process_due()
    assert relay.sent == []                                                             # still inside the undo window
    sub = ob.list_submissions(ALICE, mb["id"])[0]
    assert sub["undoStatus"] == "pending" and sub["canCancel"]
    ob.cancel(ALICE, sub["id"])
    clock.advance(60)
    ob.process_due()
    assert relay.sent == []


def test_external_auto_replies_are_off_by_default():
    store, ob, ib, clock, relay, boxes = make_world()                                    # default organisation settings
    assert store.org_settings("acme")["autoreply_external"] is False
    store.set_mailbox_settings(ALICE, boxes["alice"]["id"], {"vacation": {"enabled": True, "body": "away"}})
    receive(ib, mid="u2@x")
    clock.advance(60)
    ob.process_due()
    assert relay.sent == []
