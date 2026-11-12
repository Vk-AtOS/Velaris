"""Behaviour of the it_infrastructure agents that used to be stubs (part 1: measuring, scheduling, routing).

Every test runs against a temporary VELARIS_DATA; decisions are driven by declared
samples and timestamps, never by this machine's load or the wall clock.
"""
import os
import stat
import threading
import time
from importlib import import_module

import pytest


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    return tmp_path


def make(name, cls=None):
    return getattr(import_module(f"velaris.agents.{name}.main"), cls or f"{name}Agent")()


SAMPLE = {"cpu_percent": 25.0, "cpu_count": 8, "mem_percent": 50.0, "mem_available_mb": 4096.0,
          "disk_percent": 40.0, "disk_free_mb": 50000.0}


# ── SYSTEM_TELEMETRY ─────────────────────────────────────────────────────────
def test_telemetry_measures_the_real_machine_and_persists(data_dir):
    t = make("SYSTEM_TELEMETRY")
    r = t.collect()
    assert r["status"] == "ok" and 0 <= r["sample"]["cpu_percent"] <= 100 and r["sample"]["cpu_count"] >= 1
    assert r["sample"]["mem_total_mb"] > 0
    assert len(make("SYSTEM_TELEMETRY").history(5)) == 1                      # a new instance reads the same file
    path = data_dir / "agents" / "SYSTEM_TELEMETRY" / "samples.json"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_telemetry_summary_and_alerts_from_declared_samples():
    t = make("SYSTEM_TELEMETRY")
    assert t.summary()["status"] == "no_data" and t.alerts()["status"] == "no_data"
    for cpu in (10.0, 20.0, 30.0, 96.0):
        t.collect({**SAMPLE, "cpu_percent": cpu})
    m = t.summary(window=4)["metrics"]["cpu_percent"]
    assert (m["min"], m["max"], m["mean"], m["p95"]) == (10.0, 96.0, 39.0, 96.0)
    assert t.summary(window=2)["metrics"]["cpu_percent"]["min"] == 30.0
    alerts = t.alerts()["alerts"]
    assert [(a["metric"], a["severity"]) for a in alerts] == [("cpu_percent", "critical")]
    assert t.alerts({"mem_percent": 50.0})["alerts"][1]["metric"] == "mem_percent"


def test_telemetry_rejects_bad_input():
    t = make("SYSTEM_TELEMETRY")
    assert t.collect({"cpu_percent": 250})["status"] == "invalid_input"
    assert t.collect("fast")["status"] == "invalid_input"
    assert t.summary(window=0)["status"] == "invalid_input"
    assert t.alerts({"temperature": 5})["status"] == "invalid_input"
    assert t.history(-1) == []


# ── RESOURCE_OPTIMIZER ───────────────────────────────────────────────────────
def test_resource_optimizer_profile_and_formula():
    r = make("RESOURCE_OPTIMIZER", "ResourceOptimizer")
    p = r.profile()
    assert 0 <= p["cpu"] <= 100 and 0 <= p["ram"] <= 100
    out = r.recommend(SAMPLE, per_worker_mb=256)          # by_cpu = floor(8*0.75)=6, by_memory = floor(3584/256)=14
    assert (out["workers"], out["by_cpu"], out["by_memory"], out["limited_by"]) == (6, 6, 14, "cpu")
    assert out["findings"] == []


def test_resource_optimizer_memory_bound_and_findings():
    r = make("RESOURCE_OPTIMIZER", "ResourceOptimizer")
    out = r.recommend({**SAMPLE, "mem_available_mb": 600.0, "disk_percent": 95.0}, per_worker_mb=256)
    assert out["workers"] == 1 and out["limited_by"] == "memory"       # floor(88/256) = 0, never below one worker
    assert {f["issue"] for f in out["findings"]} == {"memory", "disk"}
    assert r.recommend({"cpu_percent": 10})["status"] == "invalid_input"
    assert r.recommend(SAMPLE, per_worker_mb=0)["status"] == "invalid_input"


# ── COMPUTE_SCALER ───────────────────────────────────────────────────────────
def test_scaler_target_tracking_up_and_clamp():
    s = make("COMPUTE_SCALER")
    assert s.set_policy("web", min_replicas=2, max_replicas=10, target_utilization=50, cooldown_s=300)["status"] == "ok"
    up = s.decide("web", current_replicas=4, utilization=90, now=1000)
    assert (up["action"], up["desired"]) == ("scale_up", 8)              # ceil(4*90/50) = 8
    assert s.decide("web", 8, 200, now=1001)["desired"] == 10            # ceil(32) clamped to max
    assert s.decide("web", 4, 52, now=1002)["action"] == "hold"          # within 10% of target


def test_scaler_cooldown_delays_scale_down_only():
    s = make("COMPUTE_SCALER")
    s.set_policy("web", 1, 10, 50, cooldown_s=300)
    s.decide("web", 4, 90, now=1000)                                     # scale up: starts the cooldown
    held = s.decide("web", 8, 10, now=1100)
    assert held["action"] == "hold" and "cooldown" in held["reason"]
    assert s.decide("web", 8, 90, now=1100)["action"] == "scale_up"      # scale-up is never delayed
    down = make("COMPUTE_SCALER").decide("web", 8, 10, now=1500)         # restart keeps the policy and the clock
    assert (down["action"], down["desired"]) == ("scale_down", 2)


def test_scaler_refuses_unknown_group_and_bad_numbers():
    s = make("COMPUTE_SCALER")
    assert s.decide("ghost", 2, 50)["status"] == "unknown_group"
    assert s.set_policy("web", min_replicas=5, max_replicas=2)["status"] == "invalid_input"
    s.set_policy("web")
    assert s.decide("web", -1, 50)["status"] == "invalid_input"
    assert s.decide("web", 2, float("nan"))["status"] == "invalid_input"
    assert s.decide(None, 2, 50)["status"] == "unknown_group"


# ── COMPUTE_KERNEL ───────────────────────────────────────────────────────────
def test_kernel_admits_by_priority_within_capacity():
    k = make("COMPUTE_KERNEL")
    k.submit("low", cpu=2, mem_mb=100, priority=1)
    k.submit("high", cpu=3, mem_mb=100, priority=9)
    k.submit("big", cpu=8, mem_mb=100, priority=5)
    r = k.schedule({"cpu": 4, "mem_mb": 1000})
    assert r["admitted"] == ["high"] and r["waiting"] == ["big", "low"]   # big never fits beside high; low needs 2, 1 free
    assert k.complete("high")["job"]["state"] == "done"
    assert make("COMPUTE_KERNEL").schedule({"cpu": 4, "mem_mb": 1000})["admitted"] == ["low"]


def test_kernel_memory_limit_and_fifo_tie_break():
    k = make("COMPUTE_KERNEL")
    for job in ("a", "b", "c"):
        k.submit(job, cpu=1, mem_mb=400)
    r = k.schedule({"cpu": 8, "mem_mb": 900})
    assert r["admitted"] == ["a", "b"] and r["waiting"] == ["c"] and r["free"]["mem_mb"] == 100
    assert k.status()["counts"] == {"running": 2, "queued": 1}


def test_kernel_bad_input():
    k = make("COMPUTE_KERNEL")
    assert k.submit("", 1, 1)["status"] == "invalid_input"
    assert k.submit("j", cpu=0)["status"] == "invalid_input"
    k.submit("j")
    assert k.submit("j")["status"] == "duplicate"
    assert k.complete("j")["status"] == "not_running"
    assert k.complete("nope")["status"] == "unknown_job"
    assert k.schedule({"cpu": "many"})["status"] == "invalid_input"


# ── PARALLEL_CORE ────────────────────────────────────────────────────────────
def test_parallel_map_keeps_order_and_really_runs_concurrently():
    p = make("PARALLEL_CORE")
    gate = threading.Barrier(4, timeout=5)        # only passes if four calls are inside fn at the same time

    def work(x):
        gate.wait()
        return x * x
    r = p.map(work, [1, 2, 3, 4], workers=4)
    assert r["status"] == "ok" and [x["value"] for x in r["results"]] == [1, 4, 9, 16]


def test_parallel_map_isolates_failures_and_times_out():
    p = make("PARALLEL_CORE")
    r = p.map(lambda x: 10 // x, [1, 0, 5], workers=2)
    assert r["status"] == "partial" and r["failed"] == 1
    assert r["results"][0] == {"ok": True, "value": 10} and "ZeroDivisionError" in r["results"][1]["error"]
    slow = p.map(lambda x: time.sleep(x) or x, [0, 0.5], workers=2, timeout_s=0.05)
    assert slow["results"][0]["ok"] and slow["results"][1] == {"ok": False, "error": "timed out"}
    assert p.map(lambda x: x, [])["results"] == []


def test_parallel_map_bad_input():
    p = make("PARALLEL_CORE")
    assert p.map("not callable", [1])["status"] == "invalid_input"
    assert p.map(len, "abc")["status"] == "invalid_input"
    assert p.map(len, [1], workers=0)["status"] == "invalid_input"
    assert p.map(len, [1], timeout_s=-1)["status"] == "invalid_input"


# ── RESOURCE_ORCHESTRATOR ────────────────────────────────────────────────────
def test_orchestrator_never_overcommits():
    o = make("RESOURCE_ORCHESTRATOR")
    o.define_pool("gpu", 4)
    assert o.allocate("gpu", "team-a", 3)["free"] == 1
    denied = o.allocate("gpu", "team-b", 2)
    assert denied["status"] == "denied" and denied["free"] == 1
    assert o.usage("gpu")["grants"] == {"team-a": 3}                      # the refusal changed nothing
    assert o.allocate("gpu", "team-b", 1)["status"] == "ok"
    assert make("RESOURCE_ORCHESTRATOR").usage("gpu")["free"] == 0        # grants survive a restart


def test_orchestrator_release_and_capacity_change():
    o = make("RESOURCE_ORCHESTRATOR")
    o.define_pool("seats", 10)
    o.allocate("seats", "a", 6)
    assert o.define_pool("seats", 5)["status"] == "denied"                # below what is granted
    assert o.release("seats", "a", 2)["still_held"] == 4
    assert o.release("seats", "a", 9)["status"] == "denied"
    assert o.release("seats", "a")["released"] == 4 and o.usage("seats")["grants"] == {}


def test_orchestrator_bad_input():
    o = make("RESOURCE_ORCHESTRATOR")
    assert o.allocate("nope", "a", 1)["status"] == "unknown_pool"
    assert o.define_pool("p", -1)["status"] == "invalid_input"
    o.define_pool("p", 1)
    assert o.allocate("p", "a", 0)["status"] == "invalid_input"
    assert o.allocate("p", "", 1)["status"] == "invalid_input"
    assert o.release("p", "ghost")["status"] == "unknown_grant"


# ── LOAD_DISTRIBUTOR ─────────────────────────────────────────────────────────
def test_distributor_weighted_round_robin_is_proportional_and_smooth():
    d = make("LOAD_DISTRIBUTOR")
    d.register("a", 5)
    d.register("b", 1)
    d.register("c", 1)
    picks = [d.pick()["backend"] for _ in range(7)]
    assert picks == ["a", "a", "b", "a", "c", "a", "a"]                   # nginx's smooth sequence for 5/1/1
    assert d.backends()["backends"]["a"]["picked"] == 5


def test_distributor_health_and_sticky_keys():
    d = make("LOAD_DISTRIBUTOR")
    for b in ("a", "b", "c"):
        d.register(b)
    owner = d.pick(key="user-42")["backend"]
    assert all(d.pick(key="user-42")["backend"] == owner for _ in range(5))
    d.set_health(owner, False)
    moved = d.pick(key="user-42")["backend"]
    assert moved != owner and owner not in {d.pick()["backend"] for _ in range(6)}
    others = [k for k in (f"k{i}" for i in range(40)) if d.pick(key=k)["backend"] != owner]
    d.set_health(owner, True)
    assert d.pick(key="user-42")["backend"] == owner                      # returns home on recovery
    assert len(others) == 40                                              # nobody was routed to the unhealthy one


def test_distributor_no_backend_and_bad_input():
    d = make("LOAD_DISTRIBUTOR")
    assert d.pick()["status"] == "unavailable"
    assert d.register("a", weight=0)["status"] == "invalid_input"
    assert d.register("a/b")["status"] == "invalid_input"
    assert d.set_health("ghost", True)["status"] == "unknown_backend"
    d.register("a")
    assert d.set_health("a", "yes")["status"] == "invalid_input"
    assert d.pick(key=5)["status"] == "invalid_input"
    d.set_health("a", False)
    assert d.pick()["status"] == "unavailable"


# ── FAILOVER_ROUTER ──────────────────────────────────────────────────────────
def test_failover_opens_after_threshold_and_recovers_through_probe():
    f = make("FAILOVER_ROUTER")
    f.configure("db", ["primary", "standby"], failure_threshold=2, recovery_s=30)
    assert f.route("db", now=0)["target"] == "primary"
    f.report("db", "primary", False, now=1)
    assert f.route("db", now=2)["target"] == "primary"                    # one failure is below the threshold
    assert f.report("db", "primary", False, now=3)["circuit"]["state"] == "open"
    r = f.route("db", now=10)
    assert (r["target"], r["failed_over"]) == ("standby", True)
    probe = make("FAILOVER_ROUTER").route("db", now=40)                   # 37s later, after a restart
    assert (probe["target"], probe["probe"]) == ("primary", True)
    f.report("db", "primary", True, now=41)
    assert f.route("db", now=42) == {"status": "ok", "service": "db", "target": "primary", "probe": False,
                                     "failed_over": False}


def test_failover_failed_probe_reopens_and_all_down_is_unavailable():
    f = make("FAILOVER_ROUTER")
    f.configure("api", ["a", "b"], failure_threshold=1, recovery_s=10)
    f.report("api", "a", False, now=0)
    f.report("api", "b", False, now=0)
    assert f.route("api", now=5)["status"] == "unavailable"
    assert f.route("api", now=11)["probe"] is True
    f.report("api", "a", False, now=12)                                   # the probe failed: full wait again
    assert f.route("api", now=15)["target"] == "b"                        # b's own wait has passed
    assert f.status("api")["circuits"]["a"]["state"] == "open"


def test_failover_bad_input():
    f = make("FAILOVER_ROUTER")
    assert f.route("ghost")["status"] == "unknown_service"
    assert f.configure("s", [])["status"] == "invalid_input"
    assert f.configure("s", ["a", "a"])["status"] == "invalid_input"
    assert f.configure("s", ["a"], failure_threshold=0)["status"] == "invalid_input"
    f.configure("s", ["a"])
    assert f.report("s", "zzz", True)["status"] == "unknown_target"
    assert f.report("s", "a", "yes")["status"] == "invalid_input"
    assert f.route("s", now="soon")["status"] == "invalid_input"


# ── LATENCY_CONTROLLER ───────────────────────────────────────────────────────
def test_latency_percentiles_and_aimd_backoff():
    c = make("LATENCY_CONTROLLER")
    c.set_slo("search", p95_ms=200, start_limit=10, max_limit=12)
    for ms in range(1, 101):
        c.record("search", ms * 3)                                        # 3..300 ms
    s = c.stats("search")
    assert (s["p50"], s["p95"], s["p99"]) == (150, 285, 297)
    step = c.control("search")
    assert step["breached"] and (step["previous_limit"], step["limit"], step["action"]) == (10, 7, "decrease")
    assert c.control("search")["status"] == "insufficient_data"           # samples were reset with the limit


def test_latency_additive_increase_stops_at_max():
    c = make("LATENCY_CONTROLLER")
    c.set_slo("q", p95_ms=100, start_limit=11, max_limit=12)
    for expected, action in ((12, "increase"), (12, "hold")):
        for _ in range(20):
            c.record("q", 10)
        step = make("LATENCY_CONTROLLER").control("q")
        assert (step["limit"], step["action"]) == (expected, action)


def test_latency_bad_input():
    c = make("LATENCY_CONTROLLER")
    assert c.record("q", -1)["status"] == "invalid_input"
    assert c.stats("q")["status"] == "no_data"
    c.record("q", 5)
    assert c.control("q")["status"] == "no_slo"
    assert c.set_slo("q", 0)["status"] == "invalid_input"
    assert c.set_slo("q", 10, start_limit=50, max_limit=5)["status"] == "invalid_input"


# ── THROUGHPUT_MANAGER ───────────────────────────────────────────────────────
def test_token_bucket_burst_refill_and_retry_after():
    t = make("THROUGHPUT_MANAGER")
    t.set_limit("api", rate_per_s=2, burst=3)
    assert [t.acquire("api", now=100)["allowed"] for _ in range(4)] == [True, True, True, False]
    refused = t.acquire("api", now=100)
    assert refused["status"] == "rate_limited" and refused["retry_after_s"] == 0.5
    assert t.acquire("api", now=100.5)["allowed"] is True                 # 0.5s * 2/s = one token
    assert t.acquire("api", now=1000)["remaining"] == 2                   # refill is capped at the burst
    assert make("THROUGHPUT_MANAGER").stats("api")["refused"] == 2


def test_token_bucket_survives_restart_and_backwards_clock():
    t = make("THROUGHPUT_MANAGER")
    t.set_limit("k", 1, 2)
    t.acquire("k", 2, now=50)
    assert make("THROUGHPUT_MANAGER").acquire("k", now=50)["allowed"] is False   # no fresh burst after restart
    assert t.acquire("k", now=10)["allowed"] is False                    # the clock went back: nothing refills


def test_token_bucket_bad_input():
    t = make("THROUGHPUT_MANAGER")
    assert t.acquire("unknown") == {"status": "no_limit", "allowed": False,
                                    "reason": "set_limit() has not been called for this key"}
    assert t.set_limit("k", 0, 5)["status"] == "invalid_input"
    t.set_limit("k", 1, 5)
    assert t.acquire("k", tokens=0)["status"] == "invalid_input"
    assert t.acquire("k", tokens=6)["status"] == "denied"
    assert t.acquire("k", now="later")["allowed"] is False


def test_state_files_and_directories_are_owner_only(data_dir):
    make("COMPUTE_SCALER").set_policy("g")
    make("THROUGHPUT_MANAGER").set_limit("k", 1, 1)
    for root, _, files in os.walk(data_dir / "agents"):
        assert stat.S_IMODE(os.stat(root).st_mode) == 0o700
        assert all(stat.S_IMODE(os.stat(os.path.join(root, f)).st_mode) == 0o600 for f in files)
