"""MCFE_CLASSIFIER: which subject domain is a piece of text about?

MCFE is read here as "multi-domain classification and field extraction":
classify incoming text (this agent), produce the fields a record of that
domain needs and fill them from the text (MCFE_FIELDGEN), and name the
department that handles it (MCFE_ROUTER); MCFE_CORE runs the three.

classify(text) counts each domain's terms in the text (word lists in
velaris.agentkit.aicore_b_text). The domain with the most hits wins; no hits
or a tie gives domain None rather than a guess. If a model is passed (or
configured) it is asked only for those undecided texts, and its answer is
accepted only if it is one of DOMAINS. The same text always gives the same
answer on the word-list path.
"""
from typing import Any, Dict, Optional

from velaris.agentkit import aicore_b_text as textkit
from velaris.agentkit.checks import text as as_text
from velaris.agentkit.models import ask_json, model_or_none
from velaris.agentkit.results import health, invalid
from velaris.intel.llm import LLM

NAME = "MCFE_CLASSIFIER"


class MCFEClassifierAgent:
    DOMAINS = ["business", "finance", "medical", "legal", "science", "engineering", "governance", "psychology"]

    def health_check(self):
        return health(NAME, domains=self.DOMAINS)

    def classify(self, text: Any, llm: Optional[LLM] = None) -> Dict[str, Any]:
        """Returns domain (or None), confidence 0..1, the per-domain scores and how it was decided."""
        body = as_text(text)
        if body is None:
            return invalid("text must be a non-empty string", domain=None, confidence=0.0)
        domain, confidence, scores = textkit.best_domain(body)
        result = {"domain": domain, "confidence": confidence, "scores": scores, "method": "word_list"}
        if domain is not None:
            return {"status": "ok", **result}
        model = model_or_none(llm)
        if model is None:
            return {"status": "no_match", **result,
                    "reason": "no domain's terms stand out in the text and no model is configured"}
        data, error = ask_json(
            model, "Classify the text into exactly one of these domains: " + ", ".join(self.DOMAINS)
            + '. Reply as {"domain": "<one of them>"}.', body, purpose="mcfe.classify")
        if error:
            return {**error, **result}
        proposed = data.get("domain") if isinstance(data, dict) else None
        if proposed not in self.DOMAINS:
            return {"status": "no_match", **result, "reason": "the model's answer was not one of the domains"}
        return {"status": "ok", **result, "domain": proposed, "confidence": None, "method": "model"}
