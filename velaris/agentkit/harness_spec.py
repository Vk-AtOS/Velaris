"""The harness contract (KAN-35): manifest entry and eval-set format, with the validators the tests run over every agent.

Manifest `harness` entry (data only, in departments/<dept>/<AGENT>/manifest.json):

  {"schema": 1, "status": "deterministic_tool" | "model_driven" | "mixed" | "not_harnessed",
   "purpose": "one sentence",
   "sensitivity": "public" | "internal" | "restricted",       # what the model may be shown; restricted never leaves approved providers
   "task_class": "worker" | "planner" | "classifier",         # which fallback chain of velaris.intel.router answers
   "tools": {"method": {"kind": "read" | "act"}},              # exposed methods; the allowlist overrides kind where it has a rule
   "excluded": {"method": "why it is not exposed"},
   "reason_code": "stub|unreachable|no_methods|unsafe", "reason": "..."       # not_harnessed only
   "eval": "evals/<dept>/<AGENT>.json",
   "wave": "KAN-nn", "reviewed": true}                         # reviewed: a person checked this entry; the generator keeps it whole

Eval set: {"schema": 1, "agent": NAME, "cases": [CASE...]} with
  CASE = {"id", "input", "execute": false, "caller": {"id","org","roles"}?,
          "expect": {"status"?, "calls": [{"tool", "args"?}]?, "answer_contains": [..]?, "grounded_numbers": bool?},
          "forbid": {"tools": [..]?, "answer_contains": [..]?}}
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, List

from velaris.agents import DEPARTMENTS_DIR
from velaris.intel import router, providers

ROOT = Path(DEPARTMENTS_DIR).parent
SCHEMA = 1
STATUSES = ("deterministic_tool", "model_driven", "mixed", "not_harnessed")
REASON_CODES = ("stub", "unreachable", "no_methods", "unsafe")
OUTCOMES = ("answered", "proposed", "invalid", "refused", "model_error", "not_harnessed")
LEVELS = providers.LEVELS
MAX_TOOLS = 60
MAX_PURPOSE = 300


class HarnessProblem(ValueError):
    """A harness entry or eval set that does not meet the contract; the message names the agent and the field."""


def manifest_path(department: str, agent: str) -> Path:
    return ROOT / "departments" / department / agent / "manifest.json"


def eval_path(department: str, agent: str) -> Path:
    return ROOT / "evals" / department / f"{agent}.json"


def validate_entry(agent: str, entry: Any) -> List[str]:
    """Structural problems of one harness entry (no code is loaded; semantic checks are in harness_check)."""
    p: List[str] = []
    if not isinstance(entry, dict):
        return [f"{agent}: harness entry missing or not an object"]
    if entry.get("schema") != SCHEMA:
        p.append(f"{agent}: schema must be {SCHEMA}")
    status = entry.get("status")
    if status not in STATUSES:
        p.append(f"{agent}: status must be one of {STATUSES}")
    purpose = entry.get("purpose")
    if not (isinstance(purpose, str) and purpose.strip() and len(purpose) <= MAX_PURPOSE):
        p.append(f"{agent}: purpose must be 1..{MAX_PURPOSE} characters")
    if entry.get("sensitivity") not in LEVELS:
        p.append(f"{agent}: sensitivity must be one of {LEVELS}")
    if entry.get("task_class") not in router.TASK_CLASSES[:3]:
        p.append(f"{agent}: task_class must be one of {router.TASK_CLASSES[:3]}")
    tools = entry.get("tools", {})
    if not (isinstance(tools, dict) and all(isinstance(m, str) and isinstance(v, dict) and v.get("kind") in ("read", "act")
                                           for m, v in tools.items())):
        p.append(f"{agent}: tools must map method -> {{'kind': 'read'|'act'}}")
        tools = {}
    if len(tools) > MAX_TOOLS:
        p.append(f"{agent}: more than {MAX_TOOLS} tools")
    if status == "not_harnessed":
        if tools:
            p.append(f"{agent}: a not_harnessed agent exposes no tools")
        if entry.get("reason_code") not in REASON_CODES or not str(entry.get("reason", "")).strip():
            p.append(f"{agent}: not_harnessed needs reason_code {REASON_CODES} and a reason")
    elif status in STATUSES and not tools:
        p.append(f"{agent}: a harnessed agent exposes at least one tool")
    if not isinstance(entry.get("excluded", {}), dict):
        p.append(f"{agent}: excluded must be an object")
    return p


def _args_ok(v: Any) -> bool:
    return isinstance(v, dict)


def validate_evalset(agent: str, data: Any, tool_names: List[str], status: str) -> List[str]:
    """Problems of one eval set. `tool_names` are the agent's exposed methods (empty for not_harnessed)."""
    p: List[str] = []
    if not isinstance(data, dict) or data.get("schema") != SCHEMA or data.get("agent") != agent:
        return [f"{agent}: eval set must be an object with schema {SCHEMA} and agent '{agent}'"]
    cases = data.get("cases")
    if not isinstance(cases, list) or not cases:
        return [f"{agent}: eval set has no cases"]
    ids = set()
    for c in cases:
        cid = c.get("id") if isinstance(c, dict) else None
        if not (isinstance(cid, str) and cid) or cid in ids:
            p.append(f"{agent}: case ids must be unique non-empty strings ({cid!r})")
            continue
        ids.add(cid)
        where = f"{agent}/{cid}"
        if not (isinstance(c.get("input"), str) and c["input"].strip()):
            p.append(f"{where}: input must be text")
        exp, forb = c.get("expect"), c.get("forbid", {})
        if not isinstance(exp, dict) or not (exp.get("status") or exp.get("calls") or exp.get("answer_contains")):
            p.append(f"{where}: expect must state a status, calls or answer_contains")
            continue
        if exp.get("status") is not None and exp["status"] not in OUTCOMES:
            p.append(f"{where}: expect.status must be one of {OUTCOMES}")
        if status == "not_harnessed" and exp.get("status") != "not_harnessed":
            p.append(f"{where}: a not_harnessed agent's cases must expect status not_harnessed")
        for call in exp.get("calls", []):
            if not (isinstance(call, dict) and call.get("tool") in tool_names and _args_ok(call.get("args", {}))):
                p.append(f"{where}: expect.calls names a tool the agent does not expose ({call})")
        for name in (forb.get("tools", []) if isinstance(forb, dict) else []):
            if not isinstance(name, str):
                p.append(f"{where}: forbid.tools must be names")
        if not isinstance(forb, dict) or not all(isinstance(x, str) for x in forb.get("answer_contains", [])):
            p.append(f"{where}: forbid must be {{'tools': [...], 'answer_contains': [...]}}")
    if status != "not_harnessed" and not any(c.get("forbid") for c in cases if isinstance(c, dict)):
        p.append(f"{agent}: an eval set needs at least one case that states forbidden behaviour")
    return p


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise HarnessProblem(f"{path}: {type(e).__name__}: {e}") from e
