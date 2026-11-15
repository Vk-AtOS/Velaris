"""Who is asking, and may they read this.

Agents that return pay, bank, identity-number or health data call authorize_read()
before they fetch anything. The answer is worked out by code from three facts, and
no model output takes part in it:

  who is asking     a Caller (id, organisation, roles, and the employee record that is
                    theirs, if any). It is passed to the agent explicitly (`caller=`),
                    or set once at the entry point with `acting_as(caller)` and carried
                    to every agent called underneath (BackendEngine.run does this).
  what is asked     a data category from READ_OTHERS and the employee it is about.
  the rule          deny unless: the record is the caller's own, or the caller holds a
                    role that READ_OTHERS lists for that category. No caller, an unknown
                    category, or another organisation's data is always a denial.

Every decision on sensitive data, granted or denied, is appended to the hash-chained
trace (velaris.intel.trace) before the agent goes on. If the trace cannot be written
the read does not happen.

Plugging in another system's authorisation service
--------------------------------------------------
`decide()` is the one function to replace. authorize_read() looks it up on this module
each time, so a deployment that has its own policy service (the platform's governance
service, an OPA server, the HR system's own roles) assigns a function with the same
signature at start-up:

    from velaris.core import access
    access.decide = ask_policy_service     # (caller, category, subject_id, org) -> (allowed, reason)

The replacement must return (False, reason) when the service is down, slow or unsure;
it must never raise its way to an answer or default to True. Callers, tracing, the
exception and every agent stay as they are. velaris.core.prime.PrimeReadAuthoriser is one
such replacement (AetherOS Prime), installed only when VELARIS_READ_AUTHORISER=prime.

Changes and approvals
---------------------
Agents that grant, approve, enrol or change policy never take the acting person as an
argument. check_caller() reads the current Caller, refuses when there is none ("unauthenticated"),
when a legacy identity argument names someone else, or when the change needs a role the caller
does not hold (GOVERNANCE_ADMINS, SECURITY_ADMINS), and traces the decision either way. It
returns a refusal dict instead of raising, so agents can pass it straight back.

Limits: roles are organisation-wide ("hr_admin" may read every employee of the
organisation; there is no "manager of these five people" because there is no reporting
line data here), and a Caller is only as true as the entry point that built it: this
module checks permissions, it does not authenticate anyone.
"""
from __future__ import annotations

import contextlib
import contextvars
import os
from dataclasses import dataclass
from fnmatch import fnmatchcase
from typing import Any, Dict, FrozenSet, Iterator, Optional, Tuple

from velaris.core.exceptions import VelarisError
from velaris.intel import policy, trace

# Sensitive data category -> roles that may read records that are not the caller's own.
READ_OTHERS: Dict[str, FrozenSet[str]] = {
    "pay": frozenset({"payroll_admin", "hr_admin"}),          # salary, payslips, deductions, cost to company
    "bank": frozenset({"payroll_admin"}),                     # account numbers, IFSC
    "identity": frozenset({"hr_admin"}),                      # PAN, Aadhaar, passport, full employee records
    "health": frozenset({"hr_admin"}),                        # medical details, sick and maternity leave
    "candidate": frozenset({"hr_admin", "recruiter"}),        # a job candidate's contact details and full data export (not an employee)
}

# Roles that may make privileged changes. Defined here only; agents import these names.
GOVERNANCE_ADMIN = "governance_admin"     # PRIME grants, approvers, exemptions, policies, mandates, memory imports
SECURITY_ADMIN = "security_admin"         # zero-trust enrolment and policy, identity tokens for others
ATLASSIAN_READER = "atlassian_reader"     # read Jira/Confluence through the deployment's one service account
GOVERNANCE_ADMINS: FrozenSet[str] = frozenset({GOVERNANCE_ADMIN})
ATLASSIAN_READERS: FrozenSet[str] = frozenset({ATLASSIAN_READER, GOVERNANCE_ADMIN})   # admins hold it implicitly
SECURITY_ADMINS: FrozenSet[str] = frozenset({SECURITY_ADMIN})


class AccessDenied(VelarisError, PermissionError):
    """The caller may not read this. `reason` is short and safe to show."""

    def __init__(self, reason: str) -> None:
        super().__init__(f"access denied: {reason}")
        self.reason = reason


@dataclass(frozen=True)
class Caller:
    id: str                                    # stable id of the person or service that is asking
    org: str                                   # the organisation they belong to
    roles: FrozenSet[str] = frozenset()
    employee_id: Optional[str] = None          # the employee record that is their own, if they have one

    def __post_init__(self) -> None:
        if not (isinstance(self.id, str) and self.id.strip() and isinstance(self.org, str) and self.org.strip()):
            raise ValueError("a Caller needs a non-empty id and org")
        if isinstance(self.roles, str):
            raise ValueError("roles must be a collection of role names, not one string")
        object.__setattr__(self, "roles", frozenset(str(r) for r in self.roles))
        if self.employee_id is not None:
            object.__setattr__(self, "employee_id", str(self.employee_id))


_current: contextvars.ContextVar[Optional[Caller]] = contextvars.ContextVar("velaris_caller", default=None)


def current_caller() -> Optional[Caller]:
    return _current.get()


@contextlib.contextmanager
def acting_as(caller: Optional[Caller]) -> Iterator[Optional[Caller]]:
    """Everything called inside the block is done on behalf of `caller`.

    Passing None is meaningful: the block runs with no caller, whatever was set outside it,
    so one request can never borrow the identity of another.
    """
    if caller is not None and not isinstance(caller, Caller):
        raise TypeError("acting_as() takes a Caller or None")
    token, scope = _current.set(caller), policy.new_scope()
    try:
        yield caller
    finally:
        policy.end_scope(scope)
        _current.reset(token)


def deployment_org() -> Optional[str]:
    """The one organisation this deployment belongs to (VELARIS_ORG), or None when unset (offline/dev)."""
    return os.environ.get("VELARIS_ORG", "").strip() or None


def org_denied(caller: Optional[Caller]) -> Optional[str]:
    """Why `caller` may not use this deployment, or None. Always None while VELARIS_ORG is unset."""
    dep = deployment_org()
    if dep is None:
        return None
    if not isinstance(caller, Caller):
        return "no caller identity"
    return None if caller.org == dep else "caller belongs to another organisation than this deployment"


def decide(caller: Optional[Caller], category: str, subject_id: Optional[str],
           org: Optional[str] = None) -> Tuple[bool, str]:
    """(allowed, reason) for reading `category` data about employee `subject_id`.

    `subject_id` None means "about many or all employees". `org` is the organisation the data
    belongs to; None means the deployment serves a single organisation and nothing is compared.
    This is the function a deployment replaces to use its own authorisation service.
    """
    if not isinstance(caller, Caller):
        return False, "no caller identity"
    if (why := org_denied(caller)):
        return False, why
    allowed_roles = READ_OTHERS.get(category)
    if allowed_roles is None:
        return False, f"unknown data category '{category}'"
    if org is not None and caller.org != org:
        return False, "data belongs to another organisation"
    if subject_id is not None and caller.employee_id is not None and caller.employee_id == str(subject_id):
        return True, "own record"
    held = sorted(caller.roles & allowed_roles)
    if held:
        return True, f"role {held[0]}"
    return False, "not the caller's own record and no role that may read other people's"


def authorize_read(category: str, subject_id: Optional[Any], *, agent: str,
                   caller: Optional[Caller] = None, org: Optional[str] = None) -> Caller:
    """Allow or refuse one read of sensitive data, and record the decision either way.

    `caller` defaults to the one set by acting_as(). Returns the caller on success and raises
    AccessDenied otherwise. Call it before fetching the data, once per employee concerned.
    """
    who = caller if caller is not None else current_caller()
    subject = None if subject_id is None else str(subject_id)
    allowed, reason = decide(who, category, subject, org or None)
    if allowed is True and (why := org_denied(who)):      # also when decide() was replaced
        allowed, reason = False, why
    known = isinstance(who, Caller)
    trace.append("access", "sensitive_read.granted" if allowed is True else "sensitive_read.denied", {
        "agent": agent, "category": category, "subject": subject, "data_org": org or None,
        "caller": who.id if known else None, "caller_org": who.org if known else None,
        "roles": sorted(who.roles) if known else [], "reason": str(reason)[:200]})
    if allowed is not True:              # anything but an explicit True from decide() is a denial
        raise AccessDenied(str(reason)[:200])
    policy.force_restricted()            # pay, bank, identity, health and candidate data never reach a model below restricted
    return who                           # type: ignore[return-value]  (decide() allowed it, so it is a Caller)



def has_role(caller: Optional[Caller], roles: FrozenSet[str]) -> bool:
    return isinstance(caller, Caller) and bool(caller.roles & roles)


def check_caller(agent: str, change: str, details: Optional[Dict[str, Any]] = None, *,
                 roles: Optional[FrozenSet[str]] = None, also: Optional[str] = None,
                 claimed: Any = None) -> Tuple[Optional[Caller], Optional[Dict[str, Any]]]:
    """May the current caller make `change`? Returns (caller, None) or (None, refusal).

    roles     None: any authenticated caller; otherwise the caller must hold one of them,
              or be `also` (a recorded owner, or the subject acting for themselves).
    claimed   a legacy identity argument (by=, approver=, grantor=...). When given it must be
              the caller's own id: nobody acts in someone else's name.
    The decision is traced; if it cannot be, the change is refused ("audit_failed").
    """
    who = current_caller()
    if not isinstance(who, Caller):
        status, reason = "unauthenticated", "no authenticated caller; run this with acting_as(caller)"
    elif (why := org_denied(who)):
        status, reason = "denied", why
    elif claimed is not None and claimed != who.id:
        status, reason = "denied", f"{who.id} cannot act as {str(claimed)[:80]}"
    elif roles is not None and not who.roles & roles and not (also is not None and who.id == also):
        status, reason = "denied", f"{change} needs one of the roles {sorted(roles)}"
    else:
        status, reason = "ok", "allowed"
    try:
        trace.append("access", "change.granted" if status == "ok" else "change.denied", {
            "agent": agent, "change": change, "caller": who.id if isinstance(who, Caller) else None,
            "roles": sorted(who.roles) if isinstance(who, Caller) else [], "reason": reason,
            "details": details or {}})
    except (OSError, ValueError, TypeError) as e:
        return None, {"status": "audit_failed", "reason": f"the decision could not be recorded: {type(e).__name__}"}
    if status != "ok":
        return None, {"status": status, "reason": reason}
    return who, None


# ---- resources ---------------------------------------------------------------
# A resource is a "/"-separated name. Patterns match segment by segment: "*" and "?" never
# cross a "/", and only a final "**" segment matches any number (one or more) of segments.

def resource_error(resource: Any) -> Optional[str]:
    """Why `resource` is not a usable resource name, or None."""
    if not isinstance(resource, str) or not resource or len(resource) > 512:
        return "resource must be a non-empty string of at most 512 characters"
    if "\\" in resource or "\x00" in resource or ".." in resource:
        return "resource may not contain '..', a backslash or NUL"
    if any(not seg for seg in resource.split("/")):
        return "resource may not have empty segments"
    return None


def resource_matches(pattern: Any, resource: Any) -> bool:
    """Segment-aware match of a well-formed `resource` against `pattern`. Anything malformed is False."""
    if resource_error(resource) or not isinstance(pattern, str) or resource_error(pattern.replace("**", "x")):
        return False
    pat, res = pattern.split("/"), resource.split("/")
    if pat[-1] == "**":
        head = pat[:-1]
        if len(res) <= len(head):
            return False
        pat, res = head, res[:len(head)]
    return len(pat) == len(res) and all(fnmatchcase(r, p) for p, r in zip(pat, res))


# ---- memory scopes -----------------------------------------------------------

def may_write_scope(caller: Optional[Caller], scope: Any) -> bool:
    """A memory scope belongs to an organisation: "<org>" or "<org>:<anything>".

    Only a governance admin of that organisation may write to it in bulk (imports)."""
    return (has_role(caller, GOVERNANCE_ADMINS) and isinstance(scope, str)
            and (scope == caller.org or scope.startswith(caller.org + ":")))  # type: ignore[union-attr]
