"""Language work for the business agents: a model drafts, code checks the draft.

Used by the branding, narrative and creative agents. The model call goes
through velaris.intel.llm; caller text is screened by velaris.intel.guard before
it reaches a prompt and is fenced as data; drafts are checked for length,
required and banned terms, and for figures that were not in the brief.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, Iterable, List, Optional

from velaris.agentkit import biz_common as kit
from velaris.intel import guard
from velaris.intel.llm import LLM, LLMError, extract_json

logger = logging.getLogger("velaris.agentkit.biz_language")

_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def blocked_fields(fields: Dict[str, str], source: str) -> List[str]:
    """Names of the supplied text fields the guard classes as an attack on the model."""
    return [name for name, value in fields.items() if guard.scan(value, source=f"{source}.{name}").blocked]


def fenced(content: str, label: str) -> str:
    """Caller-supplied text as a data block a model is told not to obey."""
    preamble, block = guard.wrap(content, label=label)
    return f"{preamble}\n\n{block}"


def complete(llm: Optional[LLM], prompt: str, *, purpose: str, max_tokens: int = 800,
             temperature: float = 0.7, want_json: bool = False) -> Dict[str, Any]:
    """One model call. Returns {"status": "ok", "text" | "data", "model"} or a
    not_configured / model_error result; never raises."""
    if llm is None:
        if not kit.model_available():
            return kit.not_configured()
        llm = LLM()
    try:
        done = llm.complete(prompt, max_tokens=max_tokens, temperature=temperature, purpose=purpose)
        if want_json:
            return {"status": "ok", "data": extract_json(done.text), "model": done.model}
        return {"status": "ok", "text": done.text.strip(), "model": done.model}
    except LLMError as e:
        logger.warning("%s: model call failed: %s", purpose, e)
        return {"status": "model_error", "reason": str(e)[:200]}


def _numbers(text: str) -> set:
    return {m.replace(",", "").rstrip("0").rstrip(".") if "." in m else m.replace(",", "")
            for m in _NUMBER.findall(text)}


def invented_numbers(draft: str, brief: str) -> List[str]:
    """Figures in the draft that do not appear in the brief (a model may not add numbers)."""
    return sorted(_numbers(draft) - _numbers(brief))


def violations(draft: str, *, max_chars: Optional[int] = None, required: Iterable[str] = (),
               banned: Iterable[str] = (), brief: Optional[str] = None) -> List[str]:
    """Every rule the draft breaks; empty means it may be shown as a draft."""
    out = []
    if not draft.strip():
        out.append("draft is empty")
    if max_chars is not None and len(draft) > max_chars:
        out.append(f"{len(draft)} characters, limit {max_chars}")
    out += [f"required term missing: {t}" for t in required if not kit.has_term(t, draft)]
    out += [f"banned term present: {t}" for t in banned if kit.has_term(t, draft)]
    if brief is not None:
        out += [f"figure not in the brief: {n}" for n in invented_numbers(draft, brief)]
    if guard.scan(draft, source="model draft").blocked:
        out.append("draft was blocked by the guard")
    return out


def term_list(value: Any, name: str, errors: List[str], limit: int = 50) -> List[str]:
    """A validated list of short strings (required/banned terms and the like)."""
    if value is None:
        return []
    if not isinstance(value, (list, tuple)) or len(value) > limit or any(kit.text(v, 100) is None for v in value):
        errors.append(f"{name} must be a list of at most {limit} short strings")
        return []
    return [v.strip() for v in value]
