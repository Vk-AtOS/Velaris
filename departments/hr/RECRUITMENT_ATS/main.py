#!/usr/bin/env python3
"""
RECRUITMENT_ATS — Velaris BOS agent for Knackforge
Ported from VKatOS recruitment_tracker. Full 8-stage ATS pipeline.
"""
import logging
import sqlite3
import csv
from datetime import datetime, timedelta
from typing import Dict, Any, List
from velaris.intel.paths import agent_file

logger = logging.getLogger("RECRUITMENT_ATS")

STAGES = [
    "sourced", "screened", "shortlisted", "interview_scheduled",
    "interviewed", "offer_made", "offer_accepted", "placed",
]


class RecruitmentTracker:
    def __init__(self, db_path: str = ""):
        db_path = db_path or agent_file("RECRUITMENT_ATS", "recruitment.db")
        self.db = sqlite3.connect(db_path)
        self._init_db()

    def _init_db(self):
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS candidates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT, email TEXT, phone TEXT, role TEXT, client TEXT,
                current_stage TEXT, stage_entered_at TEXT,
                placed INTEGER DEFAULT 0, notes TEXT);
            CREATE TABLE IF NOT EXISTS stage_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id INTEGER, from_stage TEXT,
                to_stage TEXT, moved_at TEXT, notes TEXT);
        """)
        self.db.commit()

    def add(self, name: str, role: str, client: str, email: str = "", phone: str = "") -> int:
        cursor = self.db.execute(
            "INSERT INTO candidates (name,email,phone,role,client,current_stage,stage_entered_at) VALUES (?,?,?,?,?,?,?)",
            (name, email, phone, role, client, "sourced", datetime.utcnow().isoformat()),
        )
        self.db.commit()
        logger.info("Added candidate: %s → %s at %s", name, role, client)
        return cursor.lastrowid

    def move(self, candidate_id: int, new_stage: str, notes: str = "") -> Dict[str, Any]:
        row = self.db.execute(
            "SELECT name,current_stage FROM candidates WHERE id=?", (candidate_id,)
        ).fetchone()
        if not row:
            return {"error": "candidate not found"}
        name, old = row
        now = datetime.utcnow().isoformat()
        self.db.execute(
            "UPDATE candidates SET current_stage=?,stage_entered_at=? WHERE id=?",
            (new_stage, now, candidate_id),
        )
        self.db.execute(
            "INSERT INTO stage_history (candidate_id,from_stage,to_stage,moved_at,notes) VALUES (?,?,?,?,?)",
            (candidate_id, old, new_stage, now, notes),
        )
        if new_stage == "placed":
            self.db.execute("UPDATE candidates SET placed=1 WHERE id=?", (candidate_id,))
        self.db.commit()
        logger.info("%s: %s → %s", name, old, new_stage)
        return {"candidate_id": candidate_id, "name": name, "from": old, "to": new_stage}

    def stale(self, days: int = 3) -> List[Dict]:
        cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
        rows = self.db.execute(
            "SELECT id,name,role,client,current_stage,stage_entered_at FROM candidates WHERE placed=0 AND stage_entered_at<?",
            (cutoff,),
        ).fetchall()
        return [
            {"id": r[0], "name": r[1], "role": r[2], "client": r[3], "stage": r[4], "since": r[5]}
            for r in rows
        ]

    def report(self) -> Dict[str, Any]:
        total = self.db.execute("SELECT COUNT(*) FROM candidates").fetchone()[0]
        placed = self.db.execute(
            "SELECT COUNT(*) FROM candidates WHERE placed=1"
        ).fetchone()[0]
        by_stage = {}
        for stage in STAGES:
            count = self.db.execute(
                "SELECT COUNT(*) FROM candidates WHERE current_stage=?", (stage,)
            ).fetchone()[0]
            by_stage[stage] = count
        return {
            "total": total,
            "placed": placed,
            "placement_rate": round(placed / total * 100, 1) if total else 0,
            "by_stage": by_stage,
        }

    def export(self, filename: str = "candidates.csv") -> str:
        rows = self.db.execute(
            "SELECT name,email,phone,role,client,current_stage,placed FROM candidates"
        ).fetchall()
        with open(filename, "w", newline="") as f:
            csv.writer(f).writerows(
                [["Name", "Email", "Phone", "Role", "Client", "Stage", "Placed"]] + list(rows)
            )
        logger.info("Exported %d candidates to %s", len(rows), filename)
        return filename


class RecruitmentATSAgent:
    """
    ATS pipeline — sourced→screened→shortlisted→interview_scheduled→interviewed→offer_made→offer_accepted→placed.
    Ported from VKatOS recruitment_tracker.
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        db_path = self.config.get("db_path") or agent_file("RECRUITMENT_ATS", "recruitment.db")
        self.tracker = RecruitmentTracker(db_path)
        logger.info("RECRUITMENT_ATS agent initialised")

    def health_check(self) -> Dict[str, Any]:
        return {"agent": "RECRUITMENT_ATS", "status": "ok", "stages": STAGES}

    def add_candidate(
        self, name: str, role: str, client: str, email: str = "", phone: str = ""
    ) -> int:
        return self.tracker.add(name, role, client, email, phone)

    def advance_stage(self, candidate_id: int, stage: str, notes: str = "") -> Dict[str, Any]:
        return self.tracker.move(candidate_id, stage, notes)

    def get_stale(self, days: int = 3) -> List[Dict]:
        return self.tracker.stale(days)

    def report(self) -> Dict[str, Any]:
        return self.tracker.report()

    def export_csv(self, filename: str = "candidates.csv") -> str:
        return self.tracker.export(filename)


if __name__ == "__main__":
    agent = RecruitmentATSAgent()
    print(agent.health_check())
    cid = agent.add_candidate("Arjun Kumar", "AI Engineer", "Knackforge")
    agent.advance_stage(cid, "screened")
    agent.advance_stage(cid, "shortlisted")
    print(agent.report())
