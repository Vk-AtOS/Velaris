"""Attendance monitor: reports who is present, late or absent from Zoho People attendance records.

check_today(employee_ids, date_str, caller=) returns {"present", "absent", "late", "unknown", "date"}: an employee with no
record is absent, one whose record has IsLate == "true" is late (with check-in), and one whose fetch failed (logged) is
"unknown", never absent. flag_absence_streaks(ids, from_date, to_date, threshold=3, caller=) flags employees with at least
threshold records whose Status is not "Present" in the range (the days are counted, not checked for being consecutive);
failed fetches are skipped. The shift_start_hour config is stored but not used; lateness comes from Zoho's IsLate flag.
AccessDenied from the connector propagates. State: none kept here; data comes from ZohoPeopleConnector.
"""
import logging
import datetime
from typing import Dict, Any, List, Optional

from velaris.core.access import AccessDenied, Caller

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

    def check_today(self, employee_ids: List[str], date_str: str = None, *, caller: Optional[Caller] = None) -> Dict:
        """Returns today's attendance status for all employees. An employee whose record could not be fetched is `unknown`,
        never `absent`; a read the caller may not make raises AccessDenied (it is not a finding about the employee)."""
        date_str = date_str or datetime.date.today().strftime("%m-%d-%Y")
        results: Dict[str, Any] = {"present": [], "absent": [], "late": [], "unknown": [], "date": date_str}
        for eid in employee_ids:
            try:
                records = self.people.get_attendance(eid, date_str, date_str, caller=caller)
            except AccessDenied:
                raise
            except Exception as e:
                logger.warning("Attendance check failed for %s: %s", eid, e)
                results["unknown"].append(eid)
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
        self, employee_ids: List[str], from_date: str, to_date: str, threshold: int = 3, *,
        caller: Optional[Caller] = None
    ) -> List[Dict]:
        """Flags employees with consecutive absences >= threshold days."""
        flagged = []
        for eid in employee_ids:
            try:
                records = self.people.get_attendance(eid, from_date, to_date, caller=caller)
            except AccessDenied:
                raise
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
