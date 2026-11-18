"""KAN-17: OmniRoute as an optional provider, and the health check behind the dashboard badge."""
import pytest

from velaris.intel import health, llm, providers
from velaris.tests.fake_model_server import FakeModelServer


def test_preset_is_a_free_pool_that_never_sees_restricted_data():
    p = providers.from_preset("omniroute", "omniroute", api_key="sk-omni-000000000000")
    assert (p.kind, p.base_url, p.allow_local, p.free_pool) == ("openai_compatible", "http://localhost:20128/v1", True, True)
    assert p.sensitivity_allowed == ("public", "internal")
    assert p.public()["free_pool"] is True                                   # the dashboard badge reads this
    for level in ("restricted", None):
        with pytest.raises(llm.PolicyRefused):
            llm.LLM().complete("payslip", model="omniroute:auto", sensitivity=level)
    with pytest.raises(providers.ProviderError):                             # cannot be widened to restricted
        providers.update("omniroute", sensitivity_allowed=["public", "internal", "restricted"])
    with pytest.raises(providers.ProviderError):
        providers.from_preset("o2", "omniroute", sensitivity_allowed=["restricted"])
    with pytest.raises(providers.ProviderError):
        providers.from_preset("o3", "nosuch")


def test_health_check_reports_up_down_and_never_the_providers_own_error_text():
    with FakeModelServer() as srv:
        providers.create("up", kind="openai_compatible", base_url=srv.base_url, allow_local=True)
        providers.create("rejects", kind="openai_compatible", base_url=srv.base_url, allow_local=True,
                         api_key="sk-secret-ABCDEFGH-9999")
        providers.create("blocked", kind="openai_compatible", base_url=srv.base_url)         # local, not allowed
        providers.create("dead", kind="openai_compatible", base_url="http://127.0.0.1:1/v1", allow_local=True)
        srv.reply("/models", {"data": [{"id": "m"}]})
        assert health.check("up")["ok"] and health.check("up")["models"] == 1
        srv.script.clear()
        srv.reply("/models", {"error": "bad key sk-secret-ABCDEFGH-9999"}, status=401)
        r = health.check("rejects")
        assert r == {"ok": False, "latency_s": r["latency_s"], "error": "key_rejected"}
        assert health.check("blocked")["error"] == "address_not_allowed"
        assert health.check("dead")["error"] in ("unavailable", "failed")
        assert health.check("nosuch")["error"] == "no_such_provider"
        out = health.sweep()
        assert out["dead"]["ok"] is False and "sk-secret" not in str(out)
