"""Zoho People connector: reads employee, attendance, leave and appraisal data from the Zoho People API.

get_employees(page), get_attendance(employee_id, from_date, to_date) (MM-dd-yyyy),
get_leave_summary(employee_id, year=None), get_performance(employee_id) and
get_attendance_summary(...) call the API through ZOHO_CONNECTOR. Each takes an optional
keyword caller and first calls velaris.core.access.authorize_read (identity category, or
health for leave): the person's own record or an HR administrator may read, and an
unauthorised caller gets the exception authorize_read raises before any API call.
get_attendance_summary computes present/absent/late counts and average hours from the
records. A response without a result returns an empty list or dict. Keeps no state.
"""
import datetime
import logging
from typing import Dict, Any, List, Optional

from velaris.agents.ZOHO_CONNECTOR.main import ZohoConnector
from velaris.core.access import Caller, authorize_read

logger = logging.getLogger("ZOHO_PEOPLE")


class ZohoPeopleConnector:
    """
    Pulls employee data from Zoho People:
    - Employee list and profiles
    - Attendance records (daily clock-in/out, hours worked)
    - Leave records (applied, approved, balance)
    - Performance appraisal scores
    """
    BASE = "https://people.zoho.in/api"

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.zoho = ZohoConnector(self.config)

    def health_check(self) -> Dict[str, Any]:
        return {"agent": "ZOHO_PEOPLE", "status": "ok"}

    def get_employees(self, page: int = 1, *, caller: Optional[Caller] = None) -> List[Dict]:
        """Returns list of all employees with their full employee-form records.

        Those records can hold identity numbers, bank details and dates of birth, so only an
        HR administrator may list them (velaris.core.access, category "identity").
        """
        authorize_read("identity", None, agent="ZOHO_PEOPLE", caller=caller, org=self.config.get("org"))
        resp = self.zoho.get(
            f"{self.BASE}/forms/employee/getRecords",
            {"page": page, "pageSize": 200}
        )
        return resp.get("response", {}).get("result", [])

    def get_attendance(self, employee_id: str, from_date: str, to_date: str, *, caller: Optional[Caller] = None) -> List[Dict]:
        """
        Returns attendance records for date range.
        from_date/to_date format: "MM-dd-yyyy"
        Identity access: the person's own record, or an HR administrator (velaris.core.access, traced).
        """
        authorize_read("identity", employee_id, agent="ZOHO_PEOPLE", caller=caller, org=self.config.get("org"))
        resp = self.zoho.get(
            f"{self.BASE}/forms/attendance/getAttendanceEntries",
            {"empId": employee_id, "startDate": from_date, "endDate": to_date}
        )
        return resp.get("response", {}).get("result", [])

    def get_leave_summary(self, employee_id: str, year: int = None, *, caller: Optional[Caller] = None) -> Dict:
        """Returns leave balance and taken days per leave type. Health access (sick and maternity leave are in it)."""
        authorize_read("health", employee_id, agent="ZOHO_PEOPLE", caller=caller, org=self.config.get("org"))
        year = year or datetime.date.today().year
        resp = self.zoho.get(
            f"{self.BASE}/forms/leave/getLeaveTypeDetails",
            {"empId": employee_id, "year": year}
        )
        return resp.get("response", {}).get("result", {})

    def get_performance(self, employee_id: str, *, caller: Optional[Caller] = None) -> List[Dict]:
        """Returns appraisal records and scores for the employee. Identity access."""
        authorize_read("identity", employee_id, agent="ZOHO_PEOPLE", caller=caller, org=self.config.get("org"))
        resp = self.zoho.get(
            f"{self.BASE}/forms/appraisalform/getRecords",
            {"searchField": "EmployeeID", "searchValue": employee_id}
        )
        return resp.get("response", {}).get("result", [])

    def get_attendance_summary(self, employee_id: str, from_date: str, to_date: str, *, caller: Optional[Caller] = None) -> Dict:
        """Summarises attendance: total days, present, absent, late, avg hours/day."""
        records = self.get_attendance(employee_id, from_date, to_date, caller=caller)
        total = len(records)
        present = sum(1 for r in records if r.get("Status") == "Present")
        late = sum(1 for r in records if r.get("IsLate") == "true")
        hours = [float(r.get("Hours_Worked", 0)) for r in records if r.get("Hours_Worked")]
        return {
            "employee_id": employee_id,
            "period": f"{from_date} to {to_date}",
            "total_working_days": total,
            "days_present": present,
            "days_absent": total - present,
            "late_arrivals": late,
            "attendance_pct": round(present / total * 100, 1) if total else 0,
            "avg_hours_per_day": round(sum(hours) / len(hours), 2) if hours else 0,
            "total_hours": round(sum(hours), 2)
        }
