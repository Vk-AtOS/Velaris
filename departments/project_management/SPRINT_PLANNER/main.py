import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

import logging
import math
import sqlite3
import json
from datetime import date, timedelta
from typing import Dict, Any, List, Optional
from velaris.intel.paths import agent_file

from velaris.intel.paths import agent_dir

logger = logging.getLogger("SPRINT_PLANNER")



def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(agent_file("SPRINT_PLANNER", "sprints.db"))
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS sprints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id TEXT NOT NULL,
            sprint_number INTEGER NOT NULL,
            name TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            velocity_target INTEGER DEFAULT 0,
            status TEXT DEFAULT 'planning',
            created_on TEXT NOT NULL,
            UNIQUE(project_id, sprint_number)
        );
        CREATE TABLE IF NOT EXISTS sprint_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sprint_id INTEGER NOT NULL,
            task_id TEXT NOT NULL,
            title TEXT NOT NULL,
            assignee TEXT,
            story_points INTEGER DEFAULT 0,
            status TEXT DEFAULT 'todo',
            FOREIGN KEY(sprint_id) REFERENCES sprints(id)
        );
    """)
    conn.commit()
    return conn


class SprintPlanner:
    """
    Scrum/Kanban sprint management: create sprints, assign tasks, track velocity.
    Standalone: no Zoho or Jira sync exists in this agent.
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._sprint_weeks = self.config.get("sprint_weeks", 2)
        _db().close()

    def health_check(self) -> Dict[str, Any]:
        return {"agent": "SPRINT_PLANNER", "status": "ok",
                "sprint_weeks": self._sprint_weeks}

    def create_sprint(self, project_id: str, sprint_number: int, name: str,
                      start_date: str, velocity_target: int = 0) -> Dict[str, Any]:
        start = date.fromisoformat(start_date)
        end = start + timedelta(weeks=self._sprint_weeks) - timedelta(days=1)
        conn = _db()
        try:
            cur = conn.execute(
                "INSERT INTO sprints (project_id, sprint_number, name, start_date, end_date, velocity_target, created_on) VALUES (?,?,?,?,?,?,?)",
                (project_id, sprint_number, name, start_date, end.isoformat(), velocity_target, date.today().isoformat())
            )
            sprint_id = cur.lastrowid
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return {"error": f"sprint {sprint_number} already exists for project {project_id}"}
        conn.close()
        return {"id": sprint_id, "project_id": project_id, "sprint_number": sprint_number,
                "name": name, "start_date": start_date, "end_date": end.isoformat(),
                "velocity_target": velocity_target, "status": "planning"}

    def add_task(self, sprint_id: int, task_id: str, title: str,
                 assignee: str = "", story_points: int = 0) -> Dict[str, Any]:
        if isinstance(story_points, bool) or not isinstance(story_points, (int, float)) \
                or not math.isfinite(story_points) or story_points < 0:
            return {"error": "story_points must be a finite number, zero or more"}
        conn = _db()
        if not conn.execute("SELECT 1 FROM sprints WHERE id=?", (sprint_id,)).fetchone():
            conn.close()
            return {"error": "sprint_not_found"}
        cur = conn.execute(
            "INSERT INTO sprint_tasks (sprint_id, task_id, title, assignee, story_points) VALUES (?,?,?,?,?)",
            (sprint_id, task_id, title, assignee, story_points)
        )
        item_id = cur.lastrowid
        conn.commit()
        conn.close()
        return {"id": item_id, "sprint_id": sprint_id, "task_id": task_id,
                "title": title, "assignee": assignee, "story_points": story_points}

    def update_task_status(self, item_id: int, status: str) -> Dict[str, Any]:
        """status: todo | in_progress | review | done"""
        valid = {"todo", "in_progress", "review", "done"}
        if status not in valid:
            return {"error": f"status must be one of {valid}"}
        conn = _db()
        changed = conn.execute("UPDATE sprint_tasks SET status=? WHERE id=?", (status, item_id)).rowcount
        conn.commit()
        conn.close()
        if not changed:
            return {"error": "task_not_found"}
        return {"id": item_id, "status": status}

    def get_sprint_board(self, sprint_id: int) -> Dict[str, Any]:
        conn = _db()
        sprint = conn.execute("SELECT * FROM sprints WHERE id=?", (sprint_id,)).fetchone()
        if not sprint:
            conn.close()
            return {"error": "sprint_not_found"}
        tasks = conn.execute("SELECT * FROM sprint_tasks WHERE sprint_id=?", (sprint_id,)).fetchall()
        conn.close()

        board: Dict[str, List] = {"todo": [], "in_progress": [], "review": [], "done": []}
        total_points = 0
        done_points = 0
        for t in tasks:
            d = dict(t)
            board.setdefault(d["status"], []).append(d)
            total_points += d["story_points"]
            if d["status"] == "done":
                done_points += d["story_points"]

        return {
            **dict(sprint),
            "board": board,
            "total_story_points": total_points,
            "completed_points": done_points,
            "velocity_pct": round(done_points / total_points * 100, 1) if total_points else 0,
        }

    def close_sprint(self, sprint_id: int) -> Dict[str, Any]:
        """Mark sprint done; returns velocity achieved."""
        conn = _db()
        if not conn.execute("SELECT 1 FROM sprints WHERE id=?", (sprint_id,)).fetchone():
            conn.close()
            return {"error": "sprint_not_found"}
        tasks = conn.execute(
            "SELECT story_points, status FROM sprint_tasks WHERE sprint_id=?", (sprint_id,)
        ).fetchall()
        done_pts = sum(t["story_points"] for t in tasks if t["status"] == "done")
        conn.execute("UPDATE sprints SET status='completed' WHERE id=?", (sprint_id,))
        conn.commit()
        conn.close()
        logger.info("Sprint %d closed: velocity=%d", sprint_id, done_pts)
        return {"sprint_id": sprint_id, "status": "completed", "velocity_achieved": done_pts}

    def project_velocity_trend(self, project_id: str) -> List[Dict]:
        conn = _db()
        sprints = conn.execute(
            "SELECT id, sprint_number, name, velocity_target FROM sprints WHERE project_id=? AND status='completed' ORDER BY sprint_number",
            (project_id,)
        ).fetchall()
        result = []
        for s in sprints:
            done = conn.execute(
                "SELECT COALESCE(SUM(story_points),0) as pts FROM sprint_tasks WHERE sprint_id=? AND status='done'",
                (s["id"],)
            ).fetchone()["pts"]
            result.append({
                "sprint": s["sprint_number"],
                "name": s["name"],
                "target": s["velocity_target"],
                "achieved": done,
                "delta": done - s["velocity_target"],
            })
        conn.close()
        return result
