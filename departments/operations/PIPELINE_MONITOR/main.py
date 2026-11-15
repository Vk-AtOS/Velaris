#!/usr/bin/env python3
"""
PIPELINE_MONITOR — Velaris BOS agent for Knackforge
Ported from VKatOS pipeline_monitor. Statistical risk scoring for pipeline stage durations.
"""
import logging
import sqlite3
import statistics
from datetime import datetime, timedelta
from typing import Dict, Any, List
from velaris.intel.paths import agent_file


logger = logging.getLogger("PIPELINE_MONITOR")


class PipelineMonitor:
    def __init__(self, db_path: str = "", config: Dict[str, Any] = None):
        self.config = config or {}
        self.db = sqlite3.connect(db_path or agent_file("PIPELINE_MONITOR", "pipeline_data.db"))
        self._init_db()

    def _init_db(self):
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                stage TEXT, duration_hours REAL,
                risk_score REAL, timestamp TEXT, notes TEXT)
        """)
        self.db.commit()

    def log_stage(self, stage_name: str, duration_hours: float, notes: str = "") -> Dict[str, Any]:
        risk = self._calculate_risk(stage_name, duration_hours)
        self.db.execute(
            "INSERT INTO observations (stage,duration_hours,risk_score,timestamp,notes) VALUES (?,?,?,?,?)",
            (stage_name, duration_hours, risk, datetime.utcnow().isoformat(), notes),
        )
        self.db.commit()
        label = "critical" if risk >= 0.7 else "watch" if risk >= 0.35 else "normal"
        if risk >= 0.7:
            logger.warning("PIPELINE risk %s: stage=%s duration=%.1fh", label.upper(), stage_name, duration_hours)
        else:
            logger.info("Stage logged: %s %.1fh → %s (%.0f%% risk)", stage_name, duration_hours, label, risk * 100)
        return {"stage": stage_name, "duration_hours": duration_hours, "risk": risk, "label": label}

    def _calculate_risk(self, stage: str, duration: float) -> float:
        rows = self.db.execute(
            "SELECT duration_hours FROM observations WHERE stage=? ORDER BY timestamp DESC LIMIT 30",
            (stage,),
        ).fetchall()
        if len(rows) < 3:
            baseline = self.config.get("stages", {}).get(stage, {}).get("baseline_hours", duration)
            return 0.1 if duration <= baseline * 1.2 else 0.6
        durations = [r[0] for r in rows]
        mean = statistics.mean(durations)
        std = statistics.stdev(durations) if len(durations) > 1 else 0.1
        if std <= 0:        # every earlier reading was identical: any real jump is an anomaly, not "normal"
            return 0.1 if duration <= mean * 1.2 else 0.6
        z = (duration - mean) / std
        if z < 1.5:
            return 0.1
        elif z < 2.0:
            return 0.35
        elif z < 2.5:
            return 0.65
        elif z < 3.0:
            return 0.80
        else:
            return 0.95

    def morning_briefing(self) -> str:
        yesterday = (datetime.utcnow() - timedelta(days=1)).isoformat()
        rows = self.db.execute(
            "SELECT stage, AVG(risk_score), COUNT(*) FROM observations WHERE timestamp > ? GROUP BY stage",
            (yesterday,),
        ).fetchall()
        lines = [f"Pipeline Briefing — {datetime.now().strftime('%d %b %Y')}"]
        if not rows:
            lines.append("No pipeline activity in the last 24 hours.")
        else:
            critical = [(r[0], r[1]) for r in rows if r[1] >= 0.7]
            healthy = [r for r in rows if r[1] < 0.35]
            for stage, risk in critical:
                lines.append(f"CRITICAL {stage}: {risk:.0%} risk — needs attention")
            lines.append(f"{len(healthy)} stage(s) healthy")
        return "\n".join(lines)

    def dashboard(self) -> List[Dict]:
        rows = self.db.execute(
            "SELECT stage, AVG(risk_score), MAX(timestamp) FROM observations GROUP BY stage"
        ).fetchall()
        result = []
        for stage, risk, ts in rows:
            state = "critical" if risk >= 0.7 else "watch" if risk >= 0.35 else "normal"
            result.append({"stage": stage, "avg_risk": round(risk, 3), "state": state, "last_seen": ts})
        return result


class PipelineMonitorAgent:
    """
    Statistical pipeline stage risk monitor. Z-score based anomaly detection on durations.
    Ported from VKatOS pipeline_monitor.
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        db_path = self.config.get("db_path") or agent_file("PIPELINE_MONITOR", "pipeline_data.db")
        self.monitor = PipelineMonitor(db_path, self.config)
        logger.info("PIPELINE_MONITOR agent initialised")

    def health_check(self) -> Dict[str, Any]:
        return {"agent": "PIPELINE_MONITOR", "status": "ok"}

    def log_stage(self, stage_name: str, duration_hours: float, notes: str = "") -> Dict[str, Any]:
        return self.monitor.log_stage(stage_name, duration_hours, notes)

    def morning_briefing(self) -> str:
        return self.monitor.morning_briefing()

    def dashboard(self) -> List[Dict]:
        return self.monitor.dashboard()


if __name__ == "__main__":
    agent = PipelineMonitorAgent()
    print(agent.health_check())
    agent.log_stage("requirements_review", 2.5)
    agent.log_stage("code_review", 1.0)
    agent.log_stage("qa_testing", 8.0)
    print(agent.dashboard())
    print(agent.morning_briefing())
