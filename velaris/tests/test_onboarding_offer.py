"""OFFER_LETTERS: templates, compensation arithmetic, four-eyes approval, versions, expiry, responses, rendering, org scoping."""
import base64

import pytest

from velaris.tests.onboarding_helpers import CANDIDATE, HR1, HR2, MGR, ORG, OTHER_ORG_HR, PAYROLL, Clock, FakeAts, FakeSender, person
from velaris.agents.OFFER_LETTERS.main import OfferLetters
from velaris.agents.PAYROLL_ENGINE import statutory
from velaris.agentkit.onboarding_pdf import parse_pdf
from velaris.core.access import Caller, acting_as


def make(**cfg):
    clock = Clock()
    return OfferLetters({"clock": clock, "company_name": "Acme IT Services", **cfg}), clock


def draft(o, **kw):
    args = dict(candidate_name="Asha Raman", candidate_email="asha@example.in", role_title="Software Engineer", department="Engineering",
                location="Chennai", join_date="2026-12-01", annual_ctc="1200000", hiring_manager_id="mgr1", hr_approver_id="hr2",
                manager_name="Ravi")
    args.update(kw)
    with acting_as(HR1):
        return o.create_offer(**args)


def approve_all(o, offer_id):
    with acting_as(HR1):
        assert o.submit_for_approval(offer_id)["status"] == "ok"
    with acting_as(MGR):
        assert o.approve(offer_id, acknowledge_review=True)["status"] == "ok"
    with acting_as(HR2):
        return o.approve(offer_id, acknowledge_review=True)


def test_create_shows_arithmetic_and_statutory_from_the_registry():
    o, _ = make()
    r = draft(o)
    assert r["status"] == "ok" and r["needs_review"] is True          # the registry carries unverified entries
    offer = r["offer"]
    assert offer["org"] == ORG and offer["status"] == "draft" and offer["version"] == 1
    with acting_as(HR1):
        full = o.get_offer(offer["id"])["offer"]
    comp = full["comp"]
    assert comp["monthly_ctc"] == "100000.00" and comp["components"]["basic"] == "40000.00" and comp["components"]["hra"] == "20000.00"
    assert comp["employer_contributions"]["epf"] == "3000.00"           # 12% of 25,000 ceiling in force from 17 Sep 2026
    assert comp["components"]["gross"] == "97000.00" and comp["components"]["special_allowance"] == "37000.00"
    assert any(l["item"] == "Basic" and "40" in l["formula"] for l in comp["lines"])
    assert comp["take_home_before_income_tax"] == "94000.00"
    assert any("not verified" in x or "UNVERIFIED" in x for x in comp["review_reasons"])
    assert any("income tax" in a for a in comp["assumptions"])


def test_statutory_figures_are_not_hard_coded(monkeypatch):
    o, _ = make()
    monkeypatch.setitem(statutory.PARAMS, "epf_wage_ceiling", [])
    with acting_as(HR1):
        r = o.compensation_preview("1200000", "2026-11")
    comp = r["compensation"]
    assert comp["status"] == "needs_review" and comp["employer_contributions"]["epf"] is None
    assert comp["components"]["special_allowance"] is None and any("epf_wage_ceiling" in x for x in comp["review_reasons"])


def test_ceiling_change_between_months_changes_the_numbers():
    o, _ = make()
    with acting_as(HR1):
        before = o.compensation_preview("1200000", "2026-08")["compensation"]
        after = o.compensation_preview("1200000", "2026-11")["compensation"]
    assert before["employer_contributions"]["epf"] == "1800.00" and after["employer_contributions"]["epf"] == "3000.00"


def test_bad_inputs_are_refused_without_creating_anything():
    o, _ = make()
    bad = [dict(annual_ctc="0"), dict(annual_ctc="-5"), dict(annual_ctc="abc"), dict(join_date="2026-01-01"), dict(join_date="soon"),
           dict(candidate_email="nope"), dict(candidate_name=""), dict(role_title="x" * 500), dict(valid_days=0), dict(valid_days=99),
           dict(hiring_manager_id="hr2"), dict(hiring_manager_id="hr1"), dict(hr_approver_id="hr1"),
           dict(structure={"basic_pct": "0"}), dict(structure={"basic_pct": "90", "hra_pct_of_basic": "90"}), dict(structure={"bogus": 1}),
           dict(template_id="tpl-missing")]
    for kw in bad:
        r = draft(o, **kw)
        assert r["status"] in ("invalid_input", "not_found"), (kw, r)
    with acting_as(HR1):
        assert o.list_offers()["offers"] == []


def test_denied_and_unauthenticated():
    o, _ = make()
    assert o.create_offer("A", "a@b.in", "r", "d", "l", "2026-12-01", "1", "mgr1", "hr2")["status"] == "unauthenticated"
    with acting_as(MGR):
        assert o.create_offer("A", "a@b.in", "r", "d", "l", "2026-12-01", "1", "x", "y")["status"] == "denied"
        assert o.add_template("t", "Hi {candidate_name}")["status"] == "denied"
    with acting_as(PAYROLL):
        assert o.send_offer("x")["status"] == "denied"
    with acting_as(Caller("hr9", "acme", frozenset({"hr_admin"}))):
        assert o.get_offer("ofr-nope")["status"] == "not_found"


def test_four_eyes_approval_chain():
    o, _ = make()
    oid = draft(o)["offer"]["id"]
    with acting_as(HR1):
        o.submit_for_approval(oid)
        assert o.approve(oid)["status"] == "denied"                 # the drafter, and not a named approver
    with acting_as(HR2):
        r = o.approve(oid, acknowledge_review=True)                  # named for step 2, but step 1 is first
        assert r["status"] == "denied" and "step 1" in r["reason"]
    with acting_as(person("E9")):
        assert o.approve(oid)["status"] == "denied"
    with acting_as(MGR):
        r = o.approve(oid)                                           # unverified statutory figures need an explicit acknowledgement
        assert r["status"] == "needs_review" and r["review_reasons"]
        assert o.approve(oid, acknowledge_review=True)["status"] == "ok"
        assert o.approve(oid, acknowledge_review=True)["status"] == "denied"      # not their step any more
    with acting_as(HR2):
        assert o.approve(oid)["status"] == "needs_review"
        assert o.approve(oid, acknowledge_review=True)["offer"]["status"] == "approved"
        assert o.approve(oid)["status"] == "conflict"


def test_second_step_needs_the_hr_role():
    o, _ = make()
    oid = draft(o, hr_approver_id="mgr2")["offer"]["id"]
    with acting_as(HR1):
        o.submit_for_approval(oid)
    with acting_as(MGR):
        o.approve(oid, acknowledge_review=True)
    with acting_as(Caller("mgr2", ORG, frozenset())):
        assert o.approve(oid, acknowledge_review=True)["status"] == "denied"


def test_one_person_cannot_approve_two_steps_even_with_both_roles(monkeypatch):
    o, _ = make()
    rec = draft(o, hiring_manager_id="hr2", hr_approver_id="hr3")
    assert rec["status"] == "ok"
    oid = rec["offer"]["id"]
    with acting_as(HR1):
        o.submit_for_approval(oid)
    with acting_as(HR2):
        assert o.approve(oid, acknowledge_review=True)["status"] == "ok"
        assert o.approve(oid, acknowledge_review=True)["status"] == "denied"


def test_rejection_and_revision_restarts_the_chain_and_keeps_history():
    o, _ = make()
    oid = draft(o)["offer"]["id"]
    with acting_as(HR1):
        o.submit_for_approval(oid)
    with acting_as(MGR):
        assert o.reject(oid, "too high")["offer"]["status"] == "rejected"
    with acting_as(HR1):
        r = o.revise_offer(oid, "lowered CTC", annual_ctc="1100000")
        assert r["offer"]["version"] == 2 and r["offer"]["status"] == "draft" and r["offer"]["approvals"] == []
        full = o.get_offer(oid)["offer"]
        assert full["comp"]["annual_ctc"] == "1100000.00" and full["history"][0]["comp"]["annual_ctc"] == "1200000.00"
        assert full["history"][0]["reason"] == "lowered CTC"
        assert o.revise_offer(oid, "", annual_ctc="1")["status"] == "invalid_input"
        assert o.revise_offer(oid, "bad", annual_ctc="x")["status"] == "invalid_input"
    assert approve_all(o, oid)["offer"]["status"] == "approved"
    with acting_as(HR1):
        r = o.revise_offer(oid, "after approval", role_title="Lead")             # still unsent: allowed, approvals reset
        assert r["offer"]["version"] == 3 and r["offer"]["approvals"] == []


def test_send_needs_approval_and_a_sender():
    sender = FakeSender()
    o, _ = make()
    oid = draft(o)["offer"]["id"]
    with acting_as(HR1):
        assert o.send_offer(oid)["status"] == "conflict"
    approve_all(o, oid)
    with acting_as(HR1):
        r = o.send_offer(oid)
        assert r["status"] == "not_configured" and r["draft"]["to"] == "asha@example.in"
        assert o.get_offer(oid)["offer"]["status"] == "approved"                    # nothing was pretended
        assert o.send_offer(oid, delivered_manually=True)["offer"]["status"] == "sent"
    o2, _ = make(sender=sender)
    oid2 = draft(o2)["offer"]["id"]
    approve_all(o2, oid2)
    with acting_as(HR1):
        assert o2.send_offer(oid2)["offer"]["status"] == "sent" and sender.messages[0]["to"] == "asha@example.in"
    o3, _ = make(sender=FakeSender(accept=False))
    oid3 = draft(o3)["offer"]["id"]
    approve_all(o3, oid3)
    with acting_as(HR1):
        assert o3.send_offer(oid3)["status"] == "delivery_failed"


def test_expiry_response_and_ats_notification():
    ats = FakeAts({"APP-1": CANDIDATE})
    o, clock = make(ats=ats, sender=FakeSender())
    oid = draft(o, application_id="APP-1", candidate_name="ignored", candidate_email="ignored@x.in")["offer"]["id"]
    with acting_as(HR1):
        full = o.get_offer(oid)["offer"]
    assert full["candidate"]["name"] == "Asha Raman" and full["candidate"]["consent"]["purpose"] == "recruitment"      # from the ATS
    approve_all(o, oid)
    with acting_as(HR1):
        assert o.record_response(oid, "accept")["status"] == "conflict"            # not sent yet
        o.send_offer(oid)
        assert o.record_response(oid, "maybe")["status"] == "invalid_input"
        r = o.record_response(oid, "accept", evidence_ref="sig-123")
        assert r["offer"]["status"] == "accepted" and r["ats_notified"] is True
        assert ats.outcomes == [("APP-1", "accepted", oid)]
        assert o.get_offer(oid)["offer"]["response"]["basis"] == "esign_evidence"
        assert o.withdraw_offer(oid, "x")["status"] == "conflict"
    oid2 = draft(o, valid_days=3)["offer"]["id"]
    approve_all(o, oid2)
    with acting_as(HR1):
        o.send_offer(oid2)
    clock.advance(days=4)
    with acting_as(HR1):
        assert o.record_response(oid2, "accept")["status"] == "expired"
        assert o.get_offer(oid2)["offer"]["status"] == "expired"
        oid3 = draft(o, valid_days=1)["offer"]["id"]
    approve_all(o, oid3)
    with acting_as(HR1):
        o.send_offer(oid3)
    clock.advance(days=2)
    with acting_as(HR1):
        assert o.expire_due()["expired"] == [oid3]


def test_unknown_ats_application_and_record_response_basis():
    o, _ = make(ats=FakeAts({}))
    assert draft(o, application_id="APP-9")["status"] == "not_found"
    o2, _ = make(sender=FakeSender())
    oid = draft(o2)["offer"]["id"]
    approve_all(o2, oid)
    with acting_as(HR1):
        o2.send_offer(oid)
        assert o2.record_response(oid, "decline", note="took another job")["offer"]["status"] == "declined"
        assert o2.get_offer(oid)["offer"]["response"]["basis"] == "recorded_by_hr"


def test_render_pdf_html_text_and_unverified_note():
    o, _ = make()
    oid = draft(o)["offer"]["id"]
    approve_all(o, oid)
    with acting_as(HR1):
        pdf = o.render_offer(oid, "pdf")
        raw = base64.b64decode(pdf["pdf_base64"])
        info = parse_pdf(raw)
        text = "\n".join(info["text"])
        assert info["pages"] >= 1 and "Asha Raman" in text and "40,000.00" in text and "Cost to company" in text
        assert "Acme IT Services" in text and "not verified" in text           # the acknowledged-unverified note travels with the letter
        assert pdf["sha256"] == o.render_offer(oid, "pdf")["sha256"]            # deterministic output
        html = o.render_offer(oid, "html")["content"]
        assert html.startswith("<!doctype html>") and "<table" in html and "Asha Raman" in html
        assert "40,000.00" in o.render_offer(oid, "text")["content"]
        assert o.render_offer(oid, "docx")["status"] == "invalid_input"


def test_html_escapes_candidate_input():
    o, _ = make()
    oid = draft(o, candidate_name="<script>alert(1)</script>")["offer"]["id"]
    with acting_as(HR1):
        html = o.render_offer(oid, "html")["content"]
    assert "<script>" not in html and "&lt;script&gt;" in html


def test_custom_templates_are_validated_and_used():
    o, _ = make()
    with acting_as(HR1):
        assert o.add_template("bad", "Hello {candidate_name.__class__}")["status"] == "invalid_input"
        assert o.add_template("bad", "Hello {salary_secret}")["status"] == "invalid_input"
        assert o.add_template("", "x")["status"] == "invalid_input"
        t = o.add_template("short", "Dear {candidate_name},\n\n{compensation_table}\n\nJoin on {join_date}.")
        assert t["status"] == "ok" and t["version"] == 1
        assert o.add_template("short", "v2 {candidate_name}")["version"] == 2
        assert {x["name"] for x in o.list_templates()["templates"]} >= {"standard", "short"}
    oid = draft(o, template_id=t["id"])["offer"]["id"]
    with acting_as(HR1):
        text = o.render_offer(oid, "text")["content"]
    assert text.startswith("Dear Asha Raman") and "Join on 2026-12-01." in text


def test_organisation_scoping():
    o, _ = make()
    oid = draft(o)["offer"]["id"]
    with acting_as(OTHER_ORG_HR):
        assert o.get_offer(oid)["status"] == "not_found"
        assert o.list_offers()["offers"] == []
        assert o.submit_for_approval(oid)["status"] == "not_found"
        assert o.render_offer(oid)["status"] == "not_found"
        mine = o.create_offer("B", "b@x.in", "r", "d", "l", "2026-12-01", "100000", "m", "h2", company_name="Globex")["offer"]
        assert mine["org"] == "globex"
    with acting_as(HR1):
        assert [x["id"] for x in o.list_offers()["offers"]] == [oid]


def test_pay_data_needs_pay_access_unless_you_are_a_named_participant():
    o, _ = make()
    oid = draft(o)["offer"]["id"]
    with acting_as(MGR):
        assert o.get_offer(oid)["status"] == "ok"                       # named approver
    with acting_as(PAYROLL):
        assert o.get_offer(oid)["status"] == "ok"                       # pay role
    with acting_as(person("E9")):
        assert o.get_offer(oid)["status"] == "denied" and o.compensation_preview("1000000", "2026-11")["status"] == "denied"
        assert o.list_offers()["offers"] == []
    with acting_as(MGR):
        assert "comp" in o.get_offer(oid)["offer"] and "template_body" not in o.get_offer(oid)["offer"]


def test_deployment_org_is_enforced(monkeypatch):
    o, _ = make()
    monkeypatch.setenv("VELARIS_ORG", "acme")
    with acting_as(OTHER_ORG_HR):
        assert o.create_offer("B", "b@x.in", "r", "d", "l", "2026-12-01", "100000", "m", "h2")["status"] == "denied"
        assert o.list_offers()["status"] == "denied"
