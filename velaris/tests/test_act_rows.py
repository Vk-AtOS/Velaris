"""KAN-31 (ACT pass): the ACT rows of project_management and operations. Role, approval, audit trail, and nothing riskier than
a reversible internal record."""
import pytest
from fastapi.testclient import TestClient

from velaris.agentkit.harness_spec import load_json, manifest_path
from velaris.api import allowlist
from velaris.api.app import Settings, create_app
from velaris.backend.engine import backend
from velaris.core.access import Caller
from velaris.intel import approvals, tools
from velaris.intel.llm import FakeLLM
from velaris.orchestration import autonomy, identity
from velaris.tests.test_api_service import KEY, SECRET, send

BODY = {"client": "Acme", "description": "ship the report", "deadline_hours": 24}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    settings = Settings(secret=SECRET, identity_key=KEY.public_key(), flow_db=str(tmp_path / "flow.db"), org="acme",
                        llm=FakeLLM(lambda p, m: pytest.fail("no model expected")))
    # An approver deciding another person's run needs the deployment's directory (SV2-01): the owner's CURRENT roles.
    roles = {"u1": {"ops_admin", "project_admin"}, "u2": {"flow_approver"}}
    identity.set_resolver(lambda org, uid: Caller(uid, org, frozenset(roles.get(uid, ()))))
    try:
        yield TestClient(create_app(settings))
    finally:
        identity.set_resolver(None)


def commitments():
    return backend.run("SLA_MONITOR", "dashboard")


def test_every_act_row_is_act_with_roles_a_note_and_never_runs_alone():
    assert len(allowlist.ACT_NOTES) == 8
    tools.clear()
    tools.register_allowlist(backend)
    for key, note in allowlist.ACT_NOTES.items():
        agent, method = key.split(".")
        rule = allowlist.rule_for(agent, method)
        assert rule.kind == allowlist.ACT and rule.roles and "governance_admin" in rule.roles and len(note) > 60, key
        spec = tools.get(key)
        assert spec.side_effects == "internal"                          # nothing external, nothing money
        cls = autonomy.classify(spec, {})
        assert cls == "unclassified" and autonomy.mode_of(cls) == "approval", key     # the table never lets it run alone
        assert load_json(manifest_path(spec.department, agent))["harness"]["tools"][method]["kind"] == "act"
    assert {k.split(".")[0] for k in allowlist.ACT_NOTES} == {"SPRINT_PLANNER", "SLA_MONITOR", "OPS_REPORT", "PIPELINE_MONITOR"}


def test_an_unapproved_act_does_not_run_and_a_wrong_role_is_refused(client):
    refused = send(client, "POST", "/agents/SLA_MONITOR/add_commitment", BODY, roles=["employee"])
    assert refused.status_code == 403 and refused.json()["error"]["code"] == "access_denied"
    wrong_dept = send(client, "POST", "/agents/SLA_MONITOR/add_commitment", BODY, roles=["project_admin"])
    assert wrong_dept.status_code == 403                                   # a project admin is not an operations admin
    waiting = send(client, "POST", "/agents/SLA_MONITOR/add_commitment", BODY, roles=["ops_admin"])
    assert waiting.status_code == 202 and waiting.json()["run"]["status"] == "waiting_approval"
    assert commitments() == []                                              # nothing happened without a person


def test_approval_by_a_second_person_runs_it_once_and_the_trail_records_the_decision(client):
    r = send(client, "POST", "/agents/SLA_MONITOR/add_commitment", BODY, sub="u1", roles=["ops_admin"]).json()["run"]
    run_id, h = r["run_id"], r["pending"]["call_hash"]
    own = send(client, "POST", f"/flows/{run_id}/decide", {"call_hash": h, "approve": True}, sub="u1", roles=["ops_admin"])
    assert own.json()["error"]["code"] == "four_eyes" and commitments() == []
    done = send(client, "POST", f"/flows/{run_id}/decide", {"call_hash": h, "approve": True}, sub="u2", roles=["flow_approver"])
    assert done.json()["status"] == "done" and len(commitments()) == 1
    events = [p["event"] for p in approvals.trail(system="FLOW", request_id=run_id)]
    assert events and any("decision" in e or "approv" in e for e in events), events
    assert any(p["by"] == "u2" and p["decision"] for p in approvals.trail(system="FLOW", request_id=run_id))
    assert send(client, "GET", f"/flows/{run_id}/verify").json()["ok"] is True      # the hash chain of the run holds


def test_a_rejected_act_never_runs(client):
    r = send(client, "POST", "/agents/SPRINT_PLANNER/create_sprint",
             {"project_id": "p", "sprint_number": 1, "name": "s1", "start_date": "2026-01-05"}, roles=["project_admin"]).json()["run"]
    no = send(client, "POST", f"/flows/{r['run_id']}/decide", {"call_hash": r["pending"]["call_hash"], "approve": False},
              sub="u2", roles=["flow_approver"])
    assert no.status_code == 200 and no.json()["status"] == "done" and "rejected by u2" in no.json()["output"]
    again = backend.run("SPRINT_PLANNER", "create_sprint",          # a sprint 1 of p does not exist yet: this is its first creation
                        {"project_id": "p", "sprint_number": 1, "name": "s1", "start_date": "2026-01-05"})
    assert "error" not in again
