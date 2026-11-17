"""POST /brain and GET /brain/{id} (KAN-32): authenticated, the caller comes from the signed assertion, /flows ownership."""
import json

import pytest

from velaris.intel import providers
from velaris.intel.llm import FakeLLM
from velaris.tests.test_api_service import _env, api_entries, app_client, send  # noqa: F401  (fixtures and helpers)

PLAN = json.dumps({"steps": [{"id": "s1", "department": "finance", "goal": "say hello", "depends_on": []}]})


def model(prompt, name):
    return PLAN if "central planner" in prompt else json.dumps({"final": "hello from finance"})


@pytest.fixture
def client(tmp_path):
    providers.create("fk", kind="ollama", sensitivity_allowed=["public", "internal", "restricted"])
    return app_client(tmp_path, llm=FakeLLM(model))


def test_the_brain_plans_runs_and_answers_as_the_signed_caller(client):
    r = send(client, "POST", "/brain", {"goal": "say hello to finance"}, sub="u1", roles=["employee"])
    body = r.json()
    assert r.status_code == 200 and body["status"] == "done" and "hello from finance" in body["answer"]
    assert [s["department"] for s in body["steps"]] == ["finance"]
    assert [p["caller"] for p in api_entries("brain.start")] == ["u1"]
    assert "say hello" not in json.dumps(api_entries("brain.start"))        # the goal itself is not copied into the trace


def test_unsigned_malformed_and_foreign_requests_are_refused(client):
    assert client.post("/brain", json={"goal": "x"}).status_code == 401
    assert send(client, "POST", "/brain", {"goal": ""}).status_code == 400
    assert send(client, "POST", "/brain", {"nope": 1}).status_code == 400
    assert send(client, "POST", "/brain", {"goal": "x"}, org="other").status_code == 403       # wrong organisation, before any dispatch
    assert send(client, "POST", "/brain", {"goal": "x" * 5000}).status_code == 400


def test_a_run_belongs_to_its_owner_alone(client):
    run = send(client, "POST", "/brain", {"goal": "say hello"}, sub="u1").json()["brain_run"]
    assert send(client, "GET", f"/brain/{run}", sub="u1").status_code == 200
    for who in (dict(sub="u2"), dict(sub="boss", roles=["governance_admin", "flow_approver"]), dict(sub="u1", org="other")):
        assert send(client, "GET", f"/brain/{run}", **who).status_code in (403, 404)
    assert send(client, "GET", f"/brain/{run}", sub="u2").json()["error"]["code"] == "unknown_run"
    assert send(client, "GET", "/brain/nosuchrun", sub="u1").status_code == 404
