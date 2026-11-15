import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

import json
import logging
import math
import sqlite3

from velaris.core.sealed_sqlite import connect_sealed
from datetime import date
from typing import Dict, Any, List, Optional

from velaris.agentkit import onboarding_retention as retention
from velaris.agentkit.onboarding_common import dsr_gate, HR_ADMINS, gate_change, gate_read
from velaris.core.access import AccessDenied, Caller, current_caller
from velaris.intel.paths import agent_dir

logger = logging.getLogger("PERFORMANCE_REVIEW_ENGINE")

SCALE = (0.0, 5.0)                      # every score is on this scale; the rating bands below assume it
MANAGERS = frozenset({"manager", "hiring_manager"}) | HR_ADMINS


def _db() -> sqlite3.Connection:
    conn = connect_sealed(str(agent_dir("PERFORMANCE_REVIEW_ENGINE") / "reviews.db"), "hr:PERFORMANCE_REVIEW_ENGINE")
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS okrs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT NOT NULL,
            cycle TEXT NOT NULL,
            objective TEXT NOT NULL,
            key_results TEXT NOT NULL,
            progress REAL DEFAULT 0.0,
            status TEXT DEFAULT 'active',
            created_on TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id TEXT NOT NULL,
            reviewer_id TEXT NOT NULL,
            review_type TEXT NOT NULL,
            cycle TEXT NOT NULL,
            scores TEXT NOT NULL,
            comments TEXT,
            submitted_on TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS calibration (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cycle TEXT NOT NULL,
            employee_id TEXT NOT NULL,
            raw_score REAL NOT NULL,
            calibrated_score REAL,
            rating TEXT,
            calibrated_by TEXT,
            calibrated_on TEXT
        );
    """)
    for table in ("okrs", "reviews", "calibration"):          # databases made before the organisation was recorded
        if "org" not in {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN org TEXT")
    conn.commit()
    return conn


def _scores_ok(scores: Any) -> Optional[str]:
    if not isinstance(scores, dict) or not scores:
        return "scores must be a non-empty object of criterion: number"
    for k, v in scores.items():
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not SCALE[0] <= v <= SCALE[1]:
            return f"score {str(k)[:40]!r} must be a number from {SCALE[0]} to {SCALE[1]}"
    return None


def _own_or_hr(agent_action: str, employee_id: str) -> Caller:
    """Authorised caller for a change about `employee_id`: that employee themselves or an HR administrator (traced)."""
    who = current_caller()
    if isinstance(who, Caller) and employee_id in (who.id, who.employee_id):
        return gate_change("PERFORMANCE_REVIEW_ENGINE", agent_action, None, {"own": True})   # org check + trace; no role needed
    return gate_change("PERFORMANCE_REVIEW_ENGINE", agent_action, HR_ADMINS)


def _avg(scores: Dict[str, float]) -> float:
    vals = [v for v in scores.values() if isinstance(v, (int, float))]
    return round(sum(vals) / len(vals), 2) if vals else 0.0


def _rating(score: float) -> str:
    if score >= 4.5:
        return "Outstanding"
    if score >= 3.5:
        return "Exceeds Expectations"
    if score >= 2.5:
        return "Meets Expectations"
    if score >= 1.5:
        return "Needs Improvement"
    return "Unsatisfactory"


class PerformanceReviewEngine:
    """
    OKR tracking, 360 reviews (self/peer/manager), and calibration.
    All data is stored in SQLite under VELARIS_DATA; each cycle is a string like "Q3-2026" or "FY2026".
    Every method needs an authenticated Caller (velaris.core.access; AccessDenied otherwise): you act on your own records, HR
    administrators on anyone's; the reviewer and the calibrator are the caller, never an argument; scores are 0 to 5; rows carry
    and filter on the organisation. Nothing here is a hiring, firing or pay decision: the suggested rating is for a person to weigh.
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        _db().close()

    def health_check(self) -> Dict[str, Any]:
        return {"agent": "PERFORMANCE_REVIEW_ENGINE", "status": "ok"}

    # ── OKRs ─────────────────────────────────────────────────────────────
    def set_okr(self, employee_id: str, cycle: str, objective: str,
                key_results: List[str]) -> Dict[str, Any]:
        who = _own_or_hr("set_okr", employee_id)
        conn = _db()
        cur = conn.execute(
            "INSERT INTO okrs (employee_id, cycle, objective, key_results, created_on, org) VALUES (?,?,?,?,?,?)",
            (employee_id, cycle, objective, json.dumps(key_results), date.today().isoformat(), who.org)
        )
        okr_id = cur.lastrowid
        conn.commit()
        conn.close()
        return {"id": okr_id, "employee_id": employee_id, "cycle": cycle, "objective": objective}

    def update_okr_progress(self, okr_id: int, progress: float) -> Dict[str, Any]:
        """progress: 0.0–1.0"""
        progress = max(0.0, min(1.0, progress))
        conn = _db()
        row = conn.execute("SELECT employee_id FROM okrs WHERE id=?", (okr_id,)).fetchone()
        who = _own_or_hr("update_okr_progress", row["employee_id"] if row else "")
        status = "completed" if progress >= 1.0 else "active"
        done = conn.execute("UPDATE okrs SET progress=?, status=? WHERE id=? AND org=?", (progress, status, okr_id, who.org)).rowcount
        conn.commit()
        conn.close()
        if not done:
            return {"error": "okr not found"}
        return {"id": okr_id, "progress": progress, "status": status}

    def get_okrs(self, employee_id: str, cycle: Optional[str] = None) -> List[Dict]:
        who = gate_read("PERFORMANCE_REVIEW_ENGINE", "identity", employee_id)
        conn = _db()
        if cycle:
            rows = conn.execute("SELECT * FROM okrs WHERE employee_id=? AND cycle=? AND org=?", (employee_id, cycle, who.org)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM okrs WHERE employee_id=? AND org=? ORDER BY created_on DESC", (employee_id, who.org)).fetchall()
        conn.close()
        result = []
        for r in rows:
            d = dict(r)
            d["key_results"] = json.loads(d["key_results"])
            result.append(d)
        return result

    # ── 360 Reviews ──────────────────────────────────────────────────────
    def submit_review(self, employee_id: str, reviewer_id: str,
                      review_type: str, cycle: str, scores: Dict[str, float],
                      comments: str = "") -> Dict[str, Any]:
        """
        review_type: 'self' | 'peer' | 'manager'
        scores: {"quality": 4.0, "delivery": 3.5, "collaboration": 4.5, "ownership": 4.0}
        """
        if review_type not in ("self", "peer", "manager"):
            return {"error": "review_type must be self, peer, or manager"}
        if (why := _scores_ok(scores)):
            return {"error": why}
        who = gate_change("PERFORMANCE_REVIEW_ENGINE", "submit_review", MANAGERS if review_type == "manager" else None,
                          {"type": review_type})
        if reviewer_id != who.id:
            raise AccessDenied(f"{who.id} cannot review as {str(reviewer_id)[:80]}")        # the reviewer is the caller, not an argument
        if review_type == "self" and employee_id not in (who.id, who.employee_id):
            raise AccessDenied("a self review is about yourself")
        if review_type != "self" and employee_id in (who.id, who.employee_id):
            raise AccessDenied("nobody submits a peer or manager review of themselves")
        conn = _db()
        cur = conn.execute(
            "INSERT INTO reviews (employee_id, reviewer_id, review_type, cycle, scores, comments, submitted_on, org) VALUES (?,?,?,?,?,?,?,?)",
            (employee_id, who.id, review_type, cycle, json.dumps(scores), comments, date.today().isoformat(), who.org)
        )
        rev_id = cur.lastrowid
        conn.commit()
        conn.close()
        avg = _avg(scores)
        logger.info("Review submitted: emp=%s type=%s avg=%.2f", employee_id, review_type, avg)
        return {"id": rev_id, "employee_id": employee_id, "review_type": review_type,
                "cycle": cycle, "average_score": avg}

    def get_360_summary(self, employee_id: str, cycle: str) -> Dict[str, Any]:
        """Aggregates self/peer/manager scores into one 360 summary."""
        who = gate_read("PERFORMANCE_REVIEW_ENGINE", "identity", employee_id)
        conn = _db()
        rows = conn.execute(
            "SELECT review_type, scores FROM reviews WHERE employee_id=? AND cycle=? AND org=?",
            (employee_id, cycle, who.org)
        ).fetchall()
        conn.close()
        by_type: Dict[str, List[float]] = {"self": [], "peer": [], "manager": []}
        for r in rows:
            scores = json.loads(r["scores"])
            by_type[r["review_type"]].append(_avg(scores))
        def mean(lst):
            return round(sum(lst) / len(lst), 2) if lst else None
        weighted_score = None
        self_avg = mean(by_type["self"])
        peer_avg = mean(by_type["peer"])
        mgr_avg = mean(by_type["manager"])
        components = [x for x in [self_avg, peer_avg, mgr_avg] if x is not None]
        if components:
            # weights: self 20%, peer 40%, manager 40%
            weights = [0.2, 0.4, 0.4]
            present = [(v, w) for v, w in zip([self_avg, peer_avg, mgr_avg], weights) if v is not None]
            total_w = sum(w for _, w in present)
            weighted_score = round(sum(v * w for v, w in present) / total_w, 2)
        return {
            "employee_id": employee_id,
            "cycle": cycle,
            "self_score": self_avg,
            "peer_score": peer_avg,
            "manager_score": mgr_avg,
            "weighted_score": weighted_score,
            "suggested_rating": _rating(weighted_score) if weighted_score is not None else None,
            "peer_review_count": len(by_type["peer"]),
        }

    # ── Calibration ──────────────────────────────────────────────────────
    def calibrate(self, cycle: str, employee_id: str, raw_score: float,
                  calibrated_score: float, calibrated_by: str) -> Dict[str, Any]:
        """Record calibration session adjustment (HR administrators; the person calibrating is the caller)."""
        for v in (raw_score, calibrated_score):
            if (why := _scores_ok({"score": v})):
                return {"error": why}
        who = gate_change("PERFORMANCE_REVIEW_ENGINE", "calibrate", HR_ADMINS, {"employee": str(employee_id)[:40]})
        if calibrated_by != who.id:
            raise AccessDenied(f"{who.id} cannot calibrate as {str(calibrated_by)[:80]}")
        conn = _db()
        cur = conn.execute(
            "INSERT INTO calibration (cycle, employee_id, raw_score, calibrated_score, rating, calibrated_by, calibrated_on, org) VALUES (?,?,?,?,?,?,?,?)",
            (cycle, employee_id, raw_score, calibrated_score, _rating(calibrated_score), who.id, date.today().isoformat(), who.org)
        )
        cal_id = cur.lastrowid
        conn.commit()
        conn.close()
        return {"id": cal_id, "employee_id": employee_id, "raw_score": raw_score,
                "calibrated_score": calibrated_score, "rating": _rating(calibrated_score)}

    def get_calibration_report(self, cycle: str) -> List[Dict]:
        """Full calibration table for a review cycle, sorted by calibrated score desc."""
        who = gate_read("PERFORMANCE_REVIEW_ENGINE", "identity")           # everyone's ratings: HR administrators
        conn = _db()
        rows = conn.execute(
            "SELECT * FROM calibration WHERE cycle=? AND org=? ORDER BY calibrated_score DESC",
            (cycle, who.org)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]


    # ---- data-subject support (called by EMPLOYEE_RECORDS; not an HTTP method) ----------------------
    def dsr_export(self, org: str, subject_id: str, links: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """The subject's performance data. The person themselves get their OKRs and the scores of reviews about them, with peer and
        manager reviewers left out and no free-text comments or calibration rows; an HR administrator gets everything."""
        who = dsr_gate("PERFORMANCE_REVIEW_ENGINE", org, subject_id, erase=False)
        hr = bool(who.roles & HR_ADMINS)
        conn = _db()
        q = lambda t: [dict(r) for r in conn.execute(f"SELECT * FROM {t} WHERE employee_id=? AND org=?", (subject_id, org))]
        okrs, reviews, calibration = q("okrs"), q("reviews"), q("calibration")
        conn.close()
        if not hr:
            reviews = [{k: v for k, v in r.items() if k not in ("comments",) and not (k == "reviewer_id" and r["review_type"] != "self")}
                       for r in reviews]
            calibration = []
        return {"performance": {"okrs": okrs, "reviews": reviews, "calibration": calibration,
                                **({} if hr else {"withheld": "reviewer identities of peer and manager reviews, comments and calibration are for HR administrators"})}}

    def dsr_erase(self, org: str, subject_id: str, on: Optional[date] = None, links: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Delete this person's OKRs, reviews and calibration rows when the registry says so. It has no retention row for performance
        records, so today they are HELD and reported as needs_review until the data-protection owner adds one."""
        dsr_gate("PERFORMANCE_REVIEW_ENGINE", org, subject_id, erase=True)
        d = retention.decide("performance_records", None, on or date.today())
        conn = _db()
        counts = {t: conn.execute(f"SELECT COUNT(*) FROM {t} WHERE employee_id=? AND org=?", (subject_id, org)).fetchone()[0]
                  for t in ("okrs", "reviews", "calibration")}
        total = sum(counts.values())
        if total and d["action"] == "erase":
            for t in counts:
                conn.execute(f"DELETE FROM {t} WHERE employee_id=? AND org=?", (subject_id, org))
            conn.commit()
            conn.close()
            return {"erased": [f"performance records ({total})"], "held": []}
        conn.close()
        return {"erased": [], "held": [{"what": f"performance_records({total})", **d}] if total else []}
