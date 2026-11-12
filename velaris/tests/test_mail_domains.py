"""Domain ownership (DNS challenge, one organisation per verified domain) and who may grant delegation."""
import pytest

from velaris.core.access import Caller
from velaris.intel import trace
from velaris.mail.common import MailError
from velaris.mail.store import MailStore
from velaris.tests.mail_helpers import ADMIN, ALICE, BOB, Clock, FakeResolver, make_world, verify_domain

EVIL_ADMIN = Caller("eve", "evilcorp", frozenset({"mail_admin"}))


def fresh():
    return MailStore(clock=Clock())


def test_unverified_domains_cannot_be_used_in_settings_mailboxes_or_aliases():
    s = fresh()
    for key in ("local_domains", "dkim_domains"):
        with pytest.raises(MailError) as e:
            s.set_org_settings(ADMIN, {key: ["acme.com"]})
        assert e.value.code == "domain_unverified"
    s.claim_domain(ADMIN, "acme.com")                                           # claimed is not verified
    with pytest.raises(MailError):
        s.set_org_settings(ADMIN, {"local_domains": ["acme.com"]})
    with pytest.raises(MailError) as e:
        s.create_mailbox(ADMIN, "a@acme.com", owner_id="a")
    assert e.value.code == "domain_unverified"
    s.create_mailbox(ADMIN, "mirror@gmail.com", owner_id="a", kind="external")      # connector mirrors need no hosted domain
    with pytest.raises(MailError):
        s.claim_domain(ALICE, "acme.com")                                          # admin only


def test_verification_success_failure_and_dns_trouble():
    s = fresh()
    tok = s.claim_domain(ADMIN, "acme.com")
    assert tok["status"] == "pending" and tok["record"]["name"] == "_velaris.acme.com" and tok["record"]["value"].startswith("velaris-verify=")
    for z in ({}, {"_velaris.acme.com": ["velaris-verify=wrong"]}, {"_velaris.acme.com": ["v=spf1 -all"]}):
        assert s.verify_domain(ADMIN, "acme.com", FakeResolver(txt=z))["status"] == "pending"
    with pytest.raises(MailError) as e:
        s.verify_domain(ADMIN, "acme.com", FakeResolver(down=("_velaris.acme.com",)))
    assert e.value.code == "dns_unavailable"
    with pytest.raises(MailError) as e:
        s.verify_domain(ADMIN, "other.com", FakeResolver())
    assert e.value.code == "not_claimed"
    assert s.verify_domain(ADMIN, "acme.com", FakeResolver(txt={"_velaris.acme.com": [tok["record"]["value"]]}))["status"] == "verified"
    assert s.set_org_settings(ADMIN, {"local_domains": ["ACME.com"]})["local_domains"] == ["acme.com"]
    assert s.create_mailbox(ADMIN, "a@acme.com", owner_id="a")["address"] == "a@acme.com"
    mb = s.mailboxes_for(Caller("a", "acme"))[0]
    with pytest.raises(MailError):
        s.add_alias(ADMIN, mb["id"], "x@unverified.org")
    assert s.add_alias(ADMIN, mb["id"], "ops@acme.com") == ["ops@acme.com"]


def test_a_verified_domain_belongs_to_exactly_one_organisation():
    s = fresh()
    verify_domain(s, ADMIN, "acme.com")
    with pytest.raises(MailError) as e:
        s.claim_domain(EVIL_ADMIN, "acme.com")
    assert e.value.code == "domain_taken"
    # a claim made before the owner verified cannot be verified afterwards, even with a correct-looking record
    s2 = fresh()
    tok_evil = s2.claim_domain(EVIL_ADMIN, "race.com")["record"]["value"]
    tok_acme = s2.claim_domain(ADMIN, "race.com")["record"]["value"]
    assert tok_evil != tok_acme                                                  # per-organisation tokens
    assert s2.verify_domain(ADMIN, "race.com", FakeResolver(txt={"_velaris.race.com": [tok_acme]}))["status"] == "verified"
    with pytest.raises(MailError) as e:
        s2.verify_domain(EVIL_ADMIN, "race.com", FakeResolver(txt={"_velaris.race.com": [tok_evil]}))
    assert e.value.code == "domain_taken"
    with pytest.raises(MailError):
        s2.set_org_settings(EVIL_ADMIN, {"local_domains": ["race.com"]})
    assert s2.domains(EVIL_ADMIN)[0]["status"] == "pending"


def test_dkim_signs_only_for_verified_domains():
    store, ob, _, clock, relay, boxes = make_world(settings={"dkim_domains": ["acme.com"]})
    from velaris.mail import drafts
    d = drafts.create_draft(store, ALICE, boxes["alice"]["id"], {"to": ["x@ext.org"], "subject": "s", "text": "t"})["id"]
    sub = ob.submit(ALICE, boxes["alice"]["id"], d)
    ob.decide(Caller("carol", "acme", frozenset({"mail_approver"})), sub["id"], approve=True, payload_hash_seen=sub["payload_hash"])
    store.run("UPDATE domain SET verified=0 WHERE domain='acme.com'")           # ownership lapses (e.g. re-checked and failed)
    clock.advance(31)
    ob.process_due()
    assert b"DKIM-Signature" not in relay.sent[0]["raw"]


def test_only_the_owner_grants_delegation_and_it_cannot_be_chained():
    store, ob, _, _, _, boxes = make_world()
    mb = boxes["alice"]["id"]
    carol = Caller("carol", "acme")
    eve_admin = Caller("eve", "acme", frozenset({"mail_admin"}))
    for who in (ADMIN, eve_admin):
        for rights in (["read"], ["read", "send", "approve"]):
            for target in (who.id, "bob"):
                with pytest.raises(MailError) as e:
                    store.set_delegate(who, mb, target, rights)
                assert e.value.status == 403
    assert store.delegates(ADMIN, mb) == []                                      # an admin could not read anyone's mail by this route
    store.set_delegate(ALICE, mb, "bob", ["manage"])                             # the owner can
    with pytest.raises(MailError) as e:
        store.set_delegate(BOB, mb, "carol", ["read"])                           # a delegate, even with manage, cannot hand it on
    assert e.value.status == 403
    with pytest.raises(MailError):
        store.set_delegate(BOB, mb, "bob", ["approve"])
    with pytest.raises(MailError):
        store.remove_delegate(ADMIN, mb, "bob")
    with pytest.raises(MailError):
        store.get_message(carol, mb, "x")
    assert [d["user_id"] for d in store.delegates(ALICE, mb)] == ["bob"]
    store.remove_delegate(ALICE, mb, "bob")
    ents = [e for e in trace.entries() if e["actor"] == "mail" and e["action"].startswith("delegate.")]
    assert {"delegate.set", "delegate.remove", "delegate.refused"} <= {e["action"] for e in ents}
    assert all("bob@" not in str(e) for e in ents) and any(e["payload"].get("delegate") == "bob" for e in ents)
