"""Asking AetherOS Prime: approvals for flow steps, and (optionally) sensitive reads.

PrimeGate is a flow gate (velaris.intel.flow, "Approvals made elsewhere"). A step that needs
approval becomes one Prime request of type ACTION_TYPE, on behalf of the person the run is
for, with the run id, the step's call hash, tool and arguments as its params. Prime hashes
everything the approver is shown (request_hash); the approver quotes that hash in AetherOS.

Velaris then reads the answer from Prime itself (pull). The step runs only when the request
Prime returns is the one submitted (same id and request_hash), still names this run and
this call hash, is "approved", and Prime's own last check before execution succeeded
(execution.status "succeeded"). Rejected, expired, refused, or failed that last check:
the step is rejected. Anything else - pending, Prime unreachable, an unexpected answer -
and the step keeps waiting. Nothing here ever turns into an approval by default.

Why pull and not a callback carrying the approval: Prime stays the only source of the
answer, so there is no inbound "approved" message to forge or replay, a lost message only
delays, and rejection and expiry are seen the same way as approval. Prime's executor for
ACTION_TYPE only nudges Velaris to look (GET /flows/{run_id}); the nudge carries no authority.

PrimeReadAuthoriser has the signature of velaris.core.access.decide and replaces it when
VELARIS_READ_AUTHORISER=prime. It answers False whenever Prime is down, slow or unclear.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional, Tuple

import httpx

from velaris.core import access
from velaris.core.access import Caller

logger = logging.getLogger("velaris.prime")

ACTION_TYPE = "velaris.flow.call"
EXECUTOR = "velaris.flow"
# Prime answered and said no, for good: waiting longer would not change it. Any other
# failure (401 misconfigured key, 5xx, network) means "ask again later".
_REFUSED = {400, 403, 404, 409, 422}


class PrimeError(RuntimeError):
    """Prime's answer could not be used. The step waits."""


def _client(base_url: str, api_key: str, timeout: float, transport: Optional[httpx.BaseTransport]) -> httpx.Client:
    if not base_url or not api_key:
        raise ValueError("Prime needs a base URL and an API key")
    return httpx.Client(base_url=base_url.rstrip("/"), headers={"Authorization": f"Bearer {api_key}"},
                        timeout=timeout, transport=transport)


def _json(resp: httpx.Response) -> Dict[str, Any]:
    if not 200 <= resp.status_code < 300:
        raise PrimeError(f"Prime answered HTTP {resp.status_code}")
    try:
        body = resp.json()
    except ValueError as e:
        raise PrimeError("Prime's answer was not JSON") from e
    if not isinstance(body, dict):
        raise PrimeError("Prime's answer was not an object")
    return body


class PrimeGate:
    def __init__(self, base_url: str, api_key: str, *, timeout: float = 10.0,
                 transport: Optional[httpx.BaseTransport] = None) -> None:
        self._http = _client(base_url, api_key, timeout, transport)

    def submit(self, run_id: str, pending: Dict[str, Any], meta: Dict[str, Any]) -> Dict[str, Any]:
        who = (meta.get("caller") or {}).get("id")
        if not who:
            raise PrimeError("the run names no person to ask Prime on behalf of")
        call_hash = pending["call_hash"]
        resp = self._http.post("/prime/requests", json={
            "type": ACTION_TYPE, "executor": EXECUTOR, "on_behalf_of": who,
            "params": {"run_id": run_id, "call_hash": call_hash, "tool": pending["tool"],
                       "args": pending["args"], "reason": pending["reason"]}})
        if resp.status_code in _REFUSED:
            return self._final(run_id, call_hash, "rejected", f"Prime refused the request (HTTP {resp.status_code})")
        body = _json(resp)
        view = body.get("request")
        if view is None:      # REFUSE or RECOMMEND_ONLY: nothing will ever be approved
            return self._final(run_id, call_hash, "rejected",
                               f"Prime: {body.get('outcome')}: {str(body.get('reason') or '')[:300]}")
        return self._record(view, run_id, call_hash)

    def check(self, record: Dict[str, Any]) -> Dict[str, Any]:
        request_id = record.get("prime_request_id")
        if not request_id or record.get("state") != "pending":
            raise PrimeError("nothing to ask Prime about")
        view = _json(self._http.get(f"/prime/service/requests/{request_id}"))
        if view.get("id") != request_id or view.get("request_hash") != record.get("request_hash"):
            raise PrimeError("the request in Prime is not the one that was submitted")
        return self._record(view, record["run_id"], record["call_hash"])

    @staticmethod
    def _final(run_id: str, call_hash: str, state: str, note: str) -> Dict[str, Any]:
        return {"prime_request_id": None, "request_hash": None, "run_id": run_id, "call_hash": call_hash,
                "state": state, "prime_state": None, "decided_by": "prime", "note": note}

    @staticmethod
    def _record(view: Dict[str, Any], run_id: str, call_hash: str) -> Dict[str, Any]:
        """Prime's request view -> a gate record. Raises if it is not about this exact call."""
        action = view.get("action") if isinstance(view.get("action"), dict) else {}
        params = action.get("params") if isinstance(action.get("params"), dict) else {}
        if (action.get("type") != ACTION_TYPE or view.get("executor") != EXECUTOR or not view.get("id")
                or params.get("run_id") != run_id or params.get("call_hash") != call_hash
                or not isinstance(view.get("request_hash"), str) or len(view["request_hash"]) != 64):
            raise PrimeError("Prime's request does not match the waiting call")
        prime_state = view.get("state")
        execution = view.get("execution") if isinstance(view.get("execution"), dict) else {}
        note = str(view.get("decision_reason") or "")
        if prime_state == "approved" and execution.get("status") == "succeeded":
            state = "approved"
        elif prime_state == "approved" and execution.get("status") == "failed":
            state, note = "rejected", f"approved, but Prime's check before running refused it: " \
                                      f"{str((execution.get('result') or {}).get('error') or '')[:300]}"
        elif prime_state in ("rejected", "expired"):
            state = "rejected"
            note = note or ("nobody decided before the request expired" if prime_state == "expired" else "")
        else:                 # pending, or approved and Prime has not finished its own last check
            state = "pending"
        return {"prime_request_id": view["id"], "request_hash": view["request_hash"], "run_id": run_id,
                "call_hash": call_hash, "state": state, "prime_state": prime_state,
                "decided_by": view.get("decided_by") or "prime", "note": note[:500]}


class PrimeReadAuthoriser:
    """access.decide() answered by Prime: POST /prime/service/authorize-read. Fails closed."""

    def __init__(self, base_url: str, api_key: str, *, timeout: float = 5.0,
                 transport: Optional[httpx.BaseTransport] = None) -> None:
        self._http = _client(base_url, api_key, timeout, transport)

    def __call__(self, caller: Optional[Caller], category: str, subject_id: Optional[str],
                 org: Optional[str] = None) -> Tuple[bool, str]:
        if not isinstance(caller, Caller):
            return False, "no caller identity"
        try:
            body = _json(self._http.post("/prime/service/authorize-read", json={
                "caller": {"id": caller.id, "org": caller.org, "roles": sorted(caller.roles),
                           "employee_id": caller.employee_id},
                "category": category, "subject_id": subject_id, "org": org}))
        except (httpx.HTTPError, PrimeError) as e:
            logger.warning("read authorisation could not be asked of Prime: %s", type(e).__name__)
            return False, "the authorisation service could not be asked"
        reason = str(body.get("reason") or "")[:200]
        if body.get("allowed") is not True:
            return False, reason or "refused by the authorisation service"
        return True, reason or "allowed by the authorisation service"


def prime_configured(env: Optional[Dict[str, str]] = None) -> bool:
    """True when this deployment is connected to AetherOS Prime (both settings present): Prime is then the only place where
    grants are made and allow-decisions come from. A half-set pair is not configured (gate_from_env refuses it loudly)."""
    env = os.environ if env is None else env
    return bool(env.get("VELARIS_PRIME_URL") and env.get("VELARIS_PRIME_API_KEY"))


def gate_from_env(env: Optional[Dict[str, str]] = None) -> Optional[PrimeGate]:
    """PrimeGate when VELARIS_PRIME_URL and VELARIS_PRIME_API_KEY are set; None (local decisions) otherwise."""
    env = os.environ if env is None else env
    url, key = env.get("VELARIS_PRIME_URL", ""), env.get("VELARIS_PRIME_API_KEY", "")
    if bool(url) != bool(key):
        raise ValueError("set both VELARIS_PRIME_URL and VELARIS_PRIME_API_KEY, or neither")
    return PrimeGate(url, key) if url else None


def install_read_authoriser(env: Optional[Dict[str, str]] = None) -> str:
    """Apply VELARIS_READ_AUTHORISER: "local" (default, velaris.core.access rules) or "prime"."""
    env = os.environ if env is None else env
    choice = env.get("VELARIS_READ_AUTHORISER", "local") or "local"
    if choice == "prime":
        access.decide = PrimeReadAuthoriser(env.get("VELARIS_PRIME_URL", ""), env.get("VELARIS_PRIME_API_KEY", ""))
    elif choice != "local":
        raise ValueError(f"VELARIS_READ_AUTHORISER must be 'local' or 'prime', not {choice!r}")
    return choice
