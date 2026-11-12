"""ACF context: wraps a raw input in a screened envelope before anything acts on it.

contextualize(x) accepts text or an object and returns a signal with its kind,
a fingerprint (for de-duplication), the guard risk level, and text with
personal identifiers and secrets masked. Caller-supplied context (source,
actor, tenant, ...) is attached as given. Text that the guard blocks as an
injection attempt is not contextualised: the result says "blocked".
"""
import hashlib
import json
import time

from velaris.agentkit.aicore_a_common import fail, health
from velaris.intel import guard

NAME = "ACF_CONTEXT"
LEVELS = ("none", "low", "high", "block")


class ACFContextAgent:
    def health_check(self):
        return health(NAME)

    def _screen(self, value, findings, redactions):
        """Redact every string in a JSON-like value; return (clean value, worst risk level)."""
        if isinstance(value, str):
            scan = guard.scan(value, source=NAME)
            findings.extend(f["rule"] for f in scan.findings)
            clean, counts = guard.redact(value)
            for kind, n in counts.items():
                redactions[kind] = redactions.get(kind, 0) + n
            return clean, scan.level
        if isinstance(value, dict):
            pairs = {str(k): self._screen(v, findings, redactions) for k, v in value.items()}
        elif isinstance(value, (list, tuple)):
            pairs = dict(enumerate(self._screen(v, findings, redactions) for v in value))
        else:
            return value, "none"
        worst = max((lvl for _, lvl in pairs.values()), key=LEVELS.index, default="none")
        clean = [v for v, _ in pairs.values()]
        return (dict(zip(pairs, clean)) if isinstance(value, dict) else clean), worst

    def contextualize(self, x, context=None, now=None):
        if not isinstance(x, (str, dict)) or not x or (isinstance(x, str) and not x.strip()):
            return fail("invalid_input", "input must be non-empty text or a non-empty object",
                        contextualized=False, input=x)
        if context is not None and not isinstance(context, dict):
            return fail("invalid_input", "context must be an object", contextualized=False, input=x)
        findings, redactions = [], {}
        content, risk = self._screen(x, findings, redactions)
        if risk == "block":
            return fail("blocked", "instruction-like content: " + ", ".join(sorted(set(findings))),
                        contextualized=False, risk=risk, findings=sorted(set(findings)))
        canonical = json.dumps(x, sort_keys=True, default=str)
        signal = {"kind": "text" if isinstance(x, str) else "record", "content": content,
                  "fingerprint": hashlib.sha256(canonical.encode()).hexdigest(),
                  "received_at": time.time() if now is None else now,
                  "risk": risk, "redactions": redactions, "context": dict(context or {})}
        return {"status": "ok", "contextualized": True, "signal": signal, "input": content}
