"""Checklist templates and the task arithmetic for onboarding and exit. Pure functions, no I/O.

A template item has a key, a title, a kind, an owner role, a due offset in days from an anchor date (the join date
for onboarding, the last working day for exit; negative = before it), the keys it depends on, and whether it is
required. Kinds: "task" (a person does it and says so), "collect:<identifier>" (pan, aadhaar, bank_account),
"form:<name>" (velaris.agentkit.onboarding_fields.FORMS), "document", "policy_ack" (completed only against a current POLICY_ACKS
acknowledgement of the item's `policy` key by the case's subject).

Nothing in a template is a statutory figure or deadline: the due offsets are the company's own working defaults,
set here so the first customer has something to edit. Change them by changing this file or passing a template.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

Item = Dict[str, Any]


def _i(key: str, title: str, owner: str, due: int, deps: tuple = (), kind: str = "task", required: bool = True,
       note: str = "", policy: str = "") -> Item:
    return {"policy": policy or None, "key": key, "title": title, "owner": owner, "due_offset_days": due, "depends_on": list(deps),
            "kind": kind, "required": required, "note": note}


BASE: List[Item] = [
    _i("confirm_offer_accepted", "Confirm the signed offer is on file and the join date is agreed", "hr", -7),
    _i("collect_pan", "Provide PAN", "employee", -5, ("confirm_offer_accepted",), "collect:pan"),
    _i("collect_bank_account", "Provide bank account for salary", "employee", -5, ("confirm_offer_accepted",),
       "collect:bank_account", note="Account number and IFSC."),
    _i("collect_aadhaar", "Provide Aadhaar only if a purpose applies", "employee", -5, ("confirm_offer_accepted",),
       "collect:aadhaar", False,
       "Optional. Only the last four digits and a keyed hash are kept, never the number. Skip unless a purpose "
       "(for example PF/UAN) needs it."),
    _i("upload_identity_proof", "Upload an identity or address proof", "employee", -3, ("confirm_offer_accepted",),
       "document", False),
    _i("emergency_contact", "Give an emergency contact", "employee", 0, (), "form:emergency_contact"),
    _i("tax_declaration", "Submit the tax declaration (regime choice)", "employee", 7, (), "form:tax_declaration"),
    _i("pf_nomination", "Submit the PF nomination", "employee", 14, (), "form:pf_nomination", False,
       "Data capture only. Filing is done by payroll."),
    _i("esi_nomination", "Submit the ESI nomination (if covered)", "employee", 14, (), "form:esi_nomination", False),
    _i("provision_accounts", "Create email and chat accounts", "it", -2, ("confirm_offer_accepted",)),
    _i("allocate_laptop", "Allocate and record a laptop and accessories", "it", -2, ("confirm_offer_accepted",)),
    _i("ack_code_of_conduct", "Acknowledge the code of conduct", "employee", 3, ("provision_accounts",), "policy_ack",
       policy="code_of_conduct"),
    _i("ack_infosec_policy", "Acknowledge the information security policy", "employee", 3, ("provision_accounts",),
       "policy_ack", policy="information_security"),
    _i("assign_buddy", "Assign an onboarding buddy", "manager", -3),
    _i("first_week_plan", "Write the first-week plan", "manager", -1, ("assign_buddy",)),
    _i("orientation", "Orientation session held", "hr", 0, ("provision_accounts", "allocate_laptop")),
    _i("payroll_setup", "Add the employee to payroll", "finance", 5, ("collect_pan", "collect_bank_account")),
]

ROLE_ADDONS: Dict[str, List[Item]] = {
    "engineering": [
        _i("source_control_access", "Grant source control and CI access", "it", -1, ("provision_accounts",)),
        _i("dev_environment", "Dev environment working on the new laptop", "it", 0, ("allocate_laptop",)),
        _i("secure_coding_ack", "Acknowledge the secure-coding standard", "employee", 7, ("source_control_access",),
           "policy_ack", policy="secure_coding"),
    ],
    "sales": [_i("crm_access", "Grant CRM access", "it", -1, ("provision_accounts",))],
    "support": [_i("ticketing_access", "Grant ticketing system access", "it", -1, ("provision_accounts",))],
}
LOCATION_ADDONS: Dict[str, List[Item]] = {
    "chennai": [
        _i("office_access_card", "Issue the office access card", "hr", 0),
        _i("work_location_record", "Record the work location and local body for payroll mapping", "hr", 0, (), "task",
           True, "Which local body's rules apply is payroll's decision (PAYROLL_ENGINE); this task records the fact."),
    ],
    "remote": [_i("remote_setup_check", "Check the home-office and connectivity setup", "manager", 3)],
}

EXIT_BASE: List[Item] = [
    _i("record_resignation", "Record the resignation or termination and the last working day", "hr", -30),
    _i("handover_plan", "Agree the work handover plan", "manager", -14, ("record_resignation",)),
    _i("knowledge_transfer", "Complete knowledge transfer", "manager", -2, ("handover_plan",)),
    _i("return_assets", "Collect laptop, accessories, access cards", "it", 0),
    _i("revoke_accounts", "Revoke email, chat and directory accounts", "it", 0, ("return_assets",)),
    _i("revoke_vpn_and_remote", "Revoke VPN and remote-access credentials", "it", 0),
    _i("revoke_source_control", "Remove source control, CI and cloud console access", "it", 0),
    _i("rotate_shared_secrets", "Rotate shared passwords and keys the person knew", "it", 1, ("revoke_accounts",)),
    _i("revoke_building_access", "Deactivate the office access card", "hr", 0),
    _i("final_settlement", "Prepare the final settlement for payroll", "finance", 7, ("return_assets",)),
    _i("exit_interview", "Hold the exit interview", "hr", -3, (), "task", False),
    _i("issue_relieving_letter", "Issue the relieving letter", "hr", 7, ("final_settlement",)),
]


def build_tasks(anchor: date, items: List[Item], assignees: Optional[Dict[str, str]] = None) -> List[Item]:
    """Open tasks from template items; assignee = the person named for the item's owner role, if any."""
    assignees = assignees or {}
    tasks = []
    for it in items:
        t = dict(it)
        t["depends_on"] = list(it["depends_on"])
        t["due_date"] = (anchor + timedelta(days=it["due_offset_days"])).isoformat()
        t["assignee"] = assignees.get(it["owner"])
        t.update(state="open", done_at=None, done_by=None, note_done="", evidence_ref=None)
        tasks.append(t)
    return tasks


def onboarding_items(role_group: str, location: str) -> List[Item]:
    return BASE + ROLE_ADDONS.get(role_group, []) + LOCATION_ADDONS.get(location, [])


def template_problems(items: List[Item]) -> List[str]:
    """Duplicate keys, dependencies on unknown keys, and dependency cycles."""
    keys = [i["key"] for i in items]
    problems = [f"duplicate key {k}" for k in sorted({k for k in keys if keys.count(k) > 1})]
    deps = {i["key"]: i["depends_on"] for i in items}
    problems += [f"{k} depends on unknown {d}" for k, ds in deps.items() for d in ds if d not in deps]
    state: Dict[str, int] = {}

    def visit(k: str) -> bool:
        if state.get(k) == 1:
            return True
        if state.get(k) == 2:
            return False
        state[k] = 1
        cyc = any(visit(d) for d in deps.get(k, []) if d in deps)
        state[k] = 2
        return cyc

    if any(visit(k) for k in deps):
        problems.append("dependency cycle")
    return problems


def task_view(tasks: List[Item], today: date) -> List[Dict[str, Any]]:
    """Each task with its derived state: done, waived, blocked (an unfinished dependency), overdue or ready."""
    by_key = {t["key"]: t for t in tasks}
    out = []
    for t in tasks:
        open_deps = [d for d in t["depends_on"] if by_key[d]["state"] == "open"]
        if t["state"] in ("done", "waived"):
            derived = t["state"]
        elif open_deps:
            derived = "blocked"
        elif date.fromisoformat(t["due_date"]) < today:
            derived = "overdue"
        else:
            derived = "ready"
        out.append({"key": t["key"], "title": t["title"], "owner": t["owner"], "assignee": t["assignee"],
                    "kind": t["kind"], "required": t["required"], "due_date": t["due_date"], "state": derived,
                    "blocked_by": open_deps, "late": derived == "blocked" and
                    date.fromisoformat(t["due_date"]) < today})
    return out


def progress(tasks: List[Item], today: date) -> Dict[str, Any]:
    """Completion percentage of the required tasks, and what is blocked or overdue."""
    view = task_view(tasks, today)
    req = [v for v in view if v["required"]]
    done = [v for v in req if v["state"] in ("done", "waived")]
    pct = round(100 * len(done) / len(req), 1) if req else 100.0
    blocked = [{"task": v["key"], "owner": v["owner"], "assignee": v["assignee"], "waiting_for": v["blocked_by"],
                "due_date": v["due_date"], "late": v["late"]} for v in view if v["state"] == "blocked"]
    return {"completion_percent": pct, "required_total": len(req), "required_done": len(done),
            "overdue": [v["key"] for v in view if v["state"] == "overdue"], "blocked": blocked,
            "complete": len(done) == len(req), "tasks": view}


def reminders(tasks: List[Item], today: date, within_days: int = 2) -> List[Dict[str, Any]]:
    """Drafted reminders (never sent): ready or overdue tasks that are due within `within_days`."""
    out = []
    for v in task_view(tasks, today):
        if v["state"] not in ("ready", "overdue"):
            continue
        days = (date.fromisoformat(v["due_date"]) - today).days
        if days <= within_days:
            out.append({"task": v["key"], "title": v["title"], "owner": v["owner"], "to": v["assignee"],
                        "due_date": v["due_date"], "days_overdue": max(0, -days), "state": v["state"]})
    return out
