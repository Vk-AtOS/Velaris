"""KAN-104: state-changing methods of approval, policy and audit agents refuse callers without the role."""
import time
from importlib import import_module

import pytest

from velaris.core.access import GOVERNANCE_ADMIN, SECURITY_ADMIN, Caller, acting_as
from velaris.intel import trace


def cls(path, name):
    return getattr(import_module(f"departments.{path}.main"), name)


def who(*roles):
    return acting_as(Caller("u1", "kf", frozenset(roles)))


def test_approval_status_is_a_copy_and_cannot_approve():
    h = cls("_ai_core.HUMAN_APPROVAL_WORKFLOW", "HumanApproval")()
    with who():
        rid = h.request_approval("u1", "pay", {})
    h.status(rid)["status"] = "APPROVED"
    assert h.status(rid)["status"] == "PENDING"


def test_protocol_define_needs_governance_admin_and_is_traced():
    p = cls("legal_compliance.EACPE_PROTOCOL", "EACPE_PROTOCOLAgent")()
    steps = [{"step": "a"}]
    assert p.define("x", steps)["status"] == "unauthenticated"
    with who():
        assert p.define("x", steps)["status"] == "denied"
    with who(GOVERNANCE_ADMIN):
        assert p.define("x", steps)["status"] == "ok"
    assert any(e["action"] == "change.granted" and e["payload"]["change"] == "define" for e in trace.entries())


def test_adaptation_record_and_adapt_need_governance_admin_and_rejected_stays_rejected():
    g = cls("legal_compliance.GOVERNANCE_ADAPTATION_LOOP", "GovernanceAdaptationLoop")()
    out = [{"rule": "r", "decision": "deny", "overridden": True}] * 10
    assert g.record(out)["status"] == "unauthenticated"
    with who():
        assert g.adapt({"outcomes": out})["status"] == "denied"
    with who(GOVERNANCE_ADMIN):
        pid = g.adapt({"outcomes": out})["proposals"][0]["id"]
        assert g.resolve(pid, False)["status"] == "ok"
        assert g.adapt()["proposals"] == []                    # a rejected proposal is not re-created


def test_guard_validate_cannot_consume_an_approval_for_someone_else():
    g = cls("legal_compliance.EACPE_HUMAN_GUARD", "EACPE_HUMAN_GUARDAgent")()
    act = {"class": "delete_data", "requested_by": "u1"}
    with acting_as(Caller("cfo", "kf", frozenset({GOVERNANCE_ADMIN}))):
        g.set_approvers("delete_data", ["boss"])
    with who():
        rid = g.request(act)["request_id"]
    with acting_as(Caller("boss", "kf")):
        g.decide(rid, approve=True)
    assert g.validate(act)["approved"] is False                # no caller
    with acting_as(Caller("mallory", "kf")):
        assert g.validate(act)["approved"] is False
    with who():
        assert g.validate(act)["approved"] is True


def test_self_audit_update_and_vigilis_baseline_need_security_admin(tmp_path):
    a = cls("security.SELF_AUDIT", "SELF_AUDITAgent")()
    finding = {"check": "c", "severity": "high", "detail": "d"}
    assert a.update(finding)["updated"] is False
    with who(SECURITY_ADMIN):
        assert a.update(finding)["updated"] is True
    v = cls("security.VIGILIS", "VigilisAgent")()
    f = tmp_path / "a.py"
    f.write_text("x")
    assert v.baseline([str(f)])["status"] == "unauthenticated"
    with who(GOVERNANCE_ADMIN):
        assert v.baseline([str(f)])["status"] == "denied"


def test_containment_cyber_and_lockdown_need_security_admin():
    c = cls("security.AGENT_CONTAINMENT_MODES", "AgentContainmentModes")()
    assert c.set_mode("a", "FULL_LOCK") is False and c.get_mode("a") == "UNSET"
    with who(SECURITY_ADMIN):
        assert c.set_mode("a", "FULL_LOCK") is True
    r = cls("security.CYBER_RISK_ENGINE", "CyberRiskEngine")
    profile = cls("security.CYBER_RISK_ENGINE", "AssetProfile")("x", "server", "high", 10, {})
    assert r().register(profile)["status"] == "unauthenticated"
    h = cls("security.HARD_LOCKDOWN_MODE", "HardLockdownMode")()
    with who():
        assert h.enable() is True and h.is_enabled()          # locking down needs no role
        assert h.disable() is False and h.is_enabled()
    assert cls("security.HARD_LOCKDOWN_MODE", "HardLockdownMode")().is_enabled()   # survives a restart
    with who(SECURITY_ADMIN):
        assert h.disable() is True and not h.is_enabled()
    s = cls("security.SOFT_LOCKDOWN_MODE", "SoftLockdownMode")()
    with who():
        s.enable()
        assert s.disable() is False


def test_alignment_objectives_need_governance_admin():
    e = cls("_ai_core.NEURAL_ALIGNMENT_ENGINE", "NeuralAlignmentEngine")()
    obj = [{"id": "o", "statement": "s", "keywords": ["k"]}]
    assert e.set_objectives(obj)["status"] == "unauthenticated"
    with who():
        assert e.set_objectives(obj)["status"] == "denied"


def _aae():
    policy = cls("_ai_core.AAE_POLICY", "AAE_POLICYAgent")(
        [{"id": "ok", "effect": "allow", "if": [{"field": "type", "value": "noop"}]}])
    return cls("_ai_core.AAE_RUNTIME", "AAE_RUNTIMEAgent")(policy)


def test_aae_replay_needs_same_action_and_runs_once():
    a = _aae()
    calls = []
    a.register("noop", lambda p: calls.append(1) or "done")
    with who():
        first = a.run({"id": "a1", "type": "noop", "params": {}})
        assert first["status"] == "ok"
        assert a.run({"id": "a1", "type": "noop", "params": {}})["replayed"] is True
        assert a.run({"id": "a1", "type": "noop", "params": {"x": 1}})["status"] == "id_conflict"
    assert len(calls) == 1


def test_aae_in_progress_marker_blocks_second_run():
    a = _aae()
    seen = []

    def handler(p):
        seen.append(a.run({"id": "b1", "type": "noop", "params": {}})["status"])   # re-entrant call mid-run
        return "x"
    a.register("noop", handler)
    with who():
        a.run({"id": "b1", "type": "noop", "params": {}})
    assert seen == ["in_progress"]


def test_action_tokens_are_single_use_and_allow_colons():
    t = cls("security.SECURE_ACTION_TOKENS", "SecureActionTokens")()
    tok = t.generate("deploy:prod")
    assert t.validate(tok, "deploy:prod")["status"] == "OK"
    assert t.validate(tok, "deploy:prod") == {"status": "INVALID", "reason": "Replayed"}
    assert t.generate("a") != t.generate("a")


@pytest.mark.parametrize("name", ["../../x", "a/b", "..", ".hidden", ""])
def test_rollback_refuses_path_traversal(name, tmp_path):
    r = cls("project_management.ROLLBACK_ENGINE", "RollbackEngine")()
    with pytest.raises(ValueError):
        r.create_snapshot(name, {"a": 1})
    assert r.create_snapshot("ok-1.2", {"a": 1}).startswith(r.SNAPSHOT_DIR)


def test_transcript_output_path_is_confined(tmp_path):
    t = cls("communications.CALL_TRANSCRIBER", "CallTranscriber")()
    audio = tmp_path / "a.wav"
    assert t._output_problem(str(audio), "/etc/cron.d/x.json")
    assert t._output_problem(str(audio), str(tmp_path / "a.txt"))
    assert t._output_problem(str(audio), str(tmp_path / "out.json")) is None
    assert t._output_problem(str(audio), str(tmp_path / ".." / "up.json"))


def test_budget_rejects_negative_nan_and_limit_below_spend():
    b = cls("project_management.BUDGET_GUARDRAILS", "BudgetGuardrails")()
    assert b.set_limit("ads", 100) is False                    # no caller
    with who(GOVERNANCE_ADMIN):
        assert b.set_limit("ads", 100) is True
        assert b.set_limit("ads", float("nan")) is False and b.set_limit("ads", -5) is False
        assert b.record_spend("ads", 60) is True
        assert b.record_spend("ads", -50) is False and b.record_spend("ads", float("nan")) is False
        assert b.set_limit("ads", 50) is False                 # below what is already spent
        assert b.remaining("ads") == 40
    assert b.record_spend("ads", 1) is False                   # unauthenticated
