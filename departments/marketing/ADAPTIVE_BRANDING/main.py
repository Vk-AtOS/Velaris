"""ADAPTIVE_BRANDING: rewrite one brand message for a channel and audience, then check it.

Language is the job, so a model drafts (through velaris.intel.llm); code decides
whether the draft may be shown:
  * within the character limit (max_chars, else the channel's house limit),
  * every required term present, no banned term,
  * no figure that was not in the original message,
  * not blocked by the guard.
A draft that breaks a rule is returned as `rejected` with the violations. The
message and audience are screened by the guard and fenced as data in the prompt.
Nothing is published: an accepted draft still needs a person's approval.
`not_configured` when no model is available.

HOUSE_LIMITS are this company's style lengths, not the platforms' rules.
"""
import logging
from typing import Any, Dict, List

from velaris.agentkit import biz_common as kit
from velaris.agentkit import biz_language as lang

logger = logging.getLogger("ADAPTIVE_BRANDING")
HOUSE_LIMITS = {"sms": 160, "social_short": 280, "social_long": 1500, "email_subject": 60,
                "web_headline": 80, "email_body": 2000}
TONES = ("plain", "warm", "formal", "energetic")


class AdaptiveBrandingAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.version = (config or {}).get("version", kit.VERSION)

    def health_check(self) -> Dict[str, Any]:
        return {"agent": "ADAPTIVE_BRANDING", "status": "ok", "version": self.version}

    def run(self, payload: Dict[str, Any], llm: Any = None) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            return kit.failed(["payload must be an object"])
        errors: List[str] = []
        message, channel = kit.ident(payload.get("message"), 4000), payload.get("channel")
        audience, tone = payload.get("audience", ""), payload.get("tone", "plain")
        if message is None:
            errors.append("message must be a non-empty string of at most 4000 characters")
        if not isinstance(channel, str) or channel not in HOUSE_LIMITS:
            channel = None
            errors.append(f"channel must be one of {sorted(HOUSE_LIMITS)}")
        if not isinstance(audience, str) or len(audience) > 300:
            errors.append("audience must be a string of at most 300 characters")
        if tone not in TONES:
            errors.append(f"tone must be one of {TONES}")
        max_chars = payload.get("max_chars", HOUSE_LIMITS.get(channel))
        if channel is not None and (isinstance(max_chars, bool) or not isinstance(max_chars, int)
                                        or not 10 <= max_chars <= 10_000):
            errors.append("max_chars must be a whole number from 10 to 10000")
        required = lang.term_list(payload.get("required_terms"), "required_terms", errors)
        banned = lang.term_list(payload.get("banned_terms"), "banned_terms", errors)
        if errors:
            return kit.failed(errors)
        blocked = lang.blocked_fields({"message": message, "audience": audience}, "ADAPTIVE_BRANDING")
        if blocked:
            return {"status": "blocked", "reason": "input was blocked by the guard", "fields": blocked}
        prompt = (
            f"{lang.fenced(message, 'a brand message supplied by the company')}\n\n"
            f"Rewrite that message for the channel '{channel}' in a {tone} tone"
            + (f", for this audience: {audience.strip()}" if audience.strip() else "")
            + f". Keep it under {max_chars} characters. Keep the meaning; add no facts, figures or claims "
            "that are not in the message."
            + (f" It must include: {', '.join(required)}." if required else "")
            + (f" It must not use: {', '.join(banned)}." if banned else "")
            + " Reply with the rewritten message only.")
        got = lang.complete(llm, prompt, purpose="ADAPTIVE_BRANDING.adapt", max_tokens=600)
        if got["status"] != "ok":
            return got
        draft = got["text"].strip().strip('"')
        problems = lang.violations(draft, max_chars=max_chars, required=required, banned=banned, brief=message)
        return {"status": "rejected" if problems else "ok", "draft": draft, "violations": problems,
                "channel": channel, "max_chars": max_chars, "characters": len(draft), "model": got["model"],
                "requires_human_approval": True, "published": False}
