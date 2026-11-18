"""EMPLOYEE_RECORDS and POLICY_ACKS, and the API allowlist entries for the paperwork agents."""
import inspect
import json
import os
from datetime import date
from pathlib import Path

import pytest

from velaris.tests.onboarding_helpers import CANDIDATE, HR1, HR2, MGR, ORG, OTHER_ORG_HR, PAYROLL, Clock, FakeAts, FakeOffers, person
from velaris.agents.EMPLOYEE_RECORDS.main import EmployeeRecords
from velaris.agents.ESIGN.main import Esign
from velaris.agents.OFFER_LETTERS.main import OfferLetters
from velaris.agents.ONBOARDING_FLOW.main import OnboardingFlow
from velaris.agents.PAYROLL_ENGINE.registry import Entry
from velaris.agents.POLICY_ACKS.main import PolicyAcks
from velaris.agentkit import onboarding_retention as retention
from velaris.api import allowlist
from velaris.core.access import AccessDenied, Caller, acting_as
from velaris.intel import trace


def make(**cfg):
    clock = Clock()
    ats = FakeAts({"APP-1": CANDIDATE, "APP-2": {**CANDIDATE, "name": "Ravi Kumar", "email": "ravi@example.in", "consent": None}})
    cfg = {"clock": clock, "ats": ats, "offers": FakeOffers("accepted"), **cfg}
    return EmployeeRecords(cfg), PolicyAcks(cfg), OnboardingFlow(cfg), clock, ats


def hire(er, app="APP-1", dept="Engineering", mgr="mgr1", join="2026-12-01"):
    with acting_as(HR1):
        p = er.propose_conversion(app, dept, "Software Engineer", mgr, join, offer_id="o1")
        assert p["status"] == "ok", p
    with acting_as(HR2):
        r = er.approve_conversion(p["conversion"]["id"])
        assert r["status"] == "ok", r
    return r["employee_id"]


# ---- conversion ----------------------------------------------------------------------------------------------------
def test_conversion_needs_a_second_hr_administrator_and_carries_consent_over():
    er, _, _, _, ats = make()
    with acting_as(HR1):
        p = er.propose_conversion("APP-1", "Engineering", "Engineer", "mgr1", "2026-12-01", offer_id="o1")
        cid = p["conversion"]["id"]
        assert p["conversion"]["status"] == "proposed" and p["conversion"]["needs_review"] == []
        assert er.approve_conversion(cid)["status"] == "denied"                       # the proposer cannot approve
        assert er.reject_conversion(cid, "x")["status"] == "conflict"
        assert er.list_employees()["employees"] == []                                   # nothing exists yet
    with acting_as(MGR):
        assert er.approve_conversion(cid)["status"] == "denied"
    with acting_as(HR2):
        r = er.approve_conversion(cid, "ok")
        assert r["status"] == "ok" and r["employee_id"] == "EMP-0001"
        assert er.approve_conversion(cid)["status"] == "conflict"
        emp = er.get_employee("EMP-0001")["employee"]
    assert emp["org"] == ORG and emp["status"] == "active" and emp["name"] == "Asha Raman" and emp["department"] == "Engineering"
    c = emp["consent"]
    assert c["original_purpose"] == "recruitment" and c["purpose"] == "employment" and c["purpose_changed_by"] == "hr2"
    assert c["carried_over_from"]["notice_version"] == "n1" and "s.7(i)" in c["lawful_basis"] and "lawyer" in c["lawful_basis"]
    assert emp["source"]["application_id"] == "APP-1"
    with acting_as(HR1):
        h = er.employee_history("EMP-0001")["history"]
    assert h[0]["by"] == "hr2" and "conversion" in h[0]["new"]


def test_conversion_flags_missing_consent_and_refuses_bad_input():
    er, _, _, _, ats = make()
    emp_id = hire(er, "APP-2")
    with acting_as(HR1):
        assert er.get_employee(emp_id)["employee"]["consent"]["needs_review"] == ["no candidate consent record to carry over"]
        assert er.propose_conversion("APP-2", "d", "x", "m", "2026-12-01", offer_id="o1")["status"] == "conflict"            # already converted
        assert er.propose_conversion("APP-404", "d", "x", "m", "2026-12-01", offer_id="o1")["status"] == "not_found"
        assert er.propose_conversion("", "d", "x", "m", "2026-12-01", offer_id="o1")["status"] == "invalid_input"
        assert er.propose_conversion("APP-1", "d", "x", "m", "not-a-date", offer_id="o1")["status"] == "invalid_input"
    with acting_as(MGR):
        assert er.propose_conversion("APP-1", "d", "x", "m", "2026-12-01", offer_id="o1")["status"] == "denied"
    assert er.propose_conversion("APP-1", "d", "x", "m", "2026-12-01", offer_id="o1")["status"] == "unauthenticated"


def test_conversion_without_ats_takes_given_details_and_flags_them_and_checks_the_offer():
    er = EmployeeRecords({"clock": Clock(), "offers": FakeOffers("sent")})
    with acting_as(HR1):
        assert er.propose_conversion("A1", "d", "x", "m", "2026-12-01", offer_id="o1", name="N", email="n@x.in")["status"] == "conflict"
    er = EmployeeRecords({"clock": Clock(), "offers": FakeOffers("accepted")})
    with acting_as(HR1):
        assert er.propose_conversion("A1", "d", "x", "m", "2026-12-01", offer_id="o1")["status"] == "invalid_input"
        p = er.propose_conversion("A1", "d", "x", "m", "2026-12-01", name="N", email="n@x.in", offer_id="o1")
    assert p["status"] == "ok" and p["conversion"]["needs_review"]
    with acting_as(HR2):
        assert er.reject_conversion(p["conversion"]["id"], "no")["conversion"]["status"] == "rejected"
        assert er.approve_conversion(p["conversion"]["id"])["status"] == "conflict"


def test_employee_ids_are_per_organisation_and_stamped():
    er, *_ = make()
    a = hire(er)
    with acting_as(OTHER_ORG_HR):
        assert er.get_employee(a)["status"] == "not_found"
        assert er.list_employees()["employees"] == []
        assert er.approve_conversion("cnv-x")["status"] == "not_found"
    assert a == "EMP-0001" and hire(er, "APP-2") == "EMP-0002"
    stored = json.loads((Path(os.environ["VELARIS_DATA"]) / "agents" / "EMPLOYEE_RECORDS" / "state.json").read_text())["records"]
    assert all(e["org"] == ORG for e in stored["employees"].values()) and all(c["org"] == ORG for c in stored["conversions"].values())


# ---- reading and changing ---------------------------------------------------------------------------------------------
def test_identity_reads_are_own_or_hr_only():
    er, *_ = make()
    e1, e2 = hire(er), hire(er, "APP-2")
    with acting_as(person(e1)):
        assert er.get_employee(e1)["status"] == "ok" and er.employee_history(e1)["status"] == "ok"
        assert er.get_employee(e2)["status"] == "denied" and er.list_employees()["status"] == "denied"
        assert er.export_subject(e2)["status"] == "denied" and er.retention_status(e2)["status"] == "denied"
        assert er.workforce_aggregate()["status"] == "denied"
    with acting_as(MGR):
        assert er.get_employee(e1)["status"] == "denied"
    with acting_as(PAYROLL):
        assert er.get_employee(e1)["status"] == "denied"
    with acting_as(HR1):
        assert len(er.list_employees()["employees"]) == 2 and er.get_employee("EMP-9999")["status"] == "not_found"
    reads = [e for e in trace.entries() if e["action"] == "sensitive_read.denied"]
    assert reads and all(e["payload"]["agent"] == "EMPLOYEE_RECORDS" for e in reads if e["payload"]["agent"].startswith("EMP"))


def test_change_record_keeps_who_what_why():
    er, *_ = make()
    e1, e2 = hire(er), hire(er, "APP-2")
    with acting_as(HR1):
        assert er.change_record(e1, "department", "Platform", "re-org")["status"] == "ok"
        assert er.change_record(e1, "manager_id", e2, "new lead")["status"] == "ok"
        h = er.employee_history(e1)["history"]
        assert h[-2]["field"] == "department" and h[-2]["old"] == "Engineering" and h[-2]["new"] == "Platform" and h[-2]["by"] == "hr1" and h[-2]["reason"] == "re-org"
        assert h[-1]["field"] == "manager_id" and h[-1]["new"] == e2
        for args in ((e1, "status", "exited", "x"), (e1, "name", "X", "x"), (e1, "department", "", "x"), (e1, "department", "D", ""),
                     (e1, "manager_id", e1, "self"), (e1, "manager_id", "EMP-9999", "ghost"), (e1, "department", "x" * 500, "x")):
            assert er.change_record(*args)["status"] == "invalid_input", args
        assert er.change_record("EMP-9999", "department", "D", "x")["status"] == "not_found"
    with acting_as(MGR):
        assert er.change_record(e1, "department", "Sales", "x")["status"] == "denied"
    with acting_as(person(e1)):
        assert er.change_record(e1, "department", "Sales", "x")["status"] == "denied"


# ---- exit ---------------------------------------------------------------------------------------------------------------
def test_exit_produces_tasks_not_system_changes_and_finalises_only_when_done():
    er, *_ = make()
    e1 = hire(er)
    with acting_as(HR1):
        assert er.start_exit(e1, "2026-13-40", "resignation")["status"] == "invalid_input"
        assert er.start_exit(e1, "2027-03-31", "fired-lol")["status"] == "invalid_input"
        r = er.start_exit(e1, "2027-03-31", "resignation", systems=["GitHub", "AWS console"], it_owner_id="it1")
        xid = r["exit_id"]
        assert r["status"] == "ok" and "no system was changed" in r["note"]
        assert {"revoke_access_1", "revoke_access_2", "return_assets"} <= set(r["access_revocation"])
        assert er.get_employee(e1)["employee"]["status"] == "notice"
        assert er.start_exit(e1, "2027-03-31", "resignation")["status"] == "conflict"
        fin = er.finalise_exit(xid)
        assert fin["status"] == "conflict" and "return_assets" in fin["open_tasks"]
        st = er.exit_status(xid)
        assert st["completion_percent"] == 0.0 and any(b["task"] == "revoke_accounts" for b in st["blocked"])
        assert {t["key"] for t in st["access_revocation"]} >= {"revoke_accounts", "revoke_access_1", "return_assets"}
        assert er.complete_exit_task(xid, "revoke_accounts")["status"] == "blocked"
    with acting_as(Caller("it1", ORG, frozenset())):
        assert er.complete_exit_task(xid, "return_assets")["status"] == "ok"
        assert er.complete_exit_task(xid, "revoke_accounts")["status"] == "ok"
        assert er.complete_exit_task(xid, "handover_plan")["status"] == "denied"
        assert er.exit_status(xid)["status"] == "ok"
    with acting_as(person("E9")):
        assert er.exit_status(xid)["status"] == "not_found"
    with acting_as(HR1):
        for _ in range(3):
            for t in er.exit_status(xid)["tasks"]:
                if t["required"] and t["state"] in ("ready", "overdue"):
                    er.complete_exit_task(xid, t["key"])
        assert er.finalise_exit(xid)["status"] == "ok"
        assert er.get_employee(e1)["employee"]["status"] == "exited"
        assert er.change_record(e1, "department", "X", "y")["status"] == "conflict"
        assert [h["new"] for h in er.employee_history(e1)["history"] if h["field"] == "status"] == ["notice", "exited"]


# ---- data subject rights ---------------------------------------------------------------------------------------------------
def exited_employee(er, flow, pol, clock):
    emp = hire(er)
    with acting_as(HR1):
        hire(er, "APP-2")
        cid = flow.start_onboarding(emp, "Asha Raman", "asha@example.in", "2026-12-01", "engineering", "chennai", "mgr1")["case"]["id"]
        flow.complete_task(cid, "confirm_offer_accepted")
        pol.publish_policy("code_of_conduct", "Code of conduct", "Be kind.", "2026-12-01")
    with acting_as(person(emp)):
        flow.submit_identifier(cid, "pan", "ABCDE1234F")
        flow.submit_form(cid, "tax_declaration", {"regime": "new"})
        text = pol.get_policy("code_of_conduct")["policy"]["text_sha256"]
        assert pol.acknowledge("code_of_conduct", text)["status"] == "ok"
    with acting_as(HR1):
        x = er.start_exit(emp, "2027-03-31", "resignation")["exit_id"]
        for _ in range(4):
            for t in er.exit_status(x)["tasks"]:
                if t["required"] and t["state"] in ("ready", "overdue"):
                    er.complete_exit_task(x, t["key"])
        assert er.finalise_exit(x)["status"] == "ok"
    return emp, cid


def test_export_covers_every_store_and_masks_identifiers():
    er, pol, flow, clock, _ = make()
    emp, cid = exited_employee(er, flow, pol, clock)
    with acting_as(person(emp)):
        exp = er.export_subject(emp)["export"]
    assert exp["employee"]["name"] == "Asha Raman" and exp["onboarding_cases"][0]["identifiers"]["pan"]["masked"] == "******234F"
    assert exp["policy_acknowledgements"][0]["policy_key"] == "code_of_conduct" and exp["exits"][0]["reason_code"] == "resignation"
    assert "ABCDE1234F" not in json.dumps(exp) and {r["class"] for r in exp["retention"]} >= {"payroll_records", "employee_master_core"}
    with acting_as(person("EMP-0002")):
        assert er.export_subject(emp)["status"] == "denied"
    with acting_as(OTHER_ORG_HR):
        assert er.export_subject(emp)["status"] == "not_found"


def test_erasure_holds_statutory_classes_and_flags_needs_review():
    er, pol, flow, clock, _ = make()
    emp, cid = exited_employee(er, flow, pol, clock)
    with acting_as(HR1):
        before = er.workforce_aggregate()
        assert er.erase_subject(emp, "")["status"] == "invalid_input"
        res = er.erase_subject(emp, "DSR-2027-004")
        assert res["status"] == "ok" and res["record_status"] == "restricted" and res["needs_review"] is True
        held = {h["what"].split(":")[-1] for h in res["held"]}
        assert {"payroll_records", "employee_master_core", "tax_declaration"} <= held
        assert all(h["status"] == "needs_review" for h in res["held"])
        assert any("identifiers" in x for x in res["erased"]) and any("acknowledgements" in x for x in res["erased"])
        e = er.get_employee(emp)["employee"]
        assert e["email"] is None and e["phone"] is None and e["consent"] == {"erased": True} and e["name"] == "Asha Raman"      # held: needed for statutory records
        assert e["erasure"]["request_ref"] == "DSR-2027-004"
        after = er.workforce_aggregate()
        assert (after["total"], after["by_department"], after["by_join_year"]) == (before["total"], before["by_department"], before["by_join_year"])
        assert after["by_status"] == {"active": 1, "restricted": 1}               # the person is still counted, anonymously
        assert [h["new"] for h in er.employee_history(emp)["history"] if h["field"] in ("email", "record")] == ["erased"]
    with acting_as(HR1):
        exp = flow.dsr_export(ORG, emp)["onboarding_cases"][0]
        assert exp["identifiers"] == {} and exp["name"] == "erased" and exp["forms_submitted"] == ["tax_declaration"]
        assert pol.dsr_export(ORG, emp)["policy_acknowledgements"] == []          # anonymised, not deleted
    with acting_as(HR1):
        assert er.get_employee(emp)["employee"]["status"] == "restricted"
    assert "erased-" in (Path(os.environ["VELARIS_DATA"]) / "agents" / "POLICY_ACKS" / "state.json").read_text()
    assert "ABCDE1234F" not in "".join(p.read_text(errors="ignore") for p in Path(os.environ["VELARIS_DATA"]).rglob("*.json*") if p.is_file())
    erased_events = [e for e in trace.entries() if e["action"] == "subject.erased"]
    assert len(erased_events) == 1 and emp not in json.dumps(erased_events[0]["payload"])            # the trace names no one


def test_erasure_is_refused_for_current_employees_and_other_orgs():
    er, *_ = make()
    emp = hire(er)
    with acting_as(HR1):
        r = er.erase_subject(emp, "ref")
        assert r["status"] == "conflict" and "after exit" in r["reason"]
        assert er.get_employee(emp)["employee"]["name"] == "Asha Raman"
    with acting_as(OTHER_ORG_HR):
        assert er.erase_subject(emp, "ref")["status"] == "not_found"
    with acting_as(MGR):
        assert er.erase_subject(emp, "ref")["status"] == "denied"
    assert er.erase_subject(emp, "ref")["status"] == "unauthenticated"


def test_fully_erased_when_every_statutory_period_is_verified_and_past(monkeypatch):
    er, pol, flow, clock, _ = make()
    emp, _cid = exited_employee(er, flow, pol, clock)
    for c in retention.STATUTORY:
        monkeypatch.setitem(retention.PARAMS, f"retention:{c}", [Entry(
            {"kind": "statutory", "years": 1, "from": "x"}, date(2000, 1, 1), "https://example.gov.in/r", date(2026, 11, 13), True, "test")])
    clock.advance(days=800)                                       # more than a year after the 2027-03-31 exit
    with acting_as(HR1):
        st = er.retention_status(emp)
        assert st["needs_review"] is False
        res = er.erase_subject(emp, "DSR-9")
        assert res["record_status"] == "erased" and res["needs_review"] is False and res["held"] == []
        e = er.get_employee(emp)["employee"]
        assert e["name"].startswith("erased-") and e["status"] == "erased"
        assert er.workforce_aggregate()["by_status"] == {"erased": 1, "active": 1}
    with acting_as(HR1):
        assert flow.dsr_export(ORG, emp)["onboarding_cases"][0]["forms_submitted"] == []


def test_retention_views():
    er, *_ = make()
    emp = hire(er)
    with acting_as(person("EMP-0002")):
        assert er.retention_table()["status"] == "ok"
    with acting_as(HR1):
        t = er.retention_table()
        assert t["note"].startswith("no statutory retention period has been verified") and "payroll_records" in t["statutory_classes"]
        st = er.retention_status(emp)
        assert st["needs_review"] is True and all(r["action"] == "hold" for r in st["classes"] if r["class"] in retention.STATUTORY)
        assert er.retention_status("EMP-404")["status"] == "not_found"
    assert er.retention_table()["status"] == "unauthenticated"


# ---- POLICY_ACKS ----------------------------------------------------------------------------------------------------------------
def test_policy_versions_and_acknowledgement_evidence():
    er, pol, _, clock, _ = make()
    e1, e2 = hire(er), hire(er, "APP-2", dept="Sales")
    with acting_as(HR1):
        assert pol.publish_policy("Bad Key", "t", "x", "2026-12-01")["status"] == "invalid_input"
        for kw in (dict(text=""), dict(title=""), dict(effective_date="soon"), dict(due_days=0), dict(text="x" * 300000)):
            args = dict(policy_key="infosec", title="InfoSec", text="Lock your laptop.", effective_date="2026-12-01")
            args.update(kw)
            assert pol.publish_policy(**args)["status"] == "invalid_input", kw
        v1 = pol.publish_policy("infosec", "InfoSec", "Lock your laptop.", "2026-12-01")["policy"]
        assert v1["version"] == 1 and len(v1["text_sha256"]) == 64
    with acting_as(person(e1)):
        assert pol.acknowledge("infosec", "0" * 64)["status"] == "stale_text"
        ack = pol.acknowledge("infosec", v1["text_sha256"])
        assert ack["status"] == "ok" and ack["version"] == 1 and len(ack["evidence_sha256"]) == 64
        again = pol.acknowledge("infosec", v1["text_sha256"])
        assert again["already_acknowledged"] is True and again["evidence_sha256"] == ack["evidence_sha256"]
        assert pol.acknowledge("nope", v1["text_sha256"])["status"] == "not_found"
        assert pol.pending_for_employee(e1)["pending"] == [] and pol.pending_for_employee(e2)["status"] == "denied"
    with acting_as(HR1):                                           # v2 supersedes v1: everyone must read the new text
        v2 = pol.publish_policy("infosec", "InfoSec", "Lock your laptop and use MFA.", "2026-12-02")["policy"]
        assert v2["version"] == 2 and pol.get_policy("infosec")["policy"]["text"].endswith("MFA.")
        assert pol.get_policy("infosec", 1)["policy"]["status"] == "superseded"
        assert [p["version"] for p in pol.list_policies()["policies"]] == [2]
    with acting_as(person(e1)):
        assert pol.acknowledge("infosec", v1["text_sha256"])["status"] == "stale_text"                  # old text refused
        assert [p["version"] for p in pol.pending_for_employee(e1)["pending"]] == [2]
        assert pol.acknowledge("infosec", v2["text_sha256"])["status"] == "ok"


def test_acknowledgement_identity_is_the_caller_and_only_for_addressed_current_employees():
    er, pol, _, _, _ = make()
    e1, e2 = hire(er), hire(er, "APP-2", dept="Sales")
    assert "employee_id" not in inspect.signature(PolicyAcks.acknowledge).parameters         # nobody acknowledges as someone else
    with acting_as(HR1):
        h = pol.publish_policy("eng_only", "Eng", "Text", "2026-12-01", departments=["Engineering"])["policy"]["text_sha256"]
        pol.publish_policy("named", "Named", "Text2", "2026-12-01", employee_ids=[e2])
    with acting_as(person(e2)):
        assert pol.acknowledge("eng_only", h)["status"] == "denied"                              # not in the audience
    with acting_as(HR1):
        assert pol.acknowledge("eng_only", h)["status"] == "denied"                              # HR has no employee record: cannot acknowledge
        assert pol.acknowledge("eng_only", h)["reason"].startswith("only an employee")
    with acting_as(person("EMP-0099")):
        assert pol.acknowledge("eng_only", h)["status"] == "denied"                              # not in the master
    with acting_as(person(e1, user="u-other")):
        assert pol.acknowledge("eng_only", h)["status"] == "ok"
        assert pol.acknowledge("named", "x")["status"] == "denied"
    assert pol.acknowledge("eng_only", h)["status"] == "unauthenticated"


def test_compliance_report_reminders_and_retire():
    er, pol, _, clock, _ = make()
    e1, e2 = hire(er), hire(er, "APP-2")
    with acting_as(HR1):
        h = pol.publish_policy("coc", "Code", "Be kind.", "2026-12-01", due_days=7)["policy"]["text_sha256"]
        rep = pol.compliance_report()["report"][0]
        assert rep["audience"] == 2 and rep["acknowledged"] == 0 and rep["percent"] == "0.0" and len(rep["pending"]) == 2
        assert rep["pending"][0]["due_date"] == "2026-12-08"                                    # from the later of publish and join dates
        assert pol.reminders_due(3)["reminders"] == [] and pol.reminders_due(30)["sent"] is False
    with acting_as(person(e1)):
        pol.acknowledge("coc", h)
    clock.advance(days=40)
    with acting_as(HR1):
        rep = pol.compliance_report("coc")["report"][0]
        assert rep["acknowledged"] == 1 and rep["percent"] == "50.0" and rep["overdue"] == [e2]
        rem = pol.reminders_due()["reminders"]
        assert [r["to"] for r in rem] == [e2] and "Code" not in rem[0]["message"] and "coc" in rem[0]["message"]
        assert pol.reminders_due(99)["status"] == "invalid_input"
        assert pol.retire_policy("coc", "obsolete")["status"] == "ok" and pol.compliance_report()["report"] == []
        assert pol.retire_policy("coc", "again")["status"] == "not_found"
    with acting_as(MGR):
        assert pol.compliance_report()["status"] == "denied" and pol.reminders_due()["status"] == "denied"
        assert pol.publish_policy("x_y", "t", "x", "2026-12-01")["status"] == "denied"


def test_report_does_not_claim_compliance_when_nobody_resolves():
    pol = PolicyAcks({"clock": Clock()})
    with acting_as(HR1):
        pol.publish_policy("coc", "Code", "x", "2026-12-01")
        rep = pol.compliance_report()["report"][0]
    assert rep["audience"] == 0 and rep["percent"] is None and "could be resolved" in rep["note"]


def test_policy_org_scoping():
    er, pol, *_ = make()
    hire(er)
    with acting_as(HR1):
        pol.publish_policy("coc", "Code", "x", "2026-12-01")
    with acting_as(OTHER_ORG_HR):
        assert pol.get_policy("coc")["status"] == "not_found" and pol.list_policies()["policies"] == []
        assert pol.compliance_report()["report"] == []
        assert pol.publish_policy("coc", "Other", "y", "2026-12-01")["policy"]["version"] == 1


# ---- allowlist ----------------------------------------------------------------------------------------------------------------------
AGENTS = {"OFFER_LETTERS": OfferLetters, "ESIGN": Esign, "ONBOARDING_FLOW": OnboardingFlow, "EMPLOYEE_RECORDS": EmployeeRecords, "POLICY_ACKS": PolicyAcks}
NOT_OVER_HTTP = {"health_check", "dsr_export", "dsr_erase", "ack_evidence", "request_info", "get_offer_status",     # cross-agent views take an org argument
                 "open_signing", "request_otp", "verify_otp", "give_consent", "sign_document", "decline_signing"}        # tokens, not Callers


def public_methods(cls):
    return {n for n, f in inspect.getmembers(cls, inspect.isfunction) if not n.startswith("_")}


@pytest.mark.parametrize("agent", sorted(AGENTS))
def test_every_public_method_is_listed_or_deliberately_excluded(agent):
    methods = public_methods(AGENTS[agent])
    listed = set(allowlist.METHODS[agent])
    assert listed <= methods, listed - methods
    assert methods - listed == methods & NOT_OVER_HTTP


def test_state_changes_are_act_and_signing_is_not_exposed():
    acts = {"OFFER_LETTERS": {"add_template", "create_offer", "revise_offer", "submit_for_approval", "approve", "reject", "send_offer",
                              "record_response", "withdraw_offer", "expire_due"},
            "ESIGN": {"create_request", "send_request", "void_request", "send_reminders", "process_due", "seal_request"},
            "ONBOARDING_FLOW": {"start_onboarding", "cancel_case", "waive_task", "complete_task", "submit_identifier", "submit_form", "collect_document"},
            "EMPLOYEE_RECORDS": {"propose_conversion", "approve_conversion", "reject_conversion", "change_record", "start_exit",
                                 "complete_exit_task", "finalise_exit", "erase_subject"},
            "POLICY_ACKS": {"publish_policy", "retire_policy", "acknowledge"}}
    for agent, names in acts.items():
        for m, rule in allowlist.METHODS[agent].items():
            assert (rule.kind == allowlist.ACT) == (m in names), (agent, m)
    for m in ("sign_document", "open_signing", "give_consent", "decline_signing", "request_otp", "verify_otp"):
        assert allowlist.rule_for("ESIGN", m) is None
    for m in ("dsr_export", "dsr_erase", "_seal"):
        assert allowlist.rule_for("EMPLOYEE_RECORDS", m) is None and allowlist.rule_for("ONBOARDING_FLOW", m) is None


def test_hr_only_acts_are_role_checked_before_they_wait_for_approval():
    fn = EmployeeRecords.erase_subject
    with pytest.raises(AccessDenied):
        allowlist.prepare("EMPLOYEE_RECORDS", "erase_subject", fn, {"employee_id": "EMP-1", "request_ref": "r"}, MGR)
    args = allowlist.prepare("EMPLOYEE_RECORDS", "erase_subject", fn, {"employee_id": "EMP-1", "request_ref": "r"}, HR1)
    assert args == {"employee_id": "EMP-1", "request_ref": "r"}
    with pytest.raises(ValueError):                                   # a caller cannot smuggle an identity or an unknown argument
        allowlist.prepare("POLICY_ACKS", "acknowledge", PolicyAcks.acknowledge, {"policy_key": "p", "seen_text_sha256": "x", "employee_id": "EMP-2"}, MGR)
    allowlist.prepare("POLICY_ACKS", "acknowledge", PolicyAcks.acknowledge, {"policy_key": "p", "seen_text_sha256": "x"}, person("EMP-1"))
    with pytest.raises(ValueError):
        allowlist.prepare("ESIGN", "create_request", Esign.create_request, {"title": "t", "caller": "x"}, HR1)
