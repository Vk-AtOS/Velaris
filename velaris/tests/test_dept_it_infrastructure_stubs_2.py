"""Behaviour of the it_infrastructure agents that used to be stubs (part 2: placement, offline work, tenancy, ITSM).

Temporary VELARIS_DATA throughout; no network; declared samples and timestamps only.
"""
import os
from importlib import import_module

import pytest

from velaris.core.access import Caller, acting_as
from velaris.intel import trace


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    return tmp_path


def run_as(who, fn):
    """Call fn() as the named caller (an empty name still needs someone calling)."""
    with acting_as(Caller(who or "someone", "kf")):
        return fn()


def make(name, cls=None):
    return getattr(import_module(f"velaris.agents.{name}.main"), cls or f"{name}Agent")()


SAMPLE = {"cpu_percent": 25.0, "cpu_count": 8, "mem_percent": 50.0, "mem_available_mb": 4096.0,
          "disk_percent": 40.0, "disk_free_mb": 50000.0}


# ── NETWORK_OPTIMIZER ────────────────────────────────────────────────────────
def test_network_best_path_accounts_for_loss():
    n = make("NETWORK_OPTIMIZER")
    n.set_link("a", "b", 10)
    n.set_link("b", "d", 10, loss=0.5)        # costs 20 once resends are counted
    n.set_link("a", "c", 12)
    n.set_link("c", "d", 12)
    r = n.best_path("a", "d")
    assert r["path"] == ["a", "c", "d"] and r["expected_latency_ms"] == 24 and r["hops"] == 2
    n.set_link("b", "d", 10, loss=0.0)
    assert make("NETWORK_OPTIMIZER").best_path("a", "d")["path"] == ["a", "b", "d"]


def test_network_routes_around_a_down_link():
    n = make("NETWORK_OPTIMIZER")
    n.set_link("a", "b", 1)
    n.set_link("b", "c", 1)
    n.set_link("a", "c", 50)
    n.set_link("b", "c", 1, up=False)
    assert n.best_path("a", "c")["path"] == ["a", "c"]
    n.remove_link("a", "c")
    assert n.best_path("a", "c")["status"] == "unreachable"
    assert n.best_path("a", "a")["path"] == ["a"]


def test_network_bad_input():
    n = make("NETWORK_OPTIMIZER")
    assert n.set_link("a", "a", 1)["status"] == "invalid_input"
    assert n.set_link("a", "b", -1)["status"] == "invalid_input"
    assert n.set_link("a", "b", 1, loss=1.0)["status"] == "invalid_input"
    assert n.best_path("x", "y")["status"] == "unreachable"
    assert n.best_path(1, 2)["status"] == "invalid_input"
    assert n.remove_link("a", "b")["status"] == "unknown_link"


# ── DISTRIBUTED_FABRIC ───────────────────────────────────────────────────────
def test_fabric_placement_is_stable_and_spread():
    f = make("DISTRIBUTED_FABRIC")
    for node in ("n1", "n2", "n3"):
        f.join(node)
    keys = [f"doc-{i}" for i in range(600)]
    before = {k: f.locate(k)["owners"][0] for k in keys}
    assert before == {k: make("DISTRIBUTED_FABRIC").locate(k)["owners"][0] for k in keys}   # same answer after restart
    counts = f.distribution(keys)["counts"]
    assert sum(counts.values()) == 600 and min(counts.values()) > 100       # no node is starved
    f.join("n4")
    moved = [k for k in keys if f.locate(k)["owners"][0] != before[k]]
    assert 0 < len(moved) < 300 and all(f.locate(k)["owners"][0] == "n4" for k in moved)   # keys only move to the newcomer


def test_fabric_replicas_are_distinct_nodes():
    f = make("DISTRIBUTED_FABRIC")
    f.join("n1")
    f.join("n2")
    owners = f.locate("k", replicas=3)["owners"]
    assert sorted(owners) == ["n1", "n2"]                                   # only two nodes exist
    f.leave("n1")
    assert f.locate("k", replicas=2)["owners"] == ["n2"]


def test_fabric_bad_input():
    f = make("DISTRIBUTED_FABRIC")
    assert f.locate("k")["status"] == "no_nodes"
    assert f.join("n", vnodes=0)["status"] == "invalid_input"
    assert f.leave("ghost")["status"] == "unknown_node"
    f.join("n")
    assert f.locate("")["status"] == "invalid_input"
    assert f.locate("k", replicas=0)["status"] == "invalid_input"
    assert f.distribution("abc")["status"] == "invalid_input"


# ── ENERGY_MANAGER ───────────────────────────────────────────────────────────
def test_energy_profiles_from_power_state():
    e = make("ENERGY_MANAGER")
    assert e.advise({"battery_percent": 80, "on_ac": True})["profile"] == "performance"
    assert e.advise({"battery_percent": 80, "on_ac": False})["profile"] == "balanced"
    assert e.advise({"battery_percent": 20, "on_ac": False})["profile"] == "saver"
    assert e.advise({"battery_percent": None, "on_ac": None})["profile"] == "performance"   # a desktop
    assert e.advise()["profile"] in ("performance", "balanced", "saver")                    # the real machine


def test_energy_defers_heavy_work_and_keeps_threshold():
    e = make("ENERGY_MANAGER")
    on_battery = {"battery_percent": 45, "on_ac": False}
    assert e.should_run("heavy", on_battery)["run"] is False
    assert e.should_run("normal", on_battery)["run"] is True
    e.set_low_battery(50)
    saver = make("ENERGY_MANAGER").should_run("normal", on_battery)        # the threshold survived a restart
    assert saver["run"] is False and saver["profile"] == "saver"
    assert e.should_run("critical", on_battery)["run"] is True
    assert e.estimate_energy(7200, 15)["watt_hours"] == 30


def test_energy_bad_input():
    e = make("ENERGY_MANAGER")
    assert e.advise({"battery_percent": 140})["status"] == "invalid_input"
    assert e.advise({"battery_percent": 50, "on_ac": "yes"})["status"] == "invalid_input"
    assert e.should_run("urgent")["run"] is False
    assert e.should_run("heavy", {"battery_percent": -1})["run"] is False
    assert e.set_low_battery(0)["status"] == "invalid_input"
    assert e.estimate_energy(-1, 5)["status"] == "invalid_input"


# ── LOCAL_ACCELERATOR ────────────────────────────────────────────────────────
def test_accelerator_computes_once_then_serves_from_disk():
    a = make("LOCAL_ACCELERATOR")
    calls = []
    first = a.compute("report:q3", lambda: calls.append(1) or {"total": 42}, ttl_s=60, now=1000)
    again = make("LOCAL_ACCELERATOR").compute("report:q3", lambda: calls.append(1) or {"total": 0}, now=1030)
    assert (first["hit"], again["hit"], again["value"], len(calls)) == (False, True, {"total": 42}, 1)
    assert a.stats()["hits"] == 1 and a.stats()["misses"] == 1


def test_accelerator_ttl_expiry_and_lru_eviction(monkeypatch):
    mod = import_module("velaris.agents.LOCAL_ACCELERATOR.main")
    monkeypatch.setattr(mod, "MAX_ENTRIES", 2)
    a = mod.LOCAL_ACCELERATORAgent()
    a.put("a", 1, ttl_s=10, now=100)
    assert a.get("a", now=109)["value"] == 1 and a.get("a", now=110)["status"] == "miss"
    a.put("x", 1, now=200)
    a.put("y", 2, now=201)
    a.get("x", now=202)                    # x is now the most recently used
    a.put("z", 3, now=203)
    assert a.get("y", now=204)["hit"] is False and a.get("x", now=204)["hit"] and a.get("z", now=204)["hit"]


def test_accelerator_never_caches_a_failure():
    a = make("LOCAL_ACCELERATOR")
    failed = a.compute("k", lambda: 1 / 0)
    assert failed["status"] == "compute_failed" and a.get("k")["status"] == "miss"
    assert a.compute("k", lambda: {1, 2})["status"] == "invalid_input"     # a set is not JSON
    assert a.compute("k", "not callable")["status"] == "invalid_input"
    assert a.put("", 1)["status"] == "invalid_input" and a.put("k", 1, ttl_s=0)["status"] == "invalid_input"


# ── LOCAL_REGISTRY_CACHE ─────────────────────────────────────────────────────
def test_registry_cache_refresh_scans_departments_and_persists():
    c = make("LOCAL_REGISTRY_CACHE", "LocalRegistryCache")
    assert c.cache == {} and c.is_stale() is True
    r = c.refresh()
    assert r["status"] == "ok" and r["entries"] > 100
    fresh = make("LOCAL_REGISTRY_CACHE", "LocalRegistryCache")
    assert fresh.lookup("ITSM_ENGINE")["entry"] == {"department": "it_infrastructure"}
    assert fresh.lookup("ORCHESTRIX")["entry"]["department"] == "_ai_core"


def test_registry_cache_update_staleness_and_bad_input():
    c = make("LOCAL_REGISTRY_CACHE", "LocalRegistryCache")
    assert c.update({"A": {"department": "x"}})["entries"] == 1 and c.cache == {"A": {"department": "x"}}
    updated = c._state.load()["updated_at"]
    assert c.is_stale(max_age_s=60, now=updated + 30) is False
    assert c.is_stale(max_age_s=60, now=updated + 61) is True
    assert c.is_stale(max_age_s="soon") is True
    assert c.update(["A"])["status"] == "invalid_input"
    assert c.update({"A": object()})["status"] == "invalid_input"
    assert c.cache == {"A": {"department": "x"}}                           # bad updates changed nothing
    assert c.lookup("NOPE")["status"] == "unknown_agent" and c.lookup(None)["status"] == "unknown_agent"


# ── LOCAL_ROUTER ─────────────────────────────────────────────────────────────
def test_router_keeps_restricted_work_local():
    r = make("LOCAL_ROUTER", "LocalRouter")
    assert r.route({"sensitivity": "restricted", "cloud_available": True, "est_mem_mb": 99999}, SAMPLE) == "offline"
    assert r.route({"sensitivity": "restricted", "needs_network": True, "cloud_available": True}) == "reject"
    assert r.route({"needs_network": True, "cloud_available": True}) == "reject"      # unclassified = restricted
    assert r.route({"sensitivity": "top-secret-ish"}) == "offline"


def test_router_cloud_only_when_declared_available():
    r = make("LOCAL_ROUTER", "LocalRouter")
    net = {"sensitivity": "internal", "needs_network": True}
    assert r.route(net) == "defer" and r.route({**net, "cloud_available": True}) == "cloud"
    big = {"sensitivity": "public", "est_mem_mb": 8000}
    assert r.route(big, SAMPLE) == "defer" and r.route({**big, "cloud_available": True}, SAMPLE) == "cloud"
    small = r.decide({"sensitivity": "public", "est_mem_mb": 100, "cloud_available": True}, SAMPLE)
    assert small["route"] == "offline" and small["reason"] == "fits on this machine"
    assert r.route({"sensitivity": "public"}) == "offline"


def test_router_rejects_bad_input():
    r = make("LOCAL_ROUTER", "LocalRouter")
    assert r.route("do the thing") == "reject" and r.route(None) == "reject"
    assert r.decide({"sensitivity": "public", "needs_network": "yes"})["status"] == "invalid_input"
    assert r.route({"sensitivity": "public", "est_mem_mb": -5}) == "reject"
    assert r.route({"sensitivity": "public", "est_mem_mb": 5}, {"mem_available_mb": "lots"}) == "reject"


# ── CLOUD_HANDOFF_CONTROLLER ─────────────────────────────────────────────────
def test_handoff_without_transport_claims_nothing():
    c = make("CLOUD_HANDOFF_CONTROLLER", "CloudHandoffController")
    r = c.sync({"job": "nightly-report", "sensitivity": "internal"})
    assert r["status"] == "not_configured" and r["synced"] is False and r["pending"] == 1
    assert len(make("CLOUD_HANDOFF_CONTROLLER", "CloudHandoffController").pending()) == 1


def test_handoff_delivers_in_order_and_stops_at_first_failure():
    c = make("CLOUD_HANDOFF_CONTROLLER", "CloudHandoffController")
    for n in (1, 2, 3):
        c.enqueue({"n": n, "sensitivity": "public"})
    sent = []
    partial = c.sync(sender=lambda item: sent.append(item["n"]) or item["n"] < 2)
    assert (partial["status"], partial["delivered"], partial["pending"], sent) == ("partial", 1, 2, [1, 2])
    assert c.pending()[0]["data"] == {"n": 2, "sensitivity": "public"} and c.pending()[0]["attempts"] == 1

    def broken(item):
        raise ConnectionError("link down")
    assert "ConnectionError" in c.sync(sender=broken)["reason"] and len(c.pending()) == 2
    done = c.sync(sender=lambda item: True)
    assert done == {"status": "ok", "synced": True, "delivered": 2, "pending": 0}
    assert c.sync(sender=lambda item: "yes")["synced"] is True              # nothing left to send


def test_handoff_masks_secrets_and_refuses_restricted():
    c = make("CLOUD_HANDOFF_CONTROLLER", "CloudHandoffController")
    c.enqueue({"note": "contact a.person@example.com", "nested": [{"pan": "ABCDE1234F"}], "sensitivity": "internal"})
    stored = c.pending()[0]["data"]
    assert stored == {"note": "contact [EMAIL]", "nested": [{"pan": "[PAN]"}], "sensitivity": "internal"}
    assert c.enqueue({"sensitivity": "restricted", "x": 1})["status"] == "refused"
    for label in (None, "Restricted", "confidential", "pubic", "", ["public"]):    # unclassified or misspelt stays here
        item = {"x": 1} if label is None else {"x": 1, "sensitivity": label}
        assert c.enqueue(item)["status"] == "refused", label
    assert len(c.pending()) == 1
    assert c.sync({"sensitivity": "restricted"}, sender=lambda i: True)["synced"] is False
    assert c.enqueue("text")["status"] == "invalid_input" and c.enqueue({})["status"] == "invalid_input"
    assert c.sync(sender="ftp")["status"] == "invalid_input"
    assert c.sync(sender=lambda item: 1)["synced"] is False                 # only True confirms delivery


# ── LOCAL_AUTONOMY_CORE ──────────────────────────────────────────────────────
def test_autonomy_ready_on_a_healthy_node():
    a = make("LOCAL_AUTONOMY_CORE", "LocalAutonomyCore")
    assert a.ping()["local"] is True and a.ping()["pid"] == os.getpid()
    r = a.readiness(required_agents=["OFFLINE_SANDBOX", "LOCAL_ROUTER"], sample=SAMPLE)
    assert r["mode"] == "autonomous" and r["failed"] == [] and len(r["checks"]) == 5


def test_autonomy_degraded_names_each_failing_check(data_dir):
    a = make("LOCAL_AUTONOMY_CORE", "LocalAutonomyCore")
    trace.append("test", "one", {})
    trace.append("test", "two", {})
    path = data_dir / "trace.jsonl"
    path.write_text(path.read_text().replace('"one"', '"0ne"'))            # tamper with the first entry
    r = a.readiness(required_agents=["NO_SUCH_AGENT"], min_free_disk_mb=10**9, sample={**SAMPLE, "mem_available_mb": 10})
    assert r["mode"] == "degraded"
    assert r["failed"] == ["disk_space", "memory", "agents_present", "trace_intact"]
    assert "NO_SUCH_AGENT" in next(c["detail"] for c in r["checks"] if c["check"] == "agents_present")


def test_autonomy_bad_input():
    a = make("LOCAL_AUTONOMY_CORE", "LocalAutonomyCore")
    assert a.readiness(required_agents="ALL")["status"] == "invalid_input"
    assert a.readiness(min_free_disk_mb=-1)["mode"] == "degraded"
    assert a.readiness(sample={"disk_free_mb": "plenty"})["status"] == "invalid_input"


# ── OFFLINE_SANDBOX ──────────────────────────────────────────────────────────
def test_sandbox_runs_allow_listed_command_in_clean_temp_dir(monkeypatch):
    monkeypatch.setenv("VELARIS_TEST_SECRET", "hunter2")
    s = make("OFFLINE_SANDBOX", "OfflineSandbox")
    r = s.run(["cat", "a.txt"], files={"a.txt": "alpha\nbeta\n"})
    assert (r["status"], r["exit_code"], r["stdout"]) == ("ok", 0, "alpha\nbeta\n")
    assert s.run(["wc", "-l"], stdin="1\n2\n3\n")["stdout"].strip() == "3"
    assert s.run(["false"])["exit_code"] != 0
    assert s.run(["echo", "$VELARIS_TEST_SECRET", ";", "id"])["stdout"] == "$VELARIS_TEST_SECRET ; id\n"   # no shell
    assert s.run(["cat", "missing.txt"])["exit_code"] != 0                  # the directory holds only what was passed in


def test_sandbox_timeout_and_output_cap(monkeypatch):
    mod = import_module("velaris.agents.OFFLINE_SANDBOX.main")
    s = mod.OfflineSandbox()
    hung = s.run(["tail", "-f", "log.txt"], files={"log.txt": "x\n"}, timeout_s=0.3)
    assert hung["status"] == "timeout" and hung["exit_code"] != 0 and hung["seconds"] < 5
    monkeypatch.setattr(mod, "_MAX_OUTPUT", 10)
    capped = s.run(["cat", "big.txt"], files={"big.txt": "0123456789abcdef"})
    assert capped["stdout"] == "0123456789" and capped["stdout_truncated"] is True


@pytest.mark.parametrize("argv", [
    ["rm", "-rf", "x"], ["sh", "-c", "echo hi"], ["python3", "-c", "1"], ["/bin/echo", "hi"],
    ["cat", "/etc/passwd"], ["cat", "../secret"], ["cat", "~root"], ["cat", "a\x00b"], [], "echo hi",
    ["echo", 5], None,
    # flags outside each command's explicit list: option-driven file reads and the like
    ["wc", "--files0-from=list.txt"], ["wc", "--files0-from", "list.txt"], ["tail", "--follow=name", "x"],
    ["cat", "-"], ["cat", "--", "-x"], ["head", "-n", "-5", "f"], ["head", "-n"], ["head", "-n5", "f"],
    ["echo", "-e", "x"], ["true", "--help"], ["wc", "-lw"], ["uname", "--all"], ["cat", "-v", "f"],
])
def test_sandbox_refuses_everything_else(argv):
    s = make("OFFLINE_SANDBOX", "OfflineSandbox")
    r = s.run(argv)
    assert r["status"] == "refused" and r["ran"] is False
    assert s.safe(argv)["safe"] is False and s.safe({"argv": argv})["safe"] is False


def test_sandbox_refuses_bad_files_and_limits():
    s = make("OFFLINE_SANDBOX", "OfflineSandbox")
    assert s.safe(["echo", "ok"]) == {"safe": True, "status": "ok", "reason": "on the allow-list"}
    for allowed in (["wc", "-l", "-w"], ["head", "-c", "10", "f"], ["tail", "-n", "+2", "f"], ["uname", "-s"]):
        assert s.safe(allowed)["safe"] is True, allowed
    assert s.run(["cat", "x"], files={"../x": "1"})["status"] == "refused"
    assert s.run(["cat", "x"], files={"x": b"bytes"})["status"] == "refused"
    assert s.run(["echo"], timeout_s=3600)["status"] == "refused"
    assert s.run(["echo"], stdin=b"raw")["status"] == "refused"
    assert "sh" not in s.allowed() and "rm" not in s.allowed()


# ── OFFLINE_EXECUTION_ENGINE ─────────────────────────────────────────────────
def test_engine_runs_once_per_task_id(data_dir):
    e = make("OFFLINE_EXECUTION_ENGINE", "OfflineExecutionEngine")
    first = e.execute({"id": "job-1", "argv": ["echo", "hello"]})
    assert (first["executed"], first["replayed"], first["stdout"]) == (True, False, "hello\n")
    again = make("OFFLINE_EXECUTION_ENGINE", "OfflineExecutionEngine").execute({"id": "job-1", "argv": ["echo", "changed"]})
    assert (again["executed"], again["replayed"], again["stdout"]) == (False, True, "hello\n")
    assert e.get("job-1")["exit_code"] == 0 and [j["id"] for j in e.history()] == ["job-1"]
    assert len([x for x in trace.entries() if x["actor"] == "OFFLINE_SANDBOX" and x["action"] == "run"]) == 1


def test_engine_records_refusals_and_passes_files():
    e = make("OFFLINE_EXECUTION_ENGINE", "OfflineExecutionEngine")
    refused = e.execute({"id": "bad", "argv": ["curl", "example.com"]})
    assert refused["status"] == "refused" and refused["executed"] is False
    assert e.get("bad")["status"] == "refused"
    out = e.execute({"argv": ["head", "-n", "1", "f.txt"], "files": {"f.txt": "top\nrest\n"}})
    assert out["stdout"] == "top\n" and len(e.history()) == 2


def test_engine_bad_input():
    e = make("OFFLINE_EXECUTION_ENGINE", "OfflineExecutionEngine")
    assert e.execute("echo hi")["status"] == "invalid_input"
    assert e.execute({"cmd": "echo"})["status"] == "invalid_input"
    assert e.execute({"id": "a/b", "argv": ["echo"]})["status"] == "invalid_input"
    assert e.execute({"argv": None})["status"] == "refused"
    assert e.get("nope")["status"] == "unknown_task" and e.history(0) == []


# ── MULTI_TENANCY_GRID ───────────────────────────────────────────────────────
def test_tenancy_quota_is_enforced_per_tenant():
    g = make("MULTI_TENANCY_GRID", "MultiTenancyGridAgent")
    for tenant in ("acme", "globex"):
        g.create_tenant(tenant)
        g.set_quota(tenant, "api_calls", 3)
    assert g.consume("acme", "api_calls", 3)["remaining"] == 0
    over = g.consume("acme", "api_calls")
    assert over["status"] == "quota_exceeded" and over["allowed"] is False
    assert g.consume("globex", "api_calls")["used"] == 1                    # acme's usage does not count against globex
    assert make("MULTI_TENANCY_GRID", "MultiTenancyGridAgent").usage("acme")["used"] == {"api_calls": 3}
    assert g.release("acme", "api_calls", 2)["used"] == 1 and g.consume("acme", "api_calls")["allowed"] is True


def test_tenancy_suspension_and_run_dispatch():
    g = make("MULTI_TENANCY_GRID", "MultiTenancyGridAgent")
    assert g.run({"op": "create_tenant", "tenant": "acme"})["status"] == "ok"
    assert g.run({"op": "set_quota", "tenant": "acme", "resource": "seats", "limit": 2})["limit"] == 2
    assert g.run({"op": "consume", "tenant": "acme", "resource": "seats"})["allowed"] is True
    g.run({"op": "suspend", "tenant": "acme"})
    assert g.consume("acme", "seats")["status"] == "suspended"
    g.resume("acme")
    assert g.run({"op": "usage", "tenant": "acme"})["used"] == {"seats": 1}


def test_tenancy_denies_what_was_not_declared():
    g = make("MULTI_TENANCY_GRID", "MultiTenancyGridAgent")
    assert g.consume("ghost", "x")["status"] == "unknown_tenant"
    g.create_tenant("acme")
    assert g.create_tenant("acme")["status"] == "exists"
    assert g.consume("acme", "undeclared")["status"] == "no_quota"
    assert g.consume("acme", "x", amount=-1)["allowed"] is False
    assert g.set_quota("acme", "x", "lots")["status"] == "invalid_input"
    assert g.release("acme", "x", 1)["status"] == "denied"
    assert g.run({"op": "drop_all"})["status"] == "invalid_input" and g.run("consume")["status"] == "invalid_input"
    assert g.run({"op": "consume", "tenant": None, "resource": None})["status"] == "unknown_tenant"


# ── ITSM_ENGINE ──────────────────────────────────────────────────────────────
def ticket(tid="INC-1", impact="critical", urgency="high", flags=None):
    mod = import_module("velaris.agents.ITSM_ENGINE.main")
    return mod.Ticket(tid, "database", "low", impact, urgency, "db-prod-1", flags or {})


def test_itsm_priority_is_computed_from_the_stated_formula():
    e = make("ITSM_ENGINE", "ITSMEngine")
    top = e.assess(ticket(flags={"recent_outage": True, "known_error": False}))
    assert (top["score"], top["computed_priority"], top["reported_priority"]) == (1050, "P1", "low")   # 500+300+250
    assert (top["respond_within_min"], top["resolve_within_min"]) == (15, 240)
    assert e.assess(ticket(impact="minor", urgency="low"))["computed_priority"] == "P4"                # 100
    assert e.assess(ticket(impact="major", urgency="high"))["computed_priority"] == "P2"               # 600: boundary
    same = [e.assess(ticket(tid=t, impact="moderate", urgency="medium"))["score"] for t in ("A", "B")]
    assert same == [300, 300]                                                # the id no longer changes the score


def test_itsm_lifecycle_sla_clocks_and_audit_trail():
    e = make("ITSM_ENGINE", "ITSMEngine")
    assert run_as("asha", lambda: e.open_ticket(ticket(), by="asha", now=0))["ticket"]["state"] == "new"       # P2: respond 60m, resolve 8h
    assert e.sla_status("INC-1", now=3000)["response"] == {"state": "running", "seconds_left": 600.0}
    assert e.sla_status("INC-1", now=3700)["response"]["state"] == "breached"
    run_as("ravi", lambda: e.transition("INC-1", "assigned", by="ravi", now=1800))
    run_as("ravi", lambda: e.transition("INC-1", "in_progress", by="ravi", now=2000))
    run_as("ravi", lambda: e.transition("INC-1", "on_hold", by="ravi", note="waiting for vendor", now=10000))
    assert e.sla_status("INC-1", now=99999)["resolution"] == {"state": "paused", "seconds_left": 18800.0}
    run_as("ravi", lambda: e.transition("INC-1", "in_progress", by="ravi", now=20000))              # 10,000s on hold extends the due time
    assert e.get_ticket("INC-1")["ticket"]["resolve_due"] == 28800 + 10000
    run_as("ravi", lambda: e.transition("INC-1", "resolved", by="ravi", now=38000))
    e2 = make("ITSM_ENGINE", "ITSMEngine")
    status = e2.sla_status("INC-1", now=50000)
    assert status["response"]["state"] == "met" and status["resolution"]["state"] == "met"
    history = e2.get_ticket("INC-1")["ticket"]["history"]
    assert [(h["by"], h["to"]) for h in history] == [("asha", "new"), ("ravi", "assigned"), ("ravi", "in_progress"),
                                                     ("ravi", "on_hold"), ("ravi", "in_progress"), ("ravi", "resolved")]
    traced = [x["action"] for x in trace.entries() if x["actor"] == "ITSM_ENGINE"]
    assert traced == ["ticket.open"] + ["ticket.transition"] * 5 and trace.verify()["ok"]


def test_itsm_late_resolution_breaches_and_list_orders_by_urgency():
    e = make("ITSM_ENGINE", "ITSMEngine")
    run_as("a", lambda: e.open_ticket(ticket("LOW", impact="minor", urgency="low"), by="a", now=0))
    run_as("a", lambda: e.open_ticket(ticket("HIGH", flags={"recent_outage": True}), by="a", now=0))
    assert [t["ticket_id"] for t in e.list_tickets()] == ["HIGH", "LOW"]
    run_as("b", lambda: e.transition("HIGH", "assigned", by="b", now=60))
    run_as("b", lambda: e.transition("HIGH", "in_progress", by="b", now=61))
    run_as("b", lambda: e.transition("HIGH", "resolved", by="b", now=240 * 60 + 1))              # one second past the 4h P1 target
    assert e.sla_status("HIGH")["resolution"]["state"] == "breached"
    assert [t["ticket_id"] for t in e.list_tickets(state="new")] == ["LOW"]


def test_itsm_denies_illegal_moves_and_bad_input():
    e = make("ITSM_ENGINE", "ITSMEngine")
    run_as("asha", lambda: e.open_ticket(ticket(), by="asha", now=0))
    skipped = run_as("ravi", lambda: e.transition("INC-1", "resolved", by="ravi"))
    assert skipped["status"] == "denied" and skipped["allowed"] == ["assigned", "cancelled"]
    assert e.get_ticket("INC-1")["ticket"]["state"] == "new"
    run_as("asha", lambda: e.transition("INC-1", "cancelled", by="asha"))
    assert run_as("ravi", lambda: e.transition("INC-1", "assigned", by="ravi"))["status"] == "denied"          # cancelled is final
    assert run_as("asha", lambda: e.open_ticket(ticket(), by="asha"))["status"] == "duplicate"
    assert run_as("", lambda: e.transition("INC-1", "assigned", by=""))["status"] == "invalid_input"       # every change needs a name
    assert run_as("x", lambda: e.transition("NOPE", "assigned", by="x"))["status"] == "unknown_ticket"
    bad = e.assess(ticket(impact="huge", flags={"vip": True}))
    assert bad["status"] == "failed" and "unsupported impact" in bad["errors"]
    assert e.assess({"ticket_id": "x"})["status"] == "failed"
    assert run_as("a", lambda: e.open_ticket(ticket("T2", flags={"known_error": "yes"}), by="a"))["status"] == "failed"


def test_itsm_records_the_caller_and_refuses_anonymous_or_borrowed_names():
    e = make("ITSM_ENGINE", "ITSMEngine")
    assert e.open_ticket(ticket(), now=0)["status"] == "unauthenticated"
    with acting_as(Caller("asha", "kf")):
        assert e.open_ticket(ticket(), by="ravi", now=0)["status"] == "denied"      # cannot open in ravi's name
        assert e.open_ticket(ticket(), now=0)["status"] == "ok"                     # no name needed: the caller is asha
    assert e.transition("INC-1", "assigned", now=1)["status"] == "unauthenticated"
    with acting_as(Caller("ravi", "kf")):
        assert e.transition("INC-1", "assigned", by="asha", now=1)["status"] == "denied"
        assert e.transition("INC-1", "assigned", now=1)["status"] == "ok"
    assert [(h["by"], h["to"]) for h in e.get_ticket("INC-1")["ticket"]["history"]] == [("asha", "new"),
                                                                                        ("ravi", "assigned")]


# ── IT_INFRA_ENGINE ──────────────────────────────────────────────────────────
def config(**changes):
    mod = import_module("velaris.agents.IT_INFRA_ENGINE.main")
    fields = {"name": "web", "region": "ap-south-1", "vm_count": 3, "vm_type": "medium",
              "network_cidr": "10.0.0.0/29", "tags": {"env": "prod"}}
    return mod.InfraConfig(**{**fields, **changes})


def test_infra_plan_is_deterministic_and_honest_about_not_creating_anything():
    e = make("IT_INFRA_ENGINE", "ITInfraEngine")
    plan = e.provision(config())
    assert plan["status"] == "planned" and plan["created"] is False
    assert plan["vms"] == [{"name": "web-001", "ip": "10.0.0.1", "type": "medium"},
                           {"name": "web-002", "ip": "10.0.0.2", "type": "medium"},
                           {"name": "web-003", "ip": "10.0.0.3", "type": "medium"}]
    assert plan["totals"] == {"vms": 3, "vcpu": 6, "mem_gb": 24}
    assert make("IT_INFRA_ENGINE", "ITInfraEngine").provision(config())["infra_id"] == plan["infra_id"]
    assert e.provision(config(vm_count=4))["infra_id"] != plan["infra_id"]


def test_infra_health_compares_reports_with_the_plan():
    e = make("IT_INFRA_ENGINE", "ITInfraEngine")
    assert e.health_check() == {"agent": "IT_INFRA_ENGINE", "status": "ok", "version": "1.0.0"}
    infra_id = e.provision(config())["infra_id"]
    up = [{"name": f"web-00{i}", "status": "running"} for i in (1, 2, 3)]
    assert e.health_check(infra_id, up)["health"] == "healthy"
    mixed = e.health_check(infra_id, [up[0], {"name": "web-002", "status": "stopped"}, {"name": "stray", "status": "running"}])
    assert (mixed["health"], mixed["running"], mixed["missing"]) == ("degraded", 1, ["web-003"])
    assert mixed["unhealthy"] == [{"name": "web-002", "status": "stopped"}] and mixed["unplanned"] == ["stray"]
    assert e.health_check(infra_id, [])["health"] == "down"


def test_infra_rejects_bad_requests():
    e = make("IT_INFRA_ENGINE", "ITInfraEngine")
    small = e.provision(config(vm_count=7))                                 # a /29 has 6 usable addresses
    assert small["status"] == "failed" and "6 usable addresses for 7 VMs" in small["errors"][0]
    errors = e.validate_config(config(region="mars-1", vm_type="huge", network_cidr="10.0.0.1/24", tags={"Env": "x"}))
    assert len(errors) == 4                                                 # host bits set in the CIDR is an error too
    assert e.provision(config(vm_count=True))["status"] == "failed"
    assert e.provision({"name": "web"})["status"] == "failed"
    assert e.health_check("infra-unknown", [])["status"] == "unknown_infra"
    assert e.health_check("x", "all fine")["status"] == "invalid_input"
