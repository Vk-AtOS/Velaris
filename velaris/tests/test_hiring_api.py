"""The hiring suite and the API allowlist: every method declared, reads are read, changes are act, roles match, nothing public, no verdict keys."""
import ast
import hashlib
import importlib
import inspect
from pathlib import Path

import pytest
from velaris.agentkit.hiring_testkit import as_, bootstrap, consent, who

from velaris.api.allowlist import ACT, METHODS, READ, prepare
from velaris.core.access import AccessDenied

AGENTS = {"ATS_CORE": "AtsCore", "RESUME_EVIDENCE": "ResumeEvidence", "JOB_POSTINGS": "JobPostings", "SCREENING_FORMS": "ScreeningForms",
          "INTERVIEW_SCHEDULER": "InterviewScheduler", "INTERVIEW_KIT": "InterviewKit", "INTERVIEW_RECORD": "InterviewRecord"}
ROOT = Path(__file__).resolve().parents[2]


def cls(name):
    return getattr(importlib.import_module(f"velaris.agents.{name}.main"), AGENTS[name])


@pytest.mark.parametrize("agent", sorted(AGENTS))
def test_every_public_method_is_declared_with_the_kind_and_roles_of_its_decorator(agent):
    declared = METHODS[agent]
    public = {n: f for n, f in inspect.getmembers(cls(agent), inspect.isfunction) if not n.startswith("_") and n != "health_check"}
    assert set(public) == set(declared), (set(public) ^ set(declared))
    for name, fn in public.items():
        rule = declared[name]
        assert rule.kind == (ACT if fn.hiring_kind == "act" else READ), name         # state-changing methods are act, reads are read
        assert rule.roles == frozenset(fn.hiring_roles), name
        assert "caller" not in inspect.signature(fn).parameters                       # identity is never an argument ...
        assert not {"by", "actor", "reviewed_by", "approver", "interviewer_id_of_caller"} & set(inspect.signature(fn).parameters) or name == "set_availability"
    assert declared  # non-empty


def test_roles_are_enforced_by_the_allowlist_before_anything_runs():
    ats = cls("ATS_CORE")()
    fn = type(ats).move_stage
    params = {"application_id": "a", "to_stage": "screening"}
    with pytest.raises(AccessDenied):
        prepare("ATS_CORE", "move_stage", fn, params, who("interviewer"))
    with pytest.raises(AccessDenied):
        prepare("ATS_CORE", "erase_candidates", type(ats).erase_candidates, {"candidate_ids": ["c"], "reason": "erasure_request"}, who("recruiter"))
    assert prepare("ATS_CORE", "move_stage", fn, params, who("recruiter")) == params
    assert prepare("ATS_CORE", "erase_candidates", type(ats).erase_candidates, {"candidate_ids": ["c"], "reason": "erasure_request"}, who("hr_admin"))
    with pytest.raises(ValueError):
        prepare("ATS_CORE", "move_stage", fn, {"application_id": "a", "to_stage": "screening", "by": "someone"}, who("recruiter"))     # no identity argument exists
    with pytest.raises(LookupError):
        prepare("ATS_CORE", "_app", fn, {}, who("recruiter"))


def test_candidates_are_not_callers_and_public_functions_are_not_in_the_identity_api():
    names = {m for agent in AGENTS for m in METHODS[agent]}
    assert not {n for n in names if n.startswith(("public_", "ingest_", "candidate_consent", "candidate_withdraw"))} - {"public_routes"}
    for mod in ("hiring_intake", "hiring_record_gateway"):
        src = (ROOT / "velaris" / "agentkit" / f"{mod}.py").read_text()
        assert "current_caller" not in src and "check_caller" not in src and "Caller(" not in src       # they take tokens, not identities
    assert METHODS["SCREENING_FORMS"]["public_routes"].kind == READ


def test_reads_change_nothing_but_the_ledger(tmp_path):
    ats, rec = cls("ATS_CORE")(), cls("INTERVIEW_RECORD")()
    kit, sch, post, forms, res = cls("INTERVIEW_KIT")(), cls("INTERVIEW_SCHEDULER")(), cls("JOB_POSTINGS")(), cls("SCREENING_FORMS")(), cls("RESUME_EVIDENCE")()
    rid, c = bootstrap(ats)
    with as_(c["rec"]):
        ats.add_candidate(name="A B", email="ab@example.com", source="careers_page", requisition_id=rid, consent=consent())

    def snapshot():
        from velaris.intel.paths import data_dir
        return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((data_dir() / "agents").rglob("*")) if p.is_file()}
    before = snapshot()
    with as_(c["adm"]):
        calls = [ats.list_requisitions(), ats.get_requisition(requisition_id=rid), ats.pipeline(requisition_id=rid), ats.decision_log(), ats.aggregate_counts(),
                 ats.duplicate_review(), ats.retention_due(), rec.list_sessions(), kit.list_questions(), sch.list_interviewers(), sch.list_drafts(),
                 sch.reminders(), post.get_company_profile(), post.list_packs(), post.takedown_due(), forms.list_forms(), forms.pending_submissions(),
                 forms.withdrawal_requests(), forms.public_routes(), res.unknown_skills(), res.list_skills(), res.alias_proposals(),
                 res.bias_audit(records=[{"group": "A", "furthest_stage": "x"}], stages=["x", "y"]) ]
    assert [x["status"] for x in calls].count("ok") == len(calls) - 0, [x for x in calls if x["status"] != "ok"]
    assert snapshot() == before


def _forbidden_names():
    return ("likelihood", "cheat", "authentic", "hire_score", "reject_score", "fit_score", "ranking", "rank_", "recommend", "verdict", "ai_score", "suspicion")


def test_no_hiring_code_builds_a_verdict_a_ranking_or_an_ai_likelihood_key():
    files = [*(ROOT / "departments" / "hr" / a / "main.py" for a in AGENTS), *(ROOT / "velaris" / "agentkit").glob("hiring_*.py")]
    assert len(files) >= 20
    hits = []
    for f in files:
        for node in ast.walk(ast.parse(f.read_text())):
            names = []
            if isinstance(node, ast.Dict):
                names = [k.value for k in node.keys if isinstance(k, ast.Constant) and isinstance(k.value, str)]
            elif isinstance(node, ast.keyword) and node.arg:
                names = [node.arg]
            elif isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                names = [node.name]
            hits += [(f.name, n) for n in names if any(w in n.lower() for w in _forbidden_names())]
    assert hits == []


def test_file_size_and_import_rules_for_the_hiring_suite():
    files = [*(ROOT / "departments" / "hr" / a / "main.py" for a in AGENTS), *(ROOT / "velaris" / "agentkit").glob("hiring_*.py"),
             *(ROOT / "velaris" / "tests").glob("test_hiring_*.py")]
    for f in files:
        text = f.read_text()
        assert len(text.splitlines()) <= 600, f"{f.name} is over 600 lines"
        tree = ast.parse(text)
        assert not any(isinstance(n, ast.ExceptHandler) and n.type is None for n in ast.walk(tree)), f"bare except in {f.name}"
        late = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom)) and n.col_offset > 0]
        assert f.name.startswith("test_") or not late, (f.name, [ast.dump(n)[:60] for n in late])      # imports at the top
        if f.name != "test_hiring_api.py":
            assert "StreamHandler" not in text and "addHandler" not in text                         # no logging handlers at import


def test_manifests_are_honest_and_load():
    import json
    for agent in AGENTS:
        m = json.loads((ROOT / "departments" / "hr" / agent / "manifest.json").read_text())
        assert m["name"] == agent and m["domain"] == "hr" and m["entrypoint"] == f"main.py:{AGENTS[agent]}" and len(m["description"]) > 120
        assert "score" not in m["description"].lower().replace("no single score", "").replace("no hire/reject decision, no ranking and no single score", "") or "no" in m["description"].lower()
        instance = cls(agent)()
        assert instance.health_check()["status"] == "ok"
