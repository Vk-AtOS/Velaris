"""MRF_REFLECT: turns an evaluation's failures into revision instructions, and optionally has a model apply them.

reflect(evaluation) is deterministic: one plain instruction per failed check
("Mention 'GSTIN'.", "Remove 'guaranteed'.", "Shorten to at most 400 characters.").
revise(output, evaluation, llm) sends the output and those instructions to a
model and returns its rewrite. The rewrite is only a proposal: it is checked
again by whoever called (META_REASONING_CORE re-runs MRF_EVAL on it). With no
model it returns not_configured.
"""
from typing import Any, Dict, List, Optional

from velaris.agentkit.models import ask_json, model_or_none, NOT_CONFIGURED
from velaris.agentkit.results import fail, health, invalid
from velaris.intel.llm import LLM

NAME = "MRF_REFLECT"
_SAY = {
    "required": "Mention '{d}'.",
    "forbidden": "Remove '{d}'.",
    "field": "Include the field '{d}' in the JSON.",
    "pattern": "Make the text match the pattern {d}.",
}


class MRF_REFLECTAgent:
    def health_check(self):
        return health(NAME)

    def reflect(self, evaluation: Any) -> Dict[str, Any]:
        """Instructions for every failed check. An evaluation that passed gives none."""
        if not isinstance(evaluation, dict) or not isinstance(evaluation.get("checks"), list):
            return invalid("expected a result from MRF_EVAL.evaluate", instructions=[])
        instructions: List[str] = []
        for c in evaluation["checks"]:
            if c.get("ok"):
                continue
            kind, detail = c.get("check"), str(c.get("detail", ""))
            if kind == "min_chars":
                instructions.append(f"Lengthen to at least {detail.split('< ')[-1]} characters.")
            elif kind == "max_chars":
                instructions.append(f"Shorten to at most {detail.split('> ')[-1]} characters.")
            elif kind in _SAY:
                instructions.append(_SAY[kind].format(d=detail))
        return {"status": "ok", "instructions": instructions, "needs_revision": bool(instructions)}

    def revise(self, output: Any, evaluation: Dict[str, Any], llm: Optional[LLM] = None) -> Dict[str, Any]:
        if not isinstance(output, str) or not output.strip():
            return invalid("output must be text", revised=None)
        plan = self.reflect(evaluation)
        if plan["status"] != "ok":
            return {**plan, "revised": None}
        if not plan["needs_revision"]:
            return {"status": "ok", "revised": output, "instructions": [], "changed": False}
        model = model_or_none(llm)
        if model is None:
            return {**fail("not_configured", NOT_CONFIGURED), "revised": None, "instructions": plan["instructions"]}
        data, error = ask_json(model, "Rewrite the text so that it follows these instructions, changing nothing else:\n- "
                               + "\n- ".join(plan["instructions"]) + '\nReply as {"revised": "<the full new text>"}.',
                               output, purpose="mrf.revise")
        if error:
            return {**error, "revised": None, "instructions": plan["instructions"]}
        revised = data.get("revised") if isinstance(data, dict) else None
        if not isinstance(revised, str) or not revised.strip():
            return {**fail("rejected", "the model's reply held no revised text"), "revised": None,
                    "instructions": plan["instructions"]}
        return {"status": "ok", "revised": revised, "instructions": plan["instructions"], "changed": revised != output,
                "proposed_by_model": True}
