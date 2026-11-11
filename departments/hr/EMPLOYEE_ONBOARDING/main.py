#!/usr/bin/env python3
"""
EMPLOYEE_ONBOARDING — Velaris BOS agent for Knackforge
Ported from VKatOS client_onboarding, adapted for employees (IT setup, HR docs, 30/60/90 day plan).
"""
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

logger = logging.getLogger("EMPLOYEE_ONBOARDING")

EMPLOYEE_CHECKLIST = [
    ("offer_letter_signed",   "Offer letter signed",              1),
    ("it_accounts_created",   "IT accounts and email created",    1),
    ("equipment_issued",      "Laptop/equipment issued",          2),
    ("hr_docs_submitted",     "HR documents collected",           3),
    ("system_access_granted", "System access granted",            3),
    ("buddy_assigned",        "Buddy/mentor assigned",            3),
    ("team_intro_done",       "Team introduction complete",       5),
    ("tools_training_done",   "Tools and process training done", 10),
    ("day30_checkin",         "30-day check-in completed",       30),
    ("day60_checkin",         "60-day check-in completed",       60),
    ("day90_review",          "90-day performance review done",  90),
]


class _EmployeeDB:
    def __init__(self, db_path: str = "employee_onboarding.db"):
        self.db = sqlite3.connect(db_path)
        self._init_db()

    def _init_db(self):
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT, email TEXT, department TEXT, role TEXT,
                started_at TEXT, status TEXT DEFAULT 'onboarding');
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER, key TEXT, name TEXT,
                due_date TEXT, completed INTEGER DEFAULT 0, completed_at TEXT);
        """)
        self.db.commit()

    def onboard(self, name: str, email: str, department: str, role: str) -> int:
        now = datetime.utcnow()
        cursor = self.db.execute(
            "INSERT INTO employees (name,email,department,role,started_at) VALUES (?,?,?,?,?)",
            (name, email, department, role, now.isoformat()),
        )
        eid = cursor.lastrowid
        for key, task_name, due_day in EMPLOYEE_CHECKLIST:
            due = (now + timedelta(days=due_day)).isoformat()
            self.db.execute(
                "INSERT INTO tasks (employee_id,key,name,due_date) VALUES (?,?,?,?)",
                (eid, key, task_name, due),
            )
        self.db.commit()
        logger.info("Onboarding started: %s (%s / %s) — %d tasks", name, department, role, len(EMPLOYEE_CHECKLIST))
        return eid

    def complete_step(self, employee_id: int, step_key: str) -> bool:
        result = self.db.execute(
            "UPDATE tasks SET completed=1,completed_at=? WHERE employee_id=? AND key=?",
            (datetime.utcnow().isoformat(), employee_id, step_key),
        )
        self.db.commit()
        ok = result.rowcount > 0
        if ok:
            logger.info("Step completed: employee=%d key=%s", employee_id, step_key)
        return ok

    def overdue(self) -> List[Dict]:
        now = datetime.utcnow().isoformat()
        rows = self.db.execute(
            """SELECT e.name, e.department, t.key, t.name, t.due_date
               FROM tasks t JOIN employees e ON e.id=t.employee_id
               WHERE t.completed=0 AND t.due_date<? ORDER BY t.due_date""",
            (now,),
        ).fetchall()
        return [
            {"employee": r[0], "department": r[1], "step": r[2], "task": r[3], "due": r[4]}
            for r in rows
        ]

    def progress(self, employee_id: Optional[int] = None) -> List[Dict]:
        if employee_id:
            emps = self.db.execute(
                "SELECT id,name,department,role FROM employees WHERE id=?", (employee_id,)
            ).fetchall()
        else:
            emps = self.db.execute(
                "SELECT id,name,department,role FROM employees"
            ).fetchall()
        result = []
        for eid, name, dept, role in emps:
            total = self.db.execute(
                "SELECT COUNT(*) FROM tasks WHERE employee_id=?", (eid,)
            ).fetchone()[0]
            done = self.db.execute(
                "SELECT COUNT(*) FROM tasks WHERE employee_id=? AND completed=1", (eid,)
            ).fetchone()[0]
            result.append({
                "employee_id": eid,
                "name": name,
                "department": dept,
                "role": role,
                "completed": done,
                "total": total,
                "pct": round(done / total * 100, 1) if total else 0,
            })
        return result


class EmployeeOnboardingAgent:
    """
    Employee onboarding — IT setup, HR docs, team intro, 30/60/90 day plan.
    Ported from VKatOS client_onboarding, adapted for employees.
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        db_path = self.config.get("db_path", "employee_onboarding.db")
        self._db = _EmployeeDB(db_path)
        logger.info("EMPLOYEE_ONBOARDING agent initialised")

    def health_check(self) -> Dict[str, Any]:
        return {"agent": "EMPLOYEE_ONBOARDING", "status": "ok", "checklist_steps": len(EMPLOYEE_CHECKLIST)}

    def onboard_employee(self, name: str, email: str, department: str, role: str) -> int:
        return self._db.onboard(name, email, department, role)

    def complete_step(self, employee_id: int, step_key: str) -> bool:
        return self._db.complete_step(employee_id, step_key)

    def get_overdue(self) -> List[Dict]:
        return self._db.overdue()

    def progress_report(self, employee_id: Optional[int] = None) -> List[Dict]:
        return self._db.progress(employee_id)


if __name__ == "__main__":
    agent = EmployeeOnboardingAgent()
    print(agent.health_check())
    eid = agent.onboard_employee("Kavya Rajan", "kavya@knackforge.com", "Engineering", "AI Engineer")
    agent.complete_step(eid, "offer_letter_signed")
    agent.complete_step(eid, "it_accounts_created")
    print(agent.progress_report())
    print("Overdue:", agent.get_overdue())
