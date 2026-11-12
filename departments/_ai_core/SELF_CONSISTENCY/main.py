"""SELF_CONSISTENCY: ask the same question N times and measure how far the answers agree.

agreement(answers) is deterministic: answers are normalised (case, spaces,
punctuation at the ends; numbers such as "1,200" and "1200.0" compare equal),
the most common one is the majority answer and agreement = its count / N.
consistent means N >= 2 and agreement >= threshold (default 0.6).
sample(question, n, llm) gets the N answers from a model (outside text is
screened by velaris.intel.guard) and then measures them; with no model it
returns not_configured. A low agreement is a reason to send the question to a
person, not to trust the majority.
check(record) is kept for older callers: True only for {"answers": [...]} that are consistent.
"""
import re
from collections import Counter
from typing import Any, Dict, List, Optional

from velaris.agentkit.checks import number, text
from velaris.agentkit.models import ask_json, model_or_none, NOT_CONFIGURED
from velaris.agentkit.results import fail, health, invalid
from velaris.intel.llm import LLM

NAME = "SELF_CONSISTENCY"
MAX_SAMPLES = 10
_NUM = re.compile(r"^[+-]?[\d,]*\.?\d+$")


def normalise(answer: Any) -> str:
    s = " ".join(str(answer).split()).strip(" .!?;:\"'").casefold()
    if _NUM.match(s.replace(" ", "")):
        try:
            return repr(float(s.replace(",", "").replace(" ", "")))
        except ValueError:
            return s
    return s


class SELF_CONSISTENCYAgent:
    def __init__(self):
        self.name = NAME

    def health_check(self):
        return health(self.name)

    def agreement(self, answers: Any, threshold: float = 0.6) -> Dict[str, Any]:
        t = number(threshold)
        if not isinstance(answers, list) or not answers or any(a is None or isinstance(a, (dict, list)) for a in answers):
            return invalid("answers must be a non-empty list of short answers", consistent=False)
        if t is None or not 0 < t <= 1:
            return invalid("threshold must be in (0, 1]", consistent=False)
        counts = Counter(normalise(a) for a in answers)
        top, n = counts.most_common(1)[0]
        majority = next(a for a in answers if normalise(a) == top)
        share = n / len(answers)
        return {"status": "ok", "majority": majority, "agreement": round(share, 4), "samples": len(answers),
                "distinct": len(counts), "consistent": len(answers) >= 2 and share >= t,
                "counts": dict(counts.most_common())}

    def sample(self, question: str, n: int = 5, llm: Optional[LLM] = None, threshold: float = 0.6) -> Dict[str, Any]:
        body = text(question, 4000)
        if body is None or not isinstance(n, int) or isinstance(n, bool) or not 2 <= n <= MAX_SAMPLES:
            return invalid(f"question must be text and n 2..{MAX_SAMPLES}", consistent=False)
        model = model_or_none(llm)
        if model is None:
            return {**fail("not_configured", NOT_CONFIGURED), "consistent": False}
        answers: List[str] = []
        for i in range(n):
            data, error = ask_json(model, f'Answer the question in the text briefly (attempt {i + 1}). '
                                   'Reply as {"answer": "<short answer>"}.', body, purpose="self_consistency")
            if error and error["status"] == "blocked":
                return {**error, "consistent": False}
            answer = data.get("answer") if isinstance(data, dict) else None
            if isinstance(answer, (str, int, float)) and not isinstance(answer, bool) and str(answer).strip():
                answers.append(str(answer))
        if len(answers) < 2:
            return {**fail("model_error", f"only {len(answers)} usable answers out of {n}"), "consistent": False}
        return {**self.agreement(answers, threshold), "asked": n, "answers": answers}

    def check(self, identity: Dict[str, Any]) -> bool:
        if not isinstance(identity, dict) or "answers" not in identity:
            return False
        return self.agreement(identity["answers"])["consistent"]
