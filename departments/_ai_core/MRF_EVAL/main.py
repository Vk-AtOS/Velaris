"""MRF_EVAL: scores a piece of output (a draft, an answer, a JSON reply) against a stated rubric.

MRF is read here as "measure, reflect, fix": MRF_EVAL measures an output,
MRF_REFLECT turns the failures into concrete revision instructions (and can
ask a model to apply them), META_REASONING_CORE loops the two.

Rubric (every key optional, at least one required):
  required     terms that must appear (ignoring case)
  forbidden    terms that must not appear
  min_chars / max_chars
  fields       keys that must be present when the output is JSON (an object, or text holding one)
  pattern      a regular expression the text must match (at most 200 characters)
Each rubric item is one check. score = checks passed / checks; passed means
every check passed. Deterministic.
"""
import json
import re
from typing import Any, Dict, List

from velaris.agentkit.aicore_b_common import health, ident, invalid, number
from velaris.intel.llm import LLMError, extract_json

NAME = "MRF_EVAL"
KEYS = ("required", "forbidden", "min_chars", "max_chars", "fields", "pattern")
MAX_OUTPUT = 50_000


def rubric_error(rubric: Any) -> Any:
    if not isinstance(rubric, dict) or not rubric or set(rubric) - set(KEYS):
        return f"rubric must be an object using only {KEYS}"
    for key in ("required", "forbidden", "fields"):
        if key in rubric and (not isinstance(rubric[key], list) or any(ident(t, 200) is None for t in rubric[key])):
            return f"'{key}' must be a list of non-empty strings"
    for key in ("min_chars", "max_chars"):
        if key in rubric and (number(rubric[key]) is None or rubric[key] < 0):
            return f"'{key}' must be a non-negative number"
    if "pattern" in rubric:
        if not isinstance(rubric["pattern"], str) or len(rubric["pattern"]) > 200:
            return "'pattern' must be a regular expression of at most 200 characters"
        try:
            re.compile(rubric["pattern"])
        except re.error as e:
            return f"bad pattern: {e}"
    return None


class MRF_EVALAgent:
    def health_check(self):
        return health(NAME)

    def evaluate(self, output: Any, rubric: Dict[str, Any]) -> Dict[str, Any]:
        """Returns score, passed, checks (each with ok and detail) and the failures."""
        err = rubric_error(rubric)
        if err:
            return invalid(err, passed=False, score=None)
        if isinstance(output, (dict, list)):
            data, text = output, json.dumps(output, ensure_ascii=False)
        elif isinstance(output, str):
            text, data = output, None
        else:
            return invalid("output must be text or a JSON object", passed=False, score=None)
        if len(text) > MAX_OUTPUT:
            return invalid(f"output longer than {MAX_OUTPUT} characters", passed=False, score=None)
        lowered = text.lower()
        checks: List[Dict[str, Any]] = []

        def check(name, ok, detail=""):
            checks.append({"check": name, "ok": bool(ok), "detail": detail})

        for term in rubric.get("required", []):
            check("required", term.lower() in lowered, term)
        for term in rubric.get("forbidden", []):
            check("forbidden", term.lower() not in lowered, term)
        if "min_chars" in rubric:
            check("min_chars", len(text) >= rubric["min_chars"], f"{len(text)} < {rubric['min_chars']}")
        if "max_chars" in rubric:
            check("max_chars", len(text) <= rubric["max_chars"], f"{len(text)} > {rubric['max_chars']}")
        if "fields" in rubric:
            if data is None:
                try:
                    data = extract_json(text)
                except LLMError:
                    data = None
            for field in rubric["fields"]:
                check("field", isinstance(data, dict) and field in data, field)
        if "pattern" in rubric:
            check("pattern", re.search(rubric["pattern"], text[:10_000]) is not None, rubric["pattern"])
        failures = [c for c in checks if not c["ok"]]
        return {"status": "ok", "passed": not failures, "score": round((len(checks) - len(failures)) / len(checks), 4),
                "checks": checks, "failures": failures}
