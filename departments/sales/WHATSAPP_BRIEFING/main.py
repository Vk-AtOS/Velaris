#!/usr/bin/env python3
"""
WHATSAPP_BRIEFING — Velaris BOS agent for Knackforge
Ported from VKatOS whatsapp_briefing. Daily metric logging + WhatsApp Business API dispatch.
"""
import asyncio
import concurrent.futures
import logging
import sqlite3

from velaris.core.sqlite_util import connect as connect_db
from datetime import datetime
from typing import Dict, Any

import httpx
from velaris.intel.paths import agent_file

logger = logging.getLogger("WHATSAPP_BRIEFING")


class WhatsAppBriefingSystem:
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        db_path = self.config.get("db_path") or agent_file("WHATSAPP_BRIEFING", "briefing_data.db")
        self.db = connect_db(db_path)
        self._init_db()

    def _init_db(self):
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS daily_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric_name TEXT, metric_value REAL,
                metric_unit TEXT, timestamp TEXT, notes TEXT)
        """)
        self.db.commit()

    def log(self, name: str, value: float, unit: str = "", notes: str = "") -> None:
        self.db.execute(
            "INSERT INTO daily_metrics (metric_name,metric_value,metric_unit,timestamp,notes) VALUES (?,?,?,?,?)",
            (name, value, unit, datetime.now().isoformat(), notes)   # LOCAL time: the briefing filters by the local date,
        )
        self.db.commit()
        logger.info("Metric logged: %s = %.1f %s", name, value, unit)

    def generate_briefing(self) -> str:
        today = datetime.now().strftime("%Y-%m-%d")
        rows = self.db.execute(
            "SELECT metric_name, SUM(metric_value), metric_unit FROM daily_metrics WHERE timestamp LIKE ? GROUP BY metric_name",
            (f"{today}%",),
        ).fetchall()
        lines = [
            "*Knackforge Daily Briefing*",
            f"*{datetime.now().strftime('%d %b %Y')}*",
            "",
        ]
        if not rows:
            lines.append("No metrics logged today yet.")
        else:
            for name, value, unit in rows:
                unit_str = f" {unit}" if unit else ""
                lines.append(f"- *{name}:* {value:.1f}{unit_str}")
        lines.append("")
        lines.append("_Powered by Velaris BOS — Knackforge_")
        return "\n".join(lines)

    def generate_briefing_dict(self) -> Dict[str, Any]:
        today = datetime.now().strftime("%Y-%m-%d")
        rows = self.db.execute(
            "SELECT metric_name, SUM(metric_value), metric_unit FROM daily_metrics WHERE timestamp LIKE ? GROUP BY metric_name",
            (f"{today}%",),
        ).fetchall()
        return {
            "date": today,
            "metrics": [{"name": r[0], "value": r[1], "unit": r[2]} for r in rows],
        }

    async def send(self, message: str) -> Dict[str, Any]:
        token = self.config.get("whatsapp_token")
        phone_id = self.config.get("whatsapp_phone_id")
        to = self.config.get("whatsapp_to")
        if not all([token, phone_id, to]):
            logger.info("WhatsApp not configured — briefing preview logged")
            return {"status": "preview", "message": message}
        url = f"https://graph.facebook.com/v17.0/{phone_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "to": to.replace("+", ""),
            "type": "text",
            "text": {"body": message},
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                r = await client.post(url, headers={"Authorization": f"Bearer {token}"}, json=payload)
        except httpx.HTTPError as e:
            logger.warning("WhatsApp send failed: %s", e)
            return {"status": "error", "error": str(e)}
        if r.status_code >= 400:      # the API refused it: that is not "sent"
            logger.warning("WhatsApp send refused: HTTP %d", r.status_code)
            return {"status": "error", "http_status": r.status_code, "error": f"HTTP {r.status_code}"}
        logger.info("WhatsApp sent: HTTP %d", r.status_code)
        return {"status": "sent", "http_status": r.status_code}


class WhatsAppBriefingAgent:
    """
    Daily business metric logger + WhatsApp Business dispatch.
    Ported from VKatOS whatsapp_briefing.
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.system = WhatsAppBriefingSystem(self.config)
        logger.info("WHATSAPP_BRIEFING agent initialised")

    def health_check(self) -> Dict[str, Any]:
        configured = bool(
            self.config.get("whatsapp_token")
            and self.config.get("whatsapp_phone_id")
            and self.config.get("whatsapp_to")
        )
        return {"agent": "WHATSAPP_BRIEFING", "status": "ok", "whatsapp_configured": configured}

    def log_metric(self, name: str, value: float, unit: str = "", notes: str = "") -> None:
        self.system.log(name, value, unit, notes)

    def get_briefing(self) -> str:
        return self.system.generate_briefing()

    def get_briefing_dict(self) -> Dict[str, Any]:
        return self.system.generate_briefing_dict()

    def send_briefing(self) -> Dict[str, Any]:
        message = self.system.generate_briefing()
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.system.send(message))
        # Called from inside a running event loop (an async API handler): asyncio.run would raise, so the
        # send runs on its own loop in a worker thread.
        with concurrent.futures.ThreadPoolExecutor(1) as ex:
            return ex.submit(asyncio.run, self.system.send(message)).result()


if __name__ == "__main__":
    agent = WhatsAppBriefingAgent()
    print(agent.health_check())
    agent.log_metric("Billable Hours", 142, "hrs")
    agent.log_metric("Active Projects", 7)
    agent.log_metric("Open Tickets", 23)
    agent.log_metric("Proposals Sent", 3)
    print(agent.get_briefing())
    print(agent.get_briefing_dict())
