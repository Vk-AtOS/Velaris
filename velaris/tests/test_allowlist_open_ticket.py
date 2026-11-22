"""VEL-68: ITSM_ENGINE.open_ticket over HTTP: plain JSON body -> Ticket, role-gated, validated, approval-gated."""
import pytest
from fastapi.testclient import TestClient

from velaris.api import allowlist
from velaris.api.app import Settings, create_app
from velaris.backend.engine import backend
from velaris.core.access import Caller
from velaris.intel.llm import FakeLLM
from velaris.orchestration import identity
from velaris.tests.test_api_service import KEY, SECRET, send

TICKET = {"ticket_id": "INC-1", "category": "network", "priority": "high", "impact": "major", "urgency": "high",
          "config_item": "router-1", "history_flags": {"repeat_incident": True}}
URL = "/agents/ITSM_ENGINE/open_ticket"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    roles = {"admin": {"infra_admin"}, "member": set(), "boss": {"flow_approver"}}
    identity.set_resolver(lambda org, uid: Caller(uid, org, frozenset(roles[uid])) if uid in roles else None)
    settings = Settings(secret=SECRET, identity_key=KEY.public_key(), flow_db=str(tmp_path / "flow.db"), org="acme",
                        llm=FakeLLM(lambda p, m: pytest.fail("no model expected")))
    yield TestClient(create_app(settings, engine=backend))
    identity.set_resolver(None)


def decide(client, run):
    return send(client, "POST", f"/flows/{run['run_id']}/decide", {"call_hash": run["pending"]["call_hash"], "approve": True},
                sub="boss", roles=["flow_approver"])


def test_infra_admin_opens_a_ticket_after_approval_with_the_caller_as_opener(client):
    r = send(client, "POST", URL, {"t": TICKET}, sub="admin", roles=["infra_admin"])
    assert r.status_code == 202 and r.json()["kind"] == "act"
    run = r.json()["run"]
    assert run["pending"]["args"] == {"t": TICKET}                            # plain JSON all the way to the approver
    assert decide(client, run).json()["status"] == "done"
    from velaris.agents.ITSM_ENGINE.main import ITSMEngine
    stored = ITSMEngine()._state.load()["tickets"]["INC-1"]
    assert stored["state"] == "new" and stored["history"][0]["by"] == "admin" and stored["computed_priority"] == "P2"


def test_other_roles_are_denied(client):
    assert send(client, "POST", URL, {"t": TICKET}, sub="member", roles=["employee"]).status_code == 403
    assert send(client, "POST", URL, {"t": TICKET}, sub="member").status_code == 403


@pytest.mark.parametrize("body", [
    {"t": "not an object"},
    {"t": {**TICKET, "extra": 1}},                                   # unknown field
    {"t": {k: v for k, v in TICKET.items() if k != "category"}},     # missing field
    {"t": TICKET, "now": 0},                                         # the caller may not choose the clock
    {"t": TICKET, "by": "someone-else"},                             # may not open in another's name
    {},
])
def test_bad_bodies_are_rejected(client, body):
    r = send(client, "POST", URL, body, sub="admin", roles=["infra_admin"])
    assert r.status_code in (400, 403), r.text


def test_a_bad_value_is_refused_by_the_agent_when_the_step_runs(client):
    bad = {**TICKET, "category": "plumbing"}
    run = send(client, "POST", URL, {"t": bad}, sub="admin", roles=["infra_admin"]).json()["run"]
    assert "unsupported category" in str(decide(client, run).json())
    from velaris.agents.ITSM_ENGINE.main import ITSMEngine
    assert "INC-1" not in ITSMEngine()._state.load().get("tickets", {})


def test_the_row_is_declared_as_an_act_with_a_model():
    rule = allowlist.rule_for("ITSM_ENGINE", "open_ticket")
    assert rule.kind == allowlist.ACT and rule.model == "t" and "now" in rule.refuse
