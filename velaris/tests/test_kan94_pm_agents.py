"""KAN-94: project-management safety agents behave as controls (sandbox, exact money, paths, keys)."""
import json
import os
import random
from decimal import Decimal
from importlib import import_module

import pytest

from velaris.core.access import GOVERNANCE_ADMIN, SECURITY_ADMIN, Caller, acting_as
from velaris.intel.paths import agent_dir

GOV = Caller("gov", "kf", frozenset({GOVERNANCE_ADMIN}))
SEC = Caller("sec", "kf", frozenset({SECURITY_ADMIN}))
MEMBER = Caller("bob", "kf", frozenset())


def mod(name):
    return import_module(f"velaris.agents.{name}.main")


# ---- EXECUTION_SANDBOX -------------------------------------------------------
ESCAPES = ["().__class__.__base__.__subclasses__()", "_ = ().__class__", "import os", "__import__('os')",
           "_ = open('/etc/passwd')", "_ = [x for x in range(3)]", "_ = lambda: 1", "_ = 'a' * 10**9",
           "_ = 9**9**9", "while True: pass", "_ = eval('1')", "_ = abs.__self__", "_ = range(10**9)",
           "x = 10**400", "_ = (1).real", "def f(): pass"]


@pytest.mark.parametrize("code", ESCAPES)
def test_sandbox_refuses_everything_outside_arithmetic(code):
    box = mod("EXECUTION_SANDBOX").ExecutionSandbox()
    r = box.safe_exec(code)
    assert r["status"] == "ERROR" and r["result"] is None, r


def test_sandbox_does_arithmetic_and_keeps_nothing_between_calls():
    box = mod("EXECUTION_SANDBOX").ExecutionSandbox()
    assert box.safe_exec("x = 2 + 3 * 4\n_ = max(x, 5) - abs(-1)")["result"] == 13
    assert box.safe_exec("sum(range(5)) if 1 < 2 else 0")["result"] == 10
    assert box.safe_exec("x")["status"] == "ERROR"            # locals did not persist
    assert box.safe_exec("1 / 0")["status"] == "ERROR" and box.get_last_error()
    big = box.safe_exec("\n".join(["x = 1"] + ["x = x + 1"] * 400))
    assert big["status"] == "ERROR"                           # program size is capped
    assert box.safe_exec(None)["status"] == "ERROR"


# ---- BUDGET_GUARDRAILS ---------------------------------------------------------
def test_budget_is_exact_persisted_and_atomic():
    B = mod("BUDGET_GUARDRAILS").BudgetGuardrails
    b = B()
    with acting_as(GOV):
        assert b.set_limit("ads", "100.10") and not b.set_limit("ads", 0.001)       # sub-paisa refused
        for bad in (float("inf"), float("nan"), -1, True, None, "abc", 10 ** 20):
            assert b.record_spend("ads", bad) is False
        for _ in range(3):
            assert b.record_spend("ads", 0.1)                                         # 0.1 + 0.1 + 0.1 is exactly 0.30
        assert b.spent["ads"] == Decimal("0.30")
        assert b.record_spend("ads", "99.80") and b.remaining("ads") == Decimal("0.00")
        assert b.record_spend("ads", "0.01") is False
        assert b.status("ads")["blocked"] is True
    assert B().remaining("ads") == Decimal("0.00")           # another worker sees the same totals


# ---- ROLLBACK_ENGINE -----------------------------------------------------------
def test_rollback_snapshot_is_private_atomic_and_cannot_follow_a_symlink(tmp_path):
    R = mod("ROLLBACK_ENGINE").RollbackEngine
    r = R()
    p = r.create_snapshot("s1", {"a": 1})
    assert oct(os.stat(p).st_mode & 0o777) == "0o600" and r.rollback("s1") == {"a": 1}
    outside = tmp_path / "outside.json"
    outside.write_text('{"secret": 1}')
    os.symlink(outside, os.path.join(r.SNAPSHOT_DIR, "evil.json"))
    with pytest.raises(ValueError):
        r.load_snapshot("evil")
    with pytest.raises(ValueError):
        r.create_snapshot("evil", {"x": 1})
    assert json.loads(outside.read_text()) == {"secret": 1}
    assert [e["action"] for e in R().get_log()] == ["CREATE", "ROLLBACK"]
    with pytest.raises(FileNotFoundError):
        r.load_snapshot("nope")


# ---- DRY_RUN_SIMULATION -----------------------------------------------------------
def test_dry_run_log_is_owner_only_and_shared():
    D = mod("DRY_RUN_SIMULATION").DryRunSimulation
    d = D()
    d.execute_action("a", {"x": 1})
    live = D(dry_run=False)
    live.execute_action("b", {})
    assert os.stat(d.LOG_PATH).st_mode & 0o777 == 0o600
    assert [list(e) for e in D().read_log()] == [["simulated"], ["executed"]]


# ---- SUCCESSOR_KEY_MODULE ------------------------------------------------------------
def test_successor_key_is_hashed_gated_persisted_and_throttled():
    K = mod("SUCCESSOR_KEY_MODULE").SuccessorKeyModule
    k = K()
    assert k.set_successor_key("long-enough-key") is False   # nobody
    with acting_as(MEMBER):
        assert k.set_successor_key("long-enough-key") is False and k.wipe_key() is False
    with acting_as(SEC):
        assert k.set_successor_key("short") is False
        assert k.set_successor_key("long-enough-key") and not k.set_successor_key("another-key-123")
    assert K().has_key() and K().successor_hash.startswith("scrypt$")
    assert k.wipe_key() is False                              # a stranger cannot erase and reset
    assert k.verify("long-enough-key") and not k.verify("wrong-key-0000")
    for _ in range(5):
        k.verify("bad-bad-bad")
    assert not k.verify("long-enough-key")                    # locked
    with acting_as(SEC):
        assert k.wipe_key() and not k.has_key()


# ---- SPRINT_PLANNER / TIME_TRACKER -----------------------------------------------------
def test_sprint_planner_reports_missing_ids():
    sp = mod("SPRINT_PLANNER").SprintPlanner()
    assert sp.add_task(999, "T1", "x")["error"] == "sprint_not_found"
    assert sp.update_task_status(999, "done")["error"] == "task_not_found"
    assert sp.close_sprint(999)["error"] == "sprint_not_found"
    s = sp.create_sprint("p", 1, "s1", "2026-01-05")
    t = sp.add_task(s["id"], "T1", "x", story_points=3)
    assert sp.update_task_status(t["id"], "done")["status"] == "done"
    assert sp.close_sprint(s["id"])["velocity_achieved"] == 3


def test_forgotten_timer_is_capped_at_a_day(monkeypatch):
    M = mod("TIME_TRACKER")
    tt = M.TimeTracker()
    tt.start_timer("e1", "p1")
    conn = M._db()
    conn.execute("UPDATE active_timers SET started_at='2020-01-01T00:00:00'")
    conn.commit(), conn.close()
    tt.stop_timer("e1")
    conn = M._db()
    assert conn.execute("SELECT hours FROM timelogs").fetchone()[0] == 24.0
    conn.close()


# ---- TACTICIAN / DIGITAL_TWIN_XR_ENGINE -----------------------------------------------
def test_tactician_seed_does_not_reseed_the_global_generator():
    random.seed(123)
    expected = random.random()
    random.seed(123)
    a = mod("TACTICIAN").TacticianAgent({"seed": 7})
    b = mod("TACTICIAN").TacticianAgent({"seed": 7})
    plan = {"base_success": 0.5}
    assert a.simulate_plan(plan, 50) == b.simulate_plan(plan, 50)   # still reproducible per agent
    assert random.random() == expected                              # the shared generator was untouched


def test_digital_twin_does_not_alias_the_callers_dicts():
    t = mod("DIGITAL_TWIN_XR_ENGINE").DigitalTwinXREngine()
    mine = {"pos": {"x": 1}}
    t.create_twin("A", mine)
    mine["pos"]["x"] = 99
    assert t.get_twin("a") == {"pos": {"x": 1}}
    t.get_twin("a")["pos"]["x"] = 5
    assert t.get_twin("a") == {"pos": {"x": 1}}
