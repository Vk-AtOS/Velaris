"""Every chat access rule, in one place.

decide() is a pure function: the same facts always give the same answer, nothing is read from
a model, a clock or a database. It denies unless a rule below says yes.

Facts: the action, the channel kind, the caller's role in the channel (None = not a member),
whether the channel is archived or under legal hold, whether the caller wrote the message,
and the three organisations (caller, record, deployment) which must all agree.

  action \\ kind      public            private          direct / group
  view, react, post  member            member           member
  edit               author            author           author
  delete             author, owner/admin (never under legal hold)
                                                        author (never under hold)
  invite             any member        owner/admin      nobody (fixed membership)
  remove (a member)  owner/admin       owner/admin      nobody
  pin                owner/admin       owner/admin      any member
  manage             owner/admin       owner/admin      nobody
  set_role           owner             owner            nobody
  join (yourself)    anyone            nobody           nobody
  leave              member            member           group only
  Archived channels refuse post, react, edit, invite, pin (reading and deleting still work).
  An admin cannot remove or change an owner. The org role `chat_admin` grants no reading: it
  allows export, legal hold, retention settings and the org-wide assistant switch, each traced.
"""
from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

KINDS = ("public", "private", "direct", "group")
ROLES = ("owner", "admin", "member")
ACTIONS = ("view", "post", "react", "edit", "delete", "invite", "remove", "pin", "manage", "set_role", "join", "leave")
CHAT_ADMIN = "chat_admin"
ASSISTANT_PREFIX = "assistant:"
_ELEVATED = ("owner", "admin")
_NAMED = ("public", "private")
_FIXED = ("direct", "group")
_USER_ID = re.compile(r"[^\x00-\x1f\x7f\s]{1,128}\Z")
_ASSISTANT_ID = re.compile(r"assistant:[a-z0-9][a-z0-9_-]{0,31}\Z")
_MENTION = re.compile(r"@\[([^\[\]\s]{1,128})\]")
_EMOJI = re.compile(r"[^\x00-\x1f\x7f\s]{1,32}\Z")


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str


@dataclass(frozen=True)
class Limits:
    max_body: int = 10_000            # characters
    max_topic: int = 60
    max_name: int = 80
    max_mentions: int = 10            # distinct mentions in one message
    max_attachments: int = 5
    max_file_bytes: int = 10 * 1024 * 1024
    max_members: int = 500
    max_reactions: int = 20           # distinct emoji one person may put on one message
    rate_capacity: float = 10.0       # burst
    rate_per_second: float = 1.0      # sustained
    queue_ttl_s: float = 300.0
    queue_max_events: int = 1000


def is_assistant(user_id: str) -> bool:
    return isinstance(user_id, str) and user_id.startswith(ASSISTANT_PREFIX)


def valid_user_id(user_id: object) -> bool:
    return isinstance(user_id, str) and bool(_USER_ID.match(user_id)) and not is_assistant(user_id)


def valid_assistant_id(user_id: object) -> bool:
    return isinstance(user_id, str) and bool(_ASSISTANT_ID.match(user_id))


def valid_emoji(emoji: object) -> bool:
    return isinstance(emoji, str) and bool(_EMOJI.match(emoji))


def decide(*, action: str, kind: str, role: Optional[str], caller_org: str, record_org: str,
           deployment_org: Optional[str] = None, archived: bool = False, legal_hold: bool = False,
           author: bool = False, target_role: Optional[str] = None) -> Decision:
    """May a caller with `role` do `action` in a `kind` channel? Deny unless a rule says yes."""
    if action not in ACTIONS or kind not in KINDS or (role is not None and role not in ROLES):
        return Decision(False, "unknown action, channel kind or role")
    if not caller_org or caller_org != record_org or (deployment_org and caller_org != deployment_org):
        return Decision(False, "another organisation")
    if role is None:
        if action == "join" and kind == "public" and not archived:
            return Decision(True, "public channel")
        return Decision(False, "not a member")
    if action == "join":
        return Decision(False, "already a member")
    elevated, named = role in _ELEVATED, kind in _NAMED
    if action in ("post", "react", "edit", "invite", "pin") and archived:
        return Decision(False, "channel is archived")
    if action == "view":
        return Decision(True, "member")
    if action in ("post", "react"):
        return Decision(True, "member")
    if action == "edit":
        return Decision(author, "author" if author else "only the author may edit")
    if action == "delete":
        if legal_hold:
            return Decision(False, "legal hold")
        ok = author or (elevated and named)
        return Decision(ok, "author or channel admin" if ok else "only the author or a channel admin may delete")
    if action == "invite":
        ok = (kind == "public") or (kind == "private" and elevated)
        return Decision(ok, "allowed" if ok else "this channel's membership is fixed or admin-only")
    if action in ("remove", "manage"):
        ok = named and elevated and not (action == "remove" and target_role == "owner" and role != "owner")
        return Decision(ok, "channel admin" if ok else "needs a channel admin of a public or private channel")
    if action == "pin":
        ok = (named and elevated) or kind in _FIXED
        return Decision(ok, "allowed" if ok else "only channel admins may pin here")
    if action == "set_role":
        ok = named and role == "owner"
        return Decision(ok, "channel owner" if ok else "only the owner of a public or private channel")
    if action == "leave":
        ok = kind != "direct"
        return Decision(ok, "allowed" if ok else "a direct conversation cannot be left")
    return Decision(False, "no rule")


def mentions(body: str) -> List[str]:
    """Distinct ids written as @[id], in order. `@[all]` is the broadcast."""
    seen: Dict[str, None] = {}
    for m in _MENTION.finditer(body):
        seen.setdefault(m.group(1), None)
    return list(seen)


def strip_mention(body: str, user_id: str) -> str:
    return " ".join(body.replace(f"@[{user_id}]", " ").split())


class TokenBucket:
    """Per-key token buckets. `allow(key)` takes one token or says no. Thread-safe."""

    def __init__(self, capacity: float, per_second: float, clock: Callable[[], float] = time.monotonic) -> None:
        self.capacity, self.rate, self._clock = capacity, per_second, clock
        self._state: Dict[str, List[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str, cost: float = 1.0) -> bool:
        now = self._clock()
        with self._lock:
            tokens, last = self._state.get(key, (self.capacity, now))
            tokens = min(self.capacity, tokens + (now - last) * self.rate)
            ok = tokens >= cost
            self._state[key] = [tokens - cost if ok else tokens, now]
            if len(self._state) > 50_000:     # ponytail: drop idle buckets; a full bucket is the default anyway
                self._state = {k: v for k, v in self._state.items() if v[0] < self.capacity}
            return ok
