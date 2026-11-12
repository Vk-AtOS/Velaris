"""CSM policy: builds a checkable policy from a short specification, and checks records against it.

generate_policy() takes {"name", "required": [fields], "limits": {field:
{"min"?, "max"?}}, "allowed": {field: [values]}} and returns explicit rules
with a version fingerprint. check() applies a generated policy to a record and
lists every violation. A specification with no rules is rejected, and a record
checked against something that is not a generated policy is non-compliant.
"""
import hashlib
import json

from velaris.agentkit.aicore_a_common import dig, fail, health, ident, number

NAME = "CSM_POLICY"


class CSMPolicyAgent:
    def health_check(self):
        return health(NAME)

    def generate_policy(self, x):
        def reject(reason):
            return fail("invalid_input", reason, policy="rejected", rules=[], base=x)
        if not isinstance(x, dict) or ident(x.get("name")) is None:
            return reject("need a specification object with a 'name'")
        required, limits, allowed = x.get("required", []), x.get("limits", {}), x.get("allowed", {})
        if not isinstance(required, list) or not all(ident(f) for f in required):
            return reject("'required' must be a list of field names")
        if not isinstance(limits, dict) or not isinstance(allowed, dict):
            return reject("'limits' and 'allowed' must be objects")
        rules = [{"field": f, "check": "required"} for f in sorted(set(required))]
        for field in sorted(limits):
            spec = limits[field]
            bounds = {b: number(spec.get(b)) for b in ("min", "max") if isinstance(spec, dict) and b in spec}
            if not bounds or None in bounds.values() or bounds.get("min", float("-inf")) > bounds.get("max", float("inf")):
                return reject(f"limit for {field!r} needs a numeric min and/or max, with min <= max")
            rules.append({"field": field, "check": "range", **bounds})
        for field in sorted(allowed):
            if not isinstance(allowed[field], list) or not allowed[field]:
                return reject(f"allowed values for {field!r} must be a non-empty list")
            rules.append({"field": field, "check": "allowed", "values": allowed[field]})
        if not rules:
            return reject("the specification defines no rules")
        for i, rule in enumerate(rules, start=1):
            rule["id"] = f"{x['name']}-{i}"
        version = hashlib.sha256(json.dumps(rules, sort_keys=True, default=str).encode()).hexdigest()[:12]
        return {"status": "ok", "policy": "generated", "name": x["name"], "version": version, "rules": rules, "base": x}

    def check(self, policy, record):
        """Returns compliant and the violations. Range and allowed rules apply only when the field is present."""
        rules = policy.get("rules") if isinstance(policy, dict) and policy.get("policy") == "generated" else None
        if not rules or not isinstance(record, dict):
            return fail("invalid_input", "need a generated policy and a record object", compliant=False, violations=[])
        violations = []
        for rule in rules:
            found, value = dig(record, rule["field"])
            if rule["check"] == "required":
                problem = None if found and value not in (None, "") else "is required"
            elif not found:
                problem = None
            elif rule["check"] == "range":
                n = number(value)
                low, high = rule.get("min", float("-inf")), rule.get("max", float("inf"))
                problem = "must be a number" if n is None else None if low <= n <= high else f"{n} is outside {low}..{high}"
            else:
                problem = None if value in rule["values"] else f"{value!r} is not an allowed value"
            if problem:
                violations.append({"rule": rule["id"], "field": rule["field"], "problem": problem})
        return {"status": "ok", "compliant": not violations, "violations": violations,
                "policy": policy.get("name"), "version": policy.get("version")}
