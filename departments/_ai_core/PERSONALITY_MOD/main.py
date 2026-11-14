"""PERSONALITY_MOD: the house style for messages agents send, and the code that applies it.

Not a personality. A versioned style profile:
  tone        formal | neutral | friendly       (stored; a model writing a draft can be told it)
  max_chars   20..5000                          longest message allowed
  greeting    text put first, "" for none
  sign_off    text put last, "" for none
  banned      phrases that must never appear (matched ignoring case)
apply(text) enforces what can be enforced in code: removes banned phrases,
collapses whitespace, adds greeting and sign-off, cuts the body (at a word
boundary) so the whole message fits max_chars, and lists what it changed.
Stored owner-only under this agent's state directory; every change recorded against
the current caller (velaris.core.access), who must be a governance admin.
"""
import re
from typing import Any, Dict, Optional

from velaris.agentkit.checks import ident, MAX_TEXT, number
from velaris.agentkit.results import health, invalid
from velaris.agentkit.aicore_b_versioned import VersionedDoc

NAME = "PERSONALITY_MOD"
TONES = ("formal", "neutral", "friendly")
DEFAULT = {"tone": "neutral", "max_chars": 1200, "greeting": "", "sign_off": "", "banned": []}


def _check(key: str, value: Any) -> Optional[str]:
    if key == "tone":
        return None if value in TONES else f"must be one of {TONES}"
    if key == "max_chars":
        n = number(value)
        return None if n is not None and n == int(n) and 20 <= n <= 5000 else "must be a whole number 20..5000"
    if key in ("greeting", "sign_off"):
        return None if isinstance(value, str) and len(value) <= 200 else "must be text of at most 200 characters"
    if key == "banned":
        return None if isinstance(value, list) and all(ident(p, 100) for p in value) else "must be a list of phrases"
    return f"unknown style key (one of {sorted(DEFAULT)})"


class PERSONALITY_MODAgent:
    def __init__(self):
        self.name = NAME
        self._doc = VersionedDoc(NAME, "style.json", DEFAULT, check=_check)

    def health_check(self) -> Dict[str, Any]:
        return health(self.name)

    def update(self, data: Dict[str, Any], by: Optional[str] = None) -> Dict[str, Any]:
        """Change the house style as the current caller (a governance admin); `by` must be that caller."""
        result = self._doc.change(NAME, data, by)
        return {"updated": result["status"] == "ok", **result}

    def snapshot(self) -> Dict[str, Any]:
        return {"snapshot": self.name, "status": "ok", "version": self._doc.version(), "style": self._doc.current()}

    def apply(self, text: Any) -> Dict[str, Any]:
        """The message in house style, with the list of changes made."""
        if not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT:
            return invalid("text must be a non-empty string", text=None)
        style, changes = self._doc.current(), []
        body = text
        for phrase in style["banned"]:
            body, n = re.subn(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", "", body, flags=re.I)
            if n:
                changes.append(f"removed '{phrase}' x{n}")
        body = " ".join(body.split())
        head = f"{style['greeting']}\n\n" if style["greeting"] else ""
        tail = f"\n\n{style['sign_off']}" if style["sign_off"] else ""
        room = int(style["max_chars"]) - len(head) - len(tail)
        if room < 1:
            return invalid("greeting and sign-off alone are longer than max_chars", text=None)
        if len(body) > room:
            cut = body[:max(room - 1, 0)]
            body = (cut.rsplit(" ", 1)[0] if " " in cut else cut).rstrip() + "…"
            changes.append(f"cut to fit {style['max_chars']} characters")
        if not body.strip(" …"):
            return invalid("nothing is left of the message after the banned phrases were removed", text=None)
        if head or tail:
            changes.append("added greeting/sign-off")
        return {"status": "ok", "text": head + body + tail, "tone": style["tone"], "changes": changes}
