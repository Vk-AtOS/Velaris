"""KAN-13 (catalogue) and KAN-16 (fallback chain, breaker) with scripted providers."""
import pytest

from velaris.intel import catalogue, llm, providers, router, trace
from velaris.intel.errors import Retryable
from velaris.tests.fake_model_server import FakeModelServer


# ── catalogue ────────────────────────────────────────────────────────────────

def provider(url="http://127.0.0.1:1/v1", pid="gw", **kw):
    return providers.create(pid, kind="openai_compatible", base_url=url, allow_local=True, **kw)


def test_which_models_call_tools_and_have_32k_context():
    catalogue.configure("a", "big", context_window=128000, supports_tools=True)
    catalogue.configure("a", "small", context_window=8000, supports_tools=True)
    catalogue.configure("a", "notools", context_window=64000, supports_tools=False)
    catalogue.configure("a", "unknown")                                   # nothing is known: matches nothing
    assert [e["model"] for e in catalogue.query(tools=True, min_context=32000)] == ["big"]
    assert [e["model"] for e in catalogue.query(tools=False)] == ["notools"]


def test_prices_are_configuration_and_unknown_stays_unknown():
    catalogue.configure("a", "m", price_in_per_mtok=3.0)
    assert catalogue.cost_estimate("a:m", 1000, 1000) is None             # output price unknown -> unknown, not 0
    catalogue.configure("a", "m", price_out_per_mtok=15.0)
    assert catalogue.cost_estimate("a:m", 1_000_000, 1_000_000) == pytest.approx(18.0)
    assert catalogue.cost_estimate("a:nosuch", 1, 1) is None
    for bad in (dict(price_in_per_mtok=-1), dict(supports_tools="yes"), dict(nonsense=1)):
        with pytest.raises(ValueError):
            catalogue.configure("a", "m", **bad)


def test_refresh_discovers_models_but_never_overwrites_configured_values():
    provider()
    catalogue.configure("gw", "gpt-a", context_window=1000, price_in_per_mtok=9.0)

    def fetch(*a, **k):
        return [{"id": "gpt-a", "context_length": 200000, "pricing": {"prompt": "0.000001", "completion": "0.000002"}},
                {"id": "gpt-b", "context_length": 32000, "supported_parameters": ["tools", "temperature"]}]
    out = catalogue.refresh("gw", fetch)
    assert out == {"ok": True, "error": "", "added": 1, "unlisted": 0}
    a, b = catalogue.get("gw:gpt-a"), catalogue.get("gw:gpt-b")
    assert a["context_window"] == 1000 and a["price_in_per_mtok"] == 9.0      # hand-set wins
    assert a["price_out_per_mtok"] == pytest.approx(2.0) and a["source"] == "manual"
    assert b["context_window"] == 32000 and b["supports_tools"] is True and b["source"] == "discovered"
    assert b["price_in_per_mtok"] is None
    out = catalogue.refresh("gw", lambda *a, **k: [{"id": "gpt-b"}])            # gpt-a left the list
    assert out["unlisted"] == 1 and catalogue.get("gw:gpt-a")["listed"] is False
    assert [e["model"] for e in catalogue.query(provider="gw")] == ["gpt-b"]


def test_failed_refresh_keeps_the_catalogue_and_records_the_failure():
    provider()
    catalogue.configure("gw", "keep", context_window=5)

    def down(*a, **k):
        raise llm.LLMError("gw is down")
    for n in (1, 2):
        out = catalogue.refresh("gw", down)
        assert out["ok"] is False and "down" in out["error"]
        assert catalogue.refresh_status()["gw"]["failures"] == n
    assert catalogue.get("gw:keep")["context_window"] == 5 and catalogue.get("gw:keep")["listed"]
    catalogue.refresh("gw", lambda *a, **k: [{"id": "keep"}])
    assert catalogue.refresh_status()["gw"]["failures"] == 0
    assert catalogue.refresh("nosuch")["ok"] is False


def test_refresh_all_isolates_failures_and_refresh_reads_a_real_models_endpoint():
    with FakeModelServer() as srv:
        provider(srv.base_url, "good")
        provider("http://127.0.0.1:1/v1", "bad")
        srv.reply("/models", {"data": [{"id": "m1"}, {"id": "m2", "context_length": 64000}]})
        out = catalogue.refresh_all()
        assert out["good"]["added"] == 2 and out["bad"]["ok"] is False
        assert srv.requests[0][0] == "GET"


# ── fallback chain and breaker ───────────────────────────────────────────────

class Scripted(llm.LLM):
    """Answers per model from a list: a string is a reply, an exception is raised."""

    def __init__(self, plan):
        self.plan, self.calls = plan, []

    def complete(self, prompt, *, model=None, sensitivity=None, **kw):
        self.calls.append(model)
        step = self.plan[model].pop(0) if len(self.plan[model]) > 1 else self.plan[model][0]
        if isinstance(step, Exception):
            raise step
        return llm.Completion(text=step, model=model, seconds=0.0)


@pytest.fixture
def open_providers():
    for pid in ("a", "b", "c"):
        providers.create(pid, kind="ollama", sensitivity_allowed=["public", "internal", "restricted"])
    providers.create("free", kind="ollama", sensitivity_allowed=["public"], free_pool=True)


def test_fails_over_on_timeout_429_and_5xx_but_not_on_a_bad_request(open_providers):
    fake = Scripted({"a:m": [Retryable("timeout")], "b:m": [Retryable("503")], "c:m": ["ok from c"]})
    out = router.complete("worker", "hi", llm=fake, models=["a:m", "b:m", "c:m"], breaker=router.Breaker(),
                          sensitivity="internal", max_attempts=5)
    assert out.text == "ok from c" and fake.calls == ["a:m", "b:m", "c:m"]
    assert [e["payload"]["model"] for e in trace.entries() if e["action"] == "failover"] == ["a:m", "b:m"]
    fake = Scripted({"a:m": [llm.LLMError("400 bad request")], "b:m": ["never"]})
    with pytest.raises(llm.LLMError, match="400"):
        router.complete("worker", "hi", llm=fake, models=["a:m", "b:m"], breaker=router.Breaker(), sensitivity="internal")
    assert fake.calls == ["a:m"]


def test_breaker_opens_then_half_opens_then_recovers(open_providers):
    now = [0.0]
    br = router.Breaker(failures=2, open_s=30, clock=lambda: now[0])
    down = Scripted({"a:m": [Retryable("down")], "b:m": ["from b"]})
    for _ in range(2):
        router.complete("worker", "x", llm=down, models=["a:m", "b:m"], breaker=br, sensitivity="public")
    assert br.state("a") == "open" and down.calls.count("a:m") == 2
    router.complete("worker", "x", llm=down, models=["a:m", "b:m"], breaker=br, sensitivity="public")
    assert down.calls.count("a:m") == 2                                  # open: a was not even tried
    now[0] = 31
    assert br.state("a") == "half_open"
    down.plan["a:m"] = [Retryable("still down")]
    router.complete("worker", "x", llm=down, models=["a:m", "b:m"], breaker=br, sensitivity="public")
    assert down.calls.count("a:m") == 3 and br.state("a") == "open"      # one trial, failed, open again
    now[0] = 70
    down.plan["a:m"] = ["a is back"]
    assert router.complete("worker", "x", llm=down, models=["a:m", "b:m"], breaker=br, sensitivity="public").text == "a is back"
    assert br.state("a") == "closed"


def test_half_open_lets_exactly_one_trial_through():
    now = [0.0]
    br = router.Breaker(failures=1, open_s=10, clock=lambda: now[0])
    br.failure("a")
    now[0] = 11
    assert [br.allow("a"), br.allow("a")] == [True, False]


def test_attempt_and_time_caps_give_a_clear_error(open_providers):
    fake = Scripted({"a:m": [Retryable("x")], "b:m": [Retryable("x")], "c:m": ["ok"]})
    with pytest.raises(llm.LLMError, match=r"2 attempts, cap 2 attempts"):
        router.complete("worker", "x", llm=fake, models=["a:m", "b:m", "c:m"], breaker=router.Breaker(), max_attempts=2,
                        sensitivity="public")
    assert "c:m" not in fake.calls
    t = iter([0, 0, 100, 100, 100, 100])
    with pytest.raises(llm.LLMError, match="no provider answered"):
        router.complete("worker", "x", llm=Scripted({"a:m": [Retryable("x")], "b:m": ["ok"]}), models=["a:m", "b:m"],
                        breaker=router.Breaker(), max_seconds=60, clock=lambda: next(t), sensitivity="public")


def test_restricted_calls_never_fail_over_to_a_provider_that_may_not_see_them(open_providers):
    fake = Scripted({"a:m": [Retryable("down")], "free:m": ["leaked"], "b:m": ["from b"]})
    out = router.complete("worker", "pay", llm=fake, models=["a:m", "free:m", "b:m"], breaker=router.Breaker(),
                          sensitivity="restricted")
    assert out.text == "from b" and "free:m" not in fake.calls            # skipped, not used
    fake = Scripted({"free:m": ["leaked"]})
    with pytest.raises(llm.PolicyRefused):
        router.complete("worker", "pay", llm=fake, models=["free:m"], breaker=router.Breaker(), sensitivity=None)
    assert fake.calls == []
    one = Scripted({"a:m": ["ok"], llm.default_model(): ["dflt"]})                  # no chain configured: a chain of one
    assert router.complete("planner", "x", llm=one, model="a:m", breaker=router.Breaker(), sensitivity="internal").text == "ok"
    assert router.complete("planner", "x", llm=one, breaker=router.Breaker(), sensitivity="internal").text == "dflt"


def test_chains_are_stored_per_task_class():
    router.set_chain("planner", ["a:m", "b:m"], by="admin")
    assert router.chain("planner") == ["a:m", "b:m"] and router.chain("worker") == []
    for bad in (("nope", ["a:m"]), ("planner", []), ("planner", ["nocolon"])):
        with pytest.raises(ValueError):
            router.set_chain(*bad)
