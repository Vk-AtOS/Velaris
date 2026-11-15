"""KAN-89: _ai_core GCK..NEURAL_MESH: HFAL, biometrics, canary registry, MCD, NAVARCH, LYRA."""
import json
import os
from importlib import import_module

import pytest

from velaris.core.access import SECURITY_ADMIN, Caller, acting_as
from velaris.intel.paths import agent_dir


def mod(name):
    return import_module(f"velaris.agents.{name}.main")


def test_hfal_tokens_are_random_expire_and_lock_out(monkeypatch):
    M = mod("HFAL")
    h = M.HFAL()
    t1, t2 = h.create_session("asha", "4321"), h.create_session("asha", "4321")
    assert t1 != t2 and len(t1) >= 20 and "asha" not in t1                 # was sha256(user + pin)[:12]: guessable offline
    raw = open(h.SESSION_FILE).read()
    assert "4321" not in raw and "sha256" not in raw and "scrypt$" in raw
    assert M.HFAL().validate(t1, "4321") is True and h.validate(t1, "0000") is False and h.validate("nope", "4321") is False
    for _ in range(5):
        h.validate(t2, "0000")
    assert h.validate(t2, "4321") is False                                  # locked even with the right PIN
    real = M._now()
    monkeypatch.setattr(M, "_now", lambda: real + M.SESSION_TTL + 1)
    assert h.validate(t1, "4321") is False                                  # expired
    assert h.destroy_session(t1) is True and h.destroy_session(t1) is False


def test_biometrics_are_hashed_gated_and_cannot_be_swapped_without_proof():
    B = mod("LOCAL_BIOMETRICS_INTERFACE").LocalBiometricsInterface
    b = B()
    asha, eve = Caller("asha", "kf"), Caller("eve", "kf")
    with acting_as(eve):
        assert b.enroll("asha", {"finger": "F1"}) is False                  # not their own enrolment
    with acting_as(asha):
        assert b.enroll("asha", {"finger": "F1", "face": "A1"}) is True and b.enroll("asha", {"face": "B"}) is False
        assert b.enroll("asha", {"bogus": "x"}) is False
    assert "F1" not in open(agent_dir("LOCAL_BIOMETRICS_INTERFACE") / "templates.json").read()
    assert B().verify("asha", {"finger": "F1"}) and not B().verify("asha", {"finger": "WRONG"})
    assert not b.verify("asha", {"voice": "x"}) and not b.verify("asha", {}) and not b.verify("ghost", {"finger": "F1"})
    with acting_as(asha):
        assert b.update("asha", {"finger": "WRONG"}, {"finger": "MINE"}) is False      # needs proof of the old one
        assert b.update("asha", {"finger": "F1"}, {"finger": "F2"}) is True
    assert b.verify("asha", {"finger": "F2"}) and not b.verify("asha", {"finger": "F1"})


def test_biometrics_lock_after_repeated_failures():
    b = mod("LOCAL_BIOMETRICS_INTERFACE").LocalBiometricsInterface()
    with acting_as(Caller("u", "kf")):
        b.enroll("u", {"finger": "F"})
    for _ in range(5):
        b.verify("u", {"finger": "bad"})
    assert b.verify("u", {"finger": "F"}) is False


def test_canary_registry_types_atomic_and_shared():
    C = mod("MODEL_REGISTRY_CANARY").ModelRegistryCanary
    c = C()
    assert c.register_model("m", "1", "abc") and not c.register_model("m", "1", "abc")
    for bad in (True, 12.5, "50", None, -1, 101):
        assert c.set_canary("m", "1", bad) is False                         # a string used to raise TypeError
    assert c.set_canary("m", "1", 25) and C().get_model("m", "1")["canary"] == 25
    assert oct(os.stat(c.REGISTRY_PATH).st_mode & 0o777) == "0o600"
    open(c.REGISTRY_PATH, "w").write("{ not json")
    assert C().registry == {} and list(os.listdir(os.path.dirname(c.REGISTRY_PATH))).count("registry.json") == 0  # set aside, kept


def test_mcd_escapes_html_and_navarch_refuses_negative_weights():
    m = mod("MCD").MasterControlDashboard()
    assert "<script>" not in m.render("<script>alert(1)</script>") and "&lt;script&gt;" in m.render("<script>alert(1)</script>")
    assert m.health_check()["status"] == "ok"
    n = mod("NAVARCH").NavarchAgent()
    method = next(x for x in dir(n) if "path" in x and not x.startswith("_"))
    g = {"A": {"B": 5, "C": 2}, "B": {}, "C": {"B": 1}}
    assert getattr(n, method)(g, "A", "B")["cost"] == 3
    with pytest.raises(ValueError):
        getattr(n, method)({"A": {"B": -4}, "B": {}}, "A", "B")
    with pytest.raises(ValueError):
        getattr(n, method)({"A": {"B": float("nan")}, "B": {}}, "A", "B")


def test_lyra_prefix_uses_a_real_newline():
    with open(mod("LYRA").__file__) as f:
        assert '"[TECH]/n"' not in f.read()          # "/n" was meant as a newline
