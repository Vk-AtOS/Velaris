"""/control endpoints on the Velaris API: signed, identified, org-checked; start/undo are act."""
import json
import secrets

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from velaris.api import allowlist
from velaris.api.allowlist import ACT, READ
from velaris.api.app import Settings, create_app
from velaris.api.auth import make_assertion, sign
from velaris.control import api as control_api
from velaris.control.checkpoint import CheckpointStore
from velaris.control.fake import FakeDriver
from velaris.control.service import ControlService
from velaris.core.access import AccessDenied, Caller, acting_as
from velaris.intel import trace
from velaris.intel.llm import FakeLLM
from velaris.control.testing import FINAL, FORM, PAGE, FakeRunner, model, step

SECRET, KEY = b"s" * 32, Ed25519PrivateKey.generate()


class _Engine:                                    # the control endpoints never touch the agent engine
    router = type("R", (), {"departments": {}, "failed": {}})()

    def list_agents(self):
        return []


def app_client(tmp_path, llm):
    settings = Settings(secret=SECRET, identity_key=KEY.public_key(), flow_db=str(tmp_path / "flow.db"), org="acme", llm=llm)
    return TestClient(create_app(settings, engine=_Engine()))


def send(client, method, path, body=None, *, sub="u1", org="acme", roles=()):
    content = b"" if body is None else json.dumps(body).encode()
    nonce = secrets.token_urlsafe(16)
    identity = make_assertion(KEY, sub=sub, org=org, roles=roles, nonce=nonce)
    return client.request(method, path, content=content, headers=sign(SECRET, method, path, content, identity, nonce=nonce))


def api_entries(action):
    return [e["payload"] for e in trace.entries() if e["actor"] == "api" and e["action"] == action]


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_ORG", "acme")
    w = type("W", (), {})()
    w.runner, w.driver = FakeRunner(), FakeDriver(PAGE, "about:blank")
    w.replies = []

    def build(llm=None, gate=None, flow_path=None):
        return ControlService(store=CheckpointStore(tmp_path / "cp"), llm=llm, gate=gate, workspace=tmp_path / "ws",
                              runner=w.runner, driver_factory=lambda: w.driver, flow_path=flow_path,
                              resolver=lambda h: ["93.184.216.34"])
    monkeypatch.setattr(control_api, "ControlService", lambda llm=None, gate=None, flow_path=None: build(llm, gate, flow_path))
    return w


def client(tmp_path, world, *replies):
    return app_client(tmp_path, FakeLLM(model(*replies)))


def test_tasks_start_state_report_and_the_trace(tmp_path, world):
    c = client(tmp_path, world, step("run", "uname", "-a"), step("run", "uptime"), step("run", "date"), FINAL)
    assert c.get("/control/tasks").json()["error"]["code"] == "unsigned"
    tasks = send(c, "GET", "/control/tasks").json()["tasks"]
    assert {t["id"] for t in tasks} == {"files.organise", "docs.collect", "files.export_report", "browser.fill_form",
                                        "terminal.diagnostics"}
    r = send(c, "POST", "/control/runs", {"task_id": "terminal.diagnostics", "params": {"bundle": "system"}})
    assert r.status_code == 200 and r.json()["status"] == "succeeded" and world.runner.calls == [["uname", "-a"], ["uptime"], ["date"]]
    run_id = r.json()["task_id"]
    s = send(c, "GET", f"/control/runs/{run_id}").json()
    assert s["status"] == "succeeded" and s["observations"] and "output" not in str(s["observations"])
    rep = send(c, "GET", f"/control/runs/{run_id}/report").json()
    assert rep["verification"]["ok"] and rep["org"] == "acme" and len(rep["actions"]) == 3
    assert "verified: yes" in send(c, "GET", f"/control/runs/{run_id}/report?format=text").text
    assert api_entries("control.start")[0]["kind"] == "act" and api_entries("control.started")[0]["outcome"] == "ok"
    assert send(c, "GET", "/trace/verify", roles=["governance_admin"]).json()["ok"] is True


def test_refusals(tmp_path, world):
    c = client(tmp_path, world, FINAL)
    assert send(c, "POST", "/control/runs", {"task_id": "shell.run", "params": {}}).status_code == 404
    assert send(c, "POST", "/control/runs", {"task_id": 5}).json()["error"]["code"] == "bad_run"
    assert send(c, "POST", "/control/runs", {"task_id": "terminal.diagnostics", "params": {"bundle": "x"}}).json()["error"]["code"] == "bad_params"
    assert send(c, "POST", "/control/runs", {"task_id": "terminal.diagnostics", "params": {"bundle": "disk"}}, org="globex").status_code == 403
    assert send(c, "GET", "/control/runs/nope").status_code == 404
    assert send(c, "POST", "/control/runs/abc/decide", {"call_hash": 1, "approve": True}).json()["error"]["code"] == "bad_decision"
    assert world.runner.calls == []


def test_approval_undo_and_kill_over_http(tmp_path, world):
    c = client(tmp_path, world, step("navigate", "about:blank", to=FORM), step("fill", "Full name", "Asha"),
               step("submit", "Submit"), FINAL)
    r = send(c, "POST", "/control/runs", {"task_id": "browser.fill_form",
                                          "params": {"url": FORM, "fields": {"Full name": "Asha"}, "submit": True}})
    assert r.status_code == 202 and r.json()["status"] == "waiting_approval"
    run_id, h = r.json()["task_id"], r.json()["pending"]["call_hash"]
    assert send(c, "GET", "/control/pending").json()["runs"][0]["task_id"] == run_id
    assert send(c, "GET", "/control/pending", sub="u2").json()["runs"] == []
    assert send(c, "GET", f"/control/runs/{run_id}", sub="u2").status_code == 404
    own = send(c, "POST", f"/control/runs/{run_id}/decide", {"call_hash": h, "approve": True}, roles=["flow_approver"])
    assert own.status_code == 403
    assert send(c, "POST", f"/control/runs/{run_id}/decide", {"call_hash": h, "approve": True}, sub="u2").status_code == 404
    assert send(c, "POST", f"/control/runs/{run_id}/decide", {"call_hash": h, "approve": True}, sub="u2",
                roles=["flow_approver"]).json()["status"] == "succeeded"
    assert world.driver.submissions == [{"Full name": "Asha", "Email": ""}]
    rep = send(c, "GET", f"/control/runs/{run_id}/report").json()
    assert rep["approvals"][0]["approver"] == "u2"
    undo = send(c, "POST", f"/control/runs/{run_id}/undo", {})
    assert undo.status_code == 200 and undo.json()["status"] == "undone_partial" and undo.json()["needs_human"]   # the submit stays
    assert api_entries("control.undo")[0]["kind"] == "act"
    assert send(c, "POST", f"/control/runs/{run_id}/kill", {}).json()["killed"] is True


def test_allowlist_and_agent_wrapper(tmp_path, world, monkeypatch):
    assert allowlist.rule_for("CONTROL_LAYER", "start_run").kind == ACT
    assert allowlist.rule_for("CONTROL_LAYER", "undo").kind == ACT
    assert allowlist.rule_for("CONTROL_LAYER", "list_tasks").kind == READ
    assert allowlist.rule_for("CONTROL_LAYER", "kill") is None and allowlist.rule_for("CONTROL_LAYER", "_x") is None
    from velaris.agents.CONTROL_LAYER import main as agent
    svc = ControlService(store=CheckpointStore(tmp_path / "cp2"), llm=FakeLLM(model(step("run", "date"), step("run", "uname", "-a"),
                         step("run", "uptime"), FINAL)), workspace=tmp_path / "ws2", runner=world.runner, flow_path=str(tmp_path / "f.db"))
    monkeypatch.setattr(agent, "_service", svc)
    a = agent.CONTROL_LAYERAgent()
    with pytest.raises(AccessDenied):
        a.list_tasks() and a.start_run("terminal.diagnostics", {"bundle": "system"})
    with acting_as(Caller("u1", "acme")):
        assert a.health_check()["status"] == "ok"
        out = a.start_run("terminal.diagnostics", {"bundle": "system"})
        assert out["status"] == "succeeded" and a.run_report(out["task_id"])["owner"] == "u1"
