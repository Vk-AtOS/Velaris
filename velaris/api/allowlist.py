"""Which agent methods may be called over HTTP, and how. One table; anything not in it is refused.

  read   no change of state and no outside effect beyond reading: runs on the call
  act    changes state or acts outside: becomes a one-step flow run that waits for approval
         (AetherOS Prime when configured, see velaris.core.prime), never straight through

A rule may also say:

  scope    the parameter naming an organisation scope (memory, documents). It must be the
           caller's organisation ("<org>" or "<org>:<anything>"), because those agents keep
           every organisation's data in one store and do not check.
  actor    the parameter that names who is acting (by=, reviewed_by=). Code fills it with the
           caller's id; a different value is refused. It is never offered to a model.
  own      (parameter, category): the employee the call is about. It must be the caller's own
           employee record, or the caller must hold a role that velaris.core.access lets read
           that category for others. Decided and traced by access.authorize_read().
  roles    roles of which the caller must hold one (velaris.core.access.check_caller, traced).

Every check runs again when an approved step finally executes, as the person it runs for.
Methods that guard sensitive reads themselves (authorize_read inside the agent) need no
extra rule here; the caller is set by BackendEngine.run.
"""
from __future__ import annotations

import inspect
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Dict, FrozenSet, List, Optional, Tuple

from velaris.agents.inventory import inventory
from velaris.core.access import Caller, AccessDenied, ATLASSIAN_READERS, READ_OTHERS, acting_as, authorize_read, check_caller

READ, ACT = "read", "act"
_NEVER_PARAMS = {"self", "caller"}


@dataclass(frozen=True)
class Rule:
    kind: str
    scope: Optional[str] = None
    actor: Optional[str] = None
    own: Optional[Tuple[str, str]] = None
    roles: Optional[FrozenSet[str]] = None


_ATL = ATLASSIAN_READERS
_HR = READ_OTHERS["identity"]           # who may act on another employee's HR records
# Hiring suite (recruiter / hiring_manager / interviewer are plain role names; hr_admin may do everything)
_REC = frozenset({"recruiter", "hr_admin"})
_DEC = frozenset({"hiring_manager", "hr_admin"})
_HIR = frozenset({"recruiter", "hiring_manager", "hr_admin"})
_PAN = frozenset({"recruiter", "hiring_manager", "interviewer", "hr_admin"})
_ADM = frozenset({"hr_admin"})

METHODS: Dict[str, Dict[str, Rule]] = {
    # HR
    "LEAVE_MANAGEMENT": {
        "get_balance": Rule(READ, own=("employee_id", "health")),
        "employee_history": Rule(READ),                     # authorize_read inside
        "pending_approvals": Rule(READ),                    # authorize_read inside
        "apply": Rule(ACT, own=("employee_id", "health")),
        "approve": Rule(ACT, actor="reviewed_by", roles=_HR),
        "reject": Rule(ACT, actor="reviewed_by", roles=_HR),
    },
    "ZOHO_PEOPLE": {
        "get_employees": Rule(READ),                        # authorize_read inside
        "get_leave_summary": Rule(READ, own=("employee_id", "health")),
        "get_attendance": Rule(READ, own=("employee_id", "identity")),
        "get_attendance_summary": Rule(READ, own=("employee_id", "identity")),
    },
    # Payroll: reads only. The agents check pay/bank access themselves.
    "PAYROLL_ENGINE": {
        "compute": Rule(READ), "compute_bulk": Rule(READ), "org_statutory_summary": Rule(READ),
        "get_payslip": Rule(READ), "get_statutory_deductions": Rule(READ), "get_ytd_summary": Rule(READ),
    },
    "ZOHO_PAYROLL": {
        "get_payslip": Rule(READ), "get_statutory_deductions": Rule(READ), "get_ytd_summary": Rule(READ),
        "get_cost_to_company": Rule(READ),
    },
    # Onboarding and paperwork. Reads guard sensitive data inside the agent (authorize_read); identity is the Caller.
    # The signer-facing ESIGN methods (open_signing ... decline_signing) are deliberately NOT listed: a signer holds a
    # token, not a Caller, so they need their own unauthenticated route that is not an approval-gated step.
    "OFFER_LETTERS": {
        "list_templates": Rule(READ), "list_offers": Rule(READ), "get_offer": Rule(READ), "render_offer": Rule(READ),
        "compensation_preview": Rule(READ),
        "add_template": Rule(ACT, roles=_HR), "create_offer": Rule(ACT, roles=_HR), "revise_offer": Rule(ACT, roles=_HR),
        "submit_for_approval": Rule(ACT, roles=_HR), "approve": Rule(ACT), "reject": Rule(ACT),    # named approvers, checked inside
        "send_offer": Rule(ACT, roles=_HR), "record_response": Rule(ACT, roles=_HR), "withdraw_offer": Rule(ACT, roles=_HR),
        "expire_due": Rule(ACT, roles=_HR),
    },
    "ESIGN": {
        "get_request": Rule(READ), "list_requests": Rule(READ), "verify": Rule(READ), "get_sealed_document": Rule(READ),
        "create_request": Rule(ACT, roles=_HR), "send_request": Rule(ACT, roles=_HR), "void_request": Rule(ACT),   # drafter or HR, inside
        "send_reminders": Rule(ACT, roles=_HR), "process_due": Rule(ACT, roles=_HR), "seal_request": Rule(ACT, roles=_HR),
    },
    "ONBOARDING_FLOW": {
        "list_templates": Rule(READ), "list_cases": Rule(READ), "case_status": Rule(READ), "reminders_due": Rule(READ),
        "get_identifiers": Rule(READ), "get_form": Rule(READ), "get_document": Rule(READ),        # authorize_read inside
        "check_aadhaar": Rule(READ),
        "start_onboarding": Rule(ACT, roles=_HR), "cancel_case": Rule(ACT, roles=_HR), "waive_task": Rule(ACT, roles=_HR),
        "complete_task": Rule(ACT), "submit_identifier": Rule(ACT), "submit_form": Rule(ACT), "collect_document": Rule(ACT),   # joiner or HR, inside
    },
    "EMPLOYEE_RECORDS": {
        "get_employee": Rule(READ), "list_employees": Rule(READ), "employee_history": Rule(READ), "export_subject": Rule(READ),
        "retention_status": Rule(READ), "retention_table": Rule(READ), "workforce_aggregate": Rule(READ, roles=_HR),
        "exit_status": Rule(READ),
        "propose_conversion": Rule(ACT, roles=_HR), "approve_conversion": Rule(ACT, roles=_HR), "reject_conversion": Rule(ACT, roles=_HR),
        "change_record": Rule(ACT, roles=_HR), "start_exit": Rule(ACT, roles=_HR), "complete_exit_task": Rule(ACT),
        "finalise_exit": Rule(ACT, roles=_HR), "erase_subject": Rule(ACT, roles=_HR),
    },
    "POLICY_ACKS": {
        "list_policies": Rule(READ), "get_policy": Rule(READ), "pending_for_employee": Rule(READ), "compliance_report": Rule(READ),
        "reminders_due": Rule(READ),
        "publish_policy": Rule(ACT, roles=_HR), "retire_policy": Rule(ACT, roles=_HR), "acknowledge": Rule(ACT),   # self only, inside
    },
    # IT service management
    "ITSM_ENGINE": {
        "list_tickets": Rule(READ), "get_ticket": Rule(READ), "sla_status": Rule(READ),
        "transition": Rule(ACT, actor="by"),
    },
    # Finance calculators: pure functions of their arguments
    "TREASURIX": {"project_cashflow": Rule(READ), "reserve_ratio": Rule(READ), "runway_months": Rule(READ)},
    "FISCALIS": {"cost_breakdown": Rule(READ), "forecast_expenses": Rule(READ)},
    # Research and search (read the public web through velaris.intel's guarded fetcher)
    "AUTONOMOUS_RESEARCH_ENGINE": {"research": Rule(READ)},
    "ADVANCED_SEARCH_ENGINE": {"web_search": Rule(READ), "read_page": Rule(READ)},
    # Knowledge
    "DOCUMENT_LIBRARY": {"search": Rule(READ, scope="scope"), "ask": Rule(READ, scope="scope")},
    "MODEL_COUNCIL": {"deliberate": Rule(READ)},
    # Control layer: narrow scripted tasks in files/terminal/browser. Starting and undoing change things: act.
    "CONTROL_LAYER": {"list_tasks": Rule(READ), "run_state": Rule(READ), "run_report": Rule(READ),
                      "start_run": Rule(ACT), "undo": Rule(ACT)},
    # Atlassian Cloud. The writes are act rules: a step that waits for approval, and the connector
    # itself refuses to run them anywhere else.
    # Reads use one service account, so they need the atlassian_reader role and are limited to the configured
    # projects/spaces inside the connectors (confused-deputy guard).
    "JIRA": {
        "search_issues": Rule(READ, roles=_ATL), "get_issue": Rule(READ, roles=_ATL),
        "get_transitions": Rule(READ, roles=_ATL), "list_projects": Rule(READ, roles=_ATL),
        "create_issue": Rule(ACT), "transition_issue": Rule(ACT),
    },
    "CONFLUENCE": {
        "search": Rule(READ, roles=_ATL), "get_page_markdown": Rule(READ, roles=_ATL), "list_spaces": Rule(READ, roles=_ATL),
        "ingest_space": Rule(ACT, scope="scope"),
    },
    "LONGTERM_MEMORY": {"recall": Rule(READ, scope="scope"), "remember": Rule(ACT, scope="scope")},
    # Hiring suite: reads declared read, every state change is an act (approval). Candidates are not Callers: public intake,
    # status, self-scheduling and interview-event ingestion are plain functions for a gateway (hiring_intake, hiring_sched, hiring_record_gateway), not here.
    "ATS_CORE": {
        "add_application": Rule(ACT, roles=_REC),
        "add_candidate": Rule(ACT, roles=_REC),
        "aggregate_counts": Rule(READ, roles=_HIR),
        "approve_requisition": Rule(ACT, roles=_DEC),
        "candidate_contact": Rule(READ, roles=_REC),
        "candidate_summary": Rule(READ, roles=_REC),
        "close_requisition": Rule(ACT, roles=_HIR),
        "create_requisition": Rule(ACT, roles=_HIR),
        "decision_log": Rule(READ, roles=_HIR),
        "duplicate_review": Rule(READ, roles=_REC),
        "erase_candidates": Rule(ACT, roles=_ADM),
        "export_candidate": Rule(READ, roles=_HIR),
        "get_application": Rule(READ, roles=_HIR),
        "get_requisition": Rule(READ, roles=_HIR),
        "list_requisitions": Rule(READ, roles=_HIR),
        "move_stage": Rule(ACT, roles=_HIR),
        "open_requisition": Rule(ACT, roles=_HIR),
        "pipeline": Rule(READ, roles=_HIR),
        "record_offer_outcome": Rule(ACT, roles=_ADM),
        "resolve_duplicate": Rule(ACT, roles=_REC),
        "retention_due": Rule(READ, roles=_REC),
        "withdraw_consent": Rule(ACT, roles=_REC),
    },
    "RESUME_EVIDENCE": {
        "alias_proposals": Rule(READ, roles=_HIR),
        "bias_audit": Rule(READ, roles=_REC),
        "get_evidence": Rule(READ, roles=_HIR),
        "list_skills": Rule(READ, roles=_HIR),
        "match_requisition": Rule(READ, roles=_HIR),
        "parse_resume": Rule(ACT, roles=_REC),
        "propose_alias": Rule(ACT, roles=_REC),
        "review_alias": Rule(ACT, roles=_ADM),
        "unknown_skills": Rule(READ, roles=_HIR),
    },
    "JOB_POSTINGS": {
        "approve_pack": Rule(ACT, roles=_DEC),
        "approve_posting": Rule(ACT, roles=_DEC),
        "get_company_profile": Rule(READ, roles=_HIR),
        "get_posting": Rule(READ, roles=_HIR),
        "list_packs": Rule(READ, roles=_HIR),
        "mark_pack_posted": Rule(ACT, roles=_REC),
        "mark_pack_taken_down": Rule(ACT, roles=_REC),
        "mark_posting_live": Rule(ACT, roles=_REC),
        "prepare_careers_posting": Rule(ACT, roles=_REC),
        "prepare_pack": Rule(ACT, roles=_REC),
        "resolve_tracking": Rule(READ, roles=_HIR),
        "send_indexing_notification": Rule(ACT, roles=_REC),
        "set_company_profile": Rule(ACT, roles=_REC),
        "take_down_posting": Rule(ACT, roles=_REC),
        "takedown_due": Rule(READ, roles=_HIR),
    },
    "SCREENING_FORMS": {
        "accept_submission": Rule(ACT, roles=_REC),
        "create_form": Rule(ACT, roles=_REC),
        "discard_submission": Rule(ACT, roles=_REC),
        "get_form": Rule(READ, roles=_HIR),
        "get_submission": Rule(READ, roles=_REC),
        "issue_candidate_token": Rule(ACT, roles=_REC),
        "list_forms": Rule(READ, roles=_HIR),
        "pending_submissions": Rule(READ, roles=_REC),
        "process_withdrawal": Rule(ACT, roles=_REC),
        "public_routes": Rule(READ, roles=_HIR),
        "publish_form": Rule(ACT, roles=_REC),
        "sweep_submissions": Rule(ACT, roles=_REC),
        "unpublish_form": Rule(ACT, roles=_REC),
        "withdrawal_requests": Rule(READ, roles=_REC),
    },
    "INTERVIEW_SCHEDULER": {
        "approve_draft": Rule(ACT, roles=_REC),
        "book_interview": Rule(ACT, roles=_REC),
        "cancel_interview": Rule(ACT, roles=_REC),
        "complete_interview": Rule(ACT, roles=_REC),
        "hand_off_to_mail": Rule(ACT, roles=_REC),
        "issue_schedule_token": Rule(ACT, roles=_REC),
        "list_bookings": Rule(READ, roles=_HIR),
        "list_drafts": Rule(READ, roles=_HIR),
        "list_interviewers": Rule(READ, roles=_PAN),
        "mark_no_show": Rule(ACT, roles=_REC),
        "mark_reminder_sent": Rule(ACT, roles=_REC),
        "propose_slots": Rule(READ, roles=_HIR),
        "reminders": Rule(READ, roles=_HIR),
        "render_invitation": Rule(READ, roles=_REC),
        "reschedule_interview": Rule(ACT, roles=_REC),
        "set_availability": Rule(ACT, roles=_PAN),
    },
    "INTERVIEW_KIT": {
        "add_question": Rule(ACT, roles=_HIR),
        "agreement_report": Rule(READ, roles=_PAN),
        "assign_panel": Rule(ACT, roles=_REC),
        "calibration_report": Rule(READ, roles=_HIR),
        "create_kit": Rule(ACT, roles=_HIR),
        "create_work_sample": Rule(ACT, roles=_HIR),
        "define_rubric": Rule(ACT, roles=_HIR),
        "get_kit": Rule(READ, roles=_PAN),
        "list_questions": Rule(READ, roles=_PAN),
        "list_work_samples": Rule(READ, roles=_PAN),
        "review_work_sample": Rule(ACT, roles=_PAN),
        "scorecards": Rule(READ, roles=_PAN),
        "submit_scorecard": Rule(ACT, roles=_PAN),
        "work_sample_reviews": Rule(READ, roles=_HIR),
    },
    "INTERVIEW_RECORD": {
        "close_session": Rule(ACT, roles=_HIR),
        "create_session": Rule(ACT, roles=_HIR),
        "evidence_view": Rule(READ, roles=_HIR),
        "give_consent": Rule(ACT, roles=_PAN),
        "issue_participant_token": Rule(ACT, roles=_HIR),
        "list_sessions": Rule(READ, roles=_HIR),
        "mark_event": Rule(ACT, roles=_HIR),
        "purge_expired_sessions": Rule(ACT, roles=frozenset({"hr_admin"})),
        "register_audio_track": Rule(ACT, roles=_HIR),
        "replay_pad": Rule(READ, roles=_HIR),
        "transcribe_track": Rule(ACT, roles=_HIR),
        "withdraw_my_consent": Rule(ACT, roles=_PAN),
    },
}


def rule_for(agent: str, method: str) -> Optional[Rule]:
    """The method's rule; None (not callable) for anything undeclared and for every private method."""
    return None if method.startswith("_") else METHODS.get(agent, {}).get(method)


def http_params(fn: Any) -> List[inspect.Parameter]:
    """The parameters a client may pass by name: not self/caller, not *args/**kwargs."""
    return [p for p in inspect.signature(fn).parameters.values()
            if p.name not in _NEVER_PARAMS and p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)]


def tool_params(fn: Any, rule: Rule) -> Dict[str, str]:
    """For a flow Tool: argument name -> description, without the actor parameter code fills in."""
    return {p.name: ("" if p.annotation is p.empty else str(getattr(p.annotation, "__name__", p.annotation)))
            + ("" if p.default is p.empty else f" (default {p.default!r})")
            for p in http_params(fn) if p.name != rule.actor}


def prepare(agent: str, method: str, fn: Any, params: Any, caller: Caller) -> Dict[str, Any]:
    """Check one call against its rule and return the arguments to call with.

    Raises AccessDenied (refused for this caller), LookupError (not callable over HTTP)
    or ValueError (arguments that do not fit the method).
    """
    rule = rule_for(agent, method)
    if rule is None:
        raise LookupError(f"{agent}.{method} is not callable over HTTP")
    if not isinstance(params, dict) or not all(isinstance(k, str) for k in params):
        raise ValueError("params must be a JSON object")
    allowed = {p.name for p in http_params(fn)}
    unknown = sorted(set(params) - allowed)
    if unknown:
        raise ValueError(f"unknown parameters: {unknown[:10]}")
    args = dict(params)
    if rule.actor:
        if args.get(rule.actor, caller.id) != caller.id:
            raise AccessDenied(f"{rule.actor} must be the caller")
        args[rule.actor] = caller.id
    if rule.scope:
        scope = args.get(rule.scope)
        if not (isinstance(scope, str) and (scope == caller.org or scope.startswith(caller.org + ":"))):
            raise AccessDenied("the scope belongs to another organisation")
    if rule.own:
        name, category = rule.own
        if args.get(name) is None:
            raise ValueError(f"{name} is required")
        authorize_read(category, args[name], agent=agent, caller=caller)
    if rule.roles:
        with acting_as(caller):
            _who, refusal = check_caller(agent, method, {"via": "api"}, roles=rule.roles)
        if refusal:
            raise AccessDenied(refusal["reason"][:200])
    try:
        inspect.signature(fn).bind(None, **args)        # None stands for self
    except TypeError as e:
        raise ValueError("the parameters do not fit the method (missing or extra arguments)") from e
    return args


def _summary(obj: Any) -> str:
    return (inspect.getdoc(obj) or "").strip().split("\n")[0][:200]


@lru_cache(maxsize=1)
def _statuses() -> Dict[str, str]:
    """Agent -> inventory status. Read from the source files once per process (it is slow)."""
    return {a: s for dept in inventory().values() for s, names in dept.items() for a in names}


def catalog(engine: Any) -> Dict[str, Any]:
    """Every loaded agent with department, inventory status, summary and public methods."""
    status = _statuses()
    agents = []
    for name in sorted(engine.list_agents()):
        try:
            cls = engine.agent_class(name)
        except LookupError:
            cls = None
        methods = []
        for m, fn in (inspect.getmembers(cls, inspect.isfunction) if cls else []):
            if m.startswith("_"):
                continue
            sig = inspect.signature(fn)
            sig = sig.replace(parameters=list(sig.parameters.values())[1:])
            rule = rule_for(name, m)
            methods.append({"name": m, "signature": str(sig)[:500], "summary": _summary(fn),
                            "http": rule.kind if rule else None})
        agents.append({"name": name, "department": engine.router.departments.get(name),
                       "status": status.get(name, "unknown"), "summary": _summary(cls) if cls else "",
                       "methods": methods})
    return {"agents": agents, "failed": sorted(engine.router.failed)}
