#!/usr/bin/env python3
"""
EMPLOYEE_ONBOARDING — Velaris BOS agent for Knackforge
Ported from VKatOS client_onboarding, adapted for employees (IT setup, HR docs, 30/60/90 day plan).

DEPRECATED (not served over HTTP, kept so existing databases stay readable; use ONBOARDING_FLOW). LEGACY: ONBOARDING_FLOW is the product with roles, sealed identifiers, retention and erasure. Until this older agent is merged into it or
retired (owner decision) every method needs an authenticated Caller (velaris.core.access): changes need the hr_admin role, reads go
through authorize_read("identity") (traced). Rows carry the organisation and every query filters on it; the database lives under
VELARIS_DATA, never in the working directory. A missing employee_id means "all of this organisation's", and 0 is not "all".
Raises AccessDenied when refused.
"""
import logging

from velaris.core.sealed_sqlite import connect_sealed
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from velaris.agentkit.onboarding_common import HR_ADMINS, gate_change, gate_read
from velaris.intel.paths import agent_dir

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
    def __init__(self, db_path: str = ""):
        self.db = connect_sealed(db_path or str(agent_dir("EMPLOYEE_ONBOARDING") / "employee_onboarding.db"), "hr:EMPLOYEE_ONBOARDING")
        self._init_db()

    def _init_db(self):
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT, email TEXT, department TEXT, role TEXT,
                started_at TEXT, status TEXT DEFAULT 'onboarding', org TEXT);
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER, key TEXT, name TEXT,
                due_date TEXT, completed INTEGER DEFAULT 0, completed_at TEXT);
        """)
        if "org" not in {r[1] for r in self.db.execute("PRAGMA table_info(employees)")}:      # databases made before the column existed
            self.db.execute("ALTER TABLE employees ADD COLUMN org TEXT")
        self.db.commit()

    def onboard(self, org: str, name: str, email: str, department: str, role: str) -> int:
        now = datetime.utcnow()
        cursor = self.db.execute(
            "INSERT INTO employees (name,email,department,role,started_at,org) VALUES (?,?,?,?,?,?)",
            (name, email, department, role, now.isoformat(), org),
        )
        eid = cursor.lastrowid
        for key, task_name, due_day in EMPLOYEE_CHECKLIST:
            due = (now + timedelta(days=due_day)).isoformat()
            self.db.execute(
                "INSERT INTO tasks (employee_id,key,name,due_date) VALUES (?,?,?,?)",
                (eid, key, task_name, due),
            )
        self.db.commit()
        logger.info("Onboarding started: employee %s, %d tasks", eid, len(EMPLOYEE_CHECKLIST))
        return eid

    def complete_step(self, org: str, employee_id: int, step_key: str) -> bool:
        result = self.db.execute(
            "UPDATE tasks SET completed=1,completed_at=? WHERE employee_id=? AND key=?"
            " AND employee_id IN (SELECT id FROM employees WHERE org=?)",
            (datetime.utcnow().isoformat(), employee_id, step_key, org),
        )
        self.db.commit()
        ok = result.rowcount > 0
        if ok:
            logger.info("Step completed: employee=%d key=%s", employee_id, step_key)
        return ok

    def overdue(self, org: str) -> List[Dict]:
        now = datetime.utcnow().isoformat()
        rows = self.db.execute(
            """SELECT e.name, e.department, t.key, t.name, t.due_date
               FROM tasks t JOIN employees e ON e.id=t.employee_id
               WHERE t.completed=0 AND t.due_date<? AND e.org=? ORDER BY t.due_date""",
            (now, org),
        ).fetchall()
        return [
            {"employee": r[0], "department": r[1], "step": r[2], "task": r[3], "due": r[4]}
            for r in rows
        ]

    def progress(self, org: str, employee_id: Optional[int] = None) -> List[Dict]:
        if employee_id is not None:
            emps = self.db.execute(
                "SELECT id,name,department,role FROM employees WHERE id=? AND org=?", (employee_id, org)
            ).fetchall()
        else:
            emps = self.db.execute(
                "SELECT id,name,department,role FROM employees WHERE org=?", (org,)
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
        self._db = _EmployeeDB(self.config.get("db_path", ""))
        logger.info("EMPLOYEE_ONBOARDING agent initialised")

    def health_check(self) -> Dict[str, Any]:
        return {"agent": "EMPLOYEE_ONBOARDING", "status": "ok", "checklist_steps": len(EMPLOYEE_CHECKLIST),
                "deprecated": True, "replaced_by": "ONBOARDING_FLOW",
                "legacy": "use ONBOARDING_FLOW for roles, retention and erasure"}

    def onboard_employee(self, name: str, email: str, department: str, role: str) -> int:
        who = gate_change("EMPLOYEE_ONBOARDING", "onboard_employee", HR_ADMINS)
        return self._db.onboard(who.org, name, email, department, role)

    def complete_step(self, employee_id: int, step_key: str) -> bool:
        who = gate_change("EMPLOYEE_ONBOARDING", "complete_step", HR_ADMINS, {"employee": str(employee_id)[:20], "step": str(step_key)[:40]})
        return self._db.complete_step(who.org, employee_id, step_key)

    def get_overdue(self) -> List[Dict]:
        who = gate_read("EMPLOYEE_ONBOARDING", "identity")
        return self._db.overdue(who.org)

    def progress_report(self, employee_id: Optional[int] = None) -> List[Dict]:
        who = gate_read("EMPLOYEE_ONBOARDING", "identity")
        return self._db.progress(who.org, employee_id)


if __name__ == "__main__":
    print(EmployeeOnboardingAgent().health_check())
