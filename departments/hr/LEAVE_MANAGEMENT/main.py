import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

import logging
import sqlite3

from velaris.core.sealed_sqlite import connect_sealed
from datetime import date, timedelta
from typing import Dict, Any, List, Optional

from velaris.agentkit import onboarding_retention as retention
from velaris.agentkit.onboarding_common import dsr_gate, HR_ADMINS, gate_change
from velaris.core.access import Caller, authorize_read, current_caller, deployment_org, org_denied
from velaris.intel.paths import agent_dir

logger = logging.getLogger("LEAVE_MANAGEMENT")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - LEAVE_MANAGEMENT - %(levelname)s - %(message)s"))
logger.addHandler(handler)

_LEAVE_TYPES = {"casual": 12, "sick": 12, "earned": 15, "maternity": 182, "paternity": 15}
_DB = ""          # tests may point this elsewhere; empty means <VELARIS_DATA>/agents/LEAVE_MANAGEMENT/leaves.db


def _db() -> sqlite3.Connection:
    conn = connect_sealed(_DB or str(agent_dir("LEAVE_MANAGEMENT") / "leaves.db"), "hr:LEAVE_MANAGEMENT")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS leave_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT NOT NULL,
            leave_type TEXT NOT NULL,
            from_date TEXT NOT NULL,
            to_date TEXT NOT NULL,
            days INTEGER NOT NULL,
            reason TEXT,
            status TEXT DEFAULT 'pending',
            applied_on TEXT NOT NULL,
            reviewed_by TEXT,
            reviewed_on TEXT,
            reviewed_by_employee TEXT,
            org TEXT
        )
    """)
    have = {r["name"] for r in conn.execute("PRAGMA table_info(leave_requests)")}
    for col in ("reviewed_by_employee", "org"):          # stores made before these columns existed
        if col not in have:
            conn.execute(f"ALTER TABLE leave_requests ADD COLUMN {col} TEXT")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS leave_balances (
            employee_id TEXT NOT NULL,
            leave_type TEXT NOT NULL,
            year INTEGER NOT NULL,
            entitlement INTEGER NOT NULL,
            used INTEGER DEFAULT 0,
            PRIMARY KEY (employee_id, leave_type, year)
        )
    """)
    conn.commit()
    return conn


def _business_days(from_date: str, to_date: str) -> int:
    start = date.fromisoformat(from_date)
    end = date.fromisoformat(to_date)
    count = 0
    cur = start
    while cur <= end:
        if cur.weekday() < 5:  # Mon-Fri
            count += 1
        cur += timedelta(days=1)
    return count


class LeaveManagement:
    """
    Leave request lifecycle: apply → approve/reject → balance tracking.
    Balances seeded from policy defaults; Zoho People sync optional.
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        _db().close()

    def health_check(self) -> Dict[str, Any]:
        return {"agent": "LEAVE_MANAGEMENT", "status": "ok"}

    def seed_balances(self, employee_id: str, year: int) -> Dict[str, Any]:
        """Seed default leave entitlements for a new employee/year (HR administrators)."""
        gate_change("LEAVE_MANAGEMENT", "seed_balances", HR_ADMINS, {"employee": str(employee_id)[:40]})
        conn = _db()
        for leave_type, days in _LEAVE_TYPES.items():
            conn.execute(
                "INSERT OR IGNORE INTO leave_balances VALUES (?, ?, ?, ?, 0)",
                (employee_id, leave_type, year, days)
            )
        conn.commit()
        conn.close()
        return {"employee_id": employee_id, "year": year, "seeded": list(_LEAVE_TYPES.keys())}

    def get_balance(self, employee_id: str, year: int) -> Dict[str, Any]:
        """Balances include sick leave, which is health data: your own, or an HR administrator's (authorize_read, traced)."""
        authorize_read("health", employee_id, agent="LEAVE_MANAGEMENT", org=getattr(current_caller(), "org", None))
        conn = _db()
        rows = conn.execute(
            "SELECT leave_type, entitlement, used FROM leave_balances WHERE employee_id=? AND year=?",
            (employee_id, year)
        ).fetchall()
        conn.close()
        balance = {r["leave_type"]: {"entitlement": r["entitlement"], "used": r["used"],
                                      "available": r["entitlement"] - r["used"]} for r in rows}
        return {"employee_id": employee_id, "year": year, "balance": balance}

    def apply(self, employee_id: str, leave_type: str, from_date: str,
              to_date: str, reason: str = "") -> Dict[str, Any]:
        who = current_caller()
        mine = isinstance(who, Caller) and employee_id in (who.id, who.employee_id)
        who = gate_change("LEAVE_MANAGEMENT", "apply", None if mine else HR_ADMINS, {"employee": str(employee_id)[:40]})
        if leave_type not in _LEAVE_TYPES:
            return {"error": f"invalid leave_type; must be one of {list(_LEAVE_TYPES.keys())}"}
        days = _business_days(from_date, to_date)
        if days <= 0:
            return {"error": "no business days in requested range"}
        conn = _db()
        # check balance
        row = conn.execute(
            "SELECT entitlement, used FROM leave_balances WHERE employee_id=? AND leave_type=? AND year=?",
            (employee_id, leave_type, date.fromisoformat(from_date).year)
        ).fetchone()
        if not row:
            # No balance record is not "unlimited leave": seed_balances() first.
            conn.close()
            return {"error": "no_balance_record", "employee_id": employee_id, "leave_type": leave_type}
        if (row["entitlement"] - row["used"]) < days:
            conn.close()
            return {"error": "insufficient_balance", "available": row["entitlement"] - row["used"], "requested": days}
        cur = conn.execute(
            "INSERT INTO leave_requests (employee_id, leave_type, from_date, to_date, days, reason, applied_on, org) VALUES (?,?,?,?,?,?,?,?)",
            (employee_id, leave_type, from_date, to_date, days, reason, date.today().isoformat(), who.org)
        )
        leave_id = cur.lastrowid
        conn.commit()
        conn.close()
        logger.info("Leave applied: id=%d emp=%s type=%s days=%d", leave_id, employee_id, leave_type, days)
        return {"id": leave_id, "employee_id": employee_id, "leave_type": leave_type,
                "from_date": from_date, "to_date": to_date, "days": days, "status": "pending"}

    def approve(self, leave_id: int, reviewed_by: str) -> Dict[str, Any]:
        return self._update_status(leave_id, "approved", reviewed_by)

    def reject(self, leave_id: int, reviewed_by: str) -> Dict[str, Any]:
        return self._update_status(leave_id, "rejected", reviewed_by)

    def _update_status(self, leave_id: int, status: str, reviewed_by: str) -> Dict[str, Any]:
        caller = current_caller()
        if org_denied(caller):
            return {"error": "access_denied"}
        if caller is None:
            return {"error": "unauthenticated"}                # nobody approves leave in an anonymous call
        if not caller.roles & HR_ADMINS:
            return {"error": "denied", "reason": "approving leave needs the hr_admin role"}
        if reviewed_by != caller.id:
            return {"error": "reviewer_must_be_caller"}       # nobody reviews in someone else's name
        conn = _db()
        row = conn.execute("SELECT * FROM leave_requests WHERE id=?", (leave_id,)).fetchone()
        dep = deployment_org()
        if not row or (dep is not None and row["org"] != dep):  # another organisation's (or unstamped) request
            conn.close()
            return {"error": "not_found"}
        # The request names the HR employee id; the reviewer is known by user id and, if any, employee id.
        mine = {reviewed_by, *(([caller.employee_id] if caller and caller.employee_id else []))}
        if row["employee_id"] in mine:
            conn.close()
            return {"error": "self_approval_not_allowed"}
        if row["status"] != "pending":
            conn.close()
            return {"error": f"already_{row['status']}"}
        reviewer_employee = caller.employee_id if caller else None
        if status == "approved":
            # Deduct only if the balance still covers it: several pending requests can
            # each pass the check in apply(), so the check is repeated here, atomically.
            deducted = conn.execute(
                "UPDATE leave_balances SET used=used+? WHERE employee_id=? AND leave_type=? AND year=?"
                " AND entitlement-used>=?",
                (row["days"], row["employee_id"], row["leave_type"],
                 date.fromisoformat(row["from_date"]).year, row["days"])
            ).rowcount
            if not deducted:
                conn.close()
                return {"error": "insufficient_balance", "requested": row["days"]}
        conn.execute(
            "UPDATE leave_requests SET status=?, reviewed_by=?, reviewed_by_employee=?, reviewed_on=? WHERE id=?",
            (status, reviewed_by, reviewer_employee, date.today().isoformat(), leave_id)
        )
        conn.commit()
        conn.close()
        return {"id": leave_id, "status": status, "reviewed_by": reviewed_by,
                "reviewed_by_employee": reviewer_employee}

    # Leave records say who was on sick or maternity leave and when: health data. Reading them
    # goes through velaris.core.access (own record, or an HR administrator) and is traced.
    def pending_approvals(self, *, caller: Optional[Caller] = None) -> List[Dict]:
        who = authorize_read("health", None, agent="LEAVE_MANAGEMENT", caller=caller, org=self.config.get("org"))
        conn = _db()
        rows = conn.execute(
            "SELECT * FROM leave_requests WHERE status='pending' AND org=? ORDER BY applied_on",
            (who.org,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def employee_history(self, employee_id: str, year: Optional[int] = None, *,
                         caller: Optional[Caller] = None) -> List[Dict]:
        who = authorize_read("health", employee_id, agent="LEAVE_MANAGEMENT", caller=caller, org=self.config.get("org"))
        conn = _db()
        if year:
            rows = conn.execute(
                "SELECT * FROM leave_requests WHERE employee_id=? AND strftime('%Y',from_date)=?"
                " AND org=? ORDER BY from_date DESC",
                (employee_id, str(year), who.org)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM leave_requests WHERE employee_id=? AND org=? ORDER BY from_date DESC",
                (employee_id, who.org)
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]


    # ---- data-subject support (called by EMPLOYEE_RECORDS; not an HTTP method) ----------------------
    def dsr_export(self, org: str, subject_id: str, links: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Leave rows are health data: the person's own or an HR administrator's read (checked here, org from the verified caller).
        Legacy rows that carry no organisation are included and marked, so nothing about the person is left out."""
        dsr_gate("LEAVE_MANAGEMENT", org, subject_id, erase=False, category="health")
        conn = _db()
        rows = conn.execute("SELECT * FROM leave_requests WHERE employee_id=? AND (org=? OR org IS NULL)", (subject_id, org)).fetchall()
        conn.close()
        return {"leave_requests": [{**dict(r), **({"legacy_row_without_organisation": True} if r["org"] is None else {})} for r in rows]}

    def dsr_erase(self, org: str, subject_id: str, on: Optional[date] = None, links: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Delete this person's leave rows when the retention registry allows (attendance and leave registers are a statutory class,
        so today they are HELD and reported as needs_review). Legacy rows with no organisation cannot be attributed to this
        organisation: they are never deleted here and are always reported as held (needs_review)."""
        dsr_gate("LEAVE_MANAGEMENT", org, subject_id, erase=True)
        conn = _db()
        n = conn.execute("SELECT COUNT(*) FROM leave_requests WHERE employee_id=? AND org=?", (subject_id, org)).fetchone()[0]
        legacy = conn.execute("SELECT COUNT(*) FROM leave_requests WHERE employee_id=? AND org IS NULL", (subject_id,)).fetchone()[0]
        d = retention.decide("attendance_leave_records", None, on or date.today())
        held = [{"what": f"leave_requests_without_organisation({legacy})", "class": "attendance_leave_records", "action": "hold",
                 "status": "needs_review", "reason": "legacy rows carry no organisation: an administrator must attribute or delete them"}] if legacy else []
        if n and d["action"] == "erase":
            conn.execute("DELETE FROM leave_requests WHERE employee_id=? AND org=?", (subject_id, org))
            if not legacy:
                conn.execute("DELETE FROM leave_balances WHERE employee_id=?", (subject_id,))
            conn.commit()
            conn.close()
            return {"erased": [f"leave requests ({n})"], "held": held}
        conn.close()
        return {"erased": [], "held": ([{"what": f"leave_requests({n})", **d}] if n else []) + held}
