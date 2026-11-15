"""KAN-90: it_infrastructure agents: role checks, packager exclusions, durable writes, at-most-once journal."""
import json
import os
import tarfile
from importlib import import_module

import pytest

from velaris.core.access import INFRA_ADMIN, Caller, acting_as
from velaris.intel.paths import agent_dir

ADMIN = Caller("ops", "kf", frozenset({INFRA_ADMIN}))
MEMBER = Caller("tenant-a", "kf", frozenset())


def agent(name, cls=None):
    return getattr(import_module(f"velaris.agents.{name}.main"), cls or f"{name}Agent")()


def test_tenant_admin_calls_need_the_infra_role():
    g = agent("MULTI_TENANCY_GRID", "MultiTenancyGridAgent")
    with acting_as(ADMIN):
        assert g.create_tenant("a")["status"] == "ok" and g.set_quota("a", "api", 10)["status"] == "ok"
    for caller in (None, MEMBER):
        with acting_as(caller):
            assert g.set_quota("a", "api", 10 ** 9)["status"] in ("denied", "unauthenticated")     # cannot raise own quota
            assert g.suspend("a")["status"] in ("denied", "unauthenticated")
            assert g.create_tenant("b")["status"] in ("denied", "unauthenticated")
    with acting_as(MEMBER):
        assert g.consume("a", "api", 3)["allowed"] is True                    # using the quota is not admin work
    assert g.usage("a")["quotas"] == {"api": 10}
    with acting_as(ADMIN):
        assert g.suspend("a")["status"] == "ok" and g.resume("a")["status"] == "ok"


def test_pools_and_limits_need_the_infra_role():
    ro, tm = agent("RESOURCE_ORCHESTRATOR", "RESOURCE_ORCHESTRATORAgent"), agent("THROUGHPUT_MANAGER", "THROUGHPUT_MANAGERAgent")
    with acting_as(MEMBER):
        assert ro.define_pool("p", 100)["status"] in ("denied", "unauthenticated")
        assert tm.set_limit("k", 5, 5)["status"] in ("denied", "unauthenticated")
    with acting_as(ADMIN):
        assert ro.define_pool("p", 100)["status"] == "ok" and tm.set_limit("k", 5, 5)["status"] == "ok"
        assert ro.allocate("p", "tenant-a", 10)["status"] == "ok"
    with acting_as(Caller("tenant-b", "kf")):
        assert ro.release("p", "tenant-a")["status"] == "denied"              # not their grant
    with acting_as(MEMBER):
        assert ro.release("p", "tenant-a")["status"] == "ok"                  # the owner gives back their own


def test_itsm_moves_need_the_role_except_the_opener_cancelling_or_reopening():
    M = import_module("velaris.agents.ITSM_ENGINE.main")
    e = M.ITSMEngine()
    t = M.Ticket("T1", "network", "high", "major", "high", "router api_key: sk-abcdefghijklmnop1234 mail bob@example.com", {})
    asha = Caller("asha", "kf")
    with acting_as(asha):
        assert e.open_ticket(t, now=0)["status"] == "ok"
        assert e.transition("T1", "assigned", now=1)["status"] == "denied"    # anyone could move any ticket before
        assert e.transition("T1", "cancelled", now=2)["status"] == "ok"       # the opener may cancel their own
    with acting_as(asha):
        e.open_ticket(M.Ticket("T2", "network", "high", "major", "high", "r", {}), now=0)
    with acting_as(ADMIN):
        for to in ("assigned", "in_progress", "resolved"):
            assert e.transition("T2", to, now=3, note="call bob@example.com")["status"] == "ok"
    with acting_as(asha):
        assert e.transition("T2", "closed", now=4)["status"] == "denied"
        assert e.transition("T2", "in_progress", now=4)["status"] == "ok"     # the opener may reopen
    with acting_as(Caller("eve", "kf")):
        assert e.transition("T2", "cancelled", now=5)["status"] == "denied"   # another person may not cancel it
    stored = json.dumps(e.get_ticket("T1")["ticket"]) + json.dumps(e.get_ticket("T2")["ticket"]["history"])
    assert "sk-abcdefghijklmnop1234" not in stored and "bob@example.com" not in stored


def test_packager_leaves_out_secrets_and_stays_in_its_folder(tmp_path):
    P = agent("OFFLINE_RUNTIME_PACKAGER", "OfflineRuntimePackager")
    src = tmp_path / "src"
    for d in ("agents", "tests", ".git"):
        (src / d).mkdir(parents=True)
    for f in ("agents/a.py", ".env", "agents/prod.env", "agents/vault.key", "agents/x.db", "agents/credentials.json",
              ".git/config", "agents/ok.txt"):
        (src / f).write_text("secret")
    p = P
    out = p.package(str(src), "bundle.tar")
    names = {n for n in tarfile.open(out).getnames()}
    assert {"velaris/agents/a.py", "velaris/agents/ok.txt"} <= names
    assert not [n for n in names if n.endswith((".env", ".key", ".db")) or "credentials" in n or ".git" in n], names
    assert oct(os.stat(out).st_mode & 0o777) == "0o600"
    for bad in ("../x.tar", "a/b.tar", "x", "", "..", None):
        with pytest.raises(ValueError):
            p.package(str(src), bad)
    assert not (tmp_path / "x.tar").exists()
    assert p.inspect_package(out)["count"] >= 2
    other = tmp_path / "other.tar"
    other.write_bytes(open(out, "rb").read())
    with pytest.raises(ValueError):
        p.inspect_package(str(other))                                        # not a package of ours
    with pytest.raises(ValueError):
        p.inspect_package("/etc/passwd")


def test_telemetry_survives_a_bad_payload_redacts_and_rotates(monkeypatch):
    M = import_module("velaris.agents.TELEMETRY_SPINE.main")
    t = M.TelemetrySpine()
    assert t.record("boot", {"user": "bob@example.com", "n": 1})["payload"]["user"] != "bob@example.com"
    assert t.record("bad", {"x": object()}) is None and t.record("bad", {"x": float("nan")}) is None
    assert t.record("big", {"x": "y" * 50_000}) is None and t.record("", {"a": 1}) is None
    assert [e["type"] for e in M.TelemetrySpine().query()] == ["boot"]        # earlier events intact
    monkeypatch.setattr(M, "MAX_LOG_BYTES", 10)
    t.record("again", {"a": 1})
    t.record("after-rotation", {"a": 1})
    assert os.path.exists(t.LOG_PATH + ".1") and [e["type"] for e in t.query()] == ["after-rotation"]


def test_offline_registry_is_private_and_shared():
    R = import_module("velaris.agents.OFFLINE_REGISTRY.main").OFFLINE_REGISTRYAgent
    r = R()
    r.set("mode", "offline")
    assert R().get("mode") == "offline" and r.get("nope", 7) == 7
    assert oct(os.stat(r.path).st_mode & 0o777) == "0o600"
    with pytest.raises(ValueError):
        r.set("", 1)


def test_execution_engine_runs_a_corrected_retry_and_never_runs_an_id_twice(monkeypatch):
    M = import_module("velaris.agents.OFFLINE_EXECUTION_ENGINE.main")
    e = M.OfflineExecutionEngine()
    refused = e.execute({"id": "j1", "argv": ["rm", "-rf", "/"]})
    assert refused["executed"] is False
    fixed = e.execute({"id": "j1", "argv": ["echo", "hello"]})               # same id, corrected command
    assert fixed["executed"] is True and fixed["replayed"] is False
    assert e.execute({"id": "j1", "argv": ["echo", "hello"]})["replayed"] is True
    monkeypatch.setattr(M, "_MAX_JOURNAL", 2)
    for i in range(2, 6):
        assert e.execute({"id": f"j{i}", "argv": ["echo", str(i)]})["executed"] is True
    again = e.execute({"id": "j1", "argv": ["echo", "hello"]})               # its full record was trimmed
    assert again["executed"] is False and again["replayed"] is True          # but the id is still remembered
