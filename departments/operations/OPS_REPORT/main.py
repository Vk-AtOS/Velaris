#!/usr/bin/env python3
"""
OPS_REPORT — Velaris BOS agent for Knackforge
Ported from VKatOS ops_report. Daily operations report with categories, blockers, and export.
"""
import logging
import sqlite3

from velaris.core.sqlite_util import connect as connect_db
from datetime import datetime
from typing import Dict, Any, List, Optional
from velaris.intel.paths import agent_file

from velaris.intel.paths import agent_dir

logger = logging.getLogger("OPS_REPORT")


class OpsReport:
    def __init__(self, company: str = "Knackforge", db_path: str = ""):
        db_path = db_path or agent_file("OPS_REPORT", "ops_data.db")
        self.company = company
        self.db = connect_db(db_path or str(agent_dir("OPS_REPORT") / "ops_data.db"))   # under VELARIS_DATA, not the working directory
        self._init_db()

    def _init_db(self):
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS daily_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT, item TEXT, value TEXT,
                timestamp TEXT, member TEXT);
            CREATE TABLE IF NOT EXISTS blockers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                description TEXT, owner TEXT,
                reported_at TEXT, resolved INTEGER DEFAULT 0);
        """)
        self.db.commit()

    def log(self, category: str, item: str, value: str, member: str = "") -> None:
        self.db.execute(
            "INSERT INTO daily_log (category,item,value,timestamp,member) VALUES (?,?,?,?,?)",
            (category, item, str(value), datetime.utcnow().isoformat(), member),
        )
        self.db.commit()
        logger.info("Logged: [%s] %s = %s", category, item, value)

    def add_blocker(self, description: str, owner: str) -> int:
        cursor = self.db.execute(
            "INSERT INTO blockers (description,owner,reported_at) VALUES (?,?,?)",
            (description, owner, datetime.utcnow().isoformat()),
        )
        self.db.commit()
        logger.warning("Blocker added: %s (owner: %s)", description, owner)
        return cursor.lastrowid

    def resolve_blocker(self, blocker_id: int) -> None:
        self.db.execute("UPDATE blockers SET resolved=1 WHERE id=?", (blocker_id,))
        self.db.commit()
        logger.info("Blocker %d resolved", blocker_id)

    def generate(self, date: Optional[str] = None) -> str:
        date = date or datetime.utcnow().strftime("%Y-%m-%d")      # entries are stamped in UTC
        rows = self.db.execute(
            "SELECT category,item,value,member FROM daily_log WHERE timestamp LIKE ? ORDER BY category",
            (f"{date}%",),
        ).fetchall()
        blockers = self.db.execute(
            "SELECT description,owner FROM blockers WHERE resolved=0"
        ).fetchall()
        cats: Dict[str, list] = {}
        for cat, item, val, member in rows:
            cats.setdefault(cat, []).append((item, val, member))
        lines = [
            "=" * 55,
            f"  {self.company}",
            f"  Operations Report — {datetime.strptime(date, '%Y-%m-%d').strftime('%d %b %Y')}",
            "=" * 55,
            "",
        ]
        for cat, items in cats.items():
            lines.append(f"{cat.upper()}")
            for item, val, member in items:
                m = f" ({member})" if member else ""
                lines.append(f"  - {item}: {val}{m}")
            lines.append("")
        if blockers:
            lines.append("BLOCKERS")
            for desc, owner in blockers:
                lines.append(f"  ! {desc} — {owner}")
            lines.append("")
        lines.append("-" * 55)
        return "\n".join(lines)

    def generate_dict(self, date: Optional[str] = None) -> Dict[str, Any]:
        date = date or datetime.utcnow().strftime("%Y-%m-%d")      # entries are stamped in UTC
        rows = self.db.execute(
            "SELECT category,item,value,member FROM daily_log WHERE timestamp LIKE ? ORDER BY category",
            (f"{date}%",),
        ).fetchall()
        blockers = self.db.execute(
            "SELECT id,description,owner FROM blockers WHERE resolved=0"
        ).fetchall()
        cats: Dict[str, list] = {}
        for cat, item, val, member in rows:
            cats.setdefault(cat, []).append({"item": item, "value": val, "member": member})
        return {
            "date": date,
            "company": self.company,
            "categories": cats,
            "open_blockers": [{"id": b[0], "description": b[1], "owner": b[2]} for b in blockers],
        }


class OpsReportAgent:
    """
    Daily ops report — log entries by category, track blockers, generate text or dict reports.
    Ported from VKatOS ops_report.
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        company = self.config.get("company", "Knackforge")
        db_path = self.config.get("db_path") or agent_file("OPS_REPORT", "ops_data.db")
        self.report = OpsReport(company, db_path)
        logger.info("OPS_REPORT agent initialised for %s", company)

    def health_check(self) -> Dict[str, Any]:
        return {"agent": "OPS_REPORT", "status": "ok"}

    def log(self, category: str, item: str, value: str, member: str = "") -> None:
        self.report.log(category, item, value, member)

    def add_blocker(self, description: str, owner: str) -> int:
        return self.report.add_blocker(description, owner)

    def resolve_blocker(self, blocker_id: int) -> None:
        self.report.resolve_blocker(blocker_id)

    def generate_report(self, date: Optional[str] = None) -> str:
        return self.report.generate(date)

    def generate_report_dict(self, date: Optional[str] = None) -> Dict[str, Any]:
        return self.report.generate_dict(date)


if __name__ == "__main__":
    agent = OpsReportAgent({"company": "Knackforge Soft Solutions"})
    print(agent.health_check())
    agent.log("Delivery", "Sprints completed", "3", "Arjun")
    agent.log("Sales", "Proposals sent", "2", "Priya")
    agent.log("HR", "Interviews scheduled", "5")
    bid = agent.add_blocker("AWS Bedrock quota increase pending", "DevOps team")
    print(agent.generate_report())
    print(agent.generate_report_dict())
