"""Identity, charter, house style, versioned settings, the shared board and local embeddings."""
import os
import stat

import pytest

from velaris.agents.INTER_AGENT_COHESION.main import Cohesion
from velaris.agents.LOCAL_EMBEDDING_ENGINE.main import LocalEmbeddingEngine
from velaris.agents.PERSONALITY_MOD.main import PERSONALITY_MODAgent
from velaris.agents.SELF_IDENTITY.main import SELF_IDENTITYAgent
from velaris.agents.SOUL_CORE_EXT.main import SOUL_CORE_EXTAgent
from velaris.agents.SOUL_VELARIS.main import Soul
from velaris.core.access import GOVERNANCE_ADMINS, Caller, acting_as
from velaris.intel import llm as llm_module
from velaris.intel import trace
from velaris.intel.llm import FakeLLM, LLMError


@pytest.fixture(autouse=True)
def _data(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    return tmp_path


def admin(name="admin"):
    return acting_as(Caller(name, "kf", GOVERNANCE_ADMINS))


@pytest.mark.parametrize("change", [
    lambda: SELF_IDENTITYAgent().set_identity("organisation", "Evil Corp"),
    lambda: SOUL_CORE_EXTAgent().update({"currency": "USD"})["updated"],
    lambda: SOUL_CORE_EXTAgent().rollback(0)["status"] == "ok",
    lambda: PERSONALITY_MODAgent().update({"tone": "friendly"})["updated"],
    lambda: Soul().set_charter(mission="Anything goes")["status"] == "ok",
])
def test_charter_identity_settings_and_style_need_an_admin_caller(change):
    assert change() is False                                             # nobody calling
    with acting_as(Caller("intern", "kf")):
        assert change() is False                                         # not an admin
    assert {e["action"] for e in trace.entries() if e["actor"] == "access"} == {"change.denied"}


def test_changes_are_recorded_against_the_caller_not_the_argument():
    with admin("cfo"):
        assert SOUL_CORE_EXTAgent().update({"currency": "INR"}, by="ceo")["status"] == "denied"  # cannot act as ceo
        assert SOUL_CORE_EXTAgent().update({"currency": "INR"})["updated"] is True
        assert Soul().set_charter(mission="Run the books")["status"] == "ok"
    assert [h["by"] for h in SOUL_CORE_EXTAgent().history()] == ["cfo"]
    assert Soul().history()[-1]["by"] == "cfo"


def test_identity_persists_with_a_fixed_instance_id(_data):
    a = SELF_IDENTITYAgent()
    iid = a.get_identity()["instance_id"]
    with admin():
        assert a.set_identity("organisation", "KnackForge", by="admin") is True
    b = SELF_IDENTITYAgent()
    assert b.get_identity()["organisation"] == "KnackForge" and b.get_identity()["instance_id"] == iid
    with admin():
        assert b.set_identity("instance_id", "forged") is False and b.get_identity()["instance_id"] == iid
        assert b.set_identity("region", "") is False and b.set_identity("region", 5) is False
    assert [h["by"] for h in b.history("organisation")] == ["admin"]
    assert stat.S_IMODE(os.stat(_data / "agents" / "SELF_IDENTITY" / "identity.json").st_mode) == 0o600


def test_settings_versions_history_time_travel_and_rollback():
    s = SOUL_CORE_EXTAgent()
    assert s.snapshot()["settings"] == {} and s.snapshot()["version"] == 0
    with admin("cfo"):
        assert s.update({"fiscal_year_start": "04-01", "currency": "INR"}, by="cfo")["updated"] is True
    mid = s.history()[-1]["ts"]
    with admin("ops"):
        s.update({"currency": "USD"}, by="ops")
    assert SOUL_CORE_EXTAgent().snapshot()["settings"]["currency"] == "USD"
    assert s.at(mid)["currency"] == "INR" and s.at(0) == {}
    assert s.history("currency")[-1]["changes"]["currency"] == ["INR", "USD"]
    with admin("cfo"):
        assert s.rollback(1, by="cfo")["status"] == "ok" and s.snapshot()["settings"]["currency"] == "INR"
        assert s.snapshot()["version"] == 3                              # the rollback is itself recorded
        assert s.update({"currency": "INR"}, by="cfo")["updated"] is False  # no change, no version


def test_settings_bad_input():
    s = SOUL_CORE_EXTAgent()
    with admin("x"):
        assert s.update({}, by="x")["updated"] is False
        assert s.update("currency=INR")["status"] == "invalid_input"
        assert s.update({"a": object()})["status"] == "invalid_input"
        assert s.update({"a": 1}, by="")["status"] == "denied"          # "" is not the caller
        assert s.rollback(7, by="x")["status"] == "not_found"


def test_charter_guardrails_decide_and_fail_closed():
    soul = Soul()
    assert soul.get_intent()["mission"] == "Assist, Optimize, Simulate"
    blocked = soul.check({"action": "message.send", "day": "sun"})
    assert blocked["status"] == "no_guardrails" and blocked["allowed"] is False
    rail = {"id": "no-weekend-mail", "when": [{"field": "action", "op": "==", "value": "message.send"}],
            "require": [{"field": "day", "op": "not_in", "value": ["sat", "sun"]}]}
    with admin("ceo"):
        assert soul.set_charter("ceo", mission="Run KnackForge operations", guardrails=[rail])["status"] == "ok"
    soul = Soul()
    assert soul.get_intent()["mission"] == "Run KnackForge operations" and soul.get_intent()["charter_version"] == 1
    assert soul.check({"action": "message.send", "day": "mon"})["allowed"] is True
    sunday = soul.check({"action": "message.send", "day": "sun"})
    assert sunday["allowed"] is False and sunday["violations"][0]["id"] == "no-weekend-mail"
    assert soul.check({"action": "report.generate"})["allowed"] is True     # rule does not apply
    assert soul.check("send mail")["status"] == "invalid_input"
    with admin("ceo"):
        assert soul.set_charter("ceo", guardrails=[{"id": "x", "field": "a", "op": "??"}])["status"] == "invalid_input"
        assert soul.set_charter("ceo")["status"] == "invalid_input"


def test_style_profile_is_applied_by_code():
    p = PERSONALITY_MODAgent()
    with admin("ops"):
        assert p.update({"greeting": "Dear Partner,", "sign_off": "Regards, Accounts", "max_chars": 80,
                         "banned": ["ASAP"], "tone": "formal"}, by="ops")["updated"] is True
    r = PERSONALITY_MODAgent().apply("Please   send the   GSTIN asap so we can close the books for the quarter today")
    assert r["text"].startswith("Dear Partner,\n\nPlease send the GSTIN so we") and r["text"].endswith("Regards, Accounts")
    assert len(r["text"]) <= 80 and "asap" not in r["text"].lower() and r["tone"] == "formal"
    assert any("cut" in c for c in r["changes"]) and any("ASAP" in c for c in r["changes"])
    assert p.snapshot()["style"]["max_chars"] == 80


def test_style_bad_input():
    p = PERSONALITY_MODAgent()
    with admin():
        assert p.update({"tone": "sarcastic"})["updated"] is False
        assert p.update({"max_chars": 5})["status"] == "invalid_input"
        assert p.update({"colour": "blue"})["status"] == "invalid_input"
        p.update({"banned": ["hello"]})
    assert p.apply("")["status"] == "invalid_input"
    assert p.apply("Hello hello")["status"] == "invalid_input"           # nothing left to send


def test_board_versions_and_compare_and_set():
    c = Cohesion()
    assert c.link("deals", "acme", {"stage": "proposal"}, agent="SALES")["version"] == 1
    assert Cohesion().recall("deals", "acme") == {"stage": "proposal"}
    assert c.link("deals", "acme", {"stage": "won"}, agent="SALES", expected_version=1)["version"] == 2
    stale = c.link("deals", "acme", {"stage": "lost"}, agent="CRM", expected_version=1)
    assert stale["status"] == "conflict" and stale["current"]["value"] == {"stage": "won"}
    assert c.recall("deals", "acme") == {"stage": "won"} and c.entry("deals", "acme")["agent"] == "SALES"
    assert c.link("deals", "new", {"x": 1}, expected_version=0)["status"] == "ok"
    assert c.list_namespace("deals", "ac") == {"acme": {"stage": "won"}}


def test_board_expiry_and_bad_input(monkeypatch):
    import velaris.agents.INTER_AGENT_COHESION.main as board
    now = [1000.0]
    monkeypatch.setattr(board.time, "time", lambda: now[0])
    c = Cohesion()
    c.link("tmp", "k", 1, ttl=5)
    now[0] += 5
    assert c.recall("tmp", "k") is None and c.list_namespace("tmp") == {}
    assert c.link("tmp", "k", 2, expected_version=0)["version"] == 1    # an expired entry counts as absent
    assert c.link("", "k", 1)["status"] == "invalid_input"
    assert c.link("ns", "k", {1, 2})["status"] == "invalid_input"
    assert c.link("ns", "k", 1, ttl=0)["status"] == "invalid_input"
    assert c.recall("nowhere", "k") is None


def test_embeddings_hashed_and_nearest():
    e = LocalEmbeddingEngine()
    r = e.embed(["invoice overdue", "invoice overdue"], method="hashed")
    assert r["dim"] == 256 and r["vectors"][0] == r["vectors"][1] and r["method"] == "hashed"
    near = e.nearest("overdue invoice reminder", ["team lunch on friday", "reminder: invoice overdue", "server down"])
    assert near["matches"][0]["index"] == 1 and near["matches"][0]["score"] > near["matches"][1]["score"]


def test_embeddings_model_path_and_fallback(monkeypatch):
    fake = FakeLLM({})
    monkeypatch.setattr(fake, "embed", lambda texts: [[1.0, 0.0] for _ in texts])
    used = LocalEmbeddingEngine(llm=fake).embed("hello")
    assert used["method"] == "model" and used["dim"] == 2 and used["fell_back"] is False

    def down(*a, **k):
        raise LLMError("connection refused")
    monkeypatch.setattr(llm_module, "_post", down)
    fell = LocalEmbeddingEngine().embed("hello")
    assert fell["method"] == "hashed" and fell["fell_back"] is True


def test_embeddings_bad_input():
    e = LocalEmbeddingEngine()
    for bad in (None, "", [], ["ok", ""], ["x"] * 300):
        assert e.embed(bad, method="hashed")["status"] == "invalid_input"
    assert e.embed("x", method="cloud")["status"] == "invalid_input"
    assert e.nearest("q", [], k=1)["status"] == "invalid_input"
    assert e.nearest("q", ["a"], k=0)["matches"] == []
