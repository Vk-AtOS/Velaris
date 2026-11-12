"""EACPE_ALIGNMENT: is a proposed action inside the mandate its agent was given?

A mandate is declared per agent: the action classes it may take, a spending
limit, and targets it must never touch. align(inputs) checks one proposal,
{"agent", "action_class", "amount"?, "target"?, "text"?}:

  1. mandate (deterministic): the agent has a mandate, the class is in it, the
     amount is within the limit, the target is not prohibited.
  2. principles (only when the proposal carries free text and principles are
     declared): the text is screened by velaris.intel.guard (blocked = not
     aligned); a model then reports, per principle, "consistent", "conflicts" or
     "unclear" through velaris.intel.llm. Code checks that every principle got
     exactly one of those verdicts; anything else counts as not aligned.

aligned is True only if the mandate holds and, where principles are declared,
a review ran and every principle is "consistent" (principles declared but no text
to review: not aligned, status "needs_text"). Prohibited targets are compared after
Unicode NFKC normalisation, case-folding and trimming, on both sides. Mandates and
principles are set by a governance admin only (velaris.core.access). With text to review and no model reachable, the
answer is "not_configured" and aligned is False: no judgement is invented.
"""
from __future__ import annotations

import unicodedata
from typing import Any, Dict, List, Optional

from velaris.agentkit.infra_store import State, invalid, is_name, is_number, ok
from velaris.core.access import GOVERNANCE_ADMINS, check_caller
from velaris.intel import guard
from velaris.intel.llm import LLM, LLMError, extract_json

NAME = "EACPE_ALIGNMENT"
VERDICTS = ("consistent", "conflicts", "unclear")


def _norm(target: str) -> str:
    """The form targets are compared in: "V-13", " v\u201113 " and full-width "\uff36-13" are one target."""
    return unicodedata.normalize("NFKC", target).casefold().strip()


class EACPE_ALIGNMENTAgent:
    def __init__(self, llm: Optional[LLM] = None) -> None:
        self.name = NAME
        self.llm = llm
        self._state = State(NAME)

    def health_check(self) -> Dict[str, Any]:
        return {"agent": NAME, "status": "ok", "version": "1.0.0"}

    def set_mandate(self, agent: str, action_classes: List[str], max_amount: float = 0.0,
                    prohibited_targets: Optional[List[str]] = None) -> Dict[str, Any]:
        targets = prohibited_targets or []
        if not is_name(agent) or not isinstance(action_classes, list) or not all(is_name(c) for c in action_classes):
            return invalid("need an agent name and a list of action classes")
        if not is_number(max_amount, 0) or not isinstance(targets, list) or not all(isinstance(t, str) for t in targets):
            return invalid("max_amount must be >= 0 and prohibited_targets a list of text")
        _, refused = check_caller(NAME, "set_mandate", {"agent": agent}, roles=GOVERNANCE_ADMINS)
        if refused:
            return refused
        mandate = {"classes": action_classes, "max_amount": max_amount, "prohibited": [_norm(t) for t in targets]}
        self._state.change(lambda d: d.setdefault("mandates", {}).__setitem__(agent, mandate))
        return ok(agent=agent, **mandate)

    def set_principles(self, principles: List[str]) -> Dict[str, Any]:
        if not isinstance(principles, list) or not all(isinstance(p, str) and p.strip() for p in principles) \
                or len(principles) > 20:
            return invalid("principles must be a list of up to 20 statements")
        _, refused = check_caller(NAME, "set_principles", {"count": len(principles)}, roles=GOVERNANCE_ADMINS)
        if refused:
            return refused
        self._state.change(lambda d: d.__setitem__("principles", principles))
        return ok(principles=len(principles))

    def _review(self, text: str, principles: List[str]) -> Dict[str, Any]:
        scan = guard.scan(text, source=NAME)
        if scan.blocked:
            return {"status": "refused", "reason": "proposal text was blocked by the guard", "verdicts": {}}
        preamble, block = guard.wrap(text[:6000], label="a proposed action")
        listing = "\n".join(f"{i}: {p}" for i, p in enumerate(principles))
        prompt = (f"{preamble}\n\n{block}\n\nPrinciples:\n{listing}\n\nFor each principle, say whether the proposed "
                  f"action is consistent with it, conflicts with it, or it is unclear. Reply with JSON only: "
                  '{"verdicts": {"0": "consistent|conflicts|unclear", ...}}')
        try:
            reply = extract_json((self.llm or LLM()).complete(prompt, max_tokens=300, temperature=0.0,
                                                               purpose="alignment.review").text)
        except LLMError as e:
            return {"status": "not_configured", "reason": f"no model available: {str(e)[:120]}", "verdicts": {}}
        raw = reply.get("verdicts") if isinstance(reply, dict) else None
        expected = {str(i) for i in range(len(principles))}
        if not isinstance(raw, dict) or set(raw) != expected or not all(v in VERDICTS for v in raw.values()):
            return {"status": "model_error", "reason": "the model's verdicts did not cover every principle validly",
                    "verdicts": {}}
        return {"status": "ok", "verdicts": {principles[int(i)]: v for i, v in sorted(raw.items(), key=lambda kv: int(kv[0]))}}

    def align(self, inputs: dict) -> Dict[str, Any]:
        def no(status: str, reason: str, **extra: Any) -> Dict[str, Any]:
            return {"aligned": False, "details": inputs, "status": status, "reason": reason, **extra}
        if not isinstance(inputs, dict) or not is_name(inputs.get("agent")) or not is_name(inputs.get("action_class")):
            return no("invalid_input", "need {'agent': ..., 'action_class': ...}")
        amount, target, text = inputs.get("amount", 0), inputs.get("target"), inputs.get("text")
        if not is_number(amount, 0) or (target is not None and not isinstance(target, str)) or \
                (text is not None and not isinstance(text, str)):
            return no("invalid_input", "amount must be >= 0, target and text must be text")
        data = self._state.load()
        mandate = data.get("mandates", {}).get(inputs["agent"])
        if mandate is None:
            return no("no_mandate", "this agent has no declared mandate")
        if inputs["action_class"] not in mandate["classes"]:
            return no("outside_mandate", f"{inputs['action_class']} is not in this agent's mandate")
        if amount > mandate["max_amount"]:
            return no("outside_mandate", f"amount {amount} is above the limit {mandate['max_amount']}")
        if target is not None and _norm(target) in {_norm(t) for t in mandate["prohibited"]}:
            return no("outside_mandate", f"{target} is a prohibited target")
        principles = data.get("principles", [])
        if principles and (not text or not text.strip()):
            return no("needs_text", "principles are declared, so the proposal needs text to review")
        if not principles:
            return {"aligned": True, "details": inputs, "status": "ok", "reason": "within mandate", "review": None}
        review = self._review(text, principles)
        if review["status"] != "ok":
            return no(review["status"], review["reason"], review=review)
        conflicts = [p for p, v in review["verdicts"].items() if v != "consistent"]
        if conflicts:
            return no("ok", "not consistent with: " + "; ".join(conflicts), review=review)
        return {"aligned": True, "details": inputs, "status": "ok", "reason": "within mandate and principles",
                "review": review}
