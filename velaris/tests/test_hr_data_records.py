"""KAN-107 / KAN-96: EMPLOYEE_RECORDS conversion needs a verified accepted offer; export masks contact details; erasure is complete and reported."""
from velaris.agents.EMPLOYEE_RECORDS.main import EmployeeRecords
from velaris.core.access import acting_as
from velaris.tests.onboarding_helpers import FakeOffers, HR1, Clock


def test_conversion_refused_without_offer_id_or_without_an_offer_view():
    er = EmployeeRecords({"clock": Clock(), "offers": FakeOffers("accepted")})
    with acting_as(HR1):
        assert er.propose_conversion("A1", "d", "x", "m", "2026-12-01", name="N", email="n@x.in")["status"] == "conflict"
    er = EmployeeRecords({"clock": Clock()})
    with acting_as(HR1):
        assert er.propose_conversion("A1", "d", "x", "m", "2026-12-01", offer_id="o1", name="N", email="n@x.in")["status"] == "not_configured"
        assert er.propose_conversion("A1", "d", "x", "m", "2026-12-01", name="N", email="n@x.in")["status"] == "conflict"


# ---- erasure reaches every store of the subject, and says what it did -----------------------------------------------------
def _offer(oid, status, email="asha@example.in", app="APP-1"):
    return {"id": oid, "org": "acme", "status": status, "candidate": {"name": "Asha Raman", "email": email, "application_id": app, "consent": None},
            "terms": {"role_title": "Engineer", "join_date": "2026-12-01", "manager_name": "Boss"}, "sent_at": None, "response": None}


def _request(rid, status, email="asha@example.in"):
    return {"id": rid, "org": "acme", "title": "Offer", "status": status, "document_sha256": "0" * 64, "document_ref": None,
            "signers": [{"id": "s1", "name": "Asha Raman", "email": email, "state": "signed", "phone": "9000000000", "evidence": {"x": 1},
                         "token_sha256": None}]}


def test_erase_subject_reaches_offers_and_esign_and_reports_what_was_erased_and_held():
    from velaris.tests.test_onboarding_records import exited_employee, make
    er, pol, flow, clock, _ = make()
    emp, _cid = exited_employee(er, flow, pol, clock)
    offers = [p for p in er.participants if type(p).__name__ == "OfferLetters"][0]
    esign = [p for p in er.participants if type(p).__name__ == "Esign"][0]
    offers.store.put("offers", _offer("ofr-declined", "declined"))
    offers.store.put("offers", _offer("ofr-accepted", "accepted"))
    offers.store.put("offers", _offer("ofr-other", "declined", email="someone@else.in", app="APP-9"))
    esign.store.put("requests", _request("sig-voided", "voided"))
    esign.store.put("requests", _request("sig-sealed", "sealed"))
    with acting_as(HR1):
        res = er.erase_subject(emp, "DSR-1")
    assert res["status"] == "ok" and res["complete"] is True and {"OfferLetters", "Esign"} <= set(res["stores_covered"])
    assert any("ofr-declined" in x for x in res["erased"]) and any("sig-voided" in x for x in res["erased"])
    held = {h["what"] for h in res["held"]}
    assert {"offer:ofr-accepted", "esign:sig-sealed"} <= held
    stored = offers.store.state.load()["records"]["offers"]
    assert stored["acme:ofr-declined"]["candidate"]["email"] == "erased" and stored["acme:ofr-accepted"]["candidate"]["email"] == "asha@example.in"
    assert stored["acme:ofr-other"]["candidate"]["email"] == "someone@else.in"            # someone else's offer is untouched
    reqs = esign.store.state.load()["records"]["requests"]
    assert reqs["acme:sig-voided"]["signers"][0]["email"] == "erased" and reqs["acme:sig-sealed"]["signers"][0]["email"] == "asha@example.in"


def test_a_failing_store_is_reported_not_hidden():
    from velaris.tests.test_onboarding_records import exited_employee, make
    er, pol, flow, clock, _ = make()
    emp, _cid = exited_employee(er, flow, pol, clock)

    class Broken:
        def dsr_erase(self, *a, **k):
            raise RuntimeError("disk")
    er.participants.append(Broken())
    with acting_as(HR1):
        res = er.erase_subject(emp, "DSR-2")
    assert res["status"] == "ok" and res["complete"] is False and res["failed_stores"] == ["Broken"]


def test_export_masks_contact_details():
    from velaris.tests.test_onboarding_records import hire, make
    er, *_ = make()
    emp = hire(er)
    with acting_as(HR1):
        out = er.export_subject(emp)["export"]["employee"]
    assert out["email"] == "a***@example.in" and out["phone"].endswith("0000") and "asha@example.in" not in str(out)


def test_erasure_reports_leave_and_performance_records_as_held_not_forgotten():
    from velaris.tests.test_onboarding_records import exited_employee, make
    er, pol, flow, clock, _ = make()
    emp, _cid = exited_employee(er, flow, pol, clock)
    leave = [p for p in er.participants if type(p).__name__ == "LeaveManagement"][0]
    perf = [p for p in er.participants if type(p).__name__ == "PerformanceReviewEngine"][0]
    with acting_as(HR1):
        leave.seed_balances(emp, 2026)
        assert leave.apply(emp, "casual", "2026-11-16", "2026-11-17")["status"] == "pending"
        perf.set_okr(emp, "Q1", "ship", ["a"])
        exp = er.export_subject(emp)["export"]
        assert len(exp["leave_requests"]) == 1 and len(exp["performance"]["okrs"]) == 1
        res = er.erase_subject(emp, "DSR-3")
    held = {h["what"]: h for h in res["held"]}
    assert held["leave_requests(1)"]["status"] == "needs_review" and held["performance_records(1)"]["status"] == "needs_review"
    assert res["complete"] is True and {"LeaveManagement", "PerformanceReviewEngine"} <= set(res["stores_covered"])


# ---- the data-subject methods are gated themselves (lead's review) ------------------------------------------------------
def test_every_hr_dsr_method_refuses_anonymous_other_org_and_unprivileged_callers():
    import pytest
    from velaris.core.access import AccessDenied, Caller
    from velaris.tests.test_onboarding_records import make
    er, *_ = make()
    nobody, other = Caller("u9", "acme"), Caller("hrx", "globex", frozenset({"hr_admin"}))
    for p in er.participants:
        name = type(p).__name__
        with pytest.raises(AccessDenied):
            p.dsr_export("acme", "E1")                                           # no caller
        with pytest.raises(AccessDenied):
            p.dsr_erase("acme", "E1")
        with acting_as(nobody):
            with pytest.raises(AccessDenied):
                p.dsr_export("acme", "E1")                                       # not E1 and no HR role
            with pytest.raises(AccessDenied):
                p.dsr_erase("acme", "E1")
        with acting_as(other):
            with pytest.raises(AccessDenied):
                p.dsr_export("acme", "E1")                                       # the caller's org is not the argument's
            with pytest.raises(AccessDenied):
                p.dsr_erase("acme", "E1")
        assert name


def test_leave_dsr_includes_unstamped_legacy_rows_and_holds_them():
    from velaris.tests.test_onboarding_records import make
    from velaris.agents.LEAVE_MANAGEMENT import main as lm
    er, *_ = make()
    leave = [p for p in er.participants if type(p).__name__ == "LeaveManagement"][0]
    with acting_as(HR1):
        leave.seed_balances("E1", 2026)
        leave.apply("E1", "casual", "2026-11-16", "2026-11-17")
        conn = lm._db()
        conn.execute("UPDATE leave_requests SET org=NULL")
        conn.commit()
        conn.close()
        exp = leave.dsr_export("acme", "E1")["leave_requests"]
        assert len(exp) == 1 and exp[0]["legacy_row_without_organisation"] is True
        res = leave.dsr_erase("acme", "E1")
    assert any("without_organisation" in h["what"] and h["status"] == "needs_review" for h in res["held"])


def test_performance_export_hides_reviewers_comments_and_calibration_from_the_subject():
    from velaris.agents.PERFORMANCE_REVIEW_ENGINE.main import PerformanceReviewEngine
    from velaris.core.access import Caller
    e = PerformanceReviewEngine()
    subject = Caller("u-e7", "acme", frozenset(), "E7")
    peer = Caller("p1", "acme")
    with acting_as(subject):
        e.submit_review("E7", "u-e7", "self", "Q1", {"q": 4}, "my own comment")
    with acting_as(peer):
        e.submit_review("E7", "p1", "peer", "Q1", {"q": 3}, "private remark")
    with acting_as(HR1):
        e.calibrate("Q1", "E7", 3.0, 3.0, "hr1")
        full = e.dsr_export("acme", "E7")["performance"]
    assert len(full["calibration"]) == 1 and any(r["reviewer_id"] == "p1" and r["comments"] == "private remark" for r in full["reviews"])
    with acting_as(subject):
        mine = e.dsr_export("acme", "E7")["performance"]
    assert mine["calibration"] == [] and "withheld" in mine and len(mine["reviews"]) == 2
    assert "p1" not in str(mine) and "private remark" not in str(mine) and "my own comment" not in str(mine)


def test_performance_records_have_a_retention_row_that_holds_until_verified():
    from datetime import date
    from velaris.agentkit import onboarding_retention as r
    d = r.decide("performance_records", None, date(2030, 1, 1))
    assert d["action"] == "hold" and d["status"] == "needs_review" and d["planning_years"] == 3
    assert "no retention row" not in d["reason"]
    assert "performance_records" in r.STATUTORY
