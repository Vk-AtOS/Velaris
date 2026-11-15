"""KAN-96: the older RECRUITMENT_ATS and EMPLOYEE_ONBOARDING agents need a Caller, are org-scoped and keep their data under VELARIS_DATA."""
import os
from pathlib import Path

import pytest

from velaris.agents.EMPLOYEE_ONBOARDING.main import EmployeeOnboardingAgent
from velaris.agents.RECRUITMENT_ATS.main import RecruitmentATSAgent
from velaris.core.access import AccessDenied, Caller, acting_as
from velaris.intel import trace

REC = Caller("rec1", "acme", frozenset({"recruiter"}))
HR = Caller("hr1", "acme", frozenset({"hr_admin"}))
OTHER = Caller("hrx", "globex", frozenset({"hr_admin"}))
NOBODY = Caller("emp1", "acme", frozenset())


def test_recruitment_ats_needs_roles_scopes_orgs_records_the_person_and_exports_under_data_dir():
    a = RecruitmentATSAgent()
    with pytest.raises(AccessDenied):
        a.add_candidate("Arjun", "AI Engineer", "Knackforge")                 # no caller
    with acting_as(NOBODY), pytest.raises(AccessDenied):
        a.add_candidate("Arjun", "AI Engineer", "Knackforge")
    with acting_as(REC):
        cid = a.add_candidate("Arjun", "AI Engineer", "Knackforge", email="arjun@example.in")
        assert a.advance_stage(cid, "placed")["error"]                         # a jump
        assert a.advance_stage(cid, "mystery")["error"]                        # not a stage
        assert a.advance_stage(cid, "screened")["by"] == "rec1"
        assert a.report()["total"] == 1
        path = a.export_csv("../../etc/cands.csv")
    assert Path(path).resolve().is_relative_to(Path(os.environ["VELARIS_DATA"]).resolve()) and "arjun@example.in" in Path(path).read_text()
    with acting_as(OTHER):
        assert a.report()["total"] == 0 and a.advance_stage(cid, "shortlisted")["error"] == "candidate not found"
    with acting_as(NOBODY), pytest.raises(AccessDenied):
        a.export_csv()
    assert any(e["action"] == "sensitive_read.denied" for e in trace.entries())
    assert (Path(os.environ["VELARIS_DATA"]) / "agents" / "RECRUITMENT_ATS" / "recruitment.db").exists()      # not in the working directory


def test_employee_onboarding_needs_hr_admin_and_is_org_scoped():
    a = EmployeeOnboardingAgent()
    with pytest.raises(AccessDenied):
        a.onboard_employee("Kavya", "k@example.in", "Eng", "Engineer")
    with acting_as(HR):
        eid = a.onboard_employee("Kavya", "k@example.in", "Eng", "Engineer")
        assert a.complete_step(eid, "offer_letter_signed") is True
        assert len(a.progress_report()) == 1 and a.progress_report(eid)[0]["completed"] == 1
    with acting_as(OTHER):
        assert a.progress_report() == [] and a.complete_step(eid, "it_accounts_created") is False
    with acting_as(NOBODY), pytest.raises(AccessDenied):
        a.progress_report()
    assert (Path(os.environ["VELARIS_DATA"]) / "agents" / "EMPLOYEE_ONBOARDING" / "employee_onboarding.db").exists()


def test_performance_reviews_are_gated_org_scoped_and_validated():
    from velaris.agents.PERFORMANCE_REVIEW_ENGINE.main import PerformanceReviewEngine
    e = PerformanceReviewEngine()
    emp = Caller("u-e7", "acme", frozenset(), "E7")
    mgr = Caller("m1", "acme", frozenset({"manager"}))
    peer = Caller("p1", "acme", frozenset())
    with pytest.raises(AccessDenied):
        e.set_okr("E7", "Q1", "ship", ["a"])                                       # no caller
    with acting_as(emp):
        assert e.set_okr("E7", "Q1", "ship", ["a"])["id"]
        with pytest.raises(AccessDenied):
            e.set_okr("E8", "Q1", "ship", ["a"])                                   # someone else's
        assert e.submit_review("E7", "u-e7", "self", "Q1", {"quality": 4.0})["average_score"] == 4.0
        with pytest.raises(AccessDenied):
            e.submit_review("E7", "u-e7", "peer", "Q1", {"quality": 5})            # peer review of yourself
        with pytest.raises(AccessDenied):
            e.submit_review("E7", "someone-else", "self", "Q1", {"quality": 4})    # reviewer is the caller
        assert e.submit_review("E7", "u-e7", "self", "Q1", {"quality": 9})["error"]       # off the scale
    with acting_as(peer):
        assert e.submit_review("E7", "p1", "peer", "Q1", {"quality": 0.0})["id"]
        with pytest.raises(AccessDenied):
            e.submit_review("E7", "p1", "manager", "Q1", {"quality": 3})           # not a manager
        with pytest.raises(AccessDenied):
            e.get_360_summary("E7", "Q1")                                          # not theirs to read
    with acting_as(mgr):
        assert e.submit_review("E7", "m1", "manager", "Q1", {"quality": 0.0})["id"]
        with pytest.raises(AccessDenied):
            e.calibrate("Q1", "E7", 3.0, 3.5, "m1")                                # calibration is HR's
    with acting_as(HR):
        s = e.get_360_summary("E7", "Q1")
        assert s["weighted_score"] is not None and s["suggested_rating"]
        with pytest.raises(AccessDenied):
            e.calibrate("Q1", "E7", 3.0, 3.5, "someone-else")
        assert e.calibrate("Q1", "E7", 3.0, 3.0, "hr1")["rating"] == "Meets Expectations"
        assert len(e.get_calibration_report("Q1")) == 1
    with acting_as(OTHER):
        assert e.get_calibration_report("Q1") == []
        assert e.get_okrs("E7")[0:0] == []
    with acting_as(emp):
        with pytest.raises(AccessDenied):
            e.get_calibration_report("Q1")
    with acting_as(emp):
        assert e.get_360_summary("E7", "Q1")["self_score"] == 4.0


def test_legacy_hr_agents_are_deprecated_and_not_served_over_http():
    """KAN-96: RECRUITMENT_ATS and EMPLOYEE_ONBOARDING are retired in favour of ATS_CORE and ONBOARDING_FLOW."""
    from velaris.api import allowlist
    from velaris.agents.RECRUITMENT_ATS.main import RecruitmentATSAgent
    from velaris.agents.EMPLOYEE_ONBOARDING.main import EmployeeOnboardingAgent
    assert RecruitmentATSAgent().health_check()["replaced_by"] == "ATS_CORE"
    assert EmployeeOnboardingAgent().health_check()["replaced_by"] == "ONBOARDING_FLOW"
    assert "RECRUITMENT_ATS" not in allowlist.METHODS and "EMPLOYEE_ONBOARDING" not in allowlist.METHODS
