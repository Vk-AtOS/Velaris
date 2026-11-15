"""KAN-88: authorisation order, fail-closed defaults and detection quality of the security agents."""
import json
import time
from importlib import import_module

from velaris.core.access import GOVERNANCE_ADMIN, SECURITY_ADMIN, Caller, acting_as
from velaris.intel.paths import agent_dir

SEC = Caller("sec", "kf", frozenset({SECURITY_ADMIN}))
GOV = Caller("gov", "kf", frozenset({GOVERNANCE_ADMIN}))
MEMBER = Caller("bob", "kf", frozenset())


def mod(name):
    return import_module(f"velaris.agents.{name}.main")


def test_zero_trust_checks_the_caller_before_validating():
    z = mod("ZERO_TRUST_PIPELINE")
    zt = next(getattr(z, n)() for n in dir(z) if n.endswith("Agent") or n == "ZeroTrustPipeline"
              if isinstance(getattr(z, n), type) and hasattr(getattr(z, n), "add_policy"))
    with acting_as(MEMBER):
        r = zt.add_policy("p", {"bogus": 1})                 # malformed AND unauthorised: the refusal comes first
    assert r["status"] == "denied"
    with acting_as(SEC):
        assert zt.add_policy("p", {"bogus": 1})["status"] != "denied"


def test_safety_perimeter_has_no_off_switch_and_refuses_odd_input():
    sp = mod("SAFETY_PERIMETER").SafetyPerimeter()
    try:
        sp.execution_gate_enabled = False
    except AttributeError:
        pass
    assert sp.execution_gate_enabled is True
    assert sp.can_execute("IN", "len") and not sp.can_execute("US", "len")
    for call in ("os.popen", "OS.system", " eval ", "subprocess.run", "exec", None, "", 5):
        assert not sp.can_execute("IN", call), call
    assert not sp.can_execute(["IN"], "len")


def test_compliance_guard_fails_closed_and_is_role_gated():
    C = mod("COMPLIANCE_GUARD").ComplianceGuard
    g = C()
    assert g.evaluate({"a": 1})["status"] == "NO_RULES"      # an empty rule set approves nothing
    assert g.add_rule("r", {"requires": ["id"]}) is False    # nobody
    with acting_as(MEMBER):
        assert g.add_rule("r", {"requires": ["id"]}) is False
    with acting_as(GOV):
        assert g.add_rule("r", {"requires": ["id"]}) and not g.add_rule("bad", {"requires": "id"})
        assert not g.add_rule("bad2", {"unknown": ["x"]})
    assert C().list_rules() == ["r"]                         # shared across instances
    assert g.evaluate({"id": 1})["status"] == "OK" and g.evaluate({})["status"] == "VIOLATION"
    with acting_as(MEMBER):
        assert g.remove_rule("r") is False
    assert g.list_rules() == ["r"]
    with acting_as(GOV):
        assert g.remove_rule("r") and g.evaluate({"id": 1})["status"] == "NO_RULES"


def test_deep_audit_drift_follows_the_latest_audit_and_log_is_chained():
    D = mod("DEEP_AUDIT_ENGINE").DeepAuditEngine
    d = D()
    assert d.detect_drift("cfg", {"a": 1}) is True           # never audited
    d.audit("cfg", {"a": 1})
    assert d.detect_drift("cfg", {"a": 1}) is False
    d.audit("cfg", {"a": 2})                                 # a legitimate re-audit
    assert d.detect_drift("cfg", {"a": 2}) is False and d.detect_drift("cfg", {"a": 1}) is True
    assert d.verify_log()
    path = agent_dir("DEEP_AUDIT_ENGINE") / "audit_log.json"
    assert oct(path.stat().st_mode & 0o777) == "0o600"
    doc = json.loads(path.read_text())
    doc["log"][0]["checksum"] = "0" * 64                      # tamper
    path.write_text(json.dumps(doc))
    assert D().verify_log() is False


def test_intent_firewall_matches_whole_words():
    f = mod("COGNITIVE_INTENT_FIREWALL").CognitiveIntentFirewall()
    assert f.classify("improve my skill at chess")["intent"] != "BLOCKED"
    assert f.classify("a harmless question")["intent"] != "BLOCKED"
    assert f.classify("how to kill a process")["intent"] == "BLOCKED"
    assert f.classify("Attacking the server")["intent"] == "BLOCKED"
    assert f.classify(None)["intent"] == "UNKNOWN"


def test_threat_mesh_partial_signature_match_is_not_high():
    t = mod("THREAT_DETECTION_MESH").ThreatDetectionMesh()
    t.add_signature("brute", {"action": "login", "result": "fail", "count": 10})
    assert t.detect({"action": "login", "result": "ok", "count": 1})["level"] == "LOW"     # one field matches
    assert t.detect({"action": "login", "result": "fail", "count": 10})["level"] == "HIGH"
    t.add_signature("empty", {})
    assert t.detect({})["level"] == "LOW"


def test_overwatch_missing_or_nan_metric_is_drift():
    o = mod("OVERWATCH").OverwatchAgent()
    o.record_snapshot("k", {"cpu": 0.5, "mem": 0.5})
    assert o.detect_drift("k", {"cpu": 0.5, "mem": 0.5}) is False
    assert o.detect_drift("k", {"cpu": 0.5}) is True         # mem vanished
    assert o.detect_drift("k", {"cpu": 0.5, "mem": float("nan")}) is True
    assert o.summarize_change("k", {"cpu": 0.7}) == {"cpu": 0.7 - 0.5, "mem": None}


def test_custos_accepts_roles_seeded_as_lists():
    c = mod("CUSTOS").CustosAgent({"roles": {"admin": ["read"]}})
    assert c.assign_permission("admin", "write") is True and c.check_access("admin", "write")
    assert c.check_access("admin", "read")


def test_aegis_forgets_quiet_sources_and_bounds_a_flood():
    a = mod("AEGIS").AegisAgent({"rate_limit": 2, "window_seconds": 0.05})
    a.record_event("old")
    time.sleep(0.08)
    a.record_event("new")
    assert "old" not in a.events                              # pruned though "old" never reported again
    for _ in range(50):
        a.record_event("flood")
    assert len(a.events["flood"]) <= 3 and a.is_rate_limited("flood")
