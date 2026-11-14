"""KAN-107: ATS_CORE releases contact details only under live consent; a hiring manager moves only their own requisitions."""
from velaris.agentkit.hiring_testkit import as_, advance, bootstrap, consent, who
from velaris.agents.ATS_CORE.main import AtsCore


def _setup(days=90):
    ats = AtsCore()
    rid, c = bootstrap(ats)
    with as_(c["rec"]):
        r = ats.add_candidate(name="Asha Kumar", email="asha@example.com", source="careers_page", requisition_id=rid, consent=consent(days))
    return ats, c, r["candidate_id"], r["application"]["id"]


def test_contact_refused_after_withdrawal_and_after_expiry(monkeypatch):
    ats, c, cid, app = _setup()
    with as_(c["rec"]):
        assert ats.candidate_contact(candidate_id=cid)["email"] == "asha@example.com"
        assert ats.withdraw_consent(candidate_id=cid)["status"] == "ok"
        assert ats.candidate_contact(candidate_id=cid)["status"] == "denied"
    ats2, c2, cid2, _ = _setup(days=1)
    advance(monkeypatch, 3 * 86400)
    with as_(c2["rec"]):
        assert ats2.candidate_contact(candidate_id=cid2)["status"] == "denied"


def test_hiring_manager_moves_only_own_requisition():
    ats, c, cid, app = _setup()
    with as_(who("hiring_manager", id="hm-other")):
        assert ats.move_stage(application_id=app, to_stage="screening")["status"] == "denied"
    with as_(c["mgr"]):
        assert ats.move_stage(application_id=app, to_stage="screening")["status"] == "ok"
