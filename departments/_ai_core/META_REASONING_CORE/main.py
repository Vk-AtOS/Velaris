"""META_REASONING_CORE: draft, check against a rubric, revise, re-check; keep the best attempt.

Not a reasoning engine. It is a bounded loop around MRF_EVAL and MRF_REFLECT:
  pick_best(candidates, rubric)   no model: scores each candidate, returns the best
                                   (highest score, then shortest, then first given)
  solve(task, rubric, llm)        a model writes a draft; MRF_EVAL scores it; if it
                                   fails, MRF_REFLECT has the model revise it; up to
                                   max_rounds drafts. Code decides which attempt wins
                                   and whether it passed. No model: not_configured.
"""
from typing import Any, Dict, List, Optional

from velaris.agentkit.checks import text
from velaris.agentkit.models import ask_json, model_or_none, NOT_CONFIGURED
from velaris.agentkit.results import fail, health, invalid
from velaris.agents.MRF_EVAL.main import MRF_EVALAgent, rubric_error
from velaris.agents.MRF_REFLECT.main import MRF_REFLECTAgent
from velaris.intel.llm import LLM

NAME = "META_REASONING_CORE"
MAX_ROUNDS = 5


class META_REASONING_COREAgent:
    def __init__(self):
        self.evaluator = MRF_EVALAgent()
        self.reflector = MRF_REFLECTAgent()

    def health_check(self):
        return health(NAME)

    def pick_best(self, candidates: Any, rubric: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(candidates, list) or not candidates:
            return invalid("candidates must be a non-empty list", best=None)
        scored = []
        for n, c in enumerate(candidates):
            r = self.evaluator.evaluate(c, rubric)
            if r["status"] != "ok":
                return {**r, "best": None}
            scored.append({"index": n, "score": r["score"], "passed": r["passed"], "failures": r["failures"],
                           "length": len(str(c))})
        best = min(scored, key=lambda s: (-s["score"], s["length"], s["index"]))
        return {"status": "ok", "best": candidates[best["index"]], "best_index": best["index"],
                "passed": best["passed"], "score": best["score"], "ranking": scored}

    def solve(self, task: str, rubric: Dict[str, Any], llm: Optional[LLM] = None, max_rounds: int = 3) -> Dict[str, Any]:
        body = text(task, 5000)
        err = rubric_error(rubric)
        if body is None or err or not isinstance(max_rounds, int) or not 1 <= max_rounds <= MAX_ROUNDS:
            return invalid(err or f"task must be text and max_rounds 1..{MAX_ROUNDS}", answer=None)
        model = model_or_none(llm)
        if model is None:
            return {**fail("not_configured", NOT_CONFIGURED), "answer": None}
        data, error = ask_json(model, 'Do the task described in the text. Reply as {"answer": "<your answer>"}.',
                               body, purpose="mrc.draft")
        draft = data.get("answer") if isinstance(data, dict) else None
        if error or not isinstance(draft, str):
            return {**(error or fail("rejected", "the model gave no answer")), "answer": None}
        attempts: List[Dict[str, Any]] = []
        while True:
            verdict = self.evaluator.evaluate(draft, rubric)
            attempts.append({"answer": draft, "score": verdict["score"], "failures": verdict["failures"]})
            if verdict["passed"] or len(attempts) >= max_rounds:
                break
            revised = self.reflector.revise(draft, verdict, llm=model)
            if revised["status"] != "ok":
                attempts[-1]["revision_error"] = revised.get("reason")
                break
            draft = revised["revised"]
        best = max(attempts, key=lambda a: a["score"])                 # first of equals: max keeps the earliest
        return {"status": "ok" if best["score"] == 1 else "not_passed", "answer": best["answer"],
                "passed": best["score"] == 1, "score": best["score"], "rounds": len(attempts), "attempts": attempts}
