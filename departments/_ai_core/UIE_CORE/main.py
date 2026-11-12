"""UIE_CORE: a raw message in, a decision about the next step out.

understand(message) runs UIE_SIGNAL (clean and screen), UIE_SEMANTICS
(structure) and UIE_REASONER (next step). A message the signal stage refuses
goes no further. The frame is built from the masked text, so no secret or
personal identifier appears anywhere in the result (an e-mail address shows
up as a count under "pii", not as a value).
"""
from typing import Any, Dict

from velaris.agentkit.aicore_b_common import health
from velaris.agents.UIE_REASONER.main import UIEReasonerAgent
from velaris.agents.UIE_SEMANTICS.main import UIESemanticsAgent
from velaris.agents.UIE_SIGNAL.main import UIESignalAgent

NAME = "UIE_CORE"


class UIECoreAgent:
    def __init__(self):
        self.signal = UIESignalAgent()
        self.semantics = UIESemanticsAgent()
        self.reasoner = UIEReasonerAgent()

    def health_check(self):
        return health(NAME)

    def understand(self, message: Any) -> Dict[str, Any]:
        signal = self.signal.process(message)
        if not signal["processed"]:
            return {"status": signal["status"], "reason": signal["reason"], "next_step": None,
                    "findings": signal.get("findings", [])}
        frame = self.semantics.interpret(signal["safe_text"])["frame"]
        decision = self.reasoner.reason(frame)
        return {"status": "ok", "safe_text": signal["safe_text"], "pii": signal["pii"], "risk": signal["risk"],
                "sender": signal["sender"], "channel": signal["channel"], "frame": frame,
                "next_step": decision["next_step"], "rule": decision["rule"], "missing": decision["missing"],
                "requires_approval": decision["requires_approval"], "priority": decision["priority"]}
