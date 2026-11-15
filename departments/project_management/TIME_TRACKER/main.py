import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

import logging
import math
import sqlite3
from datetime import datetime, date
from typing import Dict, Any, List, Optional
from velaris.intel.paths import agent_file

from velaris.intel.paths import agent_dir

logger = logging.getLogger("TIME_TRACKER")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - TIME_TRACKER - %(levelname)s - %(message)s"))
logger.addHandler(handler)

_WORK_HOURS_PER_DAY = 8.0
_BILLABLE_TARGET_WEEKLY = 40.0  # hours
_MAX_DAY_HOURS = 24.0


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(agent_file("TIME_TRACKER", "timelog.db"))
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS timelogs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT NOT NULL,
            project_id TEXT NOT NULL,
            task_id TEXT,
            description TEXT,
            log_date TEXT NOT NULL,
            hours REAL NOT NULL,
            billable INTEGER DEFAULT 1,
            created_on TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS active_timers (
            employee_id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            task_id TEXT,
            description TEXT,
            started_at TEXT NOT NULL
        );
    """)
    conn.commit()
    return conn


class TimeTracker:
    """
    Billable hours and utilization tracking per employee and project.
    Supports start/stop timer, manual log entry, weekly utilization reports.
    Integrates with Zoho Projects time logs when configured.
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._billable_target = self.config.get("billable_target_weekly", _BILLABLE_TARGET_WEEKLY)
        _db().close()

    def health_check(self) -> Dict[str, Any]:
        return {"agent": "TIME_TRACKER", "status": "ok",
                "billable_target_weekly_hours": self._billable_target}

    # ── Timer ─────────────────────────────────────────────────────────────
    def start_timer(self, employee_id: str, project_id: str,
                    task_id: str = "", description: str = "") -> Dict[str, Any]:
        conn = _db()
        # stop any existing timer first
        existing = conn.execute("SELECT * FROM active_timers WHERE employee_id=?", (employee_id,)).fetchone()
        if existing:
            self._stop_and_log(conn, employee_id, existing)
        conn.execute(
            "INSERT OR REPLACE INTO active_timers (employee_id, project_id, task_id, description, started_at) VALUES (?,?,?,?,?)",
            (employee_id, project_id, task_id, description, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
        return {"employee_id": employee_id, "project_id": project_id, "status": "timer_started"}

    def stop_timer(self, employee_id: str, billable: bool = True) -> Dict[str, Any]:
        conn = _db()
        row = conn.execute("SELECT * FROM active_timers WHERE employee_id=?", (employee_id,)).fetchone()
        if not row:
            conn.close()
            return {"error": "no_active_timer"}
        log_id = self._stop_and_log(conn, employee_id, row, billable=billable)
        conn.commit()
        conn.close()
        return {"log_id": log_id, "employee_id": employee_id, "status": "timer_stopped"}

    def _stop_and_log(self, conn, employee_id: str, row, billable: bool = True) -> int:
        started_at = datetime.fromisoformat(row["started_at"])
        hours = round((datetime.now() - started_at).total_seconds() / 3600, 2)
        if hours > _MAX_DAY_HOURS:        # a timer left running overnight: same ceiling as a manual entry
            logger.warning("Timer for %s ran %.1f h; logged as %s h", employee_id, hours, _MAX_DAY_HOURS)
            hours = _MAX_DAY_HOURS
        cur = conn.execute(
            "INSERT INTO timelogs (employee_id, project_id, task_id, description, log_date, hours, billable, created_on) VALUES (?,?,?,?,?,?,?,?)",
            (employee_id, row["project_id"], row["task_id"], row["description"],
             date.today().isoformat(), hours, int(billable), datetime.now().isoformat())
        )
        conn.execute("DELETE FROM active_timers WHERE employee_id=?", (employee_id,))
        logger.info("Timer stopped: emp=%s project=%s hours=%.2f", employee_id, row["project_id"], hours)
        return cur.lastrowid

    # ── Manual log ────────────────────────────────────────────────────────
    def log(self, employee_id: str, project_id: str, hours: float,
            log_date: str = "", task_id: str = "", description: str = "",
            billable: bool = True) -> Dict[str, Any]:
        if isinstance(hours, bool) or not isinstance(hours, (int, float)) or not math.isfinite(hours) \
                or hours <= 0 or hours > _MAX_DAY_HOURS:
            return {"error": "hours must be between 0 and 24"}
        log_date = log_date or date.today().isoformat()
        conn = _db()
        cur = conn.execute(
            "INSERT INTO timelogs (employee_id, project_id, task_id, description, log_date, hours, billable, created_on) VALUES (?,?,?,?,?,?,?,?)",
            (employee_id, project_id, task_id, description, log_date, hours, int(billable), datetime.now().isoformat())
        )
        log_id = cur.lastrowid
        conn.commit()
        conn.close()
        return {"id": log_id, "employee_id": employee_id, "project_id": project_id,
                "hours": hours, "log_date": log_date, "billable": billable}

    # ── Reports ───────────────────────────────────────────────────────────
    def weekly_utilization(self, employee_id: str, week_start: str) -> Dict[str, Any]:
        """week_start: ISO date of Monday"""
        conn = _db()
        rows = conn.execute(
            "SELECT project_id, hours, billable, log_date FROM timelogs WHERE employee_id=? AND log_date >= ? AND log_date < date(?, '+7 days')",
            (employee_id, week_start, week_start)
        ).fetchall()
        conn.close()
        total = sum(r["hours"] for r in rows)
        billable_hrs = sum(r["hours"] for r in rows if r["billable"])
        by_project: Dict[str, float] = {}
        for r in rows:
            by_project[r["project_id"]] = round(by_project.get(r["project_id"], 0) + r["hours"], 2)
        return {
            "employee_id": employee_id,
            "week_start": week_start,
            "total_hours": round(total, 2),
            "billable_hours": round(billable_hrs, 2),
            "non_billable_hours": round(total - billable_hrs, 2),
            "utilization_pct": round(billable_hrs / self._billable_target * 100, 1),
            "by_project": by_project,
        }

    def team_utilization(self, employee_ids: List[str], week_start: str) -> List[Dict]:
        return [self.weekly_utilization(e, week_start) for e in employee_ids]

    def project_hours_summary(self, project_id: str,
                               from_date: str, to_date: str) -> Dict[str, Any]:
        conn = _db()
        rows = conn.execute(
            "SELECT employee_id, SUM(hours) as total, SUM(CASE WHEN billable=1 THEN hours ELSE 0 END) as billable FROM timelogs WHERE project_id=? AND log_date BETWEEN ? AND ? GROUP BY employee_id",
            (project_id, from_date, to_date)
        ).fetchall()
        conn.close()
        contributors = [{"employee_id": r["employee_id"], "total": round(r["total"], 2),
                          "billable": round(r["billable"], 2)} for r in rows]
        return {
            "project_id": project_id,
            "from_date": from_date,
            "to_date": to_date,
            "total_hours": round(sum(c["total"] for c in contributors), 2),
            "billable_hours": round(sum(c["billable"] for c in contributors), 2),
            "contributors": sorted(contributors, key=lambda x: -x["total"]),
        }
