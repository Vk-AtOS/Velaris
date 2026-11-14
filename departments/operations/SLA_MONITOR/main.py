#!/usr/bin/env python3
"""
SLA_MONITOR — Velaris BOS agent for Knackforge
Ported from VKatOS sla_monitor. Tracks client/delivery SLA commitments and surfaces breaches.
"""
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from velaris.intel.paths import agent_file

logger = logging.getLogger("SLA_MONITOR")


class SLAMonitor:
    def __init__(self, db_path: str = ""):
        db_path = db_path or agent_file("SLA_MONITOR", "sla_data.db")
        self.db = sqlite3.connect(db_path)
        self._init_db()

    def _init_db(self):
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS commitments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client TEXT, description TEXT, deadline TEXT,
                status TEXT DEFAULT 'open', created_at TEXT, priority TEXT DEFAULT 'normal');
            CREATE TABLE IF NOT EXISTS breaches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                commitment_id INTEGER, detected_at TEXT, hours_overdue REAL);
        """)
        self.db.commit()

    def add(self, client: str, description: str, deadline_hours: float, priority: str = "normal") -> int:
        deadline = (datetime.utcnow() + timedelta(hours=deadline_hours)).isoformat()
        cursor = self.db.execute(
            "INSERT INTO commitments (client,description,deadline,created_at,priority) VALUES (?,?,?,?,?)",
            (client, description, deadline, datetime.utcnow().isoformat(), priority),
        )
        self.db.commit()
        logger.info("Tracking SLA: %s — %s (due in %.0fh, %s)", client, description, deadline_hours, priority)
        return cursor.lastrowid

    def close(self, commitment_id: int) -> None:
        self.db.execute("UPDATE commitments SET status='closed' WHERE id=?", (commitment_id,))
        self.db.commit()
        logger.info("Closed commitment %d", commitment_id)

    def scan(self) -> List[Dict]:
        now = datetime.utcnow().isoformat()
        overdue = self.db.execute(
            "SELECT id,client,description,deadline,priority FROM commitments WHERE status='open' AND deadline<?",
            (now,),
        ).fetchall()
        breaches = []
        for cid, client, desc, deadline, priority in overdue:
            hours = (datetime.utcnow() - datetime.fromisoformat(deadline)).total_seconds() / 3600
            recent = self.db.execute(
                "SELECT id FROM breaches WHERE commitment_id=? AND detected_at>?",
                (cid, (datetime.utcnow() - timedelta(hours=1)).isoformat()),
            ).fetchone()
            if not recent:
                self.db.execute(
                    "INSERT INTO breaches (commitment_id,detected_at,hours_overdue) VALUES (?,?,?)",
                    (cid, now, round(hours, 1)),
                )
                self.db.commit()
                breach = {"commitment_id": cid, "client": client, "description": desc,
                          "hours_overdue": round(hours, 1), "priority": priority}
                breaches.append(breach)
                logger.warning("SLA BREACH: %s — %s (%.1fh overdue)", client, desc, hours)
        return breaches

    def dashboard(self) -> List[Dict]:
        rows = self.db.execute(
            "SELECT id,client,description,deadline,priority FROM commitments WHERE status='open' ORDER BY deadline"
        ).fetchall()
        now = datetime.utcnow()
        result = []
        for cid, client, desc, deadline, priority in rows:
            dt = datetime.fromisoformat(deadline)
            if dt < now:
                h = (now - dt).total_seconds() / 3600
                state = "breached"
                hours_delta = -round(h, 1)
            else:
                h = (dt - now).total_seconds() / 3600
                state = "due_soon" if h < 1 else "ok"
                hours_delta = round(h, 1)
            result.append({"id": cid, "client": client, "description": desc,
                           "priority": priority, "state": state, "hours": hours_delta})
        return result


class SLAMonitorAgent:
    """
    SLA commitment tracker — add deadlines, scan for breaches, surface dashboard.
    Ported from VKatOS sla_monitor.
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        db_path = self.config.get("db_path") or agent_file("SLA_MONITOR", "sla_data.db")
        self.monitor = SLAMonitor(db_path)
        logger.info("SLA_MONITOR agent initialised")

    def health_check(self) -> Dict[str, Any]:
        return {"agent": "SLA_MONITOR", "status": "ok"}

    def add_commitment(
        self, client: str, description: str, deadline_hours: float, priority: str = "normal"
    ) -> int:
        return self.monitor.add(client, description, deadline_hours, priority)

    def check_breaches(self) -> List[Dict]:
        return self.monitor.scan()

    def resolve(self, commitment_id: int) -> None:
        self.monitor.close(commitment_id)

    def dashboard(self) -> List[Dict]:
        return self.monitor.dashboard()


if __name__ == "__main__":
    agent = SLAMonitorAgent()
    print(agent.health_check())
    cid = agent.add_commitment("Healthcare Client", "Deliver sprint report", 24, "high")
    agent.add_commitment("AdTech Client", "Deploy new pipeline", 48)
    print(agent.dashboard())
    print(agent.check_breaches())
