r"""Declared rules over a record: the one evaluator behind the policy, compliance and constraint agents.

A rule states what must hold:

    {"id": "approval-needed", "require": [{"field": "approved_by", "op": "exists"}],
     "when": [{"field": "amount", "op": ">", "value": 50000}],      # optional
     "severity": "high", "message": "large payments need an approver"}

Shorthand for a single unconditional requirement: {"id", "field", "op", "value"}.
A rule applies when every `when` condition holds (no `when` = always); it is
violated when any `require` condition does not hold. A missing field never
satisfies a requirement, and a malformed rule is reported as an error, so
callers can fail closed.

Conditions are list-form conditions of velaris.agentkit.conditions (which also checks
`matches` patterns). Fail closed both ways: a `when` condition that cannot be evaluated
(missing field, wrong type) counts as holding, so the rule applies; a `require` condition
that cannot be evaluated counts as not holding, so it is a violation.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from velaris.agentkit.checks import ident
from velaris.agentkit.conditions import (MAX_MATCH_INPUT, condition_error, holds, op_of,  # noqa: F401 (re-exported)
                                         pattern_error)

SEVERITIES = ("low", "medium", "high", "critical")


def _parts(rule: Dict[str, Any]) -> tuple:
    if "require" in rule or "when" in rule:
        return rule.get("when") or [], rule.get("require") or []
    return [], [{k: rule[k] for k in ("field", "op", "value") if k in rule}]


def rule_error(rule: Any) -> Optional[str]:
    """Why a rule is malformed, or None if it can be evaluated."""
    if not isinstance(rule, dict):
        return "rule must be an object"
    if ident(rule.get("id")) is None:
        return "rule needs an 'id'"
    if rule.get("severity", "medium") not in SEVERITIES:
        return f"severity must be one of {SEVERITIES}"
    when, require = _parts(rule)
    if not isinstance(when, list) or not isinstance(require, list):
        return "'when' and 'require' must be lists of conditions"
    if not require:
        return "rule requires nothing"
    for cond in [*when, *require]:
        err = condition_error(cond)
        if err:
            return err
    return None


def describe(cond: Dict[str, Any]) -> str:
    op = op_of(cond)
    return f"{cond['field']} {op}" + ("" if op in ("exists", "absent") else f" {cond.get('value')!r}")


def evaluate(rules: Any, record: Any) -> Dict[str, Any]:
    """Check `record` against `rules`.

    Returns {"violations": [{id, severity, reason, failed}], "errors": [{id, reason}],
    "checked": n, "skipped": [ids whose `when` did not apply]}. `errors` lists
    rules that could not be evaluated; treat any error as a failure.
    """
    out: Dict[str, Any] = {"violations": [], "errors": [], "checked": 0, "skipped": []}
    if not isinstance(rules, list):
        out["errors"].append({"id": None, "reason": "rules must be a list"})
        return out
    if not isinstance(record, dict):
        out["errors"].append({"id": None, "reason": "the record to check must be an object"})
        return out
    for rule in rules:
        err = rule_error(rule)
        if err:
            out["errors"].append({"id": rule.get("id") if isinstance(rule, dict) else None, "reason": err})
            continue
        when, require = _parts(rule)
        if not all(holds(c, record, "deny") for c in when):      # undecidable: the rule applies
            out["skipped"].append(rule["id"])
            continue
        out["checked"] += 1
        failed = [describe(c) for c in require if not holds(c, record)]
        if failed:
            out["violations"].append({
                "id": rule["id"], "severity": rule.get("severity", "medium"), "failed": failed,
                "reason": rule.get("message") or f"required: {'; '.join(failed)}"})
    return out


def passed(result: Dict[str, Any]) -> bool:
    """True when nothing was violated and every rule could be evaluated (an empty rule list passes: callers decide)."""
    return not result["violations"] and not result["errors"]
