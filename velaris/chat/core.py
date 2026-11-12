"""Shared plumbing for the chat service: who is asking, the policy check, the trace, and the
rule that makes delivery race-free (every commit emits its events while still holding the lock
that register() takes)."""
from __future__ import annotations

import contextlib
import hashlib
import logging
import re
import sqlite3
import time
from typing import Any, Callable, Dict, Iterable, Iterator, List, Optional

from velaris.chat.errors import ChatError
from velaris.chat.events import Hub
from velaris.chat.policy import CHAT_ADMIN, Decision, Limits, TokenBucket, decide, is_assistant, valid_assistant_id, valid_user_id
from velaris.chat.store import Store
from velaris.core import access
from velaris.core.access import Caller
from velaris.intel import trace

logger = logging.getLogger("velaris.chat")
_LOCAL_ID = re.compile(r"[A-Za-z0-9_.:\-]{1,64}\Z")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_TOUCH_EVERY_S = 60.0
ADMIN_SEEN_MAX_S = 7 * 86400.0      # a chat_admin counts as one only if their last verified request carried the role this recently


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class ChatCore:
    def __init__(self, store: Optional[Store] = None, *, limits: Optional[Limits] = None,
                 clock: Callable[[], float] = time.time, assistants: Iterable[str] = ("assistant:velaris",),
                 hub: Optional[Hub] = None, bucket: Optional[TokenBucket] = None) -> None:
        self.store = store or Store()
        self.limits = limits or Limits()
        self.clock = clock
        self.hub = hub or Hub(ttl=self.limits.queue_ttl_s, max_events=self.limits.queue_max_events)
        self.bucket = bucket or TokenBucket(self.limits.rate_capacity, self.limits.rate_per_second)
        self.assistants = frozenset(a for a in assistants if valid_assistant_id(a))
        self._after: List[Callable[[], None]] = []

    # ── writes: one transaction, then events, all under the lock register() also takes ──
    @contextlib.contextmanager
    def _write(self) -> Iterator[sqlite3.Connection]:
        with self.store.lock:
            self._after = []
            with self.store.tx() as db:
                yield db
            after, self._after = self._after, []
            for fn in after:
                fn()

    def _notify(self, users: Iterable[str], event: Dict[str, Any], org: str) -> None:
        recipients = list(users)
        self._after.append(lambda: self.hub.emit(recipients, event, org=org))

    def _members_of(self, channel_id: int) -> List[str]:
        return self.store.member_ids(channel_id)

    # ── who is asking ─────────────────────────────────────────────────────────
    def _enter(self, caller: Any) -> Caller:
        """The Caller is the only identity there is. Refuses anything else, another organisation,
        and an id that could be mistaken for an assistant."""
        if not isinstance(caller, Caller):
            raise ChatError(401, "unauthenticated", "no authenticated caller")
        if access.org_denied(caller):
            self._audit("denied", caller.id, caller.org, step="enter", reason="organisation")
            raise ChatError(403, "wrong_organisation", "this deployment does not serve the caller's organisation")
        if not valid_user_id(caller.id):
            self._audit("denied", caller.id[:64], caller.org, step="enter", reason="user_id")
            raise ChatError(403, "bad_identity", "this user id cannot use chat")
        row = self.store.one("SELECT org, last_seen FROM users WHERE id=?", (caller.id,))
        now = self.clock()
        if row is not None and row["org"] != caller.org:
            self._audit("denied", caller.id, caller.org, step="enter", reason="user_org")
            raise ChatError(403, "wrong_organisation", "this user belongs to another organisation")
        if row is None or now - row["last_seen"] > _TOUCH_EVERY_S:
            with self.store.tx() as db:
                self._ensure_user(db, caller.id, caller.org)
        self._track_admin(caller, now)              # only after every identity and organisation check has passed
        return caller

    def _track_admin(self, caller: Caller, now: float) -> None:
        """Candidate list of chat_admins: id -> time of their last verified request that carried the role. A registered
        id whose request lacks the role is removed on that request, so the list never outlives a revoked role."""
        has = CHAT_ADMIN in caller.roles
        with self.store.lock:
            seen = self.store.setting(caller.org, "chat_admin_seen", {})
            if (has and now - seen.get(caller.id, -_TOUCH_EVERY_S * 2) <= _TOUCH_EVERY_S) or (not has and caller.id not in seen):
                return
            seen = {k: v for k, v in seen.items() if k != caller.id}
            if has:
                seen[caller.id] = now
            with self.store.tx() as db:
                self.store.set_setting(db, caller.org, "chat_admin_seen", seen)

    def chat_admins(self, org: str) -> List[str]:
        """Chat admins still in good standing: their last verified request carried the role, recently enough."""
        now = self.clock()
        return [u for u, t in self.store.setting(org, "chat_admin_seen", {}).items() if 0 <= now - t <= ADMIN_SEEN_MAX_S]

    def _ensure_user(self, db: sqlite3.Connection, user_id: str, org: str) -> None:
        """Record a person (or a registered assistant) the first time they are seen or invited."""
        now = self.clock()
        row = db.execute("SELECT org FROM users WHERE id=?", (user_id,)).fetchone()
        if row is not None and row["org"] != org:
            raise ChatError(403, "wrong_organisation", "that user belongs to another organisation")
        db.execute("INSERT INTO users(id, org, first_seen, last_seen) VALUES(?,?,?,?) "
                   "ON CONFLICT(id) DO UPDATE SET last_seen=excluded.last_seen", (user_id, org, now, now))

    def _check_target(self, db: sqlite3.Connection, user_id: Any, org: str) -> str:
        """A person or registered assistant that may be put in a channel."""
        if is_assistant(user_id):
            if user_id not in self.assistants:
                raise ChatError(400, "unknown_assistant", "no such assistant is set up")
        elif not valid_user_id(user_id):
            raise ChatError(400, "bad_user", "that is not a valid user id")
        self._ensure_user(db, user_id, org)
        return user_id

    # ── trace: ids and hashes only ────────────────────────────────────────────
    def _audit(self, action: str, caller_id: str, org: str, **fields: Any) -> None:
        try:
            trace.append("chat", action, {"caller": caller_id, "org": org, **fields})
        except (OSError, ValueError, TypeError) as e:
            logger.warning("chat trace write failed for %s: %s", action, type(e).__name__)
            raise ChatError(503, "audit_unavailable", "the action could not be recorded, so it was not done") from None

    def _denied(self, caller: Caller, action: str, reason: str, channel_id: Optional[int] = None) -> None:
        try:
            trace.append("chat", "denied", {"caller": caller.id, "org": caller.org, "action": action,
                                            "reason": reason, "channel": channel_id})
        except (OSError, ValueError, TypeError) as e:       # still refused; the refusal does not depend on the trace
            logger.warning("chat denial could not be traced: %s", type(e).__name__)

    # ── lookups with the policy applied ───────────────────────────────────────
    def _channel(self, caller: Caller, channel_id: Any) -> sqlite3.Row:
        row = self.store.channel(caller.org, channel_id) if isinstance(channel_id, int) and not isinstance(channel_id, bool) else None
        if row is None:
            raise ChatError(404, "no_such_channel", "no such channel")
        return row

    def _require(self, caller: Caller, ch: sqlite3.Row, action: str, **facts: Any) -> Optional[str]:
        """Apply policy.decide() for `caller` in `ch`; returns the caller's role or raises."""
        role = self.store.role(ch["id"], caller.id)
        d: Decision = decide(action=action, kind=ch["kind"], role=role, caller_org=caller.org, record_org=ch["org"],
                             deployment_org=access.deployment_org(), archived=bool(ch["archived"]),
                             legal_hold=bool(ch["legal_hold"]), **facts)
        if d is not None and d.allowed is True:
            return role
        reason = d.reason if isinstance(d, Decision) else "no decision"
        self._denied(caller, action, reason, ch["id"])
        if role is None and ch["kind"] != "public":
            raise ChatError(404, "no_such_channel", "no such channel")        # do not reveal that it exists
        raise ChatError(403, "forbidden", f"not allowed: {reason}")

    def _spend(self, who: Caller, cost: float = 1.0) -> None:
        if not self.bucket.allow(who.id, cost):
            self._denied(who, "rate", "rate limit")
            raise ChatError(429, "rate_limited", "slow down: too many actions in a short time")

    # ── input checks ──────────────────────────────────────────────────────────
    def _text(self, value: Any, *, what: str, limit: int, empty_ok: bool = False) -> str:
        if not isinstance(value, str) or (not empty_ok and not value.strip()):
            raise ChatError(400, "bad_" + what, f"{what} must be a non-empty string")
        if len(value) > limit:
            raise ChatError(413, what + "_too_long", f"{what} may be at most {limit} characters")
        if _CONTROL.search(value):
            raise ChatError(400, "bad_" + what, f"{what} contains control characters")
        return value

    def _topic(self, ch: sqlite3.Row, topic: Any) -> str:
        if ch["kind"] in ("direct", "group"):
            return ""
        return " ".join(self._text("general" if topic is None else topic, what="topic", limit=self.limits.max_topic).split())

    def _local_id(self, local_id: Any) -> Optional[str]:
        if local_id is None:
            return None
        if not isinstance(local_id, str) or not _LOCAL_ID.match(local_id):
            raise ChatError(400, "bad_local_id", "local_id must be 1-64 letters, digits or _ . : -")
        return local_id
