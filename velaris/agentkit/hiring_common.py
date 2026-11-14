"""Shared plumbing for the hiring agents (ATS_CORE, RESUME_EVIDENCE, JOB_POSTINGS, SCREENING_FORMS,
INTERVIEW_SCHEDULER, INTERVIEW_KIT, INTERVIEW_RECORD).

What every one of them does the same way:

  identity     comes from the Caller (velaris.core.access), never from an argument. Roles are plain
               strings checked here; `recruiter`, `hiring_manager` and `interviewer` need no registry
               in velaris.core.access because check_caller()/the API allowlist only compare names.
  org          every stored record carries `org`; every read filters on the caller's organisation.
               The deployment organisation (VELARIS_ORG) is enforced by access.org_denied().
  fail closed  no caller, wrong organisation, missing role, an unwritable audit trace: refused, nothing stored.
  audit        velaris.intel.trace gets hashes and opaque ids only. Personal data never enters the
               hash-chained ledger, so erasing a person never has to rewrite it.
  erasure      each hiring module that keeps data about a candidate exposes export_candidate(org, id) and
               purge_candidate(org, id); ATS_CORE calls them all through PERSON_MODULES.

Nothing here, or in the agents built on it, ranks, scores for hire, rejects or hires anyone. Those are
human decisions taken by a named person through an approved step.
"""
from __future__ import annotations

import functools
import hashlib
import importlib
import inspect
import json
import logging
import secrets
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, FrozenSet, Iterable, List, Optional, Tuple

from velaris.agentkit.results import fail
from velaris.agentkit.state import JsonState
from velaris.core.access import AccessDenied, Caller, check_caller, current_caller, org_denied
from velaris.intel import trace

logger = logging.getLogger("velaris.hiring")

RECRUITER, HIRING_MANAGER, INTERVIEWER, HR_ADMIN = "recruiter", "hiring_manager", "interviewer", "hr_admin"
RECRUITING: FrozenSet[str] = frozenset({RECRUITER, HR_ADMIN})
DECIDERS: FrozenSet[str] = frozenset({HIRING_MANAGER, HR_ADMIN})
HIRING: FrozenSet[str] = frozenset({RECRUITER, HIRING_MANAGER, HR_ADMIN})
PANEL: FrozenSet[str] = frozenset({RECRUITER, HIRING_MANAGER, INTERVIEWER, HR_ADMIN})

PERSON_MODULES = ("velaris.agentkit.hiring_resume", "velaris.agentkit.hiring_forms", "velaris.agentkit.hiring_sched",
                  "velaris.agentkit.hiring_kit", "velaris.agentkit.hiring_record")

NO_JUDGEMENT = ("This output is evidence and bookkeeping for a person. It makes no hire or reject decision, "
                "no ranking and no score of a person; no automated judgement of a person is made.")
DAY = 86400.0


class HiringError(Exception):
    """A refusal with a status and a reason; the method decorators turn it into a result dict."""

    def __init__(self, status: str, reason: str) -> None:
        super().__init__(reason)
        self.status, self.reason = status, reason


def bad(reason: str) -> HiringError:
    return HiringError("invalid_input", reason)


def now() -> float:
    """Wall clock. A module function so tests can move time."""
    return time.time()


def iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def digest(obj: Any) -> str:
    return sha(json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str))


def hid(org: str, ident: Any) -> str:
    """Opaque, org-scoped hash of an id for the ledger."""
    return sha(f"{org}|{ident}")[:32]


def new_id(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(6)}"


def store(agent: str, filename: str, default: Dict[str, Any]) -> JsonState:
    return JsonState(agent, filename, default, encrypted=f"hiring:{agent}")


def audit(agent: str, action: str, org: str, caller: Optional[Caller] = None, **hashes: Any) -> None:
    """Append hashes and opaque ids to the ledger. Raises HiringError('audit_failed') so the change is not made."""
    payload = {"org": org, **{k: (v if isinstance(v, (int, float, bool)) or v is None else str(v)) for k, v in hashes.items()}}
    if caller is not None:
        payload["by"] = hid(org, caller.id)
    try:
        trace.append(agent, action, payload)
    except (OSError, ValueError, TypeError) as e:
        logger.warning("%s: audit trace not written (%s)", agent, type(e).__name__)
        raise HiringError("audit_failed", f"the decision could not be recorded: {type(e).__name__}") from e


def _read_gate(roles: FrozenSet[str]) -> Caller:
    who = current_caller()
    if not isinstance(who, Caller):
        raise HiringError("unauthenticated", "no authenticated caller")
    if (why := org_denied(who)):
        raise HiringError("denied", why)
    if not who.roles & (roles | {HR_ADMIN}):
        raise HiringError("denied", f"needs one of the roles {sorted(roles | {HR_ADMIN})}")
    return who


def _without_caller(fn: Callable[..., Any]) -> inspect.Signature:
    sig = inspect.signature(fn)
    return sig.replace(parameters=[p for n, p in sig.parameters.items() if n != "caller"])


def reads(agent: str, roles: FrozenSet[str]) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """A read method: `fn(self, caller, ...)`. Role + organisation checked, no state change. Sensitive data is
    fetched inside with access.authorize_read() as well."""
    def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(fn)
        def wrapper(self: Any, *a: Any, **kw: Any) -> Dict[str, Any]:
            try:
                return fn(self, _read_gate(roles), *a, **kw)
            except HiringError as e:
                return fail(e.status, e.reason)
            except AccessDenied as e:
                return fail("denied", e.reason)
            except (OSError, ValueError) as e:
                logger.warning("%s.%s failed: %s", agent, fn.__name__, e)
                return fail("error", f"{type(e).__name__}")
        wrapper.__signature__ = _without_caller(fn)  # type: ignore[attr-defined]
        wrapper.hiring_kind, wrapper.hiring_roles = "read", roles | {HR_ADMIN}  # type: ignore[attr-defined]
        return wrapper
    return deco


def acts(agent: str, roles: FrozenSet[str]) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """A state-changing method: `fn(self, caller, ...)`. access.check_caller() decides and traces (fail closed);
    the API allowlist declares the same method `act`, so it also waits for approval."""
    def deco(fn: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(fn)
        def wrapper(self: Any, *a: Any, **kw: Any) -> Dict[str, Any]:
            who, refusal = check_caller(agent, fn.__name__, {}, roles=roles | {HR_ADMIN})
            if refusal:
                return refusal
            try:
                return fn(self, who, *a, **kw)
            except HiringError as e:
                return fail(e.status, e.reason)
            except AccessDenied as e:
                return fail("denied", e.reason)
            except (OSError, ValueError) as e:
                logger.warning("%s.%s failed: %s", agent, fn.__name__, e)
                return fail("error", f"{type(e).__name__}")
        wrapper.__signature__ = _without_caller(fn)  # type: ignore[attr-defined]
        wrapper.hiring_kind, wrapper.hiring_roles = "act", roles | {HR_ADMIN}  # type: ignore[attr-defined]
        return wrapper
    return deco


def mine(records: Iterable[Dict[str, Any]], org: str) -> List[Dict[str, Any]]:
    return [r for r in records if r.get("org") == org]


def need_text(value: Any, name: str, max_len: int = 500) -> str:
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > max_len:
        raise bad(f"{name} must be non-empty text of at most {max_len} characters")
    return value.strip()


def parse_date(value: Any, name: str) -> float:
    """An ISO date (YYYY-MM-DD) or datetime as a UTC epoch."""
    try:
        d = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError as e:
        raise bad(f"{name} must be an ISO date like 2027-03-31") from e
    return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).timestamp()


def load_requisition(org: str, req_id: str) -> Optional[Dict[str, Any]]:
    """A requisition of this organisation from ATS_CORE's store (read-only helper for sibling agents)."""
    rec = store("ATS_CORE", "evaluation.json", {}).load().get("requisitions", {}).get(str(req_id))
    return rec if rec and rec.get("org") == org else None


def candidate_known(org: str, candidate_id: str) -> bool:
    rec = store("ATS_CORE", "evaluation.json", {}).load().get("candidates", {}).get(str(candidate_id))
    return bool(rec and rec.get("org") == org and not rec.get("erased_at"))


def application_known(org: str, application_id: str) -> Optional[Dict[str, Any]]:
    rec = store("ATS_CORE", "evaluation.json", {}).load().get("applications", {}).get(str(application_id))
    return rec if rec and rec.get("org") == org else None


def person_modules() -> List[Any]:
    return [importlib.import_module(m) for m in PERSON_MODULES]


def check_keys_clean(obj: Any, forbidden: Tuple[str, ...]) -> List[str]:
    """Every dict key (recursively) that contains a forbidden word; used by the tests."""
    found: List[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if any(w in str(k).lower() for w in forbidden):
                found.append(str(k))
            found += check_keys_clean(v, forbidden)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            found += check_keys_clean(v, forbidden)
    return found

