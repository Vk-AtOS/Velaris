"""KAN-12 (openai_compatible), KAN-15 (sensitivity policy), KAN-14 (metering): through the real gateway,
against a real HTTP server on 127.0.0.1 that answers from a script."""
import ast
import itertools
import json
import re
import threading
from pathlib import Path

import httpx
import pytest

from velaris.core import access
from velaris.intel import catalogue, llm, openai_compat, policy, providers, trace, usage
from velaris.intel.paths import data_dir
from velaris.tests.fake_model_server import FakeModelServer, chat_reply

KEY = "sk-live-ABCDEFGH-1234567890"


@pytest.fixture
def srv():
    with FakeModelServer() as s:
        yield s


def provider(srv, pid="gw", levels=("public", "internal", "restricted"), **kw):
    return providers.create(pid, kind="openai_compatible", base_url=srv.base_url, api_key=KEY, allow_local=True,
                            sensitivity_allowed=list(levels), **kw)


def events(action):
    return [e for e in trace.entries() if e["action"] == action]


# ── KAN-12 ───────────────────────────────────────────────────────────────────

def test_chat_returns_text_and_sends_the_key_only_in_the_header(srv):
    provider(srv)
    srv.reply("/chat/completions", chat_reply("Vanakkam", tokens=(11, 3)))
    out = llm.LLM().complete("hello", system="be brief", model="gw:big", sensitivity="internal", purpose="t.chat")
    assert out.text == "Vanakkam" and out.model == "gw:big"
    method, path, headers, body = srv.requests[0]
    assert (method, path) == ("POST", "/chat/completions") and headers["Authorization"] == f"Bearer {KEY}"
    assert body["model"] == "big" and body["messages"][0] == {"role": "system", "content": "be brief"}
    assert KEY not in json.dumps(body)
    e = events("complete")[-1]["payload"]
    assert (e["provider"], e["model"], e["sensitivity"], e["prompt_chars"], e["output_chars"]) == \
        ("gw", "gw:big", "internal", 5, 8) and "seconds" in e
    assert KEY not in (data_dir() / "trace.jsonl").read_text()


def test_error_bad_json_and_timeout_are_clear_errors(srv):
    provider(srv)
    srv.reply("/chat/completions", {"error": "bad"}, status=400)
    with pytest.raises(llm.LLMError) as e:
        llm.LLM().complete("x", model="gw:m", sensitivity="public")
    assert "400" in str(e.value) and not isinstance(e.value, llm.Retryable)
    srv.script.clear()
    srv.reply("/chat/completions", raw=b"<html>oops</html>", content_type="text/html")
    with pytest.raises(llm.LLMError, match="not JSON"):
        llm.LLM().complete("x", model="gw:m", sensitivity="public")
    srv.script.clear()
    srv.reply("/chat/completions", {"choices": []})
    with pytest.raises(llm.LLMError, match="could not be read"):
        llm.LLM().complete("x", model="gw:m", sensitivity="public")
    srv.script.clear()
    srv.reply("/chat/completions", chat_reply(), delay=1.5)
    with llm.call_timeout(0.3), pytest.raises(llm.Retryable, match="timed out"):
        llm.LLM().complete("x", model="gw:m", sensitivity="public")
    srv.script.clear()
    srv.reply("/chat/completions", {}, status=503)
    with pytest.raises(llm.Retryable):
        llm.LLM().complete("x", model="gw:m", sensitivity="public")
    assert [x["payload"]["error"] for x in events("complete.failed")][-1].startswith("127.0.0.1 returned 503")


def test_tool_calls_pass_through_untouched(srv):
    provider(srv)
    call = {"id": "c1", "type": "function", "function": {"name": "get_leave", "arguments": '{"id": 7}'}}
    srv.reply("/chat/completions", chat_reply("", tool_calls=[call]))
    tools = [{"type": "function", "function": {"name": "get_leave", "parameters": {"type": "object"}}}]
    out = llm.LLM().chat([{"role": "user", "content": "leave?"}], model="gw:m", sensitivity="internal",
                         tools=tools, tool_choice="auto")
    assert out.tool_calls == (call,)
    assert srv.requests[0][3]["tools"] == tools and srv.requests[0][3]["tool_choice"] == "auto"
    with pytest.raises(llm.LLMError, match="openai_compatible"):
        llm.LLM().chat([{"role": "user", "content": "x"}], model="ollama:x", tools=tools)


def test_streaming_is_joined_and_tool_call_fragments_are_assembled(srv):
    provider(srv)
    sse = "".join(f"data: {json.dumps(c)}\n\n" for c in [
        {"choices": [{"delta": {"content": "Hel"}}]},
        {"choices": [{"delta": {"content": "lo", "tool_calls": [{"index": 0, "id": "c", "function": {"name": "f", "arguments": '{"a"'}}]}}]},
        {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": ': 1}'}}]}, "finish_reason": "tool_calls"}],
         "usage": {"prompt_tokens": 4, "completion_tokens": 2}}]) + "data: [DONE]\n\n"
    srv.reply("/chat/completions", raw=sse.encode(), content_type="text/event-stream")
    seen = []
    out = llm.LLM().chat([{"role": "user", "content": "x"}], model="gw:m", sensitivity="public", stream=True,
                         on_delta=seen.append)
    assert out.text == "Hello" and seen == ["Hel", "lo"]
    assert out.tool_calls[0]["function"] == {"name": "f", "arguments": '{"a": 1}'}


def test_embeddings(srv, monkeypatch):
    provider(srv)
    monkeypatch.setenv("VELARIS_EMBED_MODEL", "gw:embed-1")
    srv.reply("/embeddings", {"data": [{"index": 1, "embedding": [0, 1]}, {"index": 0, "embedding": [1, 0]}]})
    assert llm.LLM().embed(["a", "b"], sensitivity="internal") == [[1.0, 0.0], [0.0, 1.0]]
    assert srv.requests[0][3] == {"model": "embed-1", "input": ["a", "b"]}


def test_local_addresses_need_allow_local_and_public_ones_are_pinned(srv, monkeypatch):
    providers.create("nolocal", kind="openai_compatible", base_url=srv.base_url, sensitivity_allowed=["public"])
    with pytest.raises(llm.LLMError, match="allow_local"):
        llm.LLM().complete("x", model="nolocal:m", sensitivity="public")
    assert srv.requests == []
    seen = []

    def handler(request):
        seen.append((str(request.url), request.headers["host"], request.extensions.get("sni_hostname")))
        return httpx.Response(200, json=chat_reply("ok"))
    monkeypatch.setattr(openai_compat, "transport", httpx.MockTransport(handler))
    monkeypatch.setattr(openai_compat, "resolver", lambda host: ["93.184.216.34"])
    providers.create("remote", kind="openai_compatible", base_url="https://api.example.com/v1", api_key=KEY,
                     sensitivity_allowed=["public"])
    assert llm.LLM().complete("x", model="remote:m", sensitivity="public").text == "ok"
    assert seen[0][:2] == ("https://93.184.216.34/v1/chat/completions", "api.example.com")   # connected to the checked IP
    assert str(seen[0][2]).strip("b'") == "api.example.com"                                 # TLS name stays the host
    monkeypatch.setattr(openai_compat, "resolver", lambda host: ["169.254.169.254"])
    with pytest.raises(llm.LLMError, match="blocked_address"):
        llm.LLM().complete("x", model="remote:m", sensitivity="public")


def test_builtin_providers_still_work_and_are_policy_neutral(monkeypatch):
    seen = []
    monkeypatch.setattr(llm.httpx, "post", lambda url, **kw: seen.append(url) or httpx.Response(
        200, json={"response": "hi", "prompt_eval_count": 3, "eval_count": 2}, request=httpx.Request("POST", url)))
    assert llm.LLM().complete("x", model="ollama:q").text == "hi"      # no level given: restricted, built-in accepts
    assert seen and usage.month_totals("default")["tokens_in"] == 3


# ── KAN-15 ───────────────────────────────────────────────────────────────────

def test_restricted_never_reaches_a_pool_that_does_not_accept_it(srv):
    provider(srv, "pool", levels=("public", "internal"), free_pool=True)
    for level in ("restricted", None, "top-secret"):                     # missing and unknown tags count as restricted
        with pytest.raises(llm.PolicyRefused, match="does not accept restricted"):
            llm.LLM().complete("pay data", model="pool:m", sensitivity=level)
    assert srv.requests == []
    srv.reply("/chat/completions", chat_reply())
    assert llm.LLM().complete("docs", model="pool:m", sensitivity="internal").text == "hi"
    assert events("complete")[-1]["payload"]["sensitivity"] == "internal"
    assert events("complete.refused")[-1]["payload"]["sensitivity"] == "restricted"


def test_a_disabled_or_unknown_provider_accepts_nothing(srv):
    provider(srv, "off", enabled=False)
    for model in ("off:m", "nosuch:m"):
        with pytest.raises(llm.PolicyRefused):
            llm.LLM().complete("x", model=model, sensitivity="public")
    assert policy.permits("anthropic", "public") and policy.permits("ollama", "restricted")   # built-ins: operator-configured


def test_reading_pay_data_forces_restricted_for_the_rest_of_the_request(srv):
    provider(srv, "pool", levels=("public", "internal"))
    srv.reply("/chat/completions", chat_reply())
    caller = access.Caller(id="u1", org="o", roles=frozenset({"payroll_admin"}), employee_id="e1")

    def request():
        with access.acting_as(caller):
            llm.LLM().complete("summary", model="pool:m", sensitivity="internal")      # fine before the read
            access.authorize_read("pay", "e2", agent="payroll", caller=caller)
            llm.LLM().complete("payslip of e2", model="pool:m", sensitivity="public")  # tag is overridden
    ctx = __import__("contextvars").copy_context()
    with pytest.raises(llm.PolicyRefused):
        ctx.run(request)
    assert len(srv.requests) == 1                                        # only the call before the read was sent
    llm.LLM().complete("next request starts clean", model="pool:m", sensitivity="public")


def test_the_floor_ends_with_the_request_scope(srv):
    provider(srv, "pool", levels=("public",))
    srv.reply("/chat/completions", chat_reply())
    caller = access.Caller(id="u1", org="o", roles=frozenset({"payroll_admin"}))
    with access.acting_as(caller):
        access.authorize_read("pay", "e2", agent="payroll", caller=caller)
        assert policy.effective("public") == "restricted"
    assert policy.effective("public") == "public"                       # next request on this thread starts clean
    assert llm.LLM().complete("x", model="pool:m", sensitivity="public").text == "hi"


def test_property_every_model_call_passes_the_policy(srv, monkeypatch):
    """For every provider x level x entry point: the provider function runs only if the policy permits."""
    provider(srv, "open", levels=("public", "internal", "restricted"))
    provider(srv, "pool", levels=("public",))
    reached = []
    monkeypatch.setattr(llm, "_chat", lambda prov, *a, **k: reached.append(prov) or
                        {"text": "t", "tool_calls": [], "finish_reason": None, "usage": None})
    for prov, level, how in itertools.product(["open", "pool", "ollama", "nosuch"],
                                              ["public", "internal", "restricted", None], ["complete", "chat"]):
        reached.clear()
        call = (lambda: llm.LLM().complete("p", model=f"{prov}:m", sensitivity=level)) if how == "complete" else \
               (lambda: llm.LLM().chat([{"role": "user", "content": "p"}], model=f"{prov}:m", sensitivity=level))
        allowed = policy.permits(prov, policy.effective(level))
        if allowed:
            call()
            assert reached == [prov]
        else:
            with pytest.raises(llm.PolicyRefused):
                call()
            assert reached == []


def test_only_the_gateway_talks_to_model_hosts():
    """Source scan: outbound model HTTP lives in llm.py and openai_compat.py, and only `_invoke` reaches `_chat`."""
    root = Path(llm.__file__).parent
    for f in root.glob("*.py"):
        src = f.read_text()
        if f.name in ("llm.py", "openai_compat.py", "web_fetch.py", "catalogue.py", "web.py", "web_markdown.py"):
            continue
        assert not re.search(r"\bhttpx\.(post|get|Client|request|stream)\b", src), f"{f.name} makes HTTP calls"
    tree = ast.parse((root / "llm.py").read_text())
    callers = {}
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.Lambda)):
            for n in ast.walk(fn):
                if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "_chat":
                    callers.setdefault(getattr(fn, "name", "<lambda>"), 0)
    assert set(callers) <= {"chat", "complete", "<lambda>"}              # only the two public entry points pass lambdas to _invoke
    invoke = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_invoke")
    assert "authorize" in ast.dump(invoke) and "check" in ast.dump(invoke)


# ── KAN-14 ───────────────────────────────────────────────────────────────────

def test_usage_is_recorded_aggregated_and_never_holds_the_prompt(srv):
    provider(srv)
    catalogue.configure("gw", "m", price_in_per_mtok=2.0, price_out_per_mtok=10.0)
    srv.reply("/chat/completions", chat_reply("SECRET-REPLY", tokens=(1000, 500)))
    with usage.usage_context(org="acme", agent="payroll"):
        llm.LLM().complete("SECRET-PROMPT salary of Priya", model="gw:m", sensitivity="internal", purpose="payroll.explain")
    row = usage.summary("org")[0]
    assert (row["key"], row["calls"], row["tokens_in"], row["tokens_out"], row["estimated_calls"]) == ("acme", 1, 1000, 500, 0)
    assert row["cost_usd"] == pytest.approx(0.002 + 0.005)
    assert usage.summary("agent")[0]["key"] == "payroll" and usage.summary("model")[0]["key"] == "gw:m"
    assert usage.summary("org", org="other-org") == [] and len(usage.summary("day")) == 1
    raw = "".join(p.read_text() for p in (data_dir() / "agents" / "llm_usage").glob("*"))
    assert "SECRET" not in raw and "Priya" not in raw


def test_provider_without_usage_data_is_estimated_and_flagged_and_unknown_price_is_unknown(srv):
    provider(srv)
    srv.reply("/chat/completions", chat_reply("x" * 40, tokens=None))
    llm.LLM().complete("y" * 80, model="gw:m", sensitivity="public")
    row = usage.summary("org")[0]
    assert (row["tokens_in"], row["tokens_out"], row["estimated_calls"], row["unpriced_calls"]) == (20, 10, 1, 1)
    assert row["cost_usd"] == 0.0 and catalogue.cost_estimate("gw:m", 1, 1) is None


def test_failed_calls_are_metered_too(srv):
    provider(srv)
    srv.reply("/chat/completions", {}, status=400)
    with pytest.raises(llm.LLMError):
        llm.LLM().complete("x", model="gw:m", sensitivity="public")
    assert usage.summary("org")[0]["errors"] == 1


def test_budget_is_a_hard_stop_with_a_reason_and_alerts_at_80_percent(srv, caplog):
    provider(srv)
    catalogue.configure("gw", "m", price_in_per_mtok=1000.0, price_out_per_mtok=1000.0)
    usage.set_budget("acme", usd=10.0)
    srv.reply("/chat/completions", chat_reply(tokens=(4000, 4000)))                 # $8 = 80% of $10
    with usage.usage_context(org="acme"):
        llm.LLM().complete("x", model="gw:m", sensitivity="public")
        assert [e["payload"]["org"] for e in events("budget.alert")] == ["acme"]
        llm.LLM().complete("x", model="gw:m", sensitivity="public")                 # $16: over, alerted only once
        with pytest.raises(llm.BudgetExceeded, match="monthly budget of \\$10.00"):
            llm.LLM().complete("x", model="gw:m", sensitivity="public")
    assert len(events("budget.alert")) == 1 and len(srv.requests) == 2
    with usage.usage_context(org="other"):                                          # another org is unaffected
        llm.LLM().complete("x", model="gw:m", sensitivity="public")


def test_unknown_price_cannot_be_metered_against_a_usd_budget(srv):
    provider(srv)
    usage.set_budget("acme", usd=5.0)
    with usage.usage_context(org="acme"), pytest.raises(llm.BudgetExceeded, match="no price"):
        llm.LLM().complete("x", model="gw:m", sensitivity="public")
    assert srv.requests == []


def test_token_budget_and_default_budget_from_the_environment(srv, monkeypatch):
    provider(srv)
    monkeypatch.setenv("VELARIS_ORG_BUDGET_TOKENS", "100")
    srv.reply("/chat/completions", chat_reply(tokens=(60, 60)))
    llm.LLM().complete("x", model="gw:m", sensitivity="public")
    with pytest.raises(llm.BudgetExceeded, match="token budget"):
        llm.LLM().complete("x", model="gw:m", sensitivity="public")


def test_kill_switch_stops_everything_and_can_be_lifted(srv):
    provider(srv)
    usage.set_kill_switch(True, by="admin")
    with pytest.raises(llm.BudgetExceeded, match="switched off"):
        llm.LLM().complete("x", model="gw:m", sensitivity="public")
    assert srv.requests == []
    usage.set_kill_switch(False, by="admin")
    srv.reply("/chat/completions", chat_reply())
    assert llm.LLM().complete("x", model="gw:m", sensitivity="public").text == "hi"


def test_concurrent_calls_lose_no_usage_records(srv):
    provider(srv)
    srv.reply("/chat/completions", chat_reply(tokens=(1, 1)))
    ts = [threading.Thread(target=lambda: [llm.LLM().complete("x", model="gw:m", sensitivity="public")
                                           for _ in range(10)]) for _ in range(6)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    row = usage.summary("org")[0]
    assert row["calls"] == 60 and usage.month_totals("default")["calls"] == 60
    assert trace.verify()["ok"]
