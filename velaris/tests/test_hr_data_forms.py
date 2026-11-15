"""KAN-107: accept_submission keeps the upload and the submission when the resume cannot be read, and a retry does not duplicate the candidate."""
import os

from velaris.agentkit.hiring_testkit import as_
from velaris.agents.SCREENING_FORMS import main as forms_mod
from velaris.intel.paths import agent_dir
from velaris.tests.test_hiring_forms import env, submit  # noqa: F401


def test_failed_parse_keeps_file_and_submission_and_retry_does_not_duplicate(env, monkeypatch):  # noqa: F811
    ats, forms, rid, fid, c = env
    sid = submit(fid)["reference"]
    import json
    path = json.loads((agent_dir("SCREENING_FORMS") / "forms.json").read_text())["submissions"][sid]["file"]["path"]
    real = forms_mod.ResumeEvidence.parse_resume
    monkeypatch.setattr(forms_mod.ResumeEvidence, "parse_resume", lambda self, **k: {"status": "invalid_input", "reason": "unreadable"})
    with as_(c["rec"]):
        out = forms.accept_submission(submission_id=sid)
        assert out["status"] == "resume_failed" and out["candidate_id"]
        assert os.path.exists(path)                                                    # the upload is not deleted
        assert [s["id"] for s in forms.pending_submissions()["submissions"]] == [sid]
        monkeypatch.setattr(forms_mod.ResumeEvidence, "parse_resume", real)
        done = forms.accept_submission(submission_id=sid)
        assert done["status"] == "ok" and done["candidate_id"] == out["candidate_id"] and done["status_token"] and done["resume_status"] == "ok"
        assert ats.aggregate_counts()["applications"] == 1                              # one candidate, not two
    assert not os.path.exists(path)


def test_a_claimed_submission_cannot_be_accepted_twice(env):  # noqa: F811
    ats, forms, rid, fid, c = env
    sid = submit(fid)["reference"]
    from velaris.agentkit import hiring_forms as hf
    hf._st().update(lambda d: d["submissions"][sid].update(status="accepting"))
    with as_(c["rec"]):
        assert forms.accept_submission(submission_id=sid)["status"] == "conflict"
