"""UIE_SIGNAL: first contact with an incoming message, before anything tries to interpret it.

UIE is read here as "user input engine": UIE_SIGNAL cleans and screens a raw
message, UIE_SEMANTICS turns it into a structured request, UIE_REASONER
decides the next step, UIE_CORE runs the three.

process(signal) takes text or {"text", "channel", "sender"}. It folds
look-alike and invisible characters, collapses whitespace, scans for text
that tries to instruct a model (velaris.intel.guard) and refuses the message
if the scan says block. It returns the clean text, a copy with secrets and
personal identifiers masked ("safe_text": the only version that should be
stored or shown to a model), and what was found.
"""
from typing import Any, Dict

from velaris.agentkit import aicore_b_text as textkit
from velaris.agentkit.checks import MAX_TEXT
from velaris.agentkit.results import health
from velaris.intel import guard

NAME = "UIE_SIGNAL"


def _masked_copy(signal: Any) -> Any:
    """The signal with secrets and personal identifiers masked, for echoing back in a result."""
    if isinstance(signal, str):
        return guard.redact(signal)[0]
    if isinstance(signal, dict):
        return {k: (guard.redact(v)[0] if isinstance(v, str) else v) for k, v in signal.items()}
    return signal


class UIESignalAgent:
    def health_check(self):
        return health(NAME)

    def process(self, signal: Any) -> Dict[str, Any]:
        base = {"processed": False, "signal": _masked_copy(signal)}
        meta = signal if isinstance(signal, dict) else {}
        raw = meta.get("text") if isinstance(signal, dict) else signal
        if not isinstance(raw, str) or not raw.strip():
            return {**base, "status": "invalid_input", "reason": "a signal is text or {'text': ...}"}
        if len(raw) > MAX_TEXT:
            return {**base, "status": "invalid_input", "reason": f"text longer than {MAX_TEXT} characters"}
        scan = guard.scan(raw, source=f"uie:{meta.get('channel', 'unknown')}")
        findings = [f["rule"] for f in scan.findings]
        if scan.blocked:
            return {**base, "status": "blocked", "risk": scan.level, "findings": findings,
                    "reason": "the message looks like an attempt to instruct a model"}
        clean = textkit.clean(raw)
        safe, pii = guard.redact(clean)
        return {"processed": True, "status": "ok", "signal": _masked_copy(signal), "text": clean, "safe_text": safe,
                "pii": pii, "risk": scan.level, "findings": findings,
                "channel": meta.get("channel"), "sender": meta.get("sender"), "chars": len(clean)}
