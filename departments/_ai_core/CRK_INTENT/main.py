"""CRK intent: names what a short request is asking for, from a fixed list of intents.

Keyword rules decide first. Only when no rule (or more than one) matches is a
language model asked, through velaris.intel.llm; its answer is accepted only if
it is one of the allowed intent names. With no model available the result is
"not_configured" with the tied candidates, never a guess. Requests containing
instruction-like text are refused before any of that.
A model is used when one is passed in or VELARIS_MODEL is set.
"""
import logging
import os
import re

from velaris.agentkit.results import fail, health, invalid, ok
from velaris.intel import guard
from velaris.intel.llm import LLM, LLMError, extract_json

NAME = "CRK_INTENT"
logger = logging.getLogger(NAME)

INTENTS = {
    "approve": ["approve", "approval", "sign off", "authorise", "authorize"],
    "reject": ["reject", "decline", "deny"],
    "create": ["create", "add", "new", "raise", "open"],
    "update": ["update", "change", "edit", "amend", "modify"],
    "cancel": ["cancel", "delete", "remove", "withdraw"],
    "report": ["report", "summary", "summarise", "summarize", "status", "show", "list"],
    "escalate": ["escalate", "urgent", "complaint"],
}
MAX_CHARS = 4000


class CRK_INTENTAgent:
    def __init__(self, name=NAME, intents=None, llm=None):
        self.name = name
        self.intents = intents if isinstance(intents, dict) and intents else INTENTS
        self._llm = llm

    def health_check(self):
        return health(self.name, model="available" if self._model() else "not_configured")

    def _model(self):
        if self._llm is not None:
            return self._llm
        return LLM() if os.environ.get("VELARIS_MODEL") else None

    def _rule_hits(self, text):
        lowered = text.lower()
        hits = {}
        for intent, words in self.intents.items():
            found = [w for w in words if re.search(rf"\b{re.escape(str(w).lower())}\b", lowered)]
            if found:
                hits[intent] = found
        return hits

    def classify(self, text):
        """Returns {"status", "intent", "method", ...}. `intent` is None unless status is ok."""
        if not isinstance(text, str) or not text.strip():
            return invalid("text must be a non-empty string", intent=None)
        if len(text) > MAX_CHARS:
            return invalid(f"text is longer than {MAX_CHARS} characters", intent=None)
        scan = guard.scan(text, source=NAME)
        if scan.blocked:
            return fail("blocked", "the request contains instruction-like text", intent=None,
                        findings=[f["rule"] for f in scan.findings])
        hits = self._rule_hits(text)
        best = max((len(v) for v in hits.values()), default=0)
        leaders = sorted(i for i, v in hits.items() if len(v) == best)
        if len(leaders) == 1:
            return ok(intent=leaders[0], method="rules", matched=hits[leaders[0]], candidates=leaders)
        llm = self._model()
        if llm is None:
            return fail("not_configured", "keyword rules were inconclusive and no model is configured",
                        intent=None, candidates=leaders)
        return self._ask(llm, text, leaders)

    def _ask(self, llm, text, leaders):
        redacted, _ = guard.redact(text)
        preamble, fenced = guard.wrap(redacted, label="a request from a user")
        allowed = sorted(self.intents)
        prompt = (f"{preamble}\n\nChoose the one intent from {allowed} that best names what the request "
                  f'asks for. Reply with JSON only: {{"intent": "<name>"}}. If none fits reply '
                  f'{{"intent": null}}.\n\n{fenced}')
        try:
            reply = extract_json(llm.complete(prompt, purpose="crk_intent", max_tokens=50, temperature=0.0).text)
        except LLMError as e:
            logger.warning("intent model call failed: %s", e)
            return fail("model_error", str(e), intent=None, candidates=leaders)
        choice = reply.get("intent") if isinstance(reply, dict) else None
        if choice not in self.intents:          # code decides: anything off the list is not an answer
            return fail("unresolved", "the model did not return an allowed intent", intent=None,
                        candidates=leaders)
        return ok(intent=choice, method="model", matched=[], candidates=leaders)
