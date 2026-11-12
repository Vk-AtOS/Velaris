"""INTENT_SYNTHESIZER: turns a loosely worded idea into a structured intent that can be planned.

synthesize(idea) takes text, or an object carrying text under "idea", "goal",
"request" or "text", and returns an intent:
  goal, action, object, risk     from the request frame (velaris.agentkit.aicore_b_text)
  constraints                    budget (first amount), deadline (first date), references
  missing                        what a planner would still need: action, object
  complete                       True when nothing is missing

That part is word lists and patterns. If a model is passed in, it is asked
only to restate the goal in one sentence and to propose success criteria; the
reply is accepted only as short strings and is labelled "proposed_by_model".
The model never fills in action, amounts or dates.
"""
from typing import Any, Dict, Optional

from velaris.agentkit import aicore_b_text as textkit
from velaris.agentkit.checks import text as as_text
from velaris.agentkit.models import ask_json
from velaris.agentkit.results import health
from velaris.intel.llm import LLM

NAME = "INTENT_SYNTHESIZER"
_TEXT_KEYS = ("idea", "goal", "request", "text")
MAX_CRITERIA, MAX_CRITERION_CHARS = 5, 200


class IntentSynthesizer:
    def __init__(self, name=NAME):
        self.name = name

    def health_check(self):
        return health(self.name)

    def synthesize(self, idea: Any, llm: Optional[LLM] = None) -> Dict[str, Any]:
        source = idea
        if isinstance(idea, dict):
            source = next((idea[k] for k in _TEXT_KEYS if isinstance(idea.get(k), str)), None)
        body = as_text(source)
        if body is None:
            return {"intent": None, "source": idea, "status": "invalid_input",
                    "reason": f"expected text, or an object with text under one of {_TEXT_KEYS}"}
        frame = textkit.frame(body)
        found = frame["entities"]
        missing = [k for k in ("action", "object") if not frame[k]]
        intent: Dict[str, Any] = {
            "goal": frame["text"], "action": frame["action"], "object": frame["object"], "risk": frame["risk"],
            "constraints": {"budget": found["amounts"][0] if found["amounts"] else None,
                            "deadline": found["dates"][0] if found["dates"] else None,
                            "references": found["references"]},
            "urgent": frame["urgent"], "missing": missing, "complete": not missing,
        }
        result = {"intent": intent, "source": idea, "status": "ok" if not missing else "incomplete"}
        if llm is None:
            return result
        data, error = ask_json(
            llm, 'Restate the goal in the text as one sentence and list up to 5 checks that would show it was '
            'achieved. Reply as {"goal": "...", "success_criteria": ["...", "..."]}.', body, purpose="intent.synthesize")
        if error:
            return {**result, "model": error}
        goal = as_text(data.get("goal"), 300) if isinstance(data, dict) else None
        criteria = data.get("success_criteria") if isinstance(data, dict) else None
        if goal is None or not isinstance(criteria, list) \
                or any(as_text(c, MAX_CRITERION_CHARS) is None for c in criteria):
            return {**result, "model": {"status": "rejected", "reason": "the model's reply had the wrong shape"}}
        intent["proposed_by_model"] = {"goal": goal, "success_criteria": [c.strip() for c in criteria[:MAX_CRITERIA]]}
        return {**result, "model": {"status": "ok"}}
