"""KAN-31 follow-up: allowlist rows for the ten departments that had none. Only pure, proven-read methods; each has a note."""
import pytest
from fastapi.testclient import TestClient

from velaris.agentkit.harness_spec import load_json, manifest_path
from velaris.api import allowlist
from velaris.api.app import Settings, create_app
from velaris.backend.engine import backend
from velaris.intel.llm import FakeLLM
from velaris.tests.test_api_service import KEY, SECRET, send

TEN = {"client_success", "communications", "executive", "legal_compliance", "marketing", "operations", "project_management",
       "sales", "security", "supply_chain"}
NEW = {k: v for k, v in ((k.split(".")[0], None) for k in allowlist.NOTES)}


def test_every_new_row_has_a_note_a_read_kind_and_the_harness_agrees():
    assert len(allowlist.NOTES) > 50
    for key, note in allowlist.NOTES.items():
        agent, method = key.split(".")
        rule = allowlist.rule_for(agent, method)
        assert rule is not None and rule.kind == allowlist.READ and len(note) > 40, key       # reads only: no ACT row was added
        department = backend.router.departments[agent]
        assert department in TEN, key
        entry = load_json(manifest_path(department, agent))["harness"]
        assert entry["tools"][method]["kind"] == "read", f"{key}: the harness's own read proof does not say read"
        if department == "security":                     # restricted department: security staff only
            assert rule.roles == allowlist.SECURITY_ADMINS, key
        assert not rule.scope and not rule.own            # nothing in these agents is organisation data
    assert {backend.router.departments[a] for a in NEW} <= TEN


def test_agents_that_keep_data_or_check_callers_themselves_are_not_listed():
    for agent in ("CALL_RECORDER", "BUDGET_GUARDRAILS", "SELF_AUDIT", "POLICY_CONTROLLER", "GOVERNANCE_KERNEL", "SECRETS_VAULT",
                  "ZERO_TRUST_PIPELINE", "CUSTOS", "LEGAL_INTELLIGENCE_ENGINE", "MACHINE_LIFECYCLE_ENGINE", "VMRK", "HELIX"):
        assert agent not in allowlist.METHODS, agent


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    settings = Settings(secret=SECRET, identity_key=KEY.public_key(), flow_db=str(tmp_path / "flow.db"), org="acme",
                        llm=FakeLLM(lambda p, m: pytest.fail("no model expected")))
    return TestClient(create_app(settings))


def test_a_listed_method_runs_over_http_and_a_security_method_needs_the_role(client):
    r = send(client, "POST", "/agents/INSIGHTA/detect_trend", {"series": [1.0, 2.0, 5.0]}, roles=["employee"])
    assert r.status_code == 200 and r.json()["kind"] == "read" and r.json()["result"] == pytest.approx(2.0)
    body = {"workflow_steps": ["a", "b"], "required_steps": ["a"]}
    assert send(client, "POST", "/agents/AUDITOR/check_compliance", body, roles=["employee"]).status_code == 403
    ok = send(client, "POST", "/agents/AUDITOR/check_compliance", body, roles=["security_admin"])
    assert ok.status_code == 200 and ok.json()["result"] is True
    # an agent that is not listed stays refused, and no new row makes an act
    assert send(client, "POST", "/agents/CALL_RECORDER/get_session", {"session_id": "x"}).status_code == 403
