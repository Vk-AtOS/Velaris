"""Action item extractor: finds action items in meeting text with fixed regex patterns and stores them (no LLM).

extract_from_segments(segments, meeting_id="") keeps each {"text", "start", "end"} segment that matches an action phrase
("will ... by", "needs to", "follow up", "deadline", ...), guesses an owner from patterns such as "Asha will" or
"assigned to Asha", and a due date: an ISO date after "by", today / tomorrow / next week resolved to ISO dates, or a text
hint such as "oct 15" or "friday" kept as written. Each item is saved and returned as {id, text, owner, due_date, status,
meeting_id}. extract_from_text(text, meeting_id="") splits the text into sentences first. close_item(item_id) marks an
item closed (an unknown id is not reported). get_open_items(owner=None) lists open items; get_overdue() lists open items
whose due date is an ISO date before today (a text hint is never overdue). health_check() returns status ok.
State: sqlite, encrypted at rest (velaris.core.sealed_sqlite), <VELARIS_DATA>/agents/ACTION_ITEM_EXTRACTOR/action_items.db (table action_items). No caller check is made.
Failure: a segment that is not a dict, or non-text input, raises AttributeError or TypeError; sqlite errors propagate.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

import logging
import json
import re
import sqlite3
from datetime import date, datetime, timedelta

from velaris.core.sealed_sqlite import connect_sealed
from typing import Dict, Any, List, Optional
from velaris.intel.paths import agent_file

logger = logging.getLogger("ACTION_ITEM_EXTRACTOR")


# Relative date resolution keywords
_DAY_MAP = {"today": 0, "tomorrow": 1, "monday": None, "tuesday": None,
            "wednesday": None, "thursday": None, "friday": None,
            "next week": 7, "end of week": None, "eow": None, "eod": 0}

# Owner extraction: "John will...", "assigned to Sarah", "Sarah to..."
_OWNER_PATTERNS = [
    r"^([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)\s+(?:will|to|needs to|should)\b",
    r"assigned to\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)\b",
    r"([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)\s+(?:is responsible|takes care)\b",
]


def _db() -> sqlite3.Connection:
    conn = connect_sealed(agent_file("ACTION_ITEM_EXTRACTOR", "action_items.db"), "agent:ACTION_ITEM_EXTRACTOR")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS action_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meeting_id TEXT,
            text TEXT NOT NULL,
            owner TEXT,
            due_date TEXT,
            status TEXT DEFAULT 'open',
            source_segment TEXT,
            created_on TEXT NOT NULL,
            closed_on TEXT
        );
    """)
    conn.commit()
    return conn


def _extract_owner(text: str) -> Optional[str]:
    for pattern in _OWNER_PATTERNS:
        m = re.search(pattern, text)
        if m:
            return m.group(1)
    return None


def _extract_due_hint(text: str) -> Optional[str]:
    lower = text.lower()
    # Explicit date: "by Oct 15" / "by 2026-10-15"
    m = re.search(r'\bby\s+(\d{4}-\d{2}-\d{2})\b', lower)
    if m:
        return m.group(1)
    m = re.search(r'\bby\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*\s+(\d{1,2})\b', lower)
    if m:
        return f"{m.group(1)[:3]} {m.group(2)}"  # hint string, not ISO
    # Relative
    for keyword in _DAY_MAP:
        if keyword in lower:
            if _DAY_MAP[keyword] is not None:
                due = date.today() + timedelta(days=_DAY_MAP[keyword])
                return due.isoformat()
            return keyword
    return None


class ActionItemExtractor:
    """
    Extracts structured action items from meeting transcripts or text,
    inferring owner and due-date hints from natural language patterns.
    Creates tasks in local SQLite; ready to integrate with Zoho Projects or Jira.
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        _db().close()

    def health_check(self) -> Dict[str, Any]:
        return {"agent": "ACTION_ITEM_EXTRACTOR", "status": "ok"}

    def extract_from_segments(self, segments: List[Dict], meeting_id: str = "") -> List[Dict[str, Any]]:
        """
        segments: list of {"text": "...", "start": 0.0, "end": 5.0}
        Returns extracted action items (also saves to DB).
        """
        action_signals = [
            r"\bwill\b.{2,60}\bby\b",
            r"\bneed(?:s)? to\b",
            r"\baction item\b",
            r"\btake(?:s)? care of\b",
            r"\bfollow(?:s)?\s*up\b",
            r"\bdue\b",
            r"\bdeadline\b",
            r"\bresponsib",
            r"\bassign(?:ed)?\b",
            r"\bensure\b",
            r"\bsend\b.{0,30}\bby\b",
            r"\bshare\b.{0,30}\bwith\b",
        ]
        items = []
        conn = _db()
        for seg in segments:
            text = seg.get("text", "").strip()
            matched = any(re.search(p, text, re.IGNORECASE) for p in action_signals)
            if not matched:
                continue
            owner = _extract_owner(text)
            due_hint = _extract_due_hint(text)
            cur = conn.execute(
                "INSERT INTO action_items (meeting_id, text, owner, due_date, source_segment, created_on) VALUES (?,?,?,?,?,?)",
                (meeting_id, text, owner, due_hint,
                 json.dumps({"start": seg.get("start"), "end": seg.get("end")}),
                 datetime.now().isoformat())
            )
            items.append({
                "id": cur.lastrowid,
                "text": text,
                "owner": owner,
                "due_date": due_hint,
                "status": "open",
                "meeting_id": meeting_id,
            })
        conn.commit()
        conn.close()
        logger.info("Extracted %d action items from meeting %s", len(items), meeting_id)
        return items

    def extract_from_text(self, text: str, meeting_id: str = "") -> List[Dict[str, Any]]:
        """Convenience: split text into pseudo-segments and extract."""
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        segments = [{"text": s} for s in sentences]
        return self.extract_from_segments(segments, meeting_id)

    def close_item(self, item_id: int) -> Dict[str, Any]:
        conn = _db()
        conn.execute(
            "UPDATE action_items SET status='closed', closed_on=? WHERE id=?",
            (datetime.now().isoformat(), item_id)
        )
        conn.commit()
        conn.close()
        return {"id": item_id, "status": "closed"}

    def get_open_items(self, owner: Optional[str] = None) -> List[Dict]:
        conn = _db()
        if owner:
            rows = conn.execute(
                "SELECT * FROM action_items WHERE status='open' AND owner=? ORDER BY created_on",
                (owner,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM action_items WHERE status='open' ORDER BY created_on"
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def get_overdue(self) -> List[Dict]:
        today = date.today().isoformat()
        conn = _db()
        rows = conn.execute(
            # ISO dates only: a hint such as "oct 15" is text, and comparing it with an ISO date as strings gave wrong answers
            "SELECT * FROM action_items WHERE status='open' AND due_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' AND due_date < ?",
            (today,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
