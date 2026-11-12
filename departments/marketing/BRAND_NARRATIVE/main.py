"""BRAND_NARRATIVE: a short company narrative written from supplied facts only.

run({"facts": {"name": ..., "services": [...], ...}, "audience"?, "max_words"?, "banned_terms"?})

A model writes (through velaris.intel.llm); code checks before anything is returned as ok:
  * the company name appears, when the facts give one,
  * the text is within max_words,
  * every figure in the text is a figure from the facts (a model may not add numbers),
  * no banned term, and the guard does not block the text.
A draft that fails is `rejected` with the violations. Facts are screened by the
guard and fenced as data. No facts -> `needs_data`; no model -> `not_configured`.
The narrative is a draft for a person to approve; the agent stores nothing.
"""
import logging
from typing import Any, Dict, List

from velaris.agentkit import biz_common as kit
from velaris.agentkit import biz_language as lang

logger = logging.getLogger("BRAND_NARRATIVE")
MAX_FACTS = 40


def _brief(facts: Dict[str, Any], errors: List[str]) -> str:
    """Facts as 'key: value' lines; values are short strings, numbers or lists of them."""
    lines = []
    for key, value in facts.items():
        items = value if isinstance(value, (list, tuple)) else [value]
        if kit.text(key, 60) is None or not items or any(
                isinstance(v, bool) or not isinstance(v, (str, int, float)) or not str(v).strip()
                or len(str(v)) > 500 for v in items):
            errors.append(f"facts[{key!r}] must be a short string, a number, or a list of them")
            continue
        lines.append(f"{key}: {', '.join(str(v).strip() for v in items)}")
    return "\n".join(lines)


class BrandNarrativeAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.version = (config or {}).get("version", kit.VERSION)

    def health_check(self) -> Dict[str, Any]:
        return {"agent": "BRAND_NARRATIVE", "status": "ok", "version": self.version}

    def run(self, payload: Dict[str, Any], llm: Any = None) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            return kit.failed(["payload must be an object"])
        facts = payload.get("facts")
        if facts is None or facts == {}:
            return kit.needs_data("no facts supplied; the narrative is written from the company's facts only")
        errors: List[str] = []
        if not isinstance(facts, dict) or len(facts) > MAX_FACTS:
            return kit.failed([f"facts must be an object with at most {MAX_FACTS} entries"])
        brief = _brief(facts, errors)
        audience, max_words = payload.get("audience", ""), payload.get("max_words", 200)
        if not isinstance(audience, str) or len(audience) > 300:
            errors.append("audience must be a string of at most 300 characters")
        if isinstance(max_words, bool) or not isinstance(max_words, int) or not 20 <= max_words <= 1000:
            errors.append("max_words must be a whole number from 20 to 1000")
        banned = lang.term_list(payload.get("banned_terms"), "banned_terms", errors)
        if errors:
            return kit.failed(errors)
        blocked = lang.blocked_fields({"facts": brief, "audience": audience}, "BRAND_NARRATIVE")
        if blocked:
            return {"status": "blocked", "reason": "input was blocked by the guard", "fields": blocked}
        prompt = (
            f"{lang.fenced(brief, 'facts about a company, supplied by the company')}\n\n"
            f"Write a brand narrative of at most {max_words} words using ONLY those facts"
            + (f", for this audience: {audience.strip()}" if audience.strip() else "")
            + ". Do not add figures, awards, clients, dates or claims that are not in the facts. "
            "Plain prose, no headings. Reply with the narrative only.")
        got = lang.complete(llm, prompt, purpose="BRAND_NARRATIVE.write", max_tokens=max_words * 3)
        if got["status"] != "ok":
            return got
        draft = got["text"]
        name = facts.get("name") if isinstance(facts.get("name"), str) else None
        problems = lang.violations(draft, required=[name] if name else [], banned=banned, brief=brief)
        words = len(draft.split())
        if words > max_words:
            problems.append(f"{words} words, limit {max_words}")
        return {"status": "rejected" if problems else "ok", "narrative": draft, "violations": problems,
                "words": words, "max_words": max_words, "facts_used": sorted(facts), "model": got["model"],
                "requires_human_approval": True}
