import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

import logging
import sqlite3
from datetime import date
from typing import Dict, Any, List, Optional

logger = logging.getLogger("PERFORMANCE_REVIEW_ENGINE")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - PERFORMANCE_REVIEW_ENGINE - %(levelname)s - %(message)s"))
logger.addHandler(handler)

_DB = os.path.join(os.path.dirname(__file__), "reviews.db")


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB)
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
    conn.commit()
    return conn


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
    All data is stored locally in SQLite; each cycle is a string like "Q3-2026" or "FY2026".
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        _db().close()

    def health_check(self) -> Dict[str, Any]:
        return {"agent": "PERFORMANCE_REVIEW_ENGINE", "status": "ok"}

    # ── OKRs ─────────────────────────────────────────────────────────────
    def set_okr(self, employee_id: str, cycle: str, objective: str,
                key_results: List[str]) -> Dict[str, Any]:
        import json
        conn = _db()
        cur = conn.execute(
            "INSERT INTO okrs (employee_id, cycle, objective, key_results, created_on) VALUES (?,?,?,?,?)",
            (employee_id, cycle, objective, json.dumps(key_results), date.today().isoformat())
        )
        okr_id = cur.lastrowid
        conn.commit()
        conn.close()
        return {"id": okr_id, "employee_id": employee_id, "cycle": cycle, "objective": objective}

    def update_okr_progress(self, okr_id: int, progress: float) -> Dict[str, Any]:
        """progress: 0.0–1.0"""
        progress = max(0.0, min(1.0, progress))
        conn = _db()
        status = "completed" if progress >= 1.0 else "active"
        conn.execute("UPDATE okrs SET progress=?, status=? WHERE id=?", (progress, status, okr_id))
        conn.commit()
        conn.close()
        return {"id": okr_id, "progress": progress, "status": status}

    def get_okrs(self, employee_id: str, cycle: Optional[str] = None) -> List[Dict]:
        import json
        conn = _db()
        if cycle:
            rows = conn.execute("SELECT * FROM okrs WHERE employee_id=? AND cycle=?", (employee_id, cycle)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM okrs WHERE employee_id=? ORDER BY created_on DESC", (employee_id,)).fetchall()
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
        import json
        if review_type not in ("self", "peer", "manager"):
            return {"error": "review_type must be self, peer, or manager"}
        conn = _db()
        cur = conn.execute(
            "INSERT INTO reviews (employee_id, reviewer_id, review_type, cycle, scores, comments, submitted_on) VALUES (?,?,?,?,?,?,?)",
            (employee_id, reviewer_id, review_type, cycle, json.dumps(scores), comments, date.today().isoformat())
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
        import json
        conn = _db()
        rows = conn.execute(
            "SELECT review_type, scores FROM reviews WHERE employee_id=? AND cycle=?",
            (employee_id, cycle)
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
            "suggested_rating": _rating(weighted_score) if weighted_score else None,
            "peer_review_count": len(by_type["peer"]),
        }

    # ── Calibration ──────────────────────────────────────────────────────
    def calibrate(self, cycle: str, employee_id: str, raw_score: float,
                  calibrated_score: float, calibrated_by: str) -> Dict[str, Any]:
        """Record calibration session adjustment."""
        conn = _db()
        cur = conn.execute(
            "INSERT INTO calibration (cycle, employee_id, raw_score, calibrated_score, rating, calibrated_by, calibrated_on) VALUES (?,?,?,?,?,?,?)",
            (cycle, employee_id, raw_score, calibrated_score, _rating(calibrated_score), calibrated_by, date.today().isoformat())
        )
        cal_id = cur.lastrowid
        conn.commit()
        conn.close()
        return {"id": cal_id, "employee_id": employee_id, "raw_score": raw_score,
                "calibrated_score": calibrated_score, "rating": _rating(calibrated_score)}

    def get_calibration_report(self, cycle: str) -> List[Dict]:
        """Full calibration table for a review cycle, sorted by calibrated score desc."""
        conn = _db()
        rows = conn.execute(
            "SELECT * FROM calibration WHERE cycle=? ORDER BY calibrated_score DESC",
            (cycle,)
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
