"""ATS_CORE: requisitions, consent, contact/evaluation split, stages, decision log, duplicates, retention, export, erasure."""
import json

import pytest
from velaris.agentkit.hiring_testkit import ORG, advance, as_, bootstrap, clean_keys, consent, trace_text, who

from velaris.agentkit import hiring_common as hc
from velaris.agents.ATS_CORE.main import AtsCore
from velaris.intel.paths import agent_dir


@pytest.fixture()
def ats():
    return AtsCore()


def add(ats, rid, caller, name="Asha Kumar", email="asha@example.com", phone="+91 98765 43210", source="careers_page", **kw):
    with as_(caller):
        return ats.add_candidate(name=name, email=email, phone=phone, source=source, requisition_id=rid, consent=kw.pop("consent", consent()), **kw)


def test_requisition_needs_a_second_person_to_approve_and_known_skills(ats):
    rec = who("recruiter")
    with as_(rec):
        r = ats.create_requisition(title="Dev", location={"city": "Chennai"}, requirements={"must": ["python"]})
        rid = r["requisition"]["id"]
        assert r["requisition"]["org"] == ORG and r["requisition"]["state"] == "draft"
        assert r["requisition"]["requirements"]["must"][0]["skill_id"] == "python"
        assert ats.create_requisition(title="Dev", location={"city": "Chennai"}, requirements={"must": ["cobol-wizardry"]})["status"] == "invalid_input"
        assert ats.approve_requisition(requisition_id=rid)["status"] == "denied"          # recruiter lacks the role
    with as_(who("hr_admin", id="admin-1")):
        assert ats.approve_requisition(requisition_id=rid)["status"] == "ok"
        assert ats.open_requisition(requisition_id=rid)["requisition"]["state"] == "open"
    with as_(who("hr_admin", id="admin-1")):
        r2 = ats.create_requisition(title="Dev 2", location={"city": "Chennai"}, requirements={"must": ["java"]})["requisition"]["id"]
        assert "other than its creator" in ats.approve_requisition(requisition_id=r2)["reason"]


def test_consent_is_required_before_anything_is_stored(ats):
    rid, c = bootstrap(ats)
    for bad in (None, {}, consent(purpose=""), consent(notice_version=""), consent(days=-1), consent(days=800), consent(channel="telepathy")):
        r = add(ats, rid, c["rec"], consent=bad)
        assert r["status"] == "invalid_input", bad
    assert not (agent_dir("ATS_CORE") / "contacts.json").exists()                 # nothing about the person was written
    with as_(c["rec"]):
        assert ats.add_candidate(name="X", source="careers_page", email="x@y.com", consent=None)["status"] == "invalid_input"
    assert add(ats, rid, c["rec"], email="", phone="")["status"] == "invalid_input"   # no way to contact


def test_contact_and_evaluation_data_are_stored_apart(ats):
    rid, c = bootstrap(ats)
    cid = add(ats, rid, c["rec"])["candidate_id"]
    ev = (agent_dir("ATS_CORE") / "evaluation.json").read_text()
    people = json.loads((agent_dir("ATS_CORE") / "contacts.json").read_text())["people"]
    assert "asha@example.com" not in ev and "Asha" not in ev and "9876543210" not in ev
    assert people[cid]["org"] == ORG and people[cid]["email"] == "asha@example.com"
    assert oct((agent_dir("ATS_CORE") / "contacts.json").stat().st_mode & 0o777) == "0o600"


def test_stage_rules_decision_log_and_deciders(ats):
    rid, c = bootstrap(ats)
    app = add(ats, rid, c["rec"])["application"]["id"]
    with as_(c["rec"]):
        assert ats.move_stage(application_id=app, to_stage="offer")["status"] == "conflict"           # not an allowed step
        assert ats.move_stage(application_id=app, to_stage="rejected")["status"] == "invalid_input"    # needs a reason code
        assert ats.move_stage(application_id=app, to_stage="rejected", reason_code="other_documented")["status"] == "invalid_input"
        assert ats.move_stage(application_id=app, to_stage="screening", note="résumé evidence read")["status"] == "ok"
        assert ats.move_stage(application_id=app, to_stage="interview")["status"] == "ok"
        assert ats.move_stage(application_id=app, to_stage="offer")["status"] == "denied"             # recruiter may not make offers
    with as_(c["mgr"]):
        assert ats.move_stage(application_id=app, to_stage="offer", reason_code="", note="panel agreed", evidence_refs=["sc-1"])["status"] == "ok"
        assert ats.move_stage(application_id=app, to_stage="hired")["application"]["stage"] == "hired"
        assert ats.move_stage(application_id=app, to_stage="interview")["status"] == "conflict"       # terminal
    with as_(c["rec"]):
        log = ats.decision_log()["entries"]
    assert [e["to"] for e in log] == ["screening", "interview", "offer", "hired"]
    assert log[0]["by"] == "recruiter-1" and log[2]["by"] == "hiring_manager-1" and log[2]["evidence_refs"] == ["sc-1"] and log[0]["org"] == ORG
    clean_keys(log)


def test_unauthenticated_wrong_role_and_wrong_org_are_refused(ats, monkeypatch):
    rid, c = bootstrap(ats)
    assert ats.list_requisitions()["status"] == "unauthenticated"
    with as_(who("interviewer")):
        assert ats.list_requisitions()["status"] == "denied"
        assert ats.create_requisition(title="x", location={"city": "c"}, requirements={"must": ["java"]})["status"] == "denied"
    monkeypatch.setenv("VELARIS_ORG", ORG)
    with as_(who("recruiter", org="other")):
        assert ats.list_requisitions()["status"] == "denied"
    with as_(who("recruiter")):
        assert len(ats.list_requisitions()["requisitions"]) == 1
    monkeypatch.delenv("VELARIS_ORG")
    with as_(who("recruiter", org="other")):                  # no deployment org: still scoped by the record's org
        assert ats.list_requisitions()["requisitions"] == []
        assert ats.get_requisition(requisition_id=rid)["status"] == "not_found"


def test_duplicates_are_proposed_never_merged_and_shared_contacts_are_ignored(ats):
    rid, c = bootstrap(ats)
    a = add(ats, rid, c["rec"])["candidate_id"]
    r = add(ats, rid, c["rec"], name="A. Kumar", email="ASHA@example.com ", phone="")
    assert r["status"] == "ok" and len(r["duplicate_reviews"]) == 1
    with as_(c["rec"]):
        items = ats.duplicate_review()["items"]
        assert items[0]["reasons"][0] == "same e-mail" and "asha@example.com" not in json.dumps(items)
        assert ats.resolve_duplicate(review_id=items[0]["id"], same_person=True)["review"]["status"] == "same_person"
        assert ats.resolve_duplicate(review_id=items[0]["id"], same_person=True)["status"] == "conflict"
    ev = json.loads((agent_dir("ATS_CORE") / "evaluation.json").read_text())
    assert len([x for x in ev["candidates"].values() if x["status"] == "active"]) == 2               # nothing merged or deleted
    for i in range(3):                                                                     # one phone number shared by many: not a key
        add(ats, rid, c["rec"], name=f"Person Number{i}", email=f"p{i}@example.com", phone="+91 90000 11111")
    fresh = add(ats, rid, c["rec"], name="Zed Quark", email="zq@example.com", phone="+91 90000 11111")
    assert fresh["duplicate_reviews"] == []
    assert a


def test_retention_sweep_lists_and_a_person_approves_erasure(ats, monkeypatch):
    rid, c = bootstrap(ats)
    cid = add(ats, rid, c["rec"], consent=consent(days=30))["candidate_id"]
    keep = add(ats, rid, c["rec"], name="Ravi Shankar", email="r@example.com", phone="+91 91111 22222", consent=consent(days=300))["candidate_id"]
    with as_(c["rec"]):
        assert ats.retention_due()["due"] == []
    advance(monkeypatch, 40 * hc.DAY)
    with as_(c["rec"]):
        due = ats.retention_due()["due"]
        assert due == [{"candidate_id": cid, "why": "retention_date_passed", "since": due[0]["since"]}]
        assert ats.erase_candidates(candidate_ids=[cid], reason="retention_due")["status"] == "denied"      # recruiter cannot delete
    with as_(c["adm"]):
        assert ats.erase_candidates(candidate_ids=[keep], reason="retention_due")["status"] == "denied"     # not due
        assert ats.erase_candidates(candidate_ids=[cid], reason="retention_due")["erased"] == 1
        assert ats.withdraw_consent(candidate_id=keep)["due_for_erasure"] is True
        assert [d["why"] for d in ats.retention_due()["due"]] == ["consent_withdrawn"]


def test_erasure_removes_the_person_but_keeps_anonymous_counts(ats):
    rid, c = bootstrap(ats)
    cid = add(ats, rid, c["rec"], source="linkedin")["candidate_id"]
    add(ats, rid, c["rec"], name="Ravi Shankar", email="r@example.com", phone="+91 91111 22222", source="naukri")
    app = [a for a in json.loads((agent_dir("ATS_CORE") / "evaluation.json").read_text())["applications"].values() if a["candidate_id"] == cid][0]["id"]
    with as_(c["rec"]):
        ats.move_stage(application_id=app, to_stage="screening", note="spoke to Asha about her notice period")
    with as_(c["adm"]):
        before = ats.aggregate_counts()
        assert ats.export_candidate(candidate_id=cid)["export"]["contact"]["email"] == "asha@example.com"
        assert ats.erase_candidates(candidate_ids=[cid], reason="erasure_request")["status"] == "ok"
        after = ats.aggregate_counts()
        assert ats.candidate_contact(candidate_id=cid)["status"] == "not_found"
    assert after["applications"] == before["applications"] == 2 and after["by_source"] == {"linkedin": 1, "naukri": 1}
    assert after["erased_candidates"] == 1 and after["by_stage"]["screening"] == 1
    on_disk = (agent_dir("ATS_CORE") / "evaluation.json").read_text() + (agent_dir("ATS_CORE") / "contacts.json").read_text()
    assert "asha@example.com" not in on_disk and "Asha" not in on_disk and "notice period" not in on_disk
    assert "Ravi" in on_disk                                                                  # the other person is untouched
    assert "asha" not in trace_text().lower() and "example.com" not in trace_text()           # the ledger never held the person


def test_export_and_contact_reads_are_identity_reads(ats):
    rid, c = bootstrap(ats)
    cid = add(ats, rid, c["rec"])["candidate_id"]
    with as_(c["rec"]):
        assert ats.candidate_contact(candidate_id=cid)["status"] == "denied"                  # recruiter has no 'identity' read
        assert ats.export_candidate(candidate_id=cid)["status"] == "denied"
        piped = ats.pipeline(requisition_id=rid)
    assert piped["stages"]["applied"][0]["candidate_id"] == cid and "email" not in json.dumps(piped)
    assert piped["order"].endswith("not a ranking")
    clean_keys(piped)
    assert "sensitive_read.denied" in trace_text()


def test_ledger_holds_hashes_only_and_every_change_is_traced(ats):
    rid, c = bootstrap(ats)
    add(ats, rid, c["rec"], name="Distinct Surname", email="unique.addr@example.org")
    t = trace_text()
    assert "candidate.added" in t and "requisition.created" in t and "application.created" in t
    assert "Distinct" not in t and "unique.addr" not in t and "Backend Engineer" not in t
