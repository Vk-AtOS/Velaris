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
