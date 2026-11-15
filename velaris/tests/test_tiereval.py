"""KAN-19: the tiering harness works end to end with scripted models. NO real model was run: the results
table for the Confluence page needs one (see tools/tier_eval.py)."""
import json
from collections import Counter


from velaris.intel import catalogue, llm, providers, tiereval


def test_there_are_20_well_formed_fixtures_across_the_classes_and_languages():
    tasks = tiereval.load_tasks()
    assert len(tasks) == 20
    assert Counter(t["class"] for t in tasks) == {"planner": 3, "worker": 5, "classifier": 4, "chat": 6, "embedding": 2}
    assert {t["language"] for t in tasks} == {"en", "ta", "tanglish"}
    assert sum(1 for t in tasks if t.get("tools")) >= 2 and sum(1 for t in tasks if t["sensitivity"] == "restricted") >= 2
    assert all(tiereval.TAMIL.search(t["prompt"]) for t in tasks if t["id"] in ("chat-tamil-policy", "embed-tamil-search"))


def test_scoring_content_tool_and_language():
    t = {"expect": {"contains_all": ["5"], "not_contains": ["unlimited"], "tamil_min_ratio": 0.5}}
    assert tiereval.score(t, "அதிகபட்சம் 5 நாட்கள்")["passed"]
    assert not tiereval.score(t, "up to 5 days")["passed"]                         # not Tamil enough
    assert not tiereval.score(t, "5 unlimited நாட்கள் நாட்கள்")["passed"]
    j = {"expect": {"json_equals": {"intent": "leave_request"}}}
    assert tiereval.score(j, 'Sure:\n```json\n{"intent": "leave_request"}\n```')["passed"]
    assert not tiereval.score(j, '{"intent": "other"}')["passed"] and not tiereval.score(j, "no json")["passed"]
    tool = {"expect": {"tool": {"name": "f", "args_subset": {"a": 1}}}}
    assert tiereval.score(tool, "", [{"function": {"name": "f", "arguments": '{"a": 1, "b": 2}'}}])["tool"] is True
    assert tiereval.score(tool, '{"tool": "f", "args": {"a": 1}}')["tool"] is True
    assert tiereval.score(tool, '{"tool": "g", "args": {"a": 1}}')["tool"] is False
    assert tiereval.score(tool, "", [{"function": {"name": "f", "arguments": "{bad"}}])["tool"] is False


def answers(prompt, model):
    """A scripted model that gets the easy tasks right and the Tamil ones wrong."""
    if "Reply JSON only" in prompt and "Intent" in prompt:
        return '{"intent": "leave_request"}'
    if "Call the right tool" in prompt or "Open a ticket" in prompt:
        return '{"tool": "get_leave_balance", "args": {"employee_id": "E1042"}}'
    return "Friday 5 41,000 thank you tomorrow closed"


def test_run_summarise_and_table_with_a_scripted_model(monkeypatch):
    catalogue.configure("fake", "model", price_in_per_mtok=1.0, price_out_per_mtok=2.0)
    fake = llm.FakeLLM(answers)
    fake.chat = lambda messages, **kw: fake.complete(messages[-1]["content"], **{k: v for k, v in kw.items()
                                                                                  if k in ("model", "sensitivity", "purpose")})
    results = tiereval.run(["fake:model"], gateway=fake)
    assert len(results) == 20 and all(r["status"] == "ok" for r in results)
    by = {r["task"]: r["score"]["passed"] for r in results}
    assert by["clf-intent-tanglish"] and by["plan-tool-leave-balance"] and by["worker-policy-question"]
    assert not by["chat-tamil-policy"] and not by["plan-tool-create-ticket"]       # wrong tool/script: scored as failures
    s = tiereval.summarise(results)["fake:model"]
    assert s["tasks"] == 20 and 0 < s["pass_rate"] < 1 and s["cost_usd"] is not None and s["tool_call_rate"] == 0.5
    table = tiereval.markdown({"fake:model": s})
    assert "fake:model" in table and "need a person" in table
    json.dumps(results, ensure_ascii=False)                                         # results are plain JSON


def test_policy_refusals_and_failures_are_recorded_not_raised(monkeypatch):
    providers.create("pool", kind="ollama", sensitivity_allowed=["public", "internal"], free_pool=True)
    tasks = [t for t in tiereval.load_tasks() if t["id"] in ("worker-payroll-explain", "clf-pii")]
    monkeypatch.setattr(llm.httpx, "post", lambda *a, **k: (_ for _ in ()).throw(llm.httpx.ConnectError("down")))
    results = {r["task"]: r for r in tiereval.run(["pool:m"], tasks)}
    assert results["worker-payroll-explain"]["status"] == "refused"                # restricted task, free pool
    assert results["clf-pii"]["status"] == "error" and results["clf-pii"]["score"] is None
    s = tiereval.summarise(list(results.values()))["pool:m"]
    assert (s["refused"], s["errors"], s["pass_rate"], s["cost_usd"]) == (1, 1, None, None)


def test_embedding_tasks_use_cosine_nearest():
    task = {"id": "e", "class": "embedding", "language": "en", "kind": "embed", "sensitivity": "internal",
            "prompt": "sick leave days", "candidates": ["office address", "sick leave days entitlement"],
            "expect": {"nearest": 1}}
    assert tiereval.run_task("fake:model", task, llm.FakeLLM({}))["score"]["passed"]
