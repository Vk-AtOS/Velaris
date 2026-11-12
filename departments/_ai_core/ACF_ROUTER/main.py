"""ACF router: sends a signal to a destination by declared rules.

A rule is {"id", "if": [conditions], "to": destination, "priority"?}. The
highest-priority rule whose conditions all hold wins (id breaks ties). A signal
no rule matches goes to the default destination ("triage" unless configured
otherwise; None means such signals are refused). A signal the guard blocks, or
an ACF_CONTEXT result that was blocked, is quarantined and never routed.
Conditions read the signal's fields, e.g. "kind", "risk", "content.amount",
"context.source".
"""
from velaris.agentkit.aicore_a_common import condition_error, fail, health, holds, ident, number
from velaris.intel import guard

NAME = "ACF_ROUTER"


class ACFRouterAgent:
    def __init__(self, rules=None, default_destination="triage"):
        self.rules, self.default_destination = [], default_destination
        self.config_error = self.set_rules(rules or []).get("reason")

    def health_check(self):
        return health(NAME, rules=len(self.rules))

    def set_rules(self, rules):
        """Replace the rule set. A malformed rule rejects the whole set and leaves the old one in place."""
        if not isinstance(rules, list):
            return fail("invalid_input", "rules must be a list")
        seen = set()
        for rule in rules:
            rid = ident(rule.get("id")) if isinstance(rule, dict) else None
            if rid is None or rid in seen or ident(rule.get("to")) is None:
                return fail("invalid_input", f"rule {rule!r} needs a unique 'id' and a 'to' destination")
            if not isinstance(rule.get("if"), list) or number(rule.get("priority", 0)) is None:
                return fail("invalid_input", f"rule {rid}: 'if' must be a list and 'priority' a number")
            for cond in rule["if"]:
                problem = condition_error(cond)
                if problem:
                    return fail("invalid_input", f"rule {rid}: {problem}")
            seen.add(rid)
        self.rules = sorted(rules, key=lambda r: (-r.get("priority", 0), r["id"]))
        return {"status": "ok", "rules": len(self.rules)}

    def route(self, signal):
        """Accepts raw text, a signal object, or an ACF_CONTEXT.contextualize() result."""
        def refuse(status, reason, destination=None):
            return fail(status, reason, routed=False, destination=destination, rule=None, signal=signal)
        if self.config_error:
            return refuse("not_configured", f"router rules were rejected: {self.config_error}")
        subject = signal
        if isinstance(signal, dict) and "contextualized" in signal:
            if not signal["contextualized"]:
                return refuse("quarantined", "the signal was not accepted by ACF_CONTEXT", "quarantine")
            subject = signal.get("signal")
        if isinstance(subject, str) and subject.strip():
            if guard.scan(subject, source=NAME).blocked:
                return refuse("quarantined", "instruction-like content", "quarantine")
            subject = {"kind": "text", "content": subject}
        if not isinstance(subject, dict) or not subject:
            return refuse("invalid_input", "signal must be non-empty text or an object")
        if subject.get("risk") == "block":
            return refuse("quarantined", "signal is marked as blocked", "quarantine")
        rule = next((r for r in self.rules if all(holds(c, subject) for c in r["if"])), None)
        if rule is None and self.default_destination is None:
            return refuse("unrouted", "no rule matched and no default destination is configured")
        return {"status": "ok", "routed": True, "destination": rule["to"] if rule else self.default_destination,
                "rule": rule["id"] if rule else None, "default": rule is None, "signal": signal}
