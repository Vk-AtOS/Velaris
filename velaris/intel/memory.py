"""Long-term memory: facts the company's agents learn and can recall later.

A memory is one self-contained statement ("Invoices above ₹50,000 need the
finance head's approval") with a scope, a source and a validity period.

  remember(text, ...)   1. a model splits the text into atomic facts
                           (or, with no model, each sentence is a fact)
                        2. each fact is compared with the nearest stored memories
                        3. same words      → nothing is written
                           related         → a model decides: ADD, UPDATE the old
                                             one, or NONE; contradictions UPDATE
                           unrelated       → ADD
                        4. an UPDATE never overwrites: the old memory is closed
                           (invalid_at = now) and the new one points back to it
  recall(query, ...)    hybrid score = meaning (embedding) + shared words,
                        weighted by recency; only currently valid memories
                        unless `at` asks for the state at an earlier time
  history(id)           the chain of versions behind a memory
  list_scope(scope)     every memory of one scope (valid now, or at `at`), oldest
                        first, for export; never more than that one scope

Nothing is ever deleted, so "what did we believe on 1 March, and who told us?"
always has an answer. Scopes keep one company's or person's memories apart:
recall never crosses a scope.
"""
from __future__ import annotations

import json
import re
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from velaris.intel import guard, trace
from velaris.intel.llm import LLM, LLMError, cosine, extract_json
from velaris.intel.paths import data_dir

RELATED_AT = 0.60        # cosine at or above this: ask whether it updates an old memory
HALF_LIFE_DAYS = 180.0   # recency weight halves over this period
_SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY, scope TEXT NOT NULL, text TEXT NOT NULL, embedding TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT '', created_at REAL NOT NULL, invalid_at REAL,
    supersedes TEXT, trace_hash TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS ix_memories_scope ON memories (scope, invalid_at);
"""


@dataclass
class Memory:
    id: str
    scope: str
    text: str
    source: str
    created_at: float
    invalid_at: Optional[float]
    supersedes: Optional[str]
    score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()


def _tokens(text: str) -> list:
    return re.findall(r"\w+", text.lower())


def _words(text: str) -> set:
    return set(re.findall(r"[a-z0-9]{3,}", text.lower()))


class MemoryStore:
    def __init__(self, llm: Optional[LLM] = None, *, path: Optional[str] = None) -> None:
        self.llm = llm or LLM()
        self._db = sqlite3.connect(path or str(data_dir() / "memory.db"), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.executescript(_SCHEMA)
        self._lock = threading.Lock()

    # ── reading ──────────────────────────────────────────────────────────────
    def _rows(self, scope: str, at: Optional[float]) -> List[sqlite3.Row]:
        if at is None:
            q, args = "SELECT * FROM memories WHERE scope=? AND invalid_at IS NULL", (scope,)
        else:
            q = "SELECT * FROM memories WHERE scope=? AND created_at<=? AND (invalid_at IS NULL OR invalid_at>?)"
            args = (scope, at, at)
        return self._db.execute(q, args).fetchall()

    @staticmethod
    def _mem(r: sqlite3.Row, score: float = 0.0) -> Memory:
        return Memory(r["id"], r["scope"], r["text"], r["source"], r["created_at"], r["invalid_at"],
                      r["supersedes"], round(score, 4))

    def _nearest(self, scope: str, vec: List[float], k: int, at: Optional[float] = None) -> List[tuple]:
        # ponytail: linear scan over the scope. Fine to tens of thousands of memories per
        # scope; move to pgvector (the platform already runs Postgres) beyond that.
        scored = [(cosine(vec, json.loads(r["embedding"])), r) for r in self._rows(scope, at)]
        return sorted(scored, key=lambda x: x[0], reverse=True)[:k]

    def recall(self, query: str, *, scope: str, k: int = 5, at: Optional[float] = None) -> List[Memory]:
        """The k most relevant memories in `scope`, valid now or at time `at`."""
        vec = self.llm.embed([query])[0]
        q_words, now = _words(query), at or time.time()
        out = []
        for sim, r in self._nearest(scope, vec, k * 4, at):
            overlap = len(q_words & _words(r["text"])) / (len(q_words) or 1)
            age_days = max(0.0, (now - r["created_at"]) / 86400)
            recency = 0.5 ** (age_days / HALF_LIFE_DAYS)
            out.append(self._mem(r, (0.7 * sim + 0.3 * overlap) * (0.8 + 0.2 * recency)))
        out.sort(key=lambda m: m.score, reverse=True)
        trace.append("memory", "recall", {"scope": scope, "query_chars": len(query), "returned": len(out[:k])})
        return out[:k]

    def list_scope(self, scope: str, *, at: Optional[float] = None) -> List[Memory]:
        """Every memory in exactly `scope` that is valid now (or was at time `at`), oldest first.

        The scope is matched exactly (no prefixes or patterns), so listing one scope never
        returns another's memories. Raises ValueError for a scope that is not a non-empty string.
        """
        if not isinstance(scope, str) or not scope.strip():
            raise ValueError("scope must be a non-empty string")
        rows = sorted(self._rows(scope, at), key=lambda r: (r["created_at"], r["id"]))
        trace.append("memory", "list", {"scope": scope, "returned": len(rows)})
        return [self._mem(r) for r in rows]

    def history(self, memory_id: str) -> List[Memory]:
        """This memory and every earlier version it replaced, newest first."""
        chain, cur = [], memory_id
        while cur:
            r = self._db.execute("SELECT * FROM memories WHERE id=?", (cur,)).fetchone()
            if not r:
                break
            chain.append(self._mem(r))
            cur = r["supersedes"]
        return chain

    # ── writing ──────────────────────────────────────────────────────────────
    def _facts(self, text: str) -> List[str]:
        """Atomic facts in `text`. Falls back to sentences if no model answers."""
        preamble, block = guard.wrap(text[:8000], label="text to take facts from")
        prompt = (f"{preamble}\n\n{block}\n\nList the durable facts in that text that would be worth remembering "
                  "months from now: decisions, rules, preferences, people's roles, amounts, dates. One fact per "
                  "item, each a complete sentence that makes sense on its own (replace 'he', 'it', 'that' with "
                  "the names). Skip greetings, opinions about the conversation and anything temporary. "
                  'Reply with JSON only: {"facts": ["...", "..."]}')
        try:
            data = extract_json(self.llm.complete(prompt, max_tokens=700, temperature=0.0,
                                                  purpose="memory.extract").text)
            facts = [f.strip() for f in data.get("facts", []) if isinstance(f, str) and len(f.strip()) > 8]
            if facts:
                return facts[:25]
        except (LLMError, AttributeError) as e:
            trace.append("memory", "extract.fallback", {"reason": str(e)[:120]})
        return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if len(s.strip()) > 20][:25]

    def _decide(self, fact: str, related: List[sqlite3.Row]) -> Dict[str, Any]:
        """ADD, UPDATE <id> or NONE for a fact that resembles existing memories."""
        listing = "\n".join(f'{i}: {r["text"]}' for i, r in enumerate(related))
        prompt = ("Existing memories:\n" + listing + f"\n\nNew fact: {fact}\n\n"
                  "Choose one:\n- NONE: an existing memory already says this.\n"
                  "- UPDATE: the new fact corrects, replaces or adds detail to exactly one existing memory "
                  "(give its number). The new fact wins.\n- ADD: it is a separate fact.\n"
                  'Reply with JSON only: {"action": "ADD|UPDATE|NONE", "target": <number or null>}')
        try:
            d = extract_json(self.llm.complete(prompt, max_tokens=60, temperature=0.0, purpose="memory.decide").text)
            action = str(d.get("action", "")).upper()
            target = d.get("target")
            if action == "UPDATE" and isinstance(target, int) and 0 <= target < len(related):
                return {"action": "UPDATE", "target": related[target]["id"]}
            if action in ("ADD", "NONE"):
                return {"action": action, "target": None}
        except (LLMError, AttributeError) as e:
            trace.append("memory", "decide.fallback", {"reason": str(e)[:120]})
        return {"action": "ADD", "target": None}     # when unsure, keep the fact: nothing is lost by adding

    def remember(self, text: str, *, scope: str, source: str = "") -> List[Dict[str, Any]]:
        """Store what is worth keeping from `text`. Returns one record per fact with the action taken.

        Secrets and personal identifiers are masked before anything is stored.
        Text that the guard blocks is not stored at all.
        """
        if guard.scan(text, source=source or "memory.remember").blocked:
            trace.append("memory", "remember.refused", {"scope": scope, "source": source})
            return [{"action": "REFUSED", "text": "", "reason": "blocked_by_guard"}]
        text, masked = guard.redact(text)
        facts = self._facts(text)
        if not facts:
            return []
        vectors = self.llm.embed(facts)
        results: List[Dict[str, Any]] = []
        with self._lock:
            for fact, vec in zip(facts, vectors):
                near = self._nearest(scope, vec, 5)
                # Only the same words in the same order count as a duplicate. A near-identical
                # sentence can still be a correction ("50,000" -> "75,000", "need" -> "need not"),
                # so anything else that is close goes to the model below.
                if near and _tokens(fact) == _tokens(near[0][1]["text"]):
                    results.append({"action": "NONE", "text": fact, "id": near[0][1]["id"]})
                    continue
                related = [r for sim, r in near if sim >= RELATED_AT]
                decision = self._decide(fact, related) if related else {"action": "ADD", "target": None}
                if decision["action"] == "NONE":
                    results.append({"action": "NONE", "text": fact, "id": None})
                    continue
                now, new_id = time.time(), str(uuid.uuid4())
                entry = trace.append("memory", "write", {"scope": scope, "id": new_id, "source": source,
                                                         "action": decision["action"],
                                                         "supersedes": decision["target"]})
                if decision["action"] == "UPDATE":
                    self._db.execute("UPDATE memories SET invalid_at=? WHERE id=?", (now, decision["target"]))
                self._db.execute(
                    "INSERT INTO memories (id, scope, text, embedding, source, created_at, supersedes, trace_hash) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (new_id, scope, fact, json.dumps(vec), source, now, decision["target"], entry["hash"]))
                self._db.commit()
                results.append({"action": decision["action"], "text": fact, "id": new_id,
                                "supersedes": decision["target"]})
        if masked:
            trace.append("memory", "redacted", {"scope": scope, "kinds": masked})
        return results

    def forget(self, memory_id: str, *, reason: str) -> bool:
        """Close a memory (it stops being recalled). The record and its history remain."""
        with self._lock:
            cur = self._db.execute("UPDATE memories SET invalid_at=? WHERE id=? AND invalid_at IS NULL",
                                   (time.time(), memory_id))
            self._db.commit()
        if cur.rowcount:
            trace.append("memory", "forget", {"id": memory_id, "reason": reason})
        return bool(cur.rowcount)

    def count(self, scope: str) -> int:
        return len(self._rows(scope, None))

