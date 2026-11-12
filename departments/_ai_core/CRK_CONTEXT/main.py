"""CRK context: turns raw facts into a screened fact set that rules can safely run on.

Each fact is {"key", "value", "source"}. Text values are scanned for
instruction-like content (velaris.intel.guard): blocked text is dropped, and
personal identifiers and secrets are masked. Two different values for one key
are reported as a conflict (the first is kept), and facts beyond the size
budget are listed as truncated instead of silently lost.
"""
import json

from velaris.agentkit.checks import ident
from velaris.agentkit.results import health, invalid, ok
from velaris.intel import guard

NAME = "CRK_CONTEXT"


class CRK_CONTEXTAgent:
    def __init__(self, name=NAME, budget_chars=8000):
        self.name = name
        self.budget_chars = budget_chars

    def health_check(self):
        return health(self.name)

    def build(self, facts):
        """Returns facts ({key: {"value", "source", "risk"}}), values ({key: value}) and what was left out."""
        if not isinstance(facts, list):
            return invalid("facts must be a list of {key, value, source}")
        kept, dropped, conflicts, truncated, redactions, used = {}, [], [], [], {}, 0
        for fact in facts:
            key = ident(fact.get("key")) if isinstance(fact, dict) else None
            if key is None or "value" not in fact:
                dropped.append({"fact": fact, "reason": "needs a 'key' and a 'value'"})
                continue
            value, source, risk = fact["value"], str(fact.get("source") or "unknown"), "none"
            if isinstance(value, str):
                scan = guard.scan(value, source=f"CRK_CONTEXT:{source}")
                if scan.blocked:
                    dropped.append({"fact": key, "reason": "instruction-like text: "
                                    + ", ".join(f["rule"] for f in scan.findings)})
                    continue
                risk = scan.level
                value, counts = guard.redact(value)
                for kind, n in counts.items():
                    redactions[kind] = redactions.get(kind, 0) + n
            if key in kept:
                if kept[key]["value"] != value:
                    conflicts.append({"key": key, "kept": kept[key]["source"], "ignored": source})
                continue
            size = len(json.dumps(value, default=str))
            if used + size > self.budget_chars:
                truncated.append(key)
                continue
            used += size
            kept[key] = {"value": value, "source": source, "risk": risk}
        return ok(facts=kept, values={k: v["value"] for k, v in kept.items()}, dropped=dropped,
                  conflicts=conflicts, truncated=truncated, redactions=redactions)
