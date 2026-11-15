"""Whether a language model is configured, and one guarded way for an agent to ask it for JSON."""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional, Tuple

from velaris.intel import router
from velaris.agentkit.results import fail
from velaris.intel import corrections, guard
from velaris.intel.llm import LLM, LLMError, extract_json

logger = logging.getLogger("velaris.agentkit.models")

CLOUD_MODEL_ENV = ("VELARIS_MODEL", "ANTHROPIC_API_KEY", "AWS_BEARER_TOKEN_BEDROCK")
MODEL_ENV = (*CLOUD_MODEL_ENV, "OLLAMA_MODEL")
NOT_CONFIGURED = "no model is configured (set VELARIS_MODEL or a provider key, or pass llm=)"


def model_available() -> bool:
    """True when the environment names a model or a provider credential (a local OLLAMA_MODEL counts).

    Without one the gateway would fall back to a local Ollama that may not be
    running, so agents answer `not_configured` instead of attempting the call.
    """
    return any(os.environ.get(k) for k in MODEL_ENV)


def model_or_none(llm: Optional[LLM]) -> Optional[LLM]:
    """The model gateway to use: the one passed in, else the real one if VELARIS_MODEL or a provider key is set.

    Unlike model_available(), OLLAMA_MODEL alone does not count here (the _ai_core agents' rule).
    """
    if llm is not None:
        return llm
    return LLM() if any(os.environ.get(k) for k in CLOUD_MODEL_ENV) else None


def ask_json(llm: LLM, instruction: str, outside_text: str, *, purpose: str) -> Tuple[Any, Optional[Dict[str, Any]]]:
    """Ask a model for JSON about a piece of outside text. Returns (data, error_result).

    The outside text is screened first (a blocked scan is never sent), fenced so
    it cannot give instructions, and stripped of secrets and personal
    identifiers. The reply is only parsed here: the caller must validate it.
    """
    scan = guard.scan(outside_text, source=purpose)
    if scan.blocked:
        return None, fail("blocked", "the text looks like an attempt to instruct the model; not sent",
                          findings=[f["rule"] for f in scan.findings])
    masked, _ = guard.redact(outside_text)
    preamble, fenced = guard.wrap(masked)
    try:
        prompt = corrections.with_corrections(f"{instruction}\n\n{preamble}\n{fenced}\n\nReply with JSON only.",
                                              corrections.for_purpose(purpose, instruction)["block"])      # what approvers changed before (KAN-24)
        reply = router.complete("worker", prompt, llm=llm, sensitivity="restricted", purpose=purpose)
        return extract_json(reply.text), None
    except LLMError as e:
        logger.warning("%s: model call failed: %s", purpose, e)
        return None, fail("model_error", str(e))
