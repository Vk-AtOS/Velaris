"""SCREENING_FORMS: forms as data, proof of work, upload sniffing, hashed expiring tokens, the staff side of intake."""

import io
import json
import os
import zipfile

import pytest
from velaris.agentkit.hiring_testkit import ORG, advance, as_, bootstrap, clean_keys, tiny_pdf, trace_text, who

from velaris.agentkit import hiring_common as hc
from velaris.agentkit import hiring_forms as hf
from velaris.agentkit import hiring_intake as hi
from velaris.agents.ATS_CORE.main import AtsCore
from velaris.agents.JOB_POSTINGS.main import JobPostings
from velaris.agents.SCREENING_FORMS.main import ScreeningForms
from velaris.intel.paths import agent_dir

NOTICE = "We collect your name, contact details and résumé to consider you for this role. We keep them 180 days. Withdraw any time using the link in our e-mails."
DEFINITION = {"title": "Backend Engineer application", "consent_text": NOTICE, "retention_days": 180, "talent_pool_offer": True,
              "fields": [{"name": "name", "type": "text", "label": "Full name", "required": True, "max_length": 80},
                         {"name": "email", "type": "email", "required": True}, {"name": "phone", "type": "phone"},
                         {"name": "years", "type": "number", "min": 0, "max": 40, "required": True},
                         {"name": "notice", "type": "choice", "choices": ["immediate", "30 days", "60 days"]},
                         {"name": "cv", "type": "file", "required": True}]}
ANSWERS = {"name": "Asha Kumar", "email": "asha@example.com", "phone": "+91 98765 43210", "years": 4, "notice": "30 days", "consent_given": True}


@pytest.fixture(autouse=True)
def fast_pow(monkeypatch):
    monkeypatch.setattr(hf, "POW_BITS", 10)


@pytest.fixture()
def env():
    ats, forms = AtsCore(), ScreeningForms()
    rid, c = bootstrap(ats)
    with as_(c["rec"]):
        fid = forms.create_form(requisition_id=rid, definition=DEFINITION)["form"]["id"]
        assert forms.publish_form(form_id=fid)["form"]["status"] == "published"
    return ats, forms, rid, fid, c


def submit(fid, answers=None, file=("cv.pdf", None), **kw):
    ch = hi.public_challenge(fid)["challenge"]
    sol = {**ch, "n": hf.solve(ch)}
    data = tiny_pdf("Skills: Python and SQL, 4 years") if file[1] is None else file[1]
    return hi.public_submit(fid, answers if answers is not None else ANSWERS, kw.pop("pow", sol), file_name=file[0], file_bytes=data)


def test_form_definition_is_validated_as_data():
    ok = hf.validate_form_definition(DEFINITION)
    assert ok["consent_version"] and len(ok["fields"]) == 6 and ok["file_rules"]["allowed"] == ["pdf", "docx", "txt"]
    for bad in ({**DEFINITION, "consent_text": "short"}, {**DEFINITION, "fields": []}, {**DEFINITION, "retention_days": 5000},
                {**DEFINITION, "fields": [{"name": "Bad Name", "type": "text"}]}, {**DEFINITION, "fields": [{"name": "x", "type": "teleport"}]},
                {**DEFINITION, "fields": [{"name": "consent_given", "type": "checkbox"}]},
                {**DEFINITION, "fields": [{"name": "a", "type": "text"}, {"name": "a", "type": "text"}]},
                {**DEFINITION, "fields": [{"name": "c", "type": "choice", "choices": ["only"]}]},
                {**DEFINITION, "fields": [{"name": "n", "type": "number", "min": 5, "max": 1}]}, "nope"):
        with pytest.raises(hc.HiringError):
            hf.validate_form_definition(bad)


def test_proof_of_work_hand_values_and_replay_expiry_forgery(env, monkeypatch):
    assert hf.leading_zero_bits(b"\x00\x0f") == 12 and hf.leading_zero_bits(b"\x80") == 0 and hf.leading_zero_bits(b"\x01\x00") == 7 and hf.leading_zero_bits(b"\x00\x00") == 16
    ats, forms, rid, fid, c = env
    ch = hi.public_challenge(fid)["challenge"]
    n = hf.solve(ch)
    sol = {**ch, "n": n}
    assert hf.check_solution(sol, fid) is None
    assert hf.check_solution(sol, fid) == "already used"                                      # replay
    ch2 = hi.public_challenge(fid)["challenge"]
    assert hf.check_solution({**ch2, "n": hf.solve(ch2) + 1_000_003}, fid) == "wrong answer"
    assert hf.check_solution({**ch2, "n": hf.solve(ch2), "bits": 1}, fid) == "bad signature"      # lowering the difficulty breaks the signature
    assert hf.check_solution({**ch2, "n": hf.solve(ch2)}, "another-form") == "bad signature"       # bound to its form
    assert hf.check_solution({"salt": "x"}, fid) == "malformed solution"
    ch3 = hi.public_challenge(fid)["challenge"]
    advance(monkeypatch, hf.POW_TTL + 5)
    assert hf.check_solution({**ch3, "n": hf.solve(ch3)}, fid) == "challenge expired"


def test_submission_requires_pow_consent_and_valid_answers(env):
    ats, forms, rid, fid, c = env
    assert hi.public_submit(fid, ANSWERS, {}, "cv.pdf", tiny_pdf("x"))["status"] == "challenge_failed"
    r = submit(fid, {**ANSWERS, "consent_given": False})
    assert r["status"] == "invalid_input" and "consent_given" in r["errors"]
    r = submit(fid, {k: v for k, v in ANSWERS.items() if k != "consent_given"})
    assert "consent_given" in r["errors"]
    r = submit(fid, {**ANSWERS, "email": "not-an-email", "years": 99, "notice": "tomorrow", "hacker": 1, "name": ""})
    assert set(r["errors"]) == {"email", "years", "notice", "hacker", "name"}
    assert hi.public_form("form-nope")["status"] == "not_found" and hi.public_challenge("form-nope")["status"] == "not_found"
    pending = [s for s in json.loads((agent_dir("SCREENING_FORMS") / "forms.json").read_text())["submissions"].values()]
    assert pending == []                                                                       # nothing stored for any refusal
    good = submit(fid)
    assert good["status"] == "ok" and good["reference"].startswith("sub-")
    stored = json.loads((agent_dir("SCREENING_FORMS") / "forms.json").read_text())["submissions"][good["reference"]]
    assert stored["org"] == ORG and stored["status"] == "pending" and stored["consent"]["notice_version"] == hf.validate_form_definition(DEFINITION)["consent_version"]
    assert stored["consent"]["retention_until"] == hc.iso(hc.now() + 180 * hc.DAY)[:10] and stored["consent"]["talent_pool"] is False


def test_upload_limits_and_type_sniffing(env):
    ats, forms, rid, fid, c = env
    pdf = tiny_pdf("hello")
    assert hf.sniff_upload("cv.pdf", pdf, ["pdf"], 10_000)["kind"] == "pdf"
    for name, data, why in (("cv.pdf", b"MZ\x90\x00" + b"x" * 100, "executable"), ("cv.pdf", b"#!/bin/sh\nrm -rf /", "executable"), ("cv.txt", pdf, "says .txt"),
                            ("cv.pdf", b"\x00\x01\x02binary", "binary"), ("cv.pdf", b"", "empty"), ("cv.pdf", pdf + b"0" * 20_000, "larger"),
                            ("cv.txt", b"<script>alert(1)</script>", "binary")):
        with pytest.raises(hc.HiringError, match=why):
            hf.sniff_upload(name, data, ["pdf", "txt"], 10_000)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("evil.exe", "x")
    with pytest.raises(hc.HiringError, match="zip"):
        hf.sniff_upload("cv.docx", buf.getvalue(), ["pdf", "docx"], 100_000)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<x/>")
        z.writestr("word/document.xml", "<x/>")
    assert hf.sniff_upload("cv.docx", buf.getvalue(), ["docx"], 100_000)["kind"] == "docx"
    assert submit(fid, file=("cv.pdf", b"MZ\x90\x00" + b"x" * 50))["status"] == "invalid_input"
    r = hi.public_submit(fid, ANSWERS, {**(ch := hi.public_challenge(fid)["challenge"]), "n": hf.solve(ch)})
    assert r["status"] == "invalid_input" and "file is required" in r["reason"]


def test_staff_accept_creates_candidate_with_form_consent_parses_resume_and_deletes_the_file(env):
    ats, forms, rid, fid, c = env
    sid = submit(fid, {**ANSWERS, "talent_pool": True})["reference"]
    path = json.loads((agent_dir("SCREENING_FORMS") / "forms.json").read_text())["submissions"][sid]["file"]["path"]
    assert os.path.exists(path) and oct(os.stat(path).st_mode & 0o777) == "0o600"
    with as_(c["rec"]):
        listing = forms.pending_submissions()
        assert [s["id"] for s in listing["submissions"]] == [sid] and "Asha" not in json.dumps(listing)
        assert forms.get_submission(submission_id=sid)["status"] == "denied"                    # identity read
        out = forms.accept_submission(submission_id=sid)
        assert out["status"] == "ok" and out["resume_status"] == "ok" and out["status_token"] and out["application"]["stage"] == "applied"
        assert forms.accept_submission(submission_id=sid)["status"] == "conflict"
    assert not os.path.exists(path)
    ev = json.loads((agent_dir("ATS_CORE") / "evaluation.json").read_text())["candidates"][out["candidate_id"]]
    assert ev["consent"]["channel"] == "web_form" and ev["consent"]["notice_version"] and ev["source"] == "careers_page"
    done = json.loads((agent_dir("SCREENING_FORMS") / "forms.json").read_text())["submissions"][sid]
    assert done["answers"] == {} and done["file"] is None and done["candidate_id"] == out["candidate_id"]
    assert "asha@example.com" not in trace_text()
    with as_(c["rec"]):
        assert forms.discard_submission(submission_id=sid)["status"] == "not_found"


def test_tracking_code_sets_the_ats_source(env):
    ats, forms, rid, fid, c = env
    jp = JobPostings()
    with as_(c["rec"]):
        jp.set_company_profile(name="CTS", website="https://cts.example", careers_base_url="https://cts.example/c")
    with as_(c["rec"]):
        pid = jp.prepare_careers_posting(requisition_id=rid, valid_through=hc.iso(hc.now() + 30 * hc.DAY)[:10])
    assert pid["status"] == "ok"
    with as_(c["rec"]):
        pack_code = jp.prepare_pack(posting_id=pid["posting"]["id"], board="foundit")["pack"]["tracking_code"]
    sid = submit(fid, {**ANSWERS, "tracking_code": pack_code})["reference"]
    with as_(c["rec"]):
        assert forms.accept_submission(submission_id=sid)["status"] == "ok"
        assert ats.aggregate_counts()["by_source"] == {"foundit": 1}


def test_tokens_are_hashed_purpose_bound_and_expire(env, monkeypatch):
    ats, forms, rid, fid, c = env
    sid = submit(fid)["reference"]
    with as_(c["rec"]):
        out = forms.accept_submission(submission_id=sid)
        app, tok = out["application"]["id"], out["status_token"]
        assert forms.issue_candidate_token(application_id="app-nope")["status"] == "not_found"
        assert forms.issue_candidate_token(application_id=app, purpose="admin")["status"] == "invalid_input"
        wtok = forms.issue_candidate_token(application_id=app, purpose="withdraw", days=2)["token"]
    assert tok not in (agent_dir("SCREENING_FORMS") / "forms.json").read_text() and hf.sha(tok) in (agent_dir("SCREENING_FORMS") / "forms.json").read_text()
    s = hi.public_status(tok)
    assert s["status"] == "ok" and s["progress"] == "Received" and set(s) == {"status", "progress", "updated"}
    assert hi.public_status(wtok)["status"] == "not_found" and hi.public_withdraw(tok)["status"] == "not_found"     # wrong purpose
    assert hi.public_status("short")["status"] == "not_found" and hi.public_status(None)["status"] == "not_found"
    with as_(c["rec"]):
        ats.move_stage(application_id=app, to_stage="screening")
    assert hi.public_status(tok)["status"] == "ok"
    advance(monkeypatch, 3 * hc.DAY)
    assert hi.public_withdraw(wtok)["status"] == "not_found"                                        # expired after 2 days
    assert hi.public_status(tok)["status"] == "ok"                                                  # 90 days


def test_candidate_status_text_hides_internal_detail(env):
    ats, forms, rid, fid, c = env
    with as_(c["rec"]):
        out = forms.accept_submission(submission_id=submit(fid)["reference"])
        ats.move_stage(application_id=out["application"]["id"], to_stage="screening", note="internal remark about salary")
        ats.move_stage(application_id=out["application"]["id"], to_stage="rejected", reason_code="no_response")
    r = hi.public_status(out["status_token"])
    assert r["status"] == "ok" and r["progress"] == "Process complete" and "internal" not in json.dumps(r) and "no_response" not in json.dumps(r)


def test_withdrawal_needs_no_login_and_ends_in_a_due_erasure(env):
    ats, forms, rid, fid, c = env
    with as_(c["rec"]):
        out = forms.accept_submission(submission_id=submit(fid)["reference"])
        app = out["application"]["id"]
        wtok = forms.issue_candidate_token(application_id=app, purpose="withdraw")["token"]
    assert hi.public_withdraw(wtok)["status"] == "ok"                                              # no Caller anywhere
    with as_(c["rec"]):
        assert [w["application_id"] for w in forms.withdrawal_requests()["requests"]] == [app]
        assert forms.process_withdrawal(application_id=app)["status"] == "ok"
        assert forms.withdrawal_requests()["requests"] == []
        assert [d["why"] for d in ats.retention_due()["due"]] == ["consent_withdrawn"]
    with as_(c["adm"]):
        assert ats.erase_candidates(candidate_ids=[out["candidate_id"]], reason="consent_withdrawn")["status"] == "ok"
    assert hi.public_status(out["status_token"])["status"] == "not_found"                            # its tokens went with the person


def test_unaccepted_submissions_expire_and_can_be_discarded(env, monkeypatch):
    ats, forms, rid, fid, c = env
    submit(fid)["reference"]
    keep = submit(fid, {**ANSWERS, "name": "Ravi S", "email": "r@example.com"})["reference"]
    with as_(c["rec"]):
        assert forms.sweep_submissions()["deleted"] == 0
        assert forms.discard_submission(submission_id=keep)["status"] == "ok"
    advance(monkeypatch, 31 * hc.DAY)
    with as_(c["rec"]):
        assert forms.sweep_submissions()["deleted"] == 1
    assert json.loads((agent_dir("SCREENING_FORMS") / "forms.json").read_text())["submissions"] == {}


def test_denied_org_and_no_public_route_in_the_identity_api(env):
    ats, forms, rid, fid, c = env
    assert forms.list_forms()["status"] == "unauthenticated"
    with as_(who("interviewer")):
        assert forms.create_form(requisition_id=rid, definition=DEFINITION)["status"] == "denied"
    with as_(who("recruiter", org="other")):
        assert forms.list_forms()["forms"] == [] and forms.get_form(form_id=fid)["status"] == "not_found"
    with as_(c["rec"]):
        routes = forms.public_routes()
        clean_keys(routes)
        bad = forms.create_form(requisition_id=rid, definition={**DEFINITION, "fields": [{"name": "name", "type": "text"}]})
        assert bad["status"] == "invalid_input"
        assert forms.create_form(requisition_id="req-nope", definition=DEFINITION)["status"] == "not_found"
    from velaris.api.allowlist import METHODS
    exposed = set(METHODS["SCREENING_FORMS"])
    assert not any(m.startswith("public_") and m != "public_routes" for m in exposed) and "public_submit" not in exposed
    assert METHODS["SCREENING_FORMS"]["accept_submission"].kind == "act"


def test_hourly_cap_counts_accepted_posts_only_and_the_post_is_one_write(env, monkeypatch):
    _, _, _, fid, _ = env
    monkeypatch.setattr(hi, "MAX_PER_HOUR", 2)
    for _ in range(5):                                                   # invalid posts must not use up the hour
        assert submit(fid, answers={})["status"] == "invalid_input"
    writes = []
    orig = hf._st().__class__.save
    monkeypatch.setattr(hf._st().__class__, "save", lambda self, d: (writes.append(1), orig(self, d))[1])
    assert submit(fid)["status"] == "ok" and len(writes) == 2            # proof-of-work replay mark + (counter and submission in ONE rewrite)
    assert submit(fid)["status"] == "ok"
    assert submit(fid)["status"] == "rate_limited"
    assert len(list((agent_dir("SCREENING_FORMS") / "uploads").glob("*.bin"))) == 2   # the refused upload was removed


def test_unreviewed_submissions_per_form_are_capped_and_a_failed_write_leaves_no_upload(env, monkeypatch):
    """KAN-64 review: submissions share one size-limited state file; a flood filled it for every organisation."""
    _, _, _, fid, _ = env
    monkeypatch.setattr(hi, "MAX_PENDING_PER_FORM", 2)
    assert submit(fid)["status"] == "ok" and submit(fid)["status"] == "ok"
    full = submit(fid)
    assert full["status"] == "rate_limited" and "recruiter reviews" in full["reason"]
    uploads = lambda: len(list((agent_dir("SCREENING_FORMS") / "uploads").glob("*.bin")))      # noqa: E731
    assert uploads() == 2
    monkeypatch.setattr(hi, "MAX_PENDING_PER_FORM", 100)

    def boom(self, d):
        raise ValueError("state file is full")
    monkeypatch.setattr(hf._st().__class__, "save", boom)
    with pytest.raises(ValueError):
        submit(fid)
    assert uploads() == 2                                                # the sealed upload of the failed post was removed
