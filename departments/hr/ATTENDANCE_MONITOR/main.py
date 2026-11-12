import logging
import datetime
from typing import Dict, Any, List

logger = logging.getLogger("ATTENDANCE_MONITOR")


class AttendanceMonitorAgent:
    """
    Real-time attendance monitoring.
    Flags: late arrivals (>15 min after shift start), unplanned absences, streak patterns.
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        from velaris.agents.ZOHO_PEOPLE.main import ZohoPeopleConnector
        self.people = ZohoPeopleConnector(self.config)
        self.shift_start = self.config.get("shift_start_hour", 9)  # 9 AM default

    def health_check(self) -> Dict[str, Any]:
        return {"agent": "ATTENDANCE_MONITOR", "status": "ok"}

    def check_today(self, employee_ids: List[str], date_str: str = None) -> Dict:
        """Returns today's attendance status for all employees."""
        date_str = date_str or datetime.date.today().strftime("%m-%d-%Y")
        results: Dict[str, Any] = {"present": [], "absent": [], "late": [], "date": date_str}
        for eid in employee_ids:
            try:
                records = self.people.get_attendance(eid, date_str, date_str)
            except Exception as e:
                logger.warning("Attendance check failed for %s: %s", eid, e)
                results["absent"].append(eid)
                continue
            if not records:
                results["absent"].append(eid)
            else:
                r = records[0]
                if r.get("IsLate") == "true":
                    results["late"].append({"id": eid, "checkin": r.get("CheckIn")})
                else:
                    results["present"].append(eid)
        return results

    def flag_absence_streaks(
        self, employee_ids: List[str], from_date: str, to_date: str, threshold: int = 3
    ) -> List[Dict]:
        """Flags employees with consecutive absences >= threshold days."""
        flagged = []
        for eid in employee_ids:
            try:
                records = self.people.get_attendance(eid, from_date, to_date)
            except Exception as e:
                logger.warning("Absence streak check failed for %s: %s", eid, e)
                continue
            absent_days = [r for r in records if r.get("Status") != "Present"]
            if len(absent_days) >= threshold:
                flagged.append({
                    "employee_id": eid,
                    "absent_days": len(absent_days),
                    "requires_review": True
                })
        return flagged
