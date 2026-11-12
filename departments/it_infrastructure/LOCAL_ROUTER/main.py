"""LOCAL_ROUTER: should this task run on this machine or be handed to the cloud?

decide(task) applies fixed rules, in this order, to what the task declares:

  1. sensitivity "restricted" (or anything unrecognised) never leaves the
     machine: it runs offline, or is rejected if it needs the network.
  2. a task that needs the network goes to the cloud if the caller says a cloud
     is available, else it is deferred.
  3. a task that needs more memory than is available locally goes to the cloud
     if available, else it is deferred.
  4. everything else runs offline.

Unless the task says cloud_available is true, the router assumes there is no
cloud. route(task) returns just the verdict: "offline", "cloud", "defer" or "reject".
"""
from __future__ import annotations

from velaris.agentkit import infra_metrics, infra_store

_NAME = "LOCAL_ROUTER"
_MAY_LEAVE = ("public", "internal")


class LocalRouter:
    def __init__(self, name=_NAME):
        self.name = name

    def health_check(self):
        return {"agent": self.name, "status": "ok", "version": "1.0.0"}

    def decide(self, task, sample=None):
        if not isinstance(task, dict):
            return infra_store.invalid("task must be an object", route="reject")
        flags = {k: task.get(k, False) for k in ("needs_network", "cloud_available")}
        mem = task.get("est_mem_mb", 0)
        if not all(isinstance(v, bool) for v in flags.values()) or not infra_store.is_number(mem, 0):
            return infra_store.invalid("needs_network and cloud_available must be true/false, est_mem_mb >= 0",
                                       route="reject")
        may_leave = task.get("sensitivity", "restricted") in _MAY_LEAVE
        if not may_leave:
            if flags["needs_network"]:
                return infra_store.fail("rejected", "restricted work cannot use the network", route="reject")
            return infra_store.ok(route="offline", reason="restricted or unclassified work stays on this machine")
        elsewhere = "cloud" if flags["cloud_available"] else "defer"
        if flags["needs_network"]:
            return infra_store.ok(route=elsewhere, reason="task needs the network")
        if mem:
            s = infra_metrics.checked(sample)
            if s is None or not infra_store.is_number(s.get("mem_available_mb"), 0):
                return infra_store.invalid("sample needs a numeric mem_available_mb", route="reject")
            if mem > s["mem_available_mb"]:
                return infra_store.ok(route=elsewhere,
                                      reason=f"needs {mem} MB, {s['mem_available_mb']} MB available locally")
        return infra_store.ok(route="offline", reason="fits on this machine")

    def route(self, task, sample=None):
        return self.decide(task, sample)["route"]
