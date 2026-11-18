"""Employee metrics engine: aggregates Zoho People, Payroll and Projects data into a per-employee profile, a ranked team scorecard and an org heatmap.

EmployeeMetricsEngine(config): health_check() reports the three connectors' status;
get_employee_profile(employee_id, month=None, year=None, caller=None) returns attendance,
leave, performance summary, payroll (gross, net, statutory) and project delivery for the
month (default: current); get_team_scorecard(employee_ids, month, year, caller) ranks by
composite = attendance_pct*0.30 + delivery completion*0.50 + latest appraisal score*20
(capped at 100)*0.20, using no pay data; an employee with a missing, withheld or failed component is listed last as unranked
(composite_score None, `missing` names the parts), never scored 0; get_org_heatmap(...) buckets attendance, delivery
and hours (avg, min, max, count under 70), lists the top 3 and composites under 60.
State: keeps no state; all data is fetched from the connectors on each call.
Failure: each section is fetched separately; AccessDenied from a connector becomes
{"withheld": reason} and any other error is logged and becomes {"error": message}, so a
profile is still returned. Pay access is decided by velaris.core.access in the payroll
connector.
"""

import logging
import datetime
from typing import Dict, Any, List, Optional

from velaris.core.access import AccessDenied, Caller

logger = logging.getLogger("EMPLOYEE_METRICS_ENGINE")


class EmployeeMetricsEngine:
    """
    Aggregates Zoho People + Zoho Payroll + Zoho Projects data
    into a unified per-employee metrics profile.
    Feeds dashboard visualizations.
    Pay figures are read through ZohoPayrollConnector, which asks velaris.core.access
    whether the caller may see them (their own record, or a payroll/HR administrator).
    When they may not, the profile carries {"withheld": reason} instead of pay; the
    scorecard and heatmap never read pay at all.
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        from velaris.agents.ZOHO_PEOPLE.main import ZohoPeopleConnector
        from velaris.agents.ZOHO_PAYROLL.main import ZohoPayrollConnector
        from velaris.agents.ZOHO_PROJECTS.main import ZohoProjectsConnector
        self.people = ZohoPeopleConnector(self.config)
        self.payroll = ZohoPayrollConnector(self.config)
        self.projects = ZohoProjectsConnector(self.config)

    def health_check(self) -> Dict[str, Any]:
        return {
            "agent": "EMPLOYEE_METRICS_ENGINE",
            "status": "ok",
            "connectors": {
                "people": self.people.health_check()["status"],
                "payroll": self.payroll.health_check()["status"],
                "projects": self.projects.health_check()["status"]
            }
        }

    def get_employee_profile(self, employee_id: str, month: int = None, year: int = None, *,
                             caller: Optional[Caller] = None) -> Dict:
        """
        Full unified profile for one employee.
        Returns attendance, leave, performance, task delivery, payroll summary.
        Payroll is included only when the caller may read this employee's pay.
        """
        return self._profile(employee_id, month, year, include_pay=True, caller=caller)

    def _profile(self, employee_id: str, month: Optional[int], year: Optional[int], *,
                 include_pay: bool, caller: Optional[Caller] = None) -> Dict:
        today = datetime.date.today()
        month = month or today.month
        year = year or today.year

        from_date = datetime.date(year, month, 1).strftime("%m-%d-%Y")
        if month < 12:
            last_day = datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)
        else:
            last_day = datetime.date(year, 12, 31)
        to_date = last_day.strftime("%m-%d-%Y")

        profile: Dict[str, Any] = {"employee_id": employee_id, "period": f"{year}-{month:02d}"}

        try:
            profile["attendance"] = self.people.get_attendance_summary(employee_id, from_date, to_date, caller=caller)
        except AccessDenied as e:
            profile["attendance"] = {"withheld": e.reason}
        except Exception as e:
            logger.warning("Attendance fetch failed for %s: %s", employee_id, e)
            profile["attendance"] = {"error": str(e)}

        try:
            profile["leave"] = self.people.get_leave_summary(employee_id, year, caller=caller)
        except AccessDenied as e:
            profile["leave"] = {"withheld": e.reason}
        except Exception as e:
            logger.warning("Leave fetch failed for %s: %s", employee_id, e)
            profile["leave"] = {"error": str(e)}

        try:
            perf = self.people.get_performance(employee_id, caller=caller)
            profile["performance"] = {
                "appraisal_count": len(perf),
                "latest_score": perf[-1].get("Overall_Score") if perf else None,
                "latest_period": perf[-1].get("Appraisal_Period") if perf else None
            }
        except AccessDenied as e:
            profile["performance"] = {"withheld": e.reason}
        except Exception as e:
            logger.warning("Performance fetch failed for %s: %s", employee_id, e)
            profile["performance"] = {"error": str(e)}

        try:
            if include_pay:
                payslip = self.payroll.get_payslip(employee_id, year, month, caller=caller)
                profile["payroll"] = {
                    "gross": payslip.get("gross_pay", 0),
                    "net": payslip.get("net_pay", 0),
                    "statutory": self.payroll.get_statutory_deductions(
                        employee_id, year, month, caller=caller)["statutory"]
                }
        except AccessDenied as e:
            profile["payroll"] = {"withheld": e.reason}
        except Exception as e:
            logger.warning("Payroll fetch failed for %s: %s", employee_id, e)
            profile["payroll"] = {"error": str(e)}

        try:
            active_projects = self.projects.get_projects()
            task_summaries = []
            total_hours = 0.0
            for p in active_projects:
                pid = p["id_string"]
                summary = self.projects.get_task_summary(pid, employee_id)
                logs = self.projects.get_timelogs(pid, employee_id, from_date, to_date)
                hours = sum(float(log.get("hours", 0)) for log in logs)
                total_hours += hours
                if summary["total_tasks"] > 0:
                    task_summaries.append({
                        "project": p["name"],
                        **summary,
                        "hours_logged": round(hours, 2)
                    })

            all_tasks = sum(s["total_tasks"] for s in task_summaries)
            all_done = sum(s["completed"] for s in task_summaries)
            profile["delivery"] = {
                "projects_active": len(task_summaries),
                "total_tasks": all_tasks,
                "tasks_completed": all_done,
                "overall_completion_rate": round(all_done / all_tasks * 100, 1) if all_tasks else 0,
                "total_hours_logged": round(total_hours, 2),
                "per_project": task_summaries
            }
        except Exception as e:
            logger.warning("Delivery fetch failed for %s: %s", employee_id, e)
            profile["delivery"] = {"error": str(e)}

        return profile

    def get_team_scorecard(self, employee_ids: List[str], month: int = None, year: int = None, *,
                           caller: Optional[Caller] = None) -> List[Dict]:
        """
        Returns ranked scorecard for a list of employees.
        Scores: attendance 30% + delivery 50% + performance 20%
        """
        today = datetime.date.today()
        month = month or today.month
        year = year or today.year

        scorecards = []
        for eid in employee_ids:
            profile = self._profile(eid, month, year, include_pay=False, caller=caller)      # the score uses no pay

            delivery = profile.get("delivery", {})
            perf = profile.get("performance", {})
            att = profile.get("attendance", {})
            # a section that was withheld, failed or lacks its figure is MISSING, not zero: scoring it 0 ranked people last because
            # a connector was down or the caller could not read it
            parts = {"attendance": att.get("attendance_pct"), "delivery": delivery.get("overall_completion_rate"),
                     "performance": perf.get("latest_score")}
            missing = sorted(k for k, v in parts.items() if isinstance(v, bool) or not isinstance(v, (int, float)))
            row = {"employee_id": eid, "attendance_pct": parts["attendance"] if "attendance" not in missing else None,
                   "delivery_pct": parts["delivery"] if "delivery" not in missing else None,
                   "performance_score": parts["performance"] if "performance" not in missing else None,
                   "hours_logged": delivery.get("total_hours_logged") if isinstance(delivery.get("total_hours_logged"), (int, float)) else None}
            if missing:
                scorecards.append({**row, "composite_score": None, "ranked": False, "missing": missing})
                continue
            total = round(parts["attendance"] * 0.30 + parts["delivery"] * 0.50 + min(float(parts["performance"]) * 20, 100) * 0.20, 1)
            scorecards.append({**row, "composite_score": total, "ranked": True, "missing": []})

        # ranked people by score; people with missing data follow, unranked, in the order given
        return sorted(scorecards, key=lambda x: (x["composite_score"] is None, -(x["composite_score"] or 0)))

    def get_org_heatmap(self, employee_ids: List[str], month: int = None, year: int = None, *,
                        caller: Optional[Caller] = None) -> Dict:
        """
        Returns org-level heatmap data: attendance distribution, delivery health, hours. (It reads no pay: there is no payroll total.)
        Suitable for dashboard chart rendering.
        """
        today = datetime.date.today()
        month = month or today.month
        year = year or today.year

        scorecard = self.get_team_scorecard(employee_ids, month, year, caller=caller)
        att_values = [s["attendance_pct"] for s in scorecard if s["attendance_pct"] is not None]
        del_values = [s["delivery_pct"] for s in scorecard if s["delivery_pct"] is not None]
        hrs_values = [s["hours_logged"] for s in scorecard if s["hours_logged"] is not None]

        def bucket(values: list) -> Dict:
            return {
                "avg": round(sum(values) / len(values), 1) if values else 0,
                "min": min(values) if values else 0,
                "max": max(values) if values else 0,
                "at_risk": sum(1 for v in values if v < 70)
            }

        return {
            "period": f"{year}-{month:02d}",
            "headcount": len(scorecard),
            "attendance": bucket(att_values),
            "delivery": bucket(del_values),
            "hours": bucket(hrs_values),
            "top_performers": [s for s in scorecard if s["ranked"]][:3],
            "unranked": sum(1 for s in scorecard if not s["ranked"]),        # data missing or withheld: not scored, not "at risk"
            "at_risk": [s for s in scorecard if s["ranked"] and s["composite_score"] < 60]
        }
