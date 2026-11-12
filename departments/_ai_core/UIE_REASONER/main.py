"""UIE_REASONER: decides what should happen next with an interpreted request.

Rule-based: it applies the fixed rules below, in order, to a frame from
UIE_SEMANTICS (text is interpreted first). It does not reason beyond them.

  1. a question                                   -> "answer"
  2. no recognised action                         -> "clarify"
  3. the action is negated ("do not pay ...")     -> "hold"
  4. a money action with no amount                -> "clarify"
  5. an action with no object                     -> "clarify"
  6. a money or destructive action                -> "approval" (a person must approve)
  7. anything else                                -> "proceed"

The result names the rule that fired, what is missing, whether approval is
required and the priority (high when the request is marked urgent).
"""
from typing import Any, Dict, List, Tuple

from velaris.agentkit.aicore_b_common import health
from velaris.agents.UIE_SEMANTICS.main import UIESemanticsAgent

NAME = "UIE_REASONER"


def _decide(frame: Dict[str, Any]) -> Tuple[str, str, List[str]]:
    if frame.get("act") == "question":
        return "answer", "question", []
    if not frame.get("action"):
        return "clarify", "no_recognised_action", ["action"]
    if frame.get("negated"):
        return "hold", "negated_action", []
    missing = []
    if frame.get("risk") == "money" and not (frame.get("entities") or {}).get("amounts"):
        missing.append("amount")
    if not frame.get("object") and not (frame.get("entities") or {}).get("references"):
        missing.append("object")
    if "amount" in missing:
        return "clarify", "money_action_without_amount", missing
    if missing:
        return "clarify", "action_without_object", missing
    if frame.get("risk") in ("money", "destructive"):
        return "approval", f"{frame['risk']}_action", []
    return "proceed", "routine_action", []


class UIEReasonerAgent:
    def __init__(self):
        self.semantics = UIESemanticsAgent()

    def health_check(self):
        return health(NAME)

    def reason(self, x: Any) -> Dict[str, Any]:
        frame = x.get("frame", x) if isinstance(x, dict) else None
        if not isinstance(frame, dict) or "act" not in frame:
            interpreted = self.semantics.interpret(x)
            if not interpreted["interpreted"]:
                return {"reasoned": False, "status": interpreted["status"], "reason": interpreted["reason"],
                        "next_step": None, "input": x}
            frame = interpreted["frame"]
        next_step, rule, missing = _decide(frame)
        return {"reasoned": True, "status": "ok", "next_step": next_step, "rule": rule, "missing": missing,
                "requires_approval": next_step == "approval",
                "priority": "high" if frame.get("urgent") else "normal", "frame": frame, "input": x}
