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
from velaris.core.access import Caller, AccessDenied, READ_OTHERS, acting_as, authorize_read, check_caller

READ, ACT = "read", "act"
_NEVER_PARAMS = {"self", "caller"}


@dataclass(frozen=True)
class Rule:
    kind: str
    scope: Optional[str] = None
    actor: Optional[str] = None
    own: Optional[Tuple[str, str]] = None
    roles: Optional[FrozenSet[str]] = None


_HR = READ_OTHERS["identity"]           # who may act on another employee's HR records

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
    "LONGTERM_MEMORY": {"recall": Rule(READ, scope="scope"), "remember": Rule(ACT, scope="scope")},
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
