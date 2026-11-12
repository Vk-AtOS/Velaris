"""CLOUD_HANDOFF_CONTROLLER: a durable outbox for work that has to leave this machine.

enqueue() stores an item on disk; secrets and personal identifiers in its text
are masked first (velaris.intel.guard). Only items whose "sensitivity" is on
infra_store.MAY_LEAVE_MACHINE ("public", "internal", the same list LOCAL_ROUTER uses)
are accepted; "restricted", a misspelt label or no label at all is refused. sync() delivers pending items oldest-first through a
`sender` the caller supplies, and stops at the first failure so order is kept;
an item counts as delivered only when the sender returns True.

This agent has no transport of its own and opens no connection. Without a
sender, sync() reports "not_configured" and everything stays queued: it never
claims a hand-off that did not happen.
"""
from __future__ import annotations

import time
import uuid

from velaris.agentkit import infra_store

_NAME = "CLOUD_HANDOFF_CONTROLLER"
_MAX_PENDING = 1000


class CloudHandoffController:
    def __init__(self, name=_NAME):
        self.name = name
        self._state = infra_store.State(_NAME, "outbox.json")

    def health_check(self):
        return {"agent": self.name, "status": "ok", "version": "1.0.0"}

    def enqueue(self, data):
        if not isinstance(data, dict) or not data or not infra_store.is_json(data):
            return infra_store.invalid("item must be a non-empty JSON object")
        if data.get("sensitivity") not in infra_store.MAY_LEAVE_MACHINE:
            return infra_store.fail("refused", "only items labelled sensitivity "
                                    f"{' or '.join(infra_store.MAY_LEAVE_MACHINE)} are handed off")
        item = {"id": uuid.uuid4().hex, "queued_at": time.time(), "attempts": 0,
                "data": infra_store.redact_json(data)}

        def add(state):
            pending = state.setdefault("pending", [])
            if len(pending) >= _MAX_PENDING:
                return infra_store.fail("full", f"outbox already holds {_MAX_PENDING} items")
            pending.append(item)
            return infra_store.ok(id=item["id"], pending=len(pending))
        return self._state.change(add)

    def pending(self):
        return list(self._state.load().get("pending", []))

    def sync(self, data=None, sender=None):
        """Queue `data` (if given), then deliver what is pending through sender(item_data) -> bool."""
        queued = None
        if data is not None:
            queued = self.enqueue(data)
            if queued["status"] != "ok":
                return {**queued, "synced": False}
        if sender is None:
            return {"status": "not_configured", "synced": False, "delivered": 0, "pending": len(self.pending()),
                    "reason": "no sender was supplied; items stay queued"}
        if not callable(sender):
            return infra_store.invalid("sender must be callable", synced=False)
        delivered, error = 0, ""
        with self._state.lock:
            state = self._state.load()
            items = state.get("pending", [])
            while items:
                items[0]["attempts"] += 1
                try:
                    sent = sender(items[0]["data"]) is True
                except Exception as e:  # the transport is the caller's code: keep the item, report
                    sent, error = False, f"{type(e).__name__}: {e}"
                if not sent:
                    error = error or "sender did not confirm delivery"
                    break
                items.pop(0)
                delivered += 1
                state["delivered_total"] = state.get("delivered_total", 0) + 1
            self._state.save(state)
        if delivered:
            infra_store.audit(_NAME, "handoff", {"delivered": delivered, "pending": len(items)})
        result = {"status": "ok" if not items else "partial", "synced": not items, "delivered": delivered,
                  "pending": len(items)}
        return {**result, "reason": error} if error else result
