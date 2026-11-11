import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

import logging
import sqlite3
from datetime import date, timedelta
from typing import Dict, Any, List, Optional

logger = logging.getLogger("LEAVE_MANAGEMENT")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - LEAVE_MANAGEMENT - %(levelname)s - %(message)s"))
logger.addHandler(handler)

_LEAVE_TYPES = {"casual": 12, "sick": 12, "earned": 15, "maternity": 182, "paternity": 15}
_DB = os.path.join(os.path.dirname(__file__), "leaves.db")


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB)
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
            reviewed_on TEXT
        )
    """)
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
        """Seed default leave entitlements for a new employee/year."""
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
            "INSERT INTO leave_requests (employee_id, leave_type, from_date, to_date, days, reason, applied_on) VALUES (?,?,?,?,?,?,?)",
            (employee_id, leave_type, from_date, to_date, days, reason, date.today().isoformat())
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
        conn = _db()
        row = conn.execute("SELECT * FROM leave_requests WHERE id=?", (leave_id,)).fetchone()
        if not row:
            conn.close()
            return {"error": "not_found"}
        if row["status"] != "pending":
            conn.close()
            return {"error": f"already_{row['status']}"}
        if status == "approved":
            if reviewed_by == row["employee_id"]:
                conn.close()
                return {"error": "self_approval_not_allowed"}
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
            "UPDATE leave_requests SET status=?, reviewed_by=?, reviewed_on=? WHERE id=?",
            (status, reviewed_by, date.today().isoformat(), leave_id)
        )
        conn.commit()
        conn.close()
        return {"id": leave_id, "status": status, "reviewed_by": reviewed_by}

    def pending_approvals(self) -> List[Dict]:
        conn = _db()
        rows = conn.execute(
            "SELECT * FROM leave_requests WHERE status='pending' ORDER BY applied_on"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    def employee_history(self, employee_id: str, year: Optional[int] = None) -> List[Dict]:
        conn = _db()
        if year:
            rows = conn.execute(
                "SELECT * FROM leave_requests WHERE employee_id=? AND strftime('%Y',from_date)=? ORDER BY from_date DESC",
                (employee_id, str(year))
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM leave_requests WHERE employee_id=? ORDER BY from_date DESC",
                (employee_id,)
            ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
