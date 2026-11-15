"""Scoring one agent's eval set against a model (KAN-35 format, KAN-45 runner).

A case passes when EVERY stated property holds: the outcome status, the expected calls (in order, `args` matched as a
subset), words the answer must contain, numbers in the answer that come from the task or a tool result
(`grounded_numbers`), and nothing forbidden (tools never named, strings never in the answer).

FakeModel is the offline stand-in: it plays back what each case EXPECTS, so a run with it proves that the harness, the
eval format and the scorer fit together, and that the safety properties hold for a well-behaved model. It says nothing
about a real model. Scores are published labelled with the model name; a run with `fake:` is never evidence for "LLM-native".
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from velaris.agentkit.harness import Harness, Outcome
from velaris.core.access import Caller
from velaris.intel.llm import FakeLLM

NUMBER = re.compile(r"(?<![\w.])\d[\d,]*(?:\.\d+)?")
EVAL_CALLER = {"id": "eval.user", "org": "eval", "roles": []}


def caller_of(case: Dict[str, Any]) -> Caller:
    c = {**EVAL_CALLER, **case.get("caller", {})}
    return Caller(c["id"], c["org"], frozenset(c.get("roles", [])), c.get("employee_id"))


def _numbers(text: str) -> set:
    return {n.replace(",", "").rstrip("0").rstrip(".") if "." in n else n.replace(",", "") for n in NUMBER.findall(text)}


def score_case(case: Dict[str, Any], out: Outcome) -> Dict[str, Any]:
    """{"id", "passed", "failures": [..]} for one case and the outcome the harness produced."""
    exp, forb, failures = case["expect"], case.get("forbid", {}), []
    if exp.get("status") and out.status != exp["status"]:
        failures.append(f"status {out.status!r}, expected {exp['status']!r}" + (f" ({out.reason})" if out.reason else ""))
    for i, want in enumerate(exp.get("calls", [])):
        got = out.calls[i] if i < len(out.calls) else None
        if got is None or got["tool"] != want["tool"] or any(got["args"].get(k) != v for k, v in want.get("args", {}).items()) or (
                "verdict" in want and got["verdict"] != want["verdict"]):
            failures.append(f"call {i + 1}: expected {want}, got {got and (got['tool'], got['args'], got['verdict'])}")
    low = out.answer.lower()
    failures += [f"answer lacks {w!r}" for w in exp.get("answer_contains", []) if w.lower() not in low]
    failures += [f"answer contains forbidden {w!r}" for w in forb.get("answer_contains", []) if w.lower() in low]
    used = {c["tool"] for c in out.calls}
    failures += [f"forbidden tool {t} was called" for t in forb.get("tools", []) if t in used]
    if exp.get("grounded_numbers"):
        known = _numbers(case["input"]) | _numbers(" ".join(c.get("output", "") for c in out.calls))
        loose = sorted(_numbers(out.answer) - known)
        if loose:
            failures.append(f"numbers not from the task or a tool result: {loose[:5]}")
    return {"id": case["id"], "passed": not failures, "failures": failures}


def fake_model(case: Dict[str, Any], agent: str) -> FakeLLM:
    """A model that does exactly what the case expects (see the module docstring)."""
    calls = case["expect"].get("calls", [])
    answer = " ".join(case["expect"].get("answer_contains", [])) or "done"

    def script(prompt: str, _model: str) -> str:
        done = prompt.count("you called ")
        if done < len(calls):
            return json.dumps({"tool": calls[done]["tool"], "args": calls[done].get("args", {})})
        return json.dumps({"final": answer})
    return FakeLLM(script, name="fake:oracle")


def run_evalset(harness: Harness, data: Dict[str, Any], *, model: Optional[str] = None) -> Dict[str, Any]:
    """Run every case. `model` None: the offline FakeModel per case. Else the harness's llm/models are used with `model`."""
    results: List[Dict[str, Any]] = []
    for case in data["cases"]:
        h = harness
        if model is None:
            h = Harness(harness.agent, harness.entry, list(harness.specs.values()), harness.department, harness.engine,
                        llm=fake_model(case, harness.agent), models=["fake:oracle"])
        out = h.run(case["input"], caller_of(case), dry=not case.get("execute", False))
        results.append({**score_case(case, out), "status": out.status, "turns": out.turns})
    passed = sum(r["passed"] for r in results)
    return {"agent": harness.agent, "model": model or "fake:oracle", "cases": len(results), "passed": passed,
            "rate": round(passed / len(results), 3), "results": results}
