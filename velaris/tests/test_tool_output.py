"""KAN-29: every registered tool declares the JSON shape of its result; a result that does not fit is a failed step."""
import json
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from velaris.agentkit import harness_tools
from velaris.agentkit.harness import Harness
from velaris.api import allowlist
from velaris.backend.engine import backend
from velaris.core.access import Caller
from velaris.intel import tools
from velaris.intel.llm import FakeLLM

ROOT = Path(__file__).resolve().parents[2]


def _ann(self) -> Dict[str, Any]: ...
def _opt(self) -> Optional[str]: ...
def _lst(self) -> List[Dict[str, Any]]: ...
def _dec(self) -> Decimal: ...
def _any(self) -> Any: ...


def _helper(msg):
    return {"status": "bad", "reason": msg}


def _observed(self, x):
    def local(why):
        return {"ok": False, "why": why}
    if x == 1:
        return local("one")
    if x == 2:
        return _helper("two")
    return {"ok": True}


def _mixed(self, x):
    return {"a": 1} if x else None


def _unclear(self, x):
    return self.compute(x)


def _plain(self):
    return f"text {self}"


def test_schema_from_the_return_annotation():
    assert tools.output_schema(_ann) == {"type": "object"}
    assert tools.output_schema(_opt) == {"type": ["null", "string"]}
    assert tools.output_schema(_lst) == {"type": "array", "items": {"type": "object"}}
    assert tools.output_schema(_dec) == {"type": "number"} and tools.output_schema(_any) == {}


def test_schema_from_what_the_returns_prove_when_there_is_no_annotation():
    assert tools.output_schema(_observed) == {"type": "object"}        # helpers nested or in the module are followed
    assert tools.output_schema(_mixed) == {"type": ["null", "object"]}
    assert tools.output_schema(_plain) == {"type": "string"}
    assert tools.output_schema(_unclear) == {}                          # nothing provable: no claim, never a guess


def test_validate_output_names_the_types_never_the_value():
    spec = tools.ToolSpec("A.b", "A", "b", {}, output={"type": "number"})
    assert tools.validate_output(spec, 3) == [] and tools.validate_output(spec, Decimal("1.5")) == []
    problems = tools.validate_output(spec, "secret-value")
    assert problems and "secret-value" not in problems[0]
    assert tools.validate_output(tools.ToolSpec("A.b", "A", "b", {}), "anything") == []
    arr = tools.ToolSpec("A.b", "A", "b", {}, output={"type": "array", "items": {"type": "string"}})
    assert tools.validate_output(arr, ["a", 1]) and tools.validate_output(arr, ("a", "b")) == []


@pytest.fixture(scope="module")
def registry():
    tools.clear()
    harness_tools.register_all(backend)
    yield
    tools.clear()


def test_every_registered_tool_has_an_output_schema_and_most_are_typed(registry):
    specs = tools.list_tools()
    assert len(specs) > 1000 and all(isinstance(s.output, dict) for s in specs)
    typed = [s for s in specs if s.output]
    assert len(typed) / len(specs) > 0.85, "the derivation proves a type for fewer methods than before"
    assert tools.get("TREASURIX.runway_months").output == {"type": "number"}


def test_the_pure_read_tools_return_what_they_declare(registry):
    """The shape OBSERVED on the eval sets' sample arguments: a declared schema that a real result breaks is a wrong schema."""
    checked = 0
    for key in allowlist.NOTES:
        agent, method = key.split(".")
        spec = tools.get(key)
        case = next((c for c in json.loads((ROOT / "evals" / spec.department / f"{agent}.json").read_text())["cases"]
                     if c["id"] == f"select-{method}"), None)
        if case is None:
            continue
        try:
            result = backend.run(agent, method, case["expect"]["calls"][0]["args"])
        except (TypeError, ValueError, KeyError, AttributeError):    # a generated sample argument the method rejects: nothing observed
            continue
        assert tools.validate_output(spec, result) == [], f"{key}: {spec.output} vs {type(result).__name__}"
        checked += 1
    assert checked > 30


def _drive(monkeypatch, value):
    monkeypatch.setattr(backend, "run", lambda *a, **k: value)
    turns = iter([{"tool": "runway_months", "args": {"monthly_burn": 1.0}}, {"final": "done"}])
    llm = FakeLLM(lambda p, m: json.dumps(next(turns)), name="fake:t")
    out = Harness.for_agent("TREASURIX", engine=backend, llm=llm, models=["fake:t"]).run("runway?", Caller("u", "o", frozenset()))
    assert out.status == "answered", out
    return out


def test_the_harness_treats_a_result_that_breaks_its_schema_as_a_failed_step(registry, monkeypatch):
    bad = _drive(monkeypatch, "not a number")
    assert bad.calls[0]["verdict"] == "failed" and "NOT DONE" in bad.calls[0]["output"]
    assert "not a number" not in bad.calls[0]["output"]
    good = _drive(monkeypatch, 4.5)
    assert good.calls[0]["verdict"] == "ran"


def test_a_flow_tool_refuses_a_result_that_breaks_its_schema(registry):
    spec = tools.get("TREASURIX.runway_months")
    ok = tools.flow_tool(spec, lambda **a: 2.0)
    assert ok.fn(monthly_burn=1.0) == 2.0
    bad = tools.flow_tool(spec, lambda **a: {"x": 1})
    with pytest.raises(tools.ToolOutputError):
        bad.fn(monthly_burn=1.0)


# ── an executed action is never turned into a failure (a failure invites a retry, a retry repeats the side effect) ──
from velaris.intel.flow import Flow     # noqa: E402


@pytest.fixture
def _data(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))


def _spec(name, side_effects, kind):
    return tools.ToolSpec(f"X.{name}", "X", name, {"type": "object", "properties": {}, "required": []},
                          side_effects=side_effects, kind=kind, output={"type": "number"})


def _model(*calls):
    it = iter([json.dumps({"tool": c, "args": {}}) for c in calls] + [json.dumps({"final": "ok"})])
    return FakeLLM(lambda p, m: next(it))


def _results(flow, run_id):
    return [e for e in flow.history(run_id) if e["kind"] == "result"]


def test_an_act_tool_with_a_wrong_shape_is_recorded_executed_with_a_warning_and_ran_once(_data):
    ran = []
    act = tools.flow_tool(_spec("send", "external", "act"), lambda **a: ran.append(1) or "a string, not a number",
                          needs_approval=False)
    flow = Flow([act], llm=_model("X.send"), permit=lambda t, a: "allow")
    r = flow.start("do it")
    res = _results(flow, r.run_id)
    assert r.status == "done" and ran == [1]
    assert res[0]["ok"] is True and res[0]["executed"] is True and res[0]["warning"].startswith("output_mismatch")
    assert "a string, not a number" not in res[0]["output"]            # the unfit result is withheld


def test_a_read_with_a_wrong_shape_fails_and_may_be_tried_again(_data):
    ran = []
    read = tools.flow_tool(_spec("peek", "none", "read"), lambda **a: ran.append(1) or "wrong")
    flow = Flow([read], llm=_model("X.peek", "X.peek"), permit=lambda t, a: "allow", max_repeat=0)
    r = flow.start("look twice")
    res = _results(flow, r.run_id)
    assert [x["ok"] for x in res] == [False, False] and ran == [1, 1] and not any(x["executed"] for x in res)


def test_a_model_loop_does_not_call_an_executed_act_tool_again(_data):
    ran = []
    act = tools.flow_tool(_spec("send", "external", "act"), lambda **a: ran.append(1) or 1.0, needs_approval=False)
    flow = Flow([act], llm=_model("X.send", "X.send"), permit=lambda t, a: "allow", max_repeat=0)
    r = flow.start("send it")
    res = _results(flow, r.run_id)
    assert ran == [1] and len(res) == 2 and "already ran" in res[1]["output"] and res[1]["ok"] is False
