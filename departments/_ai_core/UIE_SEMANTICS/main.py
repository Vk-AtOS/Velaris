"""UIE_SEMANTICS: turns a message into a structured request frame.

interpret(x) takes text (or UIE_SIGNAL's result) and returns a frame: the
speech act (question / command / statement), the requested action from a
fixed verb list with its risk class (money, destructive, normal, read), the
object words after the verb, negation, urgency, and typed values (amounts,
dates, e-mail addresses, percentages, references).

Word lists and patterns only (velaris.agentkit.aicore_b_text). A verb that is
not on the list gives action None; nothing is guessed.
"""
from typing import Any, Dict

from velaris.agentkit import aicore_b_text as textkit
from velaris.agentkit.aicore_b_common import health, text as as_text

NAME = "UIE_SEMANTICS"


class UIESemanticsAgent:
    def health_check(self):
        return health(NAME)

    def interpret(self, x: Any) -> Dict[str, Any]:
        source = x.get("text") if isinstance(x, dict) else x
        body = as_text(source)
        if body is None:
            return {"interpreted": False, "frame": None, "status": "invalid_input",
                    "reason": "expected text, or a processed signal with 'text'"}
        if isinstance(x, dict) and x.get("processed") is False:
            return {"interpreted": False, "frame": None, "status": "refused",
                    "reason": "the signal was not accepted by UIE_SIGNAL"}
        frame = textkit.frame(body)
        return {"interpreted": True, "status": "ok", "frame": frame,
                "understood": frame["action"] is not None or frame["act"] == "question"}
