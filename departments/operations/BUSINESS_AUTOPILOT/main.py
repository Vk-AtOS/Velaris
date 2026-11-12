"""BUSINESS_AUTOPILOT: threshold rules over business metrics that PROPOSE actions.

Despite the name, nothing here acts on its own. The agent keeps a list of rules
("when overdue_invoices > 5, propose: chase overdue invoices"), evaluates them
against the metrics the caller supplies, and returns the actions whose rule
fired, each with the reading that fired it and `requires_approval: True`.
It executes nothing and calls no other system.

run(payload):
  {"rules": [{"id", "metric", "op", "threshold", "action"}, ...]}   replace the stored rules
  {"metrics": {"overdue_invoices": 7, ...}}                         evaluate the stored rules
  both keys together: store, then evaluate.

op is one of > >= < <= ==. A rule whose metric is absent is reported as not
evaluated, never assumed. State: <VELARIS_DATA>/agents/BUSINESS_AUTOPILOT/rules.json.
"""
import logging
import operator
from typing import Any, Dict, List

from velaris.agentkit import biz_common as kit
from velaris.intel.paths import agent_dir

logger = logging.getLogger("BUSINESS_AUTOPILOT")
OPS = {">": operator.gt, ">=": operator.ge, "<": operator.lt, "<=": operator.le, "==": operator.eq}
MAX_RULES = 200


def _rule_errors(rules: Any) -> List[str]:
    if not isinstance(rules, (list, tuple)) or len(rules) > MAX_RULES:
        return [f"rules must be a list of at most {MAX_RULES} rules"]
    errors, seen = [], set()
    for i, r in enumerate(rules):
        if not isinstance(r, dict):
            errors.append(f"rules[{i}] must be an object")
            continue
        rid = kit.text(r.get("id"), 80)
        if rid is None or rid in seen:
            errors.append(f"rules[{i}].id must be a unique non-empty string")
        seen.add(rid)
        if kit.text(r.get("metric"), 80) is None:
            errors.append(f"rules[{i}].metric must be a non-empty string")
        if not isinstance(r.get("op"), str) or r["op"] not in OPS:
            errors.append(f"rules[{i}].op must be one of {sorted(OPS)}")
        if kit.number(r.get("threshold")) is None:
            errors.append(f"rules[{i}].threshold must be a finite number")
        if kit.text(r.get("action"), 500) is None:
            errors.append(f"rules[{i}].action must be a non-empty string")
    return errors


class BusinessAutopilotAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.version = (config or {}).get("version", kit.VERSION)
        self._state = kit.JsonState(lambda: agent_dir("BUSINESS_AUTOPILOT") / "rules.json", {"rules": []})

    def health_check(self) -> Dict[str, Any]:
        return {"agent": "BUSINESS_AUTOPILOT", "status": "ok", "version": self.version}

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(payload, dict) or not ({"rules", "metrics"} & set(payload)):
            return kit.failed(["payload must be an object with 'rules' and/or 'metrics'"])
        errors = _rule_errors(payload["rules"]) if "rules" in payload else []
        metrics = payload.get("metrics")
        if "metrics" in payload and (not isinstance(metrics, dict) or any(
                not isinstance(k, str) or kit.number(v) is None for k, v in metrics.items())):
            errors.append("metrics must map metric names to finite numbers")
        if errors:
            return kit.failed(errors)
        data = self._state.load()
        if "rules" in payload:
            data["rules"] = [{k: r[k] for k in ("id", "metric", "op", "threshold", "action")}
                             for r in payload["rules"]]
            self._state.save(data)
        if "metrics" not in payload:
            return {"status": "ok", "rules_stored": len(data["rules"]), "proposals": [], "executed": []}
        if not data["rules"]:
            return kit.needs_data("no rules are stored; send 'rules' first", proposals=[], executed=[])
        proposals, quiet, skipped = [], [], []
        for r in data["rules"]:
            if r["metric"] not in metrics:
                skipped.append({"rule": r["id"], "reason": f"metric '{r['metric']}' not supplied"})
            elif OPS[r["op"]](metrics[r["metric"]], r["threshold"]):
                proposals.append({"rule": r["id"], "action": r["action"], "requires_approval": True,
                                  "evidence": f"{r['metric']} = {metrics[r['metric']]} {r['op']} {r['threshold']}"})
            else:
                quiet.append(r["id"])
        return {"status": "ok", "proposals": proposals, "rules_not_fired": quiet, "rules_not_evaluated": skipped,
                "executed": [], "note": "Proposals only. Nothing is carried out without a person's approval."}
