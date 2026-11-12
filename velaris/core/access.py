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
exception and every agent stay as they are. Nothing of that service is built here.

Limits: roles are organisation-wide ("hr_admin" may read every employee of the
organisation; there is no "manager of these five people" because there is no reporting
line data here), and a Caller is only as true as the entry point that built it: this
module checks permissions, it does not authenticate anyone.
"""
from __future__ import annotations

import contextlib
import contextvars
from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, Iterator, Optional, Tuple

from velaris.core.exceptions import VelarisError
from velaris.intel import trace

# Sensitive data category -> roles that may read records that are not the caller's own.
READ_OTHERS: Dict[str, FrozenSet[str]] = {
    "pay": frozenset({"payroll_admin", "hr_admin"}),          # salary, payslips, deductions, cost to company
    "bank": frozenset({"payroll_admin"}),                     # account numbers, IFSC
    "identity": frozenset({"hr_admin"}),                      # PAN, Aadhaar, passport, full employee records
    "health": frozenset({"hr_admin"}),                        # medical details, sick and maternity leave
}


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
    token = _current.set(caller)
    try:
        yield caller
    finally:
        _current.reset(token)


def decide(caller: Optional[Caller], category: str, subject_id: Optional[str],
           org: Optional[str] = None) -> Tuple[bool, str]:
    """(allowed, reason) for reading `category` data about employee `subject_id`.

    `subject_id` None means "about many or all employees". `org` is the organisation the data
    belongs to; None means the deployment serves a single organisation and nothing is compared.
    This is the function a deployment replaces to use its own authorisation service.
    """
    if not isinstance(caller, Caller):
        return False, "no caller identity"
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
    known = isinstance(who, Caller)
    trace.append("access", "sensitive_read.granted" if allowed is True else "sensitive_read.denied", {
        "agent": agent, "category": category, "subject": subject, "data_org": org or None,
        "caller": who.id if known else None, "caller_org": who.org if known else None,
        "roles": sorted(who.roles) if known else [], "reason": str(reason)[:200]})
    if allowed is not True:              # anything but an explicit True from decide() is a denial
        raise AccessDenied(str(reason)[:200])
    return who                           # type: ignore[return-value]  (decide() allowed it, so it is a Caller)

