"""hr_wiring: the real adapters make the paths that used to refuse work end to end, and each still refuses when its adapter is absent."""
import base64
import hashlib
import json

import pytest

from velaris.agentkit import hr_wiring
from velaris.agentkit.hiring_testkit import as_, bootstrap, consent, trace_text, who
from velaris.agentkit.onboarding_pdf import build_pdf
from velaris.agents.ATS_CORE.main import AtsCore
from velaris.agents.ESIGN.main import Esign
from velaris.agents.OFFER_LETTERS.main import OfferLetters
from velaris.backend.engine import backend
from velaris.core.access import Caller, acting_as
from velaris.intel.paths import agent_dir
from velaris.tests.mail_helpers import make_world
from velaris.tests.onboarding_helpers import HR1, HR2, MGR, ORG, Clock, FakeSender, person

IT = Caller("it1", ORG, frozenset())
OTHER_HR = Caller("hrx", "globex", frozenset({"hr_admin"}))
NOT_WIRED = {}


def run(agent, method, caller, config=None, **params):
    return backend.run(agent, method, params, caller=caller, config=config)


@pytest.fixture()
def application():
    """An application in ATS_CORE (real, with consent) for Asha Kumar."""
    ats = AtsCore()
    rid, c = bootstrap(ats)
    with as_(c["rec"]):
        r = ats.add_candidate(name="Asha Kumar", email="asha@example.com", phone="+91 98765 43210", source="careers_page",
                              requisition_id=rid, consent=consent())
    return r["application"]["id"], c


def accepted_offer(app):
    oid = make_offer(app)
    assert run("OFFER_LETTERS", "send_offer", HR1, offer_id=oid, delivered_manually=True)["status"] == "ok"
    assert run("OFFER_LETTERS", "record_response", HR1, offer_id=oid, response="accept")["status"] == "ok"
    return oid


def convert(app, caller=HR1, approver=HR2, **kw):
    kw.setdefault("offer_id", accepted_offer(app))
    p = run("EMPLOYEE_RECORDS", "propose_conversion", caller, application_id=app, department="Engineering", designation="Engineer",
            manager_id="mgr1", join_date="2026-12-01", **kw)
    if p["status"] != "ok":
        return p, None
    r = run("EMPLOYEE_RECORDS", "approve_conversion", approver, conversion_id=p["conversion"]["id"])
    return p, r


# ---- composition ------------------------------------------------------------------------------------------------------
def test_hr_config_builds_what_each_agent_takes_and_keeps_what_is_given():
    assert set(hr_wiring.hr_config("ONBOARDING_FLOW")) == {"policy_acks", "offers"}
    assert set(hr_wiring.hr_config("EMPLOYEE_RECORDS")) == {"ats", "offers", "policy_acks"}
    assert set(hr_wiring.hr_config("OFFER_LETTERS", environ={})) == {"ats", "esign"}                  # no mailbox: no sender
    esign = hr_wiring.hr_config("ESIGN")
    assert esign == {} and "pdf_signer" not in esign and "sender" not in esign                         # left not_configured
    assert hr_wiring.hr_config("LEAVE_MANAGEMENT") == {}
    fake = object()
    assert hr_wiring.hr_config("EMPLOYEE_RECORDS", {"ats": fake})["ats"] is fake


def test_adapters_answer_only_for_the_organisation_of_the_current_caller(application):
    app, _ = application
    ats, offers = hr_wiring.AtsReader(), hr_wiring.OffersReader()
    assert ats.get_candidate(app, ORG) is None and ats.record_offer_outcome(app, ORG, "accepted", "o1") is False     # no caller
    with acting_as(HR1):
        got = ats.get_candidate(app, ORG)
        assert got["name"] == "Asha Kumar" and got["email"] == "asha@example.com" and got["consent"]["notice_version"] == "v1"
        assert got["role_title"] == "Backend Engineer" and set(got["consent"]) == {"purpose", "notice_version", "given_at", "retention_until"}
        assert ats.get_candidate(app, "globex") is None and offers.get_offer_status("x", "globex") is None
        assert ats.get_candidate("app-nope", ORG) is None
    with acting_as(OTHER_HR):
        assert ats.get_candidate(app, ORG) is None and ats.get_candidate(app, "globex") is None        # not their organisation's data
    with acting_as(person("E1")):
        assert ats.get_candidate(app, ORG) is None                                                      # ATS_CORE's own role gate: no hiring role
    with acting_as(who("hiring_manager")):
        assert ats.get_candidate(app, ORG) is None                                                      # access category 'candidate'


# ---- candidate -> employee conversion reads ATS -----------------------------------------------------------------------
def test_conversion_reads_the_candidate_from_ats_and_refuses_without_the_adapter(application):
    app, _ = application
    p, r = convert(app)
    assert p["conversion"]["needs_review"] == []                                                          # consent was carried over from the ATS
    assert r["status"] == "ok" and r["employee_id"]
    emp = run("EMPLOYEE_RECORDS", "get_employee", HR1, employee_id=r["employee_id"])["employee"]
    assert emp["name"] == "Asha Kumar" and emp["email"] == "asha@example.com"                              # taken from ATS_CORE
    oid = accepted_offer(app)
    p2 = run("EMPLOYEE_RECORDS", "propose_conversion", HR1, application_id="app-nope", department="E", designation="E", manager_id="m",
             join_date="2026-12-01", offer_id=oid)
    assert p2["status"] == "not_found"                                                                    # the ATS has no such application
    assert run("EMPLOYEE_RECORDS", "propose_conversion", OTHER_HR, application_id=app, department="E", designation="E", manager_id="m",
               join_date="2027-01-04", offer_id=oid)["status"] == "not_found"                                           # another organisation's caller
    absent = run("EMPLOYEE_RECORDS", "propose_conversion", HR1, config=NOT_WIRED, application_id="app-other", department="E",
                 designation="E", manager_id="m", join_date="2027-01-04", offer_id=oid)
    assert absent["status"] == "invalid_input" and "no applicant tracking agent" in absent["reason"]       # fail closed: names are not taken on trust


def test_a_withdrawn_consent_is_not_carried_into_an_employee_record(application):
    app, c = application
    oid = accepted_offer(app)
    cid = json.loads((agent_dir("ATS_CORE") / "evaluation.json").read_text())["applications"][app]["candidate_id"]
    with as_(c["rec"]):
        assert AtsCore().withdraw_consent(candidate_id=cid)["status"] == "ok"
    p = run("EMPLOYEE_RECORDS", "propose_conversion", HR1, application_id=app, department="E", designation="E", manager_id="m", join_date="2027-01-04",
            offer_id=oid)
    assert p["status"] == "not_found"


# ---- policy acknowledgement task completes with the real POLICY_ACKS --------------------------------------------------
def test_policy_ack_task_completes_through_the_real_adapter_and_refuses_without_it(application):
    app, _ = application
    _, hired = convert(app)
    emp = hired["employee_id"]
    run("POLICY_ACKS", "publish_policy", HR1, policy_key="code_of_conduct", title="Code of conduct", text="Be decent.", effective_date="2026-11-01")
    me = Caller("u-" + emp, ORG, frozenset(), emp)
    text_sha = hashlib.sha256(b"Be decent.").hexdigest()
    got = run("POLICY_ACKS", "get_policy", me, policy_key="code_of_conduct")["policy"]
    ack = run("POLICY_ACKS", "acknowledge", me, policy_key="code_of_conduct", seen_text_sha256=got.get("text_sha256", text_sha))
    assert ack["status"] == "ok", ack
    case = run("ONBOARDING_FLOW", "start_onboarding", HR1, subject_id=emp, name="Asha Kumar", email="asha@example.com", join_date="2026-12-01",
               role_group="engineering", location="chennai", manager_id="mgr1", it_owner_id="it1")["case"]["id"]
    assert run("ONBOARDING_FLOW", "complete_task", HR1, case_id=case, task_key="confirm_offer_accepted")["status"] == "ok"
    assert run("ONBOARDING_FLOW", "complete_task", IT, case_id=case, task_key="provision_accounts")["status"] == "ok"
    args = dict(case_id=case, task_key="ack_code_of_conduct", evidence_ref=ack["evidence_sha256"])
    assert run("ONBOARDING_FLOW", "complete_task", me, config=NOT_WIRED, **args)["status"] == "not_configured"      # adapter absent
    assert run("ONBOARDING_FLOW", "complete_task", me, **{**args, "evidence_ref": "made-up"})["status"] == "evidence_mismatch"
    assert run("ONBOARDING_FLOW", "complete_task", Caller("u-x", "globex", frozenset(), emp), **args)["status"] in ("not_found", "denied")
    assert run("ONBOARDING_FLOW", "complete_task", me, **args)["status"] == "ok"                                       # real evidence, real adapter


# ---- offer response with sealed e-sign evidence -----------------------------------------------------------------------
def make_offer(app):
    r = run("OFFER_LETTERS", "create_offer", HR1, candidate_name="ignored", candidate_email="ignored@x.in", role_title="Engineer", department="Eng",
            location="Chennai", join_date="2027-02-01", annual_ctc="1200000", hiring_manager_id="mgr1", hr_approver_id="hr2", application_id=app, company_name="Acme IT Services")
    assert r["status"] == "ok", r
    oid = r["offer"]["id"]
    assert run("OFFER_LETTERS", "submit_for_approval", HR1, offer_id=oid)["status"] == "ok"
    assert run("OFFER_LETTERS", "approve", MGR, offer_id=oid, acknowledge_review=True)["status"] == "ok"
    assert run("OFFER_LETTERS", "approve", HR2, offer_id=oid, acknowledge_review=True)["status"] == "ok"
    return oid


def seal(oid, email="asha@example.com", name="Asha Kumar", otp=False, pdf_b64=None):
    sender, clock = FakeSender(), Clock()
    e = Esign({"sender": sender, "clock": clock})
    with acting_as(HR1):
        rid = e.create_request("Offer", pdf_b64 or base64.b64encode(build_pdf([("h1", "Offer")])).decode(), [{"name": name, "email": email}],
                               document_ref=oid)["request"]["id"]
        assert e.send_request(rid)["status"] == "ok"
    tok = sender.token_for(email)
    ip, ua = "203.0.113.9", "test"
    assert e.open_signing(tok, email, ip, ua)["status"] == "ok"
    assert e.give_consent(tok, email, ip, ua, "v1")["status"] == "ok"
    assert e.sign_document(tok, email, name, ip, ua)["request_status"] == "completed"
    return rid


def test_offer_response_cites_sealed_esign_evidence_through_the_real_adapters(application):
    app, c = application
    oid = make_offer(app)
    assert run("OFFER_LETTERS", "get_offer", HR1, offer_id=oid)["offer"]["candidate"]["name"] == "Asha Kumar"      # from ATS, not the arguments
    assert run("OFFER_LETTERS", "send_offer", HR1, offer_id=oid)["status"] == "not_configured"                     # no sender: only a draft
    assert run("OFFER_LETTERS", "send_offer", HR1, offer_id=oid, delivered_manually=True)["offer"]["status"] == "sent"
    pdf = run("OFFER_LETTERS", "render_offer", HR1, offer_id=oid, fmt="pdf")["pdf_base64"]
    rid = seal(oid, pdf_b64=pdf)
    other = seal("ofr-other", email="other@example.com", name="Other Person")                                     # sealed, but for another document
    wrong_doc = seal(oid)                                                                                          # names this offer, carries another document
    wrong_person = seal(oid, email="stranger@example.com", name="Some Stranger", pdf_b64=pdf)                      # right document, not the candidate
    assert run("OFFER_LETTERS", "record_response", HR1, offer_id=oid, response="accept", evidence_ref=wrong_doc)["status"] == "evidence_mismatch"
    assert run("OFFER_LETTERS", "record_response", HR1, offer_id=oid, response="accept", evidence_ref=wrong_person)["status"] == "evidence_mismatch"
    assert run("OFFER_LETTERS", "record_response", HR1, config=NOT_WIRED, offer_id=oid, response="accept", evidence_ref=rid)["status"] == "not_configured"
    assert run("OFFER_LETTERS", "record_response", HR1, offer_id=oid, response="accept", evidence_ref=other)["status"] == "evidence_mismatch"
    assert run("OFFER_LETTERS", "record_response", OTHER_HR, offer_id=oid, response="accept", evidence_ref=rid)["status"] == "evidence_mismatch"   # ESIGN is not looked into
    done = run("OFFER_LETTERS", "record_response", HR1, offer_id=oid, response="accept", evidence_ref=rid)
    assert done["offer"]["status"] == "accepted" and done["ats_notified"] is True
    assert run("OFFER_LETTERS", "get_offer", HR1, offer_id=oid)["offer"]["response"]["basis"] == "esign_evidence"
    ev = json.loads((agent_dir("ATS_CORE") / "evaluation.json").read_text())["applications"][app]
    assert ev["offer_outcomes"][0]["outcome"] == "accepted" and ev["offer_outcomes"][0]["by"] == HR1.id
    assert ev["stage"] == "applied"                                                                                # no stage was moved by a machine
    # an accepted offer is what onboarding and conversion check through OffersReader
    case = run("ONBOARDING_FLOW", "start_onboarding", HR1, subject_id="E9", name="Asha Kumar", email="asha@example.com", join_date="2027-02-01",
               role_group="engineering", location="chennai", manager_id="mgr1", offer_id=oid)
    assert case["status"] == "ok" and case["case"]["offer_check"] == "accepted"
    assert run("ONBOARDING_FLOW", "start_onboarding", HR1, subject_id="E8", name="B", email="b@example.com", join_date="2027-02-01",
               role_group="engineering", location="chennai", manager_id="mgr1", offer_id="ofr-nope")["status"] == "conflict"


# ---- the mail drafts sender: drafts, never sends ----------------------------------------------------------------------
def test_offer_goes_to_the_mailbox_as_a_draft_and_nothing_is_sent(application, monkeypatch):
    app, _ = application
    store, _ob, _ib, _clock, relay, boxes = make_world()
    box = boxes["alice"]["id"]
    sender = hr_wiring.hr_config("OFFER_LETTERS", environ={hr_wiring.MAILBOX_ENV: box}, mail_store=store)["sender"]
    assert isinstance(sender, hr_wiring.MailDraftSender) and sender.drafts_only is True
    oid = make_offer(app)
    cfg = {"sender": sender, "ats": hr_wiring.AtsReader()}
    alice = Caller("alice", ORG, frozenset({"hr_admin"}))              # owns the mailbox
    bob = Caller("bob", ORG, frozenset({"hr_admin"}))                  # an HR admin with no right on that mailbox
    count = lambda: store.one("SELECT COUNT(*) AS n FROM message WHERE mailbox_id=?", (box,))["n"]
    with acting_as(bob):
        r = OfferLetters(cfg).send_offer(oid)
        assert r["status"] == "delivery_failed" and r["draft"]["to"] == "asha@example.com" and count() == 0      # no widening of mailbox access
    with acting_as(alice):
        r = OfferLetters(cfg).send_offer(oid)
    assert r["status"] == "ok" and r["offer"]["status"] == "sent" and "drafted only" in r["delivery"]
    assert count() == 1 and relay.sent == [] and '"via": "mail_draft"' in trace_text()                                                                    # a draft exists, nothing left
    with acting_as(None):
        assert sender.send("a@b.c", "s", "b") is False                                                           # no caller: no draft
