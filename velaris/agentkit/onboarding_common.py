"""Plumbing shared by the onboarding and paperwork agents (OFFER_LETTERS, ESIGN, ONBOARDING_FLOW,
EMPLOYEE_RECORDS, POLICY_ACKS).

  Store            one owner-only JSON document per agent (velaris.agentkit.state.JsonState) holding named
                   collections of records. Every record is stamped with the organisation that owns it, and
                   every read filters on that organisation: a record of another organisation is "not found".
  reader / writer  who is asking. Identity comes from the current Caller (velaris.core.access), never from
                   an argument. writer() goes through check_caller(), which traces the decision.
  hashing helpers  sha256, canonical JSON, a keyed hash for values that must not be stored raw (IP addresses).

Models are not used anywhere in these agents: every decision is made by code.
"""
from __future__ import annotations

import copy
import hashlib
import hmac
import json
import secrets
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Tuple

from velaris.agentkit.results import fail
from velaris.agentkit.state import JsonState
from velaris.core.access import Caller, READ_OTHERS, check_caller, current_caller, org_denied
from velaris.intel.paths import agent_dir, data_dir, load_or_create_key, private_dir

HR_ADMINS: FrozenSet[str] = READ_OTHERS["identity"]       # the hr_admin role: the only HR role that exists

Refusal = Dict[str, Any]


def utcnow(config: Dict[str, Any]) -> datetime:
    """The current time, from config["clock"] (a callable returning an aware datetime) when injected (tests)."""
    clock: Optional[Callable[[], datetime]] = config.get("clock")
    now = clock() if clock else datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("clock() must return a timezone-aware datetime")
    return now.astimezone(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def parse_date(value: Any, name: str) -> date:
    """A YYYY-MM-DD date. Raises ValueError naming the field."""
    try:
        return date.fromisoformat(str(value))
    except ValueError as e:
        raise ValueError(f"{name} must be a YYYY-MM-DD date") from e


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=True).encode("utf-8")


def keyed_hash(key_name: str, value: str) -> str:
    """HMAC-SHA256 of `value` under a per-deployment key kept owner-only in the data directory.

    Used for IP addresses and user agents: a plain hash of an IPv4 address can be reversed by trying all
    four billion addresses, a keyed one cannot be reversed without the key file.
    """
    key = load_or_create_key(data_dir() / f"{key_name}.key", 32)
    return hmac.new(key, value.encode("utf-8"), hashlib.sha256).hexdigest()


def clean_text(value: Any, name: str, *, max_len: int = 200, required: bool = True) -> str:
    """A short single-line string without control characters. Raises ValueError naming the field."""
    if value is None and not required:
        return ""
    if not isinstance(value, str) or (required and not value.strip()):
        raise ValueError(f"{name} must be a non-empty string")
    text = value.strip()
    if len(text) > max_len or any(ord(c) < 32 for c in text):
        raise ValueError(f"{name} must be at most {max_len} characters without control characters")
    return text


def reader(agent: str) -> Tuple[Optional[Caller], Optional[Refusal]]:
    """The caller for a read that is not itself sensitive: authenticated and inside this deployment's organisation."""
    who = current_caller()
    if not isinstance(who, Caller):
        return None, fail("unauthenticated", "no authenticated caller; run this with acting_as(caller)")
    if (why := org_denied(who)):
        return None, fail("denied", why)
    return who, None


def writer(agent: str, change: str, details: Optional[Dict[str, Any]] = None, *,
           roles: Optional[FrozenSet[str]] = None, also: Optional[str] = None) -> Tuple[Optional[Caller], Optional[Refusal]]:
    """check_caller() for the current caller: (caller, None) or (None, refusal). Traced either way."""
    return check_caller(agent, change, details, roles=roles, also=also)


class Refused(Exception):
    """Raised inside Store.update() functions to refuse the change; `result` is returned to the agent's caller."""

    def __init__(self, result: Refusal) -> None:
        super().__init__(result.get("reason", ""))
        self.result = result


class Store:
    """Named collections of records, each stamped with its organisation, in one owner-only JSON file."""

    def __init__(self, agent: str, filename: str = "state.json") -> None:
        self.state = JsonState(agent, filename, {"records": {}}, encrypted=f"hr:{agent}")

    @property
    def lock(self) -> Any:
        return self.state.lock

    def load(self) -> Dict[str, Any]:
        return self.state.load()

    def _coll(self, data: Dict[str, Any], coll: str) -> Dict[str, Any]:
        return data.setdefault("records", {}).setdefault(coll, {})

    def get(self, coll: str, rec_id: Any, org: str) -> Optional[Dict[str, Any]]:
        """A copy of the record, or None when it does not exist or belongs to another organisation."""
        rec = self._coll(self.load(), coll).get(self.key(org, rec_id))
        return copy.deepcopy(rec) if rec is not None and rec.get("org") == org else None

    def all(self, coll: str, org: str) -> List[Dict[str, Any]]:
        return [copy.deepcopy(r) for r in self._coll(self.load(), coll).values() if r.get("org") == org]

    @staticmethod
    def key(org: str, rec_id: Any) -> str:
        """Records are keyed by organisation AND id: two organisations may both have an EMP-0001 or a policy "code_of_conduct"."""
        return f"{org}:{rec_id}"

    def put(self, coll: str, rec: Dict[str, Any]) -> None:
        """Insert or replace by (org, rec["id"]). The record must carry its org."""
        if not rec.get("id") or not rec.get("org"):
            raise ValueError("a record needs an id and an org")

        def _do(data: Dict[str, Any]) -> None:
            self._coll(data, coll)[self.key(rec["org"], rec["id"])] = rec

        self.state.update(_do)

    def update(self, coll: str, rec_id: str, org: str, fn: Callable[[Dict[str, Any]], Any]) -> Any:
        """Atomically load one record of `org`, let fn mutate it, save, and return what fn returned.

        fn refuses by raising Refused(result): nothing it changed is saved and the result is returned.
        """
        def _do(data: Dict[str, Any]) -> Any:
            bucket = self._coll(data, coll)
            rec = bucket.get(self.key(org, rec_id))
            if rec is None or rec.get("org") != org:
                return fail("not_found", f"no such {coll} record")
            work = copy.deepcopy(rec)
            try:
                out = fn(work)
            except Refused as r:
                return r.result
            work["org"] = org
            bucket[self.key(org, rec_id)] = work
            return out if out is not None else work

        return self.state.update(_do)

    def next_seq(self, org: str, name: str) -> int:
        def _do(data: Dict[str, Any]) -> int:
            seq = data.setdefault("seq", {}).setdefault(org, {})
            seq[name] = int(seq.get(name, 0)) + 1
            return seq[name]
        return self.state.update(_do)

    def files_dir(self, sub: str) -> Path:
        return private_dir(agent_dir(self.state.agent) / sub)


def new_id(prefix: str) -> str:
    return f"{prefix}-{secrets.token_hex(6)}"
