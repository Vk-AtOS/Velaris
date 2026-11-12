"""Read-only view of the employee master kept by EMPLOYEE_RECORDS, for agents that need to know who works here
(POLICY_ACKS: who must acknowledge a policy). It reads that agent's state file directly, so there is no import
cycle and no second copy of the data. It returns only what the caller needs and only for the organisation asked.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from velaris.agentkit.state import JsonState

ACTIVE = ("active", "notice")


def _records(org: str) -> List[Dict[str, Any]]:
    data = JsonState("EMPLOYEE_RECORDS", "state.json", {"records": {}}).load()
    return [r for r in data.get("records", {}).get("employees", {}).values() if r.get("org") == org]


def active_employees(org: str) -> List[Dict[str, Any]]:
    """[{"id", "department", "status", "join_date"}] for current employees of `org` (no names, no contact details)."""
    return [{"id": r["id"], "department": r["department"], "status": r["status"], "join_date": r["join_date"]}
            for r in _records(org) if r["status"] in ACTIVE]


def get(org: str, employee_id: str) -> Optional[Dict[str, Any]]:
    return next(({"id": r["id"], "department": r["department"], "status": r["status"], "join_date": r["join_date"]}
                 for r in _records(org) if r["id"] == employee_id), None)
