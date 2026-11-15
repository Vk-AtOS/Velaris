"""Round 3 (KAN-93): EPISODIC_MEMORY does not hold its lock across the model, LONGTERM_MEMORY checks caller and scope,
BUSINESS_DNA does not lose a concurrent set."""
import json
import multiprocessing as mp
import os
import threading

import pytest

from velaris.agents.BUSINESS_DNA.main import BusinessDnaAgent
from velaris.agents.EPISODIC_MEMORY.main import EPISODIC_MEMORYAgent
from velaris.agents.LONGTERM_MEMORY.main import LONGTERM_MEMORYAgent
from velaris.agentkit import infra_memory
from velaris.core.access import AccessDenied, Caller, acting_as

ASHA = Caller("asha", "acme")


@pytest.fixture(autouse=True)
def _data(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))


def test_record_is_not_blocked_while_consolidate_waits_for_the_model(monkeypatch):
    e = EPISODIC_MEMORYAgent()
    e.record({"summary": "met the client"})
    started, release = threading.Event(), threading.Event()

    def slow(llm, texts, scope, source):
        started.set()
        assert release.wait(20)
        return {"status": "ok", "facts": [], "counts": {}}
    monkeypatch.setattr(infra_memory, "remember", slow)
    out = {}
    t = threading.Thread(target=lambda: out.update(e.consolidate("acme")))
    t.start()
    assert started.wait(10)
    assert e.consolidate("acme")["episodes"] == 0                              # a second consolidate skips the claimed episode
    done = threading.Event()
    threading.Thread(target=lambda: (e.record({"summary": "second"}), done.set())).start()
    assert done.wait(5), "record() was blocked behind the model call"          # the lock is not held while the model runs
    release.set()
    t.join(10)
    assert out["episodes"] == 1 and [x["_consolidated"] for x in e.list_episodes()] == [True, False]


def test_a_failed_consolidation_releases_its_claim(monkeypatch):
    e = EPISODIC_MEMORYAgent()
    e.record({"summary": "x"})
    monkeypatch.setattr(infra_memory, "remember", lambda *a: (_ for _ in ()).throw(RuntimeError("model down")))
    with pytest.raises(RuntimeError):
        e.consolidate("acme")
    monkeypatch.setattr(infra_memory, "remember", lambda *a: {"status": "ok", "facts": [], "counts": {}})
    assert e.consolidate("acme")["episodes"] == 1


def test_longterm_memory_needs_a_caller_and_the_callers_own_scope():
    m = LONGTERM_MEMORYAgent()
    for call in (lambda: m.remember("fact", "acme"), lambda: m.recall("fact", "acme"), lambda: m.put("k", 1)):
        with pytest.raises(AccessDenied):
            call()
    with acting_as(ASHA):
        with pytest.raises(AccessDenied):
            m.remember("fact", "rival")
        with pytest.raises(AccessDenied):
            m.recall("fact", "acmeX")                                          # prefix without the colon is another org
        m.put("k", {"v": 1})
        assert m.get("k") == {"v": 1} and LONGTERM_MEMORYAgent().get("k") == {"v": 1}
        with pytest.raises(TypeError):
            m.put("bad", {1, 2})
    from velaris.core import vault
    assert vault.is_sealed(open(m.path, "rb").read())                          # sealed at rest


def _set(data_dir, field, n):
    os.environ["VELARIS_DATA"] = data_dir
    a = BusinessDnaAgent()
    for i in range(n):
        assert a.run({"action": "set", "profile": {field: f"v{i}"}})["status"] in ("ok", "needs_data")


def test_two_workers_setting_different_fields_lose_nothing(tmp_path):
    ctx = mp.get_context("fork")
    ps = [ctx.Process(target=_set, args=(str(tmp_path), f, 20)) for f in ("name", "sector", "location", "legal_form")]
    [p.start() for p in ps]
    [p.join(60) for p in ps]
    r = BusinessDnaAgent().run({"action": "get"})
    assert set(r["profile"]) == {"name", "sector", "location", "legal_form"} and r["profile_version"] == 80
