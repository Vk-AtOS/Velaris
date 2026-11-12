"""Event delivery: one queue per client, acknowledged by last event id.

The shape follows the design Zulip documents; the code is our own.

  register()           the service creates a queue and builds the snapshot under the same lock that
                       every commit holds while it emits. So each commit is either in the snapshot
                       (its events were emitted before the queue existed) or in the queue (emitted
                       after), never neither, never both.
  emit(users, event)   called after a commit, with the explicit user ids that may see the event,
                       worked out from membership at that moment. A queue only receives events
                       addressed to its own user.
  poll(queue, last_id) drops what the client has acknowledged (id <= last_id) and returns what is
                       left, waiting up to `timeout` if nothing is. Asking again with the same
                       last_id returns the same events, so a lost response loses nothing.
  revoke(user, chan)   a removed member's queued events for that channel are dropped.

Queues are kept in memory. ponytail: a restart or an expiry (idle for queue_ttl) makes the next poll
answer bad_queue, and the client registers again for a fresh snapshot; persist queues in the store
if restarts must be invisible. A queue that falls max_events behind is dropped the same way.
"""
from __future__ import annotations

import json
import secrets
import threading
import time
from typing import Any, Callable, Dict, Iterable, List, Optional


class BadQueue(Exception):
    """The queue is unknown, expired, overflowed or belongs to someone else. Register again."""


class _Queue:
    __slots__ = ("user", "org", "events", "next_id", "touched", "dead")

    def __init__(self, user: str, org: str, now: float) -> None:
        self.user, self.org, self.events, self.next_id, self.touched, self.dead = user, org, [], 0, now, False


class Hub:
    def __init__(self, *, ttl: float = 300.0, max_events: int = 1000,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.ttl, self.max_events, self._clock = ttl, max_events, clock
        self._queues: Dict[str, _Queue] = {}
        self._cond = threading.Condition()

    def register(self, user: str, org: str) -> str:
        qid = secrets.token_urlsafe(18)
        with self._cond:
            self._gc()
            self._queues[qid] = _Queue(user, org, self._clock())
        return qid

    def delete(self, queue_id: str, user: str) -> bool:
        with self._cond:
            q = self._queues.get(queue_id)
            if q is None or q.user != user:
                return False
            del self._queues[queue_id]
            self._cond.notify_all()
            return True

    def drop_user(self, user: str) -> int:
        """Delete every queue of `user` (erasure, or an account that is gone)."""
        with self._cond:
            gone = [k for k, q in self._queues.items() if q.user == user]
            for k in gone:
                del self._queues[k]
            self._cond.notify_all()
            return len(gone)

    def emit(self, users: Iterable[str], event: Dict[str, Any], *, org: str) -> int:
        """Queue `event` for every queue of the listed users (same org only). Returns queues reached."""
        wanted, reached = set(users), 0
        with self._cond:
            for qid, q in list(self._queues.items()):
                if q.user not in wanted or q.org != org or q.dead:
                    continue
                if len(q.events) >= self.max_events:
                    q.dead, q.events = True, []        # too far behind: the client must re-register
                    continue
                q.events.append({**event, "id": q.next_id})
                q.next_id += 1
                reached += 1
            self._cond.notify_all()
        return reached

    def revoke(self, user: str, channel_id: int, *, keep: Optional[Callable[[Dict[str, Any]], bool]] = None) -> None:
        """Drop queued events about `channel_id` for `user`, except those `keep` accepts (the removal itself)."""
        with self._cond:
            for q in self._queues.values():
                if q.user == user:
                    q.events = [e for e in q.events if e.get("channel_id") != channel_id or (keep and keep(e))]

    def poll(self, queue_id: str, user: str, last_event_id: int, timeout: float = 0.0,
             acknowledged: Optional[int] = None) -> List[Dict[str, Any]]:
        """Events after `last_event_id`. What is dropped is what is acknowledged: `last_event_id`, or `acknowledged`
        when given (a stream that has sent more than the client has confirmed)."""
        deadline = self._clock() + max(0.0, timeout)
        with self._cond:
            while True:
                q = self._get(queue_id, user)
                q.events = [e for e in q.events if e["id"] > (last_event_id if acknowledged is None else acknowledged)]
                fresh = [e for e in q.events if e["id"] > last_event_id]
                if fresh:
                    return fresh
                remaining = deadline - self._clock()
                if remaining <= 0:
                    return []
                self._cond.wait(min(remaining, 1.0))

    def _get(self, queue_id: str, user: str) -> _Queue:
        q = self._queues.get(queue_id)
        now = self._clock()
        if q is None or q.user != user:
            raise BadQueue()                     # unknown, or someone else's: say nothing more
        if q.dead or now - q.touched > self.ttl:
            del self._queues[queue_id]
            raise BadQueue()
        q.touched = now
        return q

    def _gc(self) -> None:
        now = self._clock()
        for qid in [k for k, q in self._queues.items() if q.dead or now - q.touched > self.ttl]:
            del self._queues[qid]

    def queues(self) -> int:
        with self._cond:
            return len(self._queues)


def sse_frame(event: Dict[str, Any]) -> bytes:
    """One Server-Sent Events frame: id (the event id, which a reconnect sends back as Last-Event-ID),
    event (the type) and a single-line JSON data field, ended by a blank line."""
    kind = str(event.get("type", "message")).replace("\n", " ").replace("\r", " ")
    data = json.dumps(event, separators=(",", ":"), default=str)       # JSON has no raw newlines
    return f"id: {event['id']}\nevent: {kind}\ndata: {data}\n\n".encode()


SSE_KEEPALIVE = b": keepalive\n\n"
