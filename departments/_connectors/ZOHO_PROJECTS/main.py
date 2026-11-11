import logging
import os
import time
from typing import Dict, Any, List

from velaris.agents.ZOHO_CONNECTOR.main import ZohoConnector

logger = logging.getLogger("ZOHO_PROJECTS")


class ZohoProjectsConnector:
    """
    Pulls project delivery data from Zoho Projects:
    - Tasks assigned to each employee
    - Completion rates and on-time delivery
    - Time logged per employee per project
    - Milestones and status
    """
    BASE = "https://projectsapi.zoho.in/restapi/portal"

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.zoho = ZohoConnector(config)
        self.portal = config.get("portal_id") or os.getenv("ZOHO_PORTAL_ID", "")

    def health_check(self) -> Dict[str, Any]:
        return {"agent": "ZOHO_PROJECTS", "status": "ok"}

    def get_projects(self) -> List[Dict]:
        resp = self.zoho.get(f"{self.BASE}/{self.portal}/projects/", {"status": "active"})
        return resp.get("projects", [])

    def get_tasks_by_owner(self, project_id: str, owner_id: str) -> List[Dict]:
        resp = self.zoho.get(
            f"{self.BASE}/{self.portal}/projects/{project_id}/tasks/",
            {"owner": owner_id}
        )
        return resp.get("tasks", [])

    def get_timelogs(self, project_id: str, owner_id: str, from_date: str, to_date: str) -> List[Dict]:
        """Returns time logs for an employee in a project. Dates: MM-dd-yyyy"""
        resp = self.zoho.get(
            f"{self.BASE}/{self.portal}/projects/{project_id}/logs/",
            {
                "users_list": owner_id,
                "fromDate": from_date,
                "toDate": to_date,
                "view_type": "day",
                "component_type": "task"
            }
        )
        return resp.get("timelogs", {}).get("grandtotal", [])

    def get_task_summary(self, project_id: str, owner_id: str) -> Dict:
        """Returns task completion rate and on-time delivery for an employee."""
        tasks = self.get_tasks_by_owner(project_id, owner_id)
        total = len(tasks)
        completed = sum(1 for t in tasks if t.get("status", {}).get("name") == "Closed")
        overdue = sum(
            1 for t in tasks
            if t.get("status", {}).get("name") != "Closed"
            and t.get("end_date_long", 0) < time.time() * 1000
        )
        return {
            "total_tasks": total,
            "completed": completed,
            "completion_rate": round(completed / total * 100, 1) if total else 0,
            "overdue": overdue,
            "on_time_rate": round((completed - overdue) / completed * 100, 1) if completed else 0
        }
