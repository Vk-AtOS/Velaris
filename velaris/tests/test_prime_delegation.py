"""Defect 12: AetherOS Prime (velaris.core.prime) is canonical; the local PRIME agent delegates once Prime is configured."""
import pytest

from velaris.agents.PRIME.main import VelarisPrime
from velaris.core import prime
from velaris.core.access import Caller, acting_as
from velaris.tests.test_aicore_b_prime_vcas import T0, _grant

BOT = Caller("ap-bot", "acme")


@pytest.fixture(autouse=True)
def _data(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    monkeypatch.delenv("VELARIS_PRIME_URL", raising=False)
    monkeypatch.delenv("VELARIS_PRIME_API_KEY", raising=False)


def test_prime_configured_needs_both_settings():
    assert prime.prime_configured({}) is False
    assert prime.prime_configured({"VELARIS_PRIME_URL": "https://p.example"}) is False
    assert prime.prime_configured({"VELARIS_PRIME_URL": "https://p.example", "VELARIS_PRIME_API_KEY": "k"}) is True


def test_a_local_grant_can_no_longer_allow_once_prime_is_configured(monkeypatch):
    local = VelarisPrime()
    assert _grant(local)["status"] == "ok"                                           # made before Prime was connected
    ask = lambda: local.authorize("ap-bot", "invoice.approve", "inv/1", {"amount": 20_000, "currency": "INR"}, now=T0 + 60)  # noqa: E731
    assert ask()["decision"] == "allow"                                              # the local fallback, as before
    monkeypatch.setenv("VELARIS_PRIME_URL", "https://prime.example")
    monkeypatch.setenv("VELARIS_PRIME_API_KEY", "k")
    later = ask()
    assert later["decision"] == "needs_approval" and "AetherOS Prime" in later["reason"]
    refused = _grant(local, principal="other-bot")
    assert refused["status"] == "delegated_to_prime", refused
    with acting_as(BOT):                                                             # and execute() runs nothing
        assert local.execute("VIGILIS", "health_check", principal="ap-bot")["executed"] is False


def test_execute_runs_through_the_backend_engine_as_the_caller(monkeypatch):
    """Defect 15: execute() used a second engine, without acting_as, so the callee saw no caller (a bypass of caller handling)."""
    from velaris.backend.engine import backend
    from velaris.core.access import current_caller
    local, seen = VelarisPrime(), []
    with acting_as(Caller("meena", "acme", frozenset({"governance_admin"}))):
        local.grant(principal="ops-bot", actions=["agent.execute"], approver="kumar", resources=["VIGILIS.health_check"], autonomy="act")
    monkeypatch.setattr(backend, "run", lambda a, m, p=None, caller=None: seen.append((a, m, caller)) or {"status": "ok"})
    with acting_as(Caller("ops-bot", "acme")):
        assert local.execute("VIGILIS", "health_check", principal="ops-bot") == {"status": "ok"}
    assert seen and seen[0][:2] == ("VIGILIS", "health_check") and seen[0][2].id == "ops-bot"
    assert current_caller() is None
