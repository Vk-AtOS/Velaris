"""MCFE_CORE: one pass over an incoming text: domain, fields, department.

process(text) calls MCFE_CLASSIFIER, then MCFE_FIELDGEN.extract for the
domain found, then MCFE_ROUTER. The result is "ok" only when a domain was
found, every required field was filled and a department exists; otherwise it
is "needs_review" with the reasons, so a person picks it up.
"""
from typing import Any, Dict, Optional

from velaris.agentkit.aicore_b_common import health
from velaris.agents.MCFE_CLASSIFIER.main import MCFEClassifierAgent
from velaris.agents.MCFE_FIELDGEN.main import MCFEFieldGenAgent
from velaris.agents.MCFE_ROUTER.main import MCFERouterAgent
from velaris.intel.llm import LLM

NAME = "MCFE_CORE"


class MCFECoreAgent:
    def __init__(self):
        self.classifier = MCFEClassifierAgent()
        self.fieldgen = MCFEFieldGenAgent()
        self.router = MCFERouterAgent()

    def health_check(self):
        return health(NAME)

    def process(self, text: Any, llm: Optional[LLM] = None) -> Dict[str, Any]:
        classified = self.classifier.classify(text, llm=llm)
        out: Dict[str, Any] = {"domain": classified["domain"], "classification": classified, "record": {},
                               "department": None, "review_reasons": []}
        if classified["status"] == "invalid_input":
            return {**out, "status": "invalid_input", "reason": classified["reason"]}
        if classified["domain"] is None:
            out["review_reasons"].append(classified.get("reason", "no domain found"))
            return {**out, "status": "needs_review"}
        extracted = self.fieldgen.extract(text, classified["domain"])
        routed = self.router.route(classified["domain"])
        out.update(record=extracted["record"], department=routed["department"])
        if extracted["missing"]:
            out["review_reasons"].append("missing required fields: " + ", ".join(extracted["missing"]))
        if routed["route"] != "ok":
            out["review_reasons"].append(routed["reason"])
        return {**out, "status": "needs_review" if out["review_reasons"] else "ok"}
