"""One orchestrator per department, registered in one place (KAN-31).

Each is the base (orchestration.base) + that department's registry tools + a scope and an escalation target.
`names()` lists them, `get(name)` returns one, `build()` makes them all with the same wiring (model, engine, gate).
The departments are exactly the folders under departments/ (a test keeps the two lists equal).

Only departments that have methods in velaris.api.allowlist.METHODS have tools today (_ai_core, _connectors,
data_knowledge, finance, hr, it_infrastructure). The others can still be asked: with no tool they answer or hand
the goal on, and they gain tools as methods are reviewed into the allowlist, with no change here.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from velaris.orchestration.base import DepartmentOrchestrator, Limits

BRAIN = "the central brain, then a person"
# department -> (what it covers and does not, who a stuck run goes to)
DEPARTMENTS: Dict[str, tuple] = {
    "_ai_core": ("Platform intelligence: policy decisions, model council, web research and search. It does not act on "
                 "business records.", BRAIN),
    "_connectors": ("Connected systems: Jira, Confluence and the Zoho connectors. Reads need the atlassian_reader role; "
                    "writes wait for approval.", "a governance_admin"),
    "client_success": ("Customer success and logistics follow-up for existing clients.", BRAIN),
    "communications": ("Meetings, calls, transcripts, summaries and action items.", BRAIN),
    "data_knowledge": ("Company memory and documents: search and ask over what the organisation stored, and remember "
                       "notes. Only the caller's own organisation.", BRAIN),
    "executive": ("Strategy and market intelligence for leadership: scans, scenarios, opportunities. Advice only.", BRAIN),
    "finance": ("Finance calculations (cash flow, runway, expense forecasts) and finance records. Money moves only "
                "after a person approves.", "the payroll_admin"),
    "hr": ("People operations: leave, onboarding, employee records, payroll reads, hiring. Personal data is read "
           "only as the caller may; offers, exits and erasures need a person.", "the hr_admin"),
    "it_infrastructure": ("IT service desk and infrastructure: tickets, SLAs, capacity.", "the infra_admin"),
    "legal_compliance": ("Legal and compliance review and policy. It never files anything.", "a governance_admin"),
    "marketing": ("Marketing content, branding and campaign analysis. Nothing is published without a person.", BRAIN),
    "operations": ("Operations: workflows, quality, SLAs and process analysis.", BRAIN),
    "project_management": ("Project plans, sprints, budgets and risk. It does not change a plan without approval.", BRAIN),
    "sales": ("Sales pipeline, prospects and retention analysis. It sends nothing to a customer by itself.", BRAIN),
    "security": ("Security monitoring, audit and access review. Access changes always need a security_admin.",
                 "the security_admin"),
    "supply_chain": ("Inventory, logistics, routes and fleet analysis.", BRAIN),
}
_built: Dict[str, DepartmentOrchestrator] = {}


def names() -> List[str]:
    return sorted(DEPARTMENTS)


def build(*, limits: Optional[Dict[str, Limits]] = None, **wiring: Any) -> Dict[str, DepartmentOrchestrator]:
    """Create and register all of them. `wiring` (llm, engine, gate, flow_path, route, models, on_escalate) is shared;
    `limits` may override one department's Limits."""
    _built.clear()
    for dept, (scope, to) in DEPARTMENTS.items():
        _built[dept] = DepartmentOrchestrator(dept, scope=scope, escalate_to=to, limits=(limits or {}).get(dept), **wiring)
    return dict(_built)


def get(department: str) -> Optional[DepartmentOrchestrator]:
    return _built.get(department)
