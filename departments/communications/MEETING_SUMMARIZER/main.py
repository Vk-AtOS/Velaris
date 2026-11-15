"""Meeting summarizer: builds a rule-based summary, decisions and action items from a transcript and stores them.

summarize(transcript, meeting_meta) takes a dict with "text" and "segments" (each segment has "text") and optional meta
(call_id, title, participants, recorded_at, transcript_path). It returns the summary (the five highest keyword-scoring
sentences in original order), decisions and action_items_raw (segments matching fixed regex phrase lists), word and
segment counts. No LLM is used; the llm_callable hook is declared but never called. summarize_from_file(path, meta) loads
a transcript JSON file first; a missing or invalid file raises OSError or ValueError. get_recent_meetings(limit) and
get_meeting(id) read back rows; an unknown id returns {"error": "not_found"}.
State: sqlite at <VELARIS_DATA>/agents/MEETING_SUMMARIZER/meetings.db, one row per summarize() call.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

import logging
import json
import re
import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional
from velaris.intel.paths import agent_file

logger = logging.getLogger("MEETING_SUMMARIZER")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - MEETING_SUMMARIZER - %(levelname)s - %(message)s"))
logger.addHandler(handler)


# Phrases that signal a decision or action item in transcript text
_DECISION_SIGNALS = [
    r"\bwe(?:'re| are| will| decided| agreed| confirmed)\b",
    r"\bit(?:'s| is) decided\b",
    r"\bgoing forward\b",
    r"\bfinal(?:ly|ized)?\b.*\bagree",
    r"\bapproved\b",
    r"\bsigned off\b",
]
_ACTION_SIGNALS = [
    r"\bwill\b.{0,40}\bby\b",
    r"\bneed(?:s)? to\b",
    r"\baction item\b",
    r"\btake(?:s)? care of\b",
    r"\bfollows?\s+up\b",
    r"\bdeadline\b",
    r"\bdue\b.{0,20}\b(?:monday|tuesday|wednesday|thursday|friday|today|tomorrow|next week)\b",
    r"\bassign(?:ed)?\b",
    r"\bresponsib",
]


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(agent_file("MEETING_SUMMARIZER", "meetings.db"))
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS meetings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            call_id TEXT,
            title TEXT,
            participants TEXT,
            recorded_at TEXT,
            transcript_path TEXT,
            summary TEXT,
            decisions TEXT,
            action_items TEXT,
            created_on TEXT NOT NULL
        );
    """)
    conn.commit()
    return conn


def _extract_decisions(segments: List[Dict]) -> List[str]:
    decisions = []
    for seg in segments:
        text = seg.get("text", "")
        for pattern in _DECISION_SIGNALS:
            if re.search(pattern, text, re.IGNORECASE):
                decisions.append(text.strip())
                break
    return decisions


def _extract_action_items_raw(segments: List[Dict]) -> List[str]:
    actions = []
    for seg in segments:
        text = seg.get("text", "")
        for pattern in _ACTION_SIGNALS:
            if re.search(pattern, text, re.IGNORECASE):
                actions.append(text.strip())
                break
    return actions


def _rule_based_summary(text: str, segments: List[Dict]) -> str:
    """
    Simple extractive summary: first sentence + topic sentences
    based on keyword density. No LLM needed for a basic summary.
    """
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    if not sentences:
        return ""
    # Score each sentence by keyword presence
    keywords = ["decided", "agreed", "will", "need", "action", "issue", "problem",
                "resolution", "approved", "deadline", "risk", "concern", "client",
                "project", "budget", "team", "delivery"]
    scored = []
    for s in sentences:
        score = sum(1 for k in keywords if k.lower() in s.lower())
        scored.append((score, s))
    scored.sort(key=lambda x: -x[0])
    # Take top 5 unique sentences, preserve order
    top = {s for _, s in scored[:5]}
    summary_sentences = [s for s in sentences if s in top][:5]
    return " ".join(summary_sentences)


class MeetingSummarizer:
    """
    Produces structured meeting summaries from transcripts.
    Works purely rule-based (no LLM required), extracting:
    - Decisions (sentences signalling agreement/finalization)
    - Action items (sentences signalling tasks/deadlines)
    - Extractive summary (top-scored sentences)
    Optional: pass an LLM callable for richer summaries.
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._llm = None  # inject via config["llm_callable"] if available
        _db().close()

    def health_check(self) -> Dict[str, Any]:
        return {"agent": "MEETING_SUMMARIZER", "status": "ok"}

    def summarize(self, transcript: Dict[str, Any], meeting_meta: Optional[Dict] = None) -> Dict[str, Any]:
        """
        transcript: output from CALL_TRANSCRIBER (has 'text' + 'segments')
        meeting_meta: optional {"call_id", "title", "participants", "recorded_at", "transcript_path"}
        """
        meta = meeting_meta or {}
        text = transcript.get("text", "")
        segments = transcript.get("segments", [])

        decisions = _extract_decisions(segments)
        action_items_raw = _extract_action_items_raw(segments)
        summary = _rule_based_summary(text, segments)

        result = {
            "call_id": meta.get("call_id", ""),
            "title": meta.get("title", "Meeting"),
            "participants": meta.get("participants", []),
            "recorded_at": meta.get("recorded_at", datetime.now().isoformat()),
            "summary": summary,
            "decisions": decisions,
            "action_items_raw": action_items_raw,
            "word_count": len(text.split()),
            "segment_count": len(segments),
        }

        # Persist to DB
        conn = _db()
        conn.execute(
            "INSERT INTO meetings (call_id, title, participants, recorded_at, transcript_path, summary, decisions, action_items, created_on) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                result["call_id"], result["title"],
                json.dumps(result["participants"]),
                result["recorded_at"],
                meta.get("transcript_path", ""),
                summary,
                json.dumps(decisions),
                json.dumps(action_items_raw),
                datetime.now().isoformat()
            )
        )
        conn.commit()
        conn.close()
        logger.info("Meeting summarized: title=%s decisions=%d actions=%d",
                    result["title"], len(decisions), len(action_items_raw))
        return result

    def summarize_from_file(self, transcript_path: str, meeting_meta: Optional[Dict] = None) -> Dict[str, Any]:
        """Load a transcript JSON file and summarize it."""
        with open(transcript_path, encoding="utf-8") as f:
            transcript = json.load(f)
        meta = meeting_meta or {}
        meta["transcript_path"] = transcript_path
        return self.summarize(transcript, meta)

    def get_recent_meetings(self, limit: int = 10) -> List[Dict]:
        conn = _db()
        rows = conn.execute(
            "SELECT id, call_id, title, recorded_at, summary FROM meetings ORDER BY created_on DESC LIMIT ?",
            (limit,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_meeting(self, meeting_id: int) -> Dict[str, Any]:
        conn = _db()
        row = conn.execute("SELECT * FROM meetings WHERE id=?", (meeting_id,)).fetchone()
        conn.close()
        if not row:
            return {"error": "not_found"}
        d = dict(row)
        d["participants"] = json.loads(d["participants"] or "[]")
        d["decisions"] = json.loads(d["decisions"] or "[]")
        d["action_items"] = json.loads(d["action_items"] or "[]")
        return d
