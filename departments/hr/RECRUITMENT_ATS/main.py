#!/usr/bin/env python3
"""
RECRUITMENT_ATS — Velaris BOS agent for Knackforge
Ported from VKatOS recruitment_tracker. Full 8-stage ATS pipeline.

LEGACY: ATS_CORE is the product with consent, retention and erasure; this older tracker has none of those. Until it is merged into
ATS_CORE or retired (owner decision), every method needs an authenticated Caller (velaris.core.access): changes need the recruiter or
hr_admin role, reads and the CSV export go through authorize_read("candidate") (traced). Every row carries the organisation and
every query filters on it, the acting person is recorded in stage_history, a stage must be one of STAGES and move one step forward
or back, and the database and export live under VELARIS_DATA, never in the working directory. Raises AccessDenied when refused.
"""
import csv
import io
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any, List

from velaris.agentkit.onboarding_common import gate_change, gate_read
from velaris.intel.paths import agent_dir, private_dir, write_private

logger = logging.getLogger("RECRUITMENT_ATS")

RECRUITERS = frozenset({"recruiter", "hr_admin"})
STAGES = [
    "sourced", "screened", "shortlisted", "interview_scheduled",
    "interviewed", "offer_made", "offer_accepted", "placed",
]


class RecruitmentTracker:
    def __init__(self, db_path: str = ""):
        self.db = sqlite3.connect(db_path or str(agent_dir("RECRUITMENT_ATS") / "recruitment.db"))
        self._init_db()

    def _init_db(self):
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT, email TEXT, phone TEXT, role TEXT, client TEXT,
                current_stage TEXT, stage_entered_at TEXT,
                placed INTEGER DEFAULT 0, notes TEXT, org TEXT);
            CREATE TABLE IF NOT EXISTS stage_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id INTEGER, from_stage TEXT,
                to_stage TEXT, moved_at TEXT, notes TEXT, moved_by TEXT);
        """)
        for table, col in (("candidates", "org"), ("stage_history", "moved_by")):     # databases made before these columns existed
            if col not in {r[1] for r in self.db.execute(f"PRAGMA table_info({table})")}:
                self.db.execute(f"ALTER TABLE {table} ADD COLUMN {col} TEXT")
        self.db.commit()

    def add(self, org: str, name: str, role: str, client: str, email: str = "", phone: str = "") -> int:
        cursor = self.db.execute(
            "INSERT INTO candidates (name,email,phone,role,client,current_stage,stage_entered_at,org) VALUES (?,?,?,?,?,?,?,?)",
            (name, email, phone, role, client, "sourced", datetime.utcnow().isoformat(), org),
        )
        self.db.commit()
        logger.info("Added candidate %s", cursor.lastrowid)
        return cursor.lastrowid

    def move(self, org: str, by: str, candidate_id: int, new_stage: str, notes: str = "") -> Dict[str, Any]:
        if new_stage not in STAGES:
            return {"error": f"stage must be one of {STAGES}"}
        row = self.db.execute(
            "SELECT name,current_stage FROM candidates WHERE id=? AND org=?", (candidate_id, org)
        ).fetchone()
        if not row:
            return {"error": "candidate not found"}
        name, old = row
        if abs(STAGES.index(new_stage) - STAGES.index(old)) != 1:
            return {"error": f"{old} cannot move to {new_stage}: one step forward or back at a time"}
        now = datetime.utcnow().isoformat()
        self.db.execute(
            "UPDATE candidates SET current_stage=?,stage_entered_at=? WHERE id=? AND org=?",
            (new_stage, now, candidate_id, org),
        )
        self.db.execute(
            "INSERT INTO stage_history (candidate_id,from_stage,to_stage,moved_at,notes,moved_by) VALUES (?,?,?,?,?,?)",
            (candidate_id, old, new_stage, now, notes, by),
        )
        if new_stage == "placed":
            self.db.execute("UPDATE candidates SET placed=1 WHERE id=?", (candidate_id,))
        self.db.commit()
        logger.info("candidate %s: %s -> %s", candidate_id, old, new_stage)
        return {"candidate_id": candidate_id, "name": name, "from": old, "to": new_stage, "by": by}

    def stale(self, org: str, days: int = 3) -> List[Dict]:
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        rows = self.db.execute(
            "SELECT id,name,role,client,current_stage,stage_entered_at FROM candidates WHERE placed=0 AND stage_entered_at<? AND org=?",
            (cutoff, org),
        ).fetchall()
        return [
            {"id": r[0], "name": r[1], "role": r[2], "client": r[3], "stage": r[4], "since": r[5]}
            for r in rows
        ]

    def report(self, org: str) -> Dict[str, Any]:
        total = self.db.execute("SELECT COUNT(*) FROM candidates WHERE org=?", (org,)).fetchone()[0]
        placed = self.db.execute("SELECT COUNT(*) FROM candidates WHERE placed=1 AND org=?", (org,)).fetchone()[0]
        by_stage = {}
        for stage in STAGES:
            by_stage[stage] = self.db.execute(
                "SELECT COUNT(*) FROM candidates WHERE current_stage=? AND org=?", (stage, org)).fetchone()[0]
        return {
            "total": total,
            "placed": placed,
            "placement_rate": round(placed / total * 100, 1) if total else 0,
            "by_stage": by_stage,
        }

    def export(self, org: str, filename: str) -> str:
        rows = self.db.execute(
            "SELECT name,email,phone,role,client,current_stage,placed FROM candidates WHERE org=?", (org,)
        ).fetchall()
        out = private_dir(agent_dir("RECRUITMENT_ATS") / "exports") / (str(filename).replace("/", "_").replace("\\", "_").lstrip(".") or "candidates.csv")
        buf = io.StringIO(newline="")
        csv.writer(buf).writerows([["Name", "Email", "Phone", "Role", "Client", "Stage", "Placed"]] + list(rows))
        write_private(out, buf.getvalue())
        logger.info("Exported %d candidates", len(rows))
        return str(out)


class RecruitmentATSAgent:
    """
    ATS pipeline — sourced→screened→shortlisted→interview_scheduled→interviewed→offer_made→offer_accepted→placed.
    Ported from VKatOS recruitment_tracker.
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.tracker = RecruitmentTracker(self.config.get("db_path", ""))
        logger.info("RECRUITMENT_ATS agent initialised")

    def health_check(self) -> Dict[str, Any]:
        return {"agent": "RECRUITMENT_ATS", "status": "ok", "stages": STAGES, "legacy": "use ATS_CORE for consent, retention and erasure"}

    def add_candidate(
        self, name: str, role: str, client: str, email: str = "", phone: str = ""
    ) -> int:
        who = gate_change("RECRUITMENT_ATS", "add_candidate", RECRUITERS)
        return self.tracker.add(who.org, name, role, client, email, phone)

    def advance_stage(self, candidate_id: int, stage: str, notes: str = "") -> Dict[str, Any]:
        who = gate_change("RECRUITMENT_ATS", "advance_stage", RECRUITERS, {"candidate": str(candidate_id)[:20], "to": str(stage)[:30]})
        return self.tracker.move(who.org, who.id, candidate_id, stage, notes)

    def get_stale(self, days: int = 3) -> List[Dict]:
        who = gate_read("RECRUITMENT_ATS", "candidate")
        return self.tracker.stale(who.org, days)

    def report(self) -> Dict[str, Any]:
        who = gate_read("RECRUITMENT_ATS", "candidate")
        return self.tracker.report(who.org)

    def export_csv(self, filename: str = "candidates.csv") -> str:
        """Writes a CSV of the organisation's candidates under VELARIS_DATA and returns its path (owner-only file)."""
        who = gate_read("RECRUITMENT_ATS", "candidate")
        return self.tracker.export(who.org, filename)


if __name__ == "__main__":
    print(RecruitmentATSAgent().health_check())
