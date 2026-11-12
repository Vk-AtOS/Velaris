"""CREATIVE_ENGINE: campaign ideas, variations and blends, drafted by a model.

  generate_idea(theme)        one concrete idea for the theme
  variations(base, count)     `count` distinct rewrites of a line
  blend(a, b)                 one concept combining two

The drafting is done by a language model through velaris.intel.llm; code checks
each reply (non-empty, the requested number of distinct items, not blocked by
the guard) and screens the caller's text before it reaches a prompt. Without a
model nothing is made up: generate_idea returns `not_configured` with no idea,
variations returns [] and blend returns "" (see `last_status`).

There is no quality score: `creative_score` stays None because nothing here can
measure how good an idea is. History of accepted ideas is kept at
<VELARIS_DATA>/agents/CREATIVE_ENGINE/history.json (owner-only).
"""
import logging
from typing import Any, Dict, List, Optional

from velaris.agentkit import biz_common as kit
from velaris.agentkit import biz_language as lang
from velaris.intel.llm import LLM
from velaris.intel.paths import agent_dir

logger = logging.getLogger("CREATIVE_ENGINE")
MAX_HISTORY = 500
MAX_VARIATIONS = 10


class CreativeEngine:
    def __init__(self, llm: Optional[LLM] = None):
        self._llm = llm
        self._state = kit.JsonState(lambda: agent_dir("CREATIVE_ENGINE") / "history.json", {"history": []})
        self.last_status = "ok"

    def health_check(self) -> Dict[str, Any]:
        return kit.health("CREATIVE_ENGINE")

    def _ask(self, texts: Dict[str, str], instruction: str, purpose: str, want_json: bool = False) -> Dict[str, Any]:
        """Screen the caller's texts, fence them, ask the model. Sets last_status."""
        if any(kit.text(t, 500) is None for t in texts.values()):
            got: Dict[str, Any] = kit.failed([f"{', '.join(texts)} must be non-empty strings of at most 500 characters"])
        elif lang.blocked_fields(texts, "CREATIVE_ENGINE"):
            got = {"status": "blocked", "reason": "input was blocked by the guard"}
        else:
            block = lang.fenced("\n".join(f"{k}: {v.strip()}" for k, v in texts.items()), "text supplied by the user")
            got = lang.complete(self._llm, f"{block}\n\n{instruction}", purpose=purpose, want_json=want_json)
        self.last_status = got["status"]
        return got

    def generate_idea(self, theme: str) -> Dict:
        got = self._ask({"theme": theme}, "Propose one concrete marketing idea for that theme in at most "
                        "three sentences. Reply with the idea only.", "CREATIVE_ENGINE.idea")
        idea = {"theme": theme, "idea": None, "creative_score": None, "status": got["status"]}
        if got["status"] != "ok":
            idea["reason"] = got.get("reason") or "; ".join(got.get("errors", []))
            return idea
        problems = lang.violations(got["text"], max_chars=1000)
        if problems:
            self.last_status = "rejected"
            return {**idea, "status": "rejected", "reason": "; ".join(problems)}
        idea.update(idea=got["text"], model=got["model"])
        data = self._state.load()
        data["history"] = (data["history"] + [idea])[-MAX_HISTORY:]
        self._state.save(data)
        return idea

    def variations(self, base: str, count: int = 3) -> List[str]:
        if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= MAX_VARIATIONS:
            self.last_status = "failed"
            return []
        got = self._ask({"line": base}, f"Write {count} different variations of that line. Reply with a JSON "
                        "array of strings only.", "CREATIVE_ENGINE.variations", want_json=True)
        if got["status"] != "ok":
            return []
        items = got["data"] if isinstance(got["data"], list) else []
        clean = list(dict.fromkeys(i.strip() for i in items if isinstance(i, str) and i.strip()
                                   and i.strip().lower() != base.strip().lower()
                                   and not lang.violations(i, max_chars=1000)))
        if len(clean) < count:
            self.last_status = "rejected"      # the model did not deliver what was asked; nothing is padded
            return []
        return clean[:count]

    def blend(self, a: str, b: str) -> str:
        got = self._ask({"first": a, "second": b}, "Combine those two concepts into one new concept, in at "
                        "most two sentences. Reply with the concept only.", "CREATIVE_ENGINE.blend")
        if got["status"] != "ok":
            return ""
        if lang.violations(got["text"], max_chars=600):
            self.last_status = "rejected"
            return ""
        return got["text"]

    def get_history(self) -> List[Dict]:
        return list(self._state.load()["history"])
