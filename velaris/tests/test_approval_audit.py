"""KAN-27 defect 11: every approval mechanism writes its requests, decisions and executions through ONE helper."""
import json

import pytest

from velaris.agents.AAE_POLICY.main import AAE_POLICYAgent
from velaris.agents.AAE_RUNTIME.main import AAE_RUNTIMEAgent
from velaris.agents.HUMAN_APPROVAL_WORKFLOW.main import HumanApproval
from velaris.agents.PRIME.main import VelarisPrime
from velaris.agents.VCAS_AUTOPILOT.main import VCASAutopilotAgent
from velaris.agents.VCAS_CORE.main import VCASCoreAgent
from velaris.agents.VCAS_SUPERVISOR.main import VCASSupervisorAgent
from velaris.core.access import GOVERNANCE_ADMIN, Caller, acting_as
from velaris.intel import approvals, trace
from velaris.intel.flow import Flow, Tool
from velaris.intel.llm import FakeLLM

UNIFORM = {"system", "event", "request_id", "subject_sha256", "by", "decision", "note"}


@pytest.fixture(autouse=True)
def _data(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    return tmp_path


def events(system, request_id=None):
    out = list(approvals.trail(system=system, request_id=request_id))
    assert all(UNIFORM <= set(p) for p in out)
    return [(p["event"], p["decision"], p["by"]) for p in out]


def test_human_approval_workflow_was_untraced_and_now_records_request_and_decision():
    book = HumanApproval()
    with acting_as(Caller("bot", "kf")):
        rid = book.request_approval("bot", "pay", {"amount": 9})
    with acting_as(Caller("asha", "kf")):
        assert book.approve(rid, "asha") is True
    assert events("HUMAN_APPROVAL_WORKFLOW", rid) == [("requested", "needs_approval", "bot"), ("decided", "approve", "asha")]
    assert all(p["subject_sha256"] for p in approvals.trail(request_id=rid))      # the content is a digest, never stored


def test_an_approval_that_cannot_be_recorded_does_not_happen(monkeypatch):
    book = HumanApproval()
    monkeypatch.setattr(trace, "append", lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
    with acting_as(Caller("bot", "kf")):
        assert book.request_approval("bot", "pay", {}) == "" and book.requests == {}


def test_prime_vcas_and_aae_use_the_same_trail_and_keep_the_entries_other_modules_verify():
    gov, bot, kumar = Caller("meena", "acme", frozenset({GOVERNANCE_ADMIN})), Caller("ap-bot", "acme"), Caller("kumar", "acme")
    prime = VelarisPrime()
    with acting_as(gov):
        g = prime.grant(principal="ap-bot", actions=["invoice.approve"], approver="kumar", autonomy="act", max_amount=50_000, currency="INR")
    assert events("PRIME", g["grant_id"]) == [("granted", "allow", "meena")]
    pilot = VCASAutopilotAgent()
    pilot.register("invoice.approve", lambda p: "ok")
    core = VCASCoreAgent(autopilot=pilot, supervisor=VCASSupervisorAgent(prime))
    task = {"id": "t2", "action": "invoice.approve", "principal": "ap-bot", "context": {"amount": 90_000, "currency": "INR"},
            "params": {"invoice": 2}}
    with acting_as(bot):
        assert core.submit(task)["outcome"] == "pending"
    with acting_as(kumar):
        assert core.decide("t2", True)["outcome"] == "done"
    assert events("VCAS_CORE", "t2") == [("requested", "needs_approval", "ap-bot"), ("decided", "approve", "kumar")]
    assert events("VCAS_AUTOPILOT", "t2") == [("executed", "done", "ap-bot")]
    # the decision entry is still the shape approval_proven looks up (actor VCAS_CORE, action decision, approved, by, task_digest)
    entry = next(e for e in trace.entries() if e["actor"] == "VCAS_CORE" and e["action"] == "decision")
    assert entry["payload"]["approved"] is True and entry["payload"]["by"] == "kumar" and entry["payload"]["task_digest"]

    rules = [{"id": "big", "effect": "require_approval", "if": [{"field": "type", "value": "refund"}]}]
    rt = AAE_RUNTIMEAgent(AAE_POLICYAgent(rules))
    rt.register("refund", lambda p: {"refunded": p["amount"]})
    act = {"id": "a1", "type": "refund", "params": {"amount": 5000}}
    with acting_as(bot):
        assert rt.run(act)["status"] == "needs_approval"
    with acting_as(kumar):
        assert rt.run(act, approved_by="kumar")["status"] == "ok"
    assert [e[:2] for e in events("AAE_RUNTIME", "a1")] == [("requested", "needs_approval"), ("executed", "done")]


def test_flow_anchors_go_through_the_helper_too():
    flow = Flow([Tool("pay", lambda: "paid", "Pay")], llm=FakeLLM(lambda p, m: json.dumps({"tool": "pay", "args": {}})))
    run = flow.start("pay")
    flow.decide(run.run_id, run.pending["call_hash"], approve=True, by="asha")
    kinds = [(e, d, b) for e, d, b in events("FLOW", run.run_id)]
    assert ("decision", "approve", "asha") in kinds and any(e == "call" and d == "approve" for e, d, _ in kinds)
