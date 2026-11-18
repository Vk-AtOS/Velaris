"""POLICY_CONTROLLER: a versioned policy store with a deterministic decision that names its rule.

put_policy(pid, policy) stores a new version of a policy; nothing is overwritten,
so every earlier version stays readable and evaluate() can be re-run as of any
earlier revision of the policy set. A policy that has an "effect" is a rule:

    {"effect": "allow" | "deny", "priority": int (default 0), "when": {conditions}}

with conditions as in velaris.agentkit.conditions (an absent field never
matches an allow rule and always matches a deny rule). A policy without "effect" is stored as a plain document and takes no
part in decisions. A rule-shaped policy that is malformed is refused at write time.

evaluate(context) orders the active rules by priority (highest first), then deny
before allow, then id, and the first rule whose conditions all hold decides. If
none holds, the answer is deny by the implicit "default_deny" rule. The result
always names the deciding rule, its version and the policy-set revision.

put_policy() and retire() are for governance admins only, and a change that cannot be written to the trace is not made (audit_failed); who made a change is the
current caller (velaris.core.access), never an argument.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from velaris.agentkit import conditions
from velaris.agentkit.checks import is_json, is_name, is_number
from velaris.agentkit.results import fail, invalid, ok
from velaris.agentkit.state import JsonState
from velaris.agentkit.infra_store import audit
from velaris.core.access import GOVERNANCE_ADMINS, check_caller

NAME = "POLICY_CONTROLLER"
RULE_FIELDS = ("effect", "priority", "when", "description")


def rule_problems(policy: Dict[str, Any]) -> List[str]:
    if "effect" not in policy:
        return []
    problems = [f"unknown rule field {k}" for k in policy if k not in RULE_FIELDS]
    if policy["effect"] not in ("allow", "deny"):
        problems.append("effect must be 'allow' or 'deny'")
    priority = policy.get("priority", 0)
    if not is_number(priority, -1000000, 1000000) or isinstance(priority, float):
        problems.append("priority must be a whole number")
    return problems + conditions.problems(policy.get("when", {}))


class POLICY_CONTROLLERAgent:
    def __init__(self) -> None:
        self.name = NAME
        self._state = JsonState(NAME, "policies.json")

    def health_check(self) -> Dict[str, Any]:
        return {"agent": self.name, "status": "ok", "version": "1.0.0"}

    @property
    def store(self) -> Dict[str, Any]:
        """{pid: current policy} for every policy that has not been retired."""
        return {pid: versions[-1]["policy"] for pid, versions in self._state.load().get("policies", {}).items()
                if versions[-1]["policy"] is not None}

    def _write(self, pid: str, policy: Optional[Dict[str, Any]], by: str) -> Dict[str, Any]:
        def add(data: Dict[str, Any]) -> Dict[str, Any]:
            versions = data.setdefault("policies", {}).get(pid, [])
            if policy is None and (not versions or versions[-1]["policy"] is None):
                return fail("unknown_policy", "no active policy with this id")
            if not audit(NAME, "policy.retire" if policy is None else "policy.put",
                         {"policy_id": pid, "version": len(versions) + 1, "by": by}):
                return fail("audit_failed", "the change could not be recorded, so it was not made")    # no trace, no new rule
            data["policies"][pid] = versions
            data["rev"] = data.get("rev", 0) + 1
            versions.append({"version": len(versions) + 1, "rev": data["rev"], "policy": policy, "by": by,
                             "ts": time.time()})
            return ok(policy_id=pid, version=len(versions), rev=data["rev"])
        return self._state.update(add)

    def put_policy(self, pid: str, policy: Dict[str, Any], by: Optional[str] = None) -> Dict[str, Any]:
        """Store a new version of a policy, as the current caller (a governance admin)."""
        if not is_name(pid):
            return invalid("policy id must be a short name")
        if not isinstance(policy, dict) or not is_json(policy):
            return invalid("policy must be a JSON object")
        problems = rule_problems(policy)
        if problems:
            return invalid("; ".join(problems))
        caller, refused = check_caller(NAME, "put_policy", {"policy_id": pid}, roles=GOVERNANCE_ADMINS, claimed=by)
        return refused or self._write(pid, policy, caller.id)

    def retire(self, pid: str, by: Optional[str] = None) -> Dict[str, Any]:
        """Stop a policy taking part (its history is kept). Governance admins only."""
        if not isinstance(pid, str):
            return invalid("policy id must be a name")
        caller, refused = check_caller(NAME, "retire", {"policy_id": pid}, roles=GOVERNANCE_ADMINS, claimed=by)
        return refused or self._write(pid, None, caller.id)

    def get_policy(self, pid: str, version: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """The current policy (or a given version); None if absent, retired or the version does not exist."""
        versions = self._state.load().get("policies", {}).get(pid, []) if isinstance(pid, str) else []
        if version is None:
            return versions[-1]["policy"] if versions else None
        if not isinstance(version, int) or isinstance(version, bool) or not 1 <= version <= len(versions):
            return None
        return versions[version - 1]["policy"]

    def history(self, pid: str) -> List[Dict[str, Any]]:
        return list(self._state.load().get("policies", {}).get(pid, [])) if isinstance(pid, str) else []

    def evaluate(self, context: Dict[str, Any], at_rev: Optional[int] = None) -> Dict[str, Any]:
        """Decide for `context` with the rules active now, or as they stood at revision `at_rev`."""
        if not isinstance(context, dict):
            return {**invalid("context must be an object"), "decision": "deny", "rule": None}
        if at_rev is not None and (not is_number(at_rev, 0) or isinstance(at_rev, float)):
            return {**invalid("at_rev must be a whole number >= 0"), "decision": "deny", "rule": None}
        data = self._state.load()
        rev = data.get("rev", 0) if at_rev is None else min(at_rev, data.get("rev", 0))
        rules = []
        for pid, versions in data.get("policies", {}).items():
            current = [v for v in versions if v["rev"] <= rev]
            if current and current[-1]["policy"] is not None and "effect" in current[-1]["policy"]:
                rules.append((pid, current[-1]))
        rules.sort(key=lambda r: (-r[1]["policy"].get("priority", 0), r[1]["policy"]["effect"] != "deny", r[0]))
        for pid, v in rules:
            if conditions.evaluate(v["policy"].get("when", {}), context, v["policy"]["effect"])[0]:
                return ok(decision=v["policy"]["effect"], allowed=v["policy"]["effect"] == "allow", rule=pid,
                          rule_version=v["version"], rev=rev, considered=len(rules))
        return ok(decision="deny", allowed=False, rule="default_deny", rule_version=None, rev=rev, considered=len(rules))
