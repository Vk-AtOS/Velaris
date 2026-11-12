"""FAILOVER_ROUTER: send a service's traffic to its first working target.

Each service has an ordered list of targets (primary first). Every target has a
circuit breaker driven by the outcomes the caller reports:

  closed      in use. `failure_threshold` consecutive failures open it.
  open        skipped until `recovery_s` has passed since it opened.
  half_open   after that wait, route() offers it again as a probe: one success
              closes it, one failure re-opens it for another full wait.

route() returns the first target in priority order that is closed or due a
probe, so traffic returns to the primary once it has recovered. With every
circuit open it answers "unavailable" rather than guess.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from velaris.agentkit.checks import is_name, is_number
from velaris.agentkit.results import fail, invalid, ok
from velaris.agentkit.state import JsonState

NAME = "FAILOVER_ROUTER"


class FAILOVER_ROUTERAgent:
    def __init__(self, name: str = NAME) -> None:
        self.name = name
        self._state = JsonState(NAME)

    def health_check(self) -> Dict[str, Any]:
        return {"agent": self.name, "status": "ok", "version": "1.0.0"}

    def configure(self, service: str, targets: List[str], failure_threshold: int = 3,
                  recovery_s: float = 30.0) -> Dict[str, Any]:
        if not is_name(service):
            return invalid("service must be a short name")
        if (not isinstance(targets, list) or not targets or len(set(map(str, targets))) != len(targets)
                or not all(is_name(t) for t in targets)):
            return invalid("targets must be a non-empty list of distinct names, primary first")
        if not is_number(failure_threshold, 1, 1000) or isinstance(failure_threshold, float) or not is_number(recovery_s, 0):
            return invalid("failure_threshold must be a whole number >= 1 and recovery_s >= 0")

        def put(data: Dict[str, Any]) -> None:
            old = data.setdefault("services", {}).get(service, {}).get("circuits", {})
            data["services"][service] = {
                "targets": targets, "failure_threshold": failure_threshold, "recovery_s": recovery_s,
                "circuits": {t: old.get(t, {"state": "closed", "failures": 0, "opened_at": None}) for t in targets}}
        self._state.update(put)
        return ok(service=service, targets=targets)

    @staticmethod
    def _checked_now(now: Optional[float]) -> Optional[float]:
        if now is None:
            return time.time()
        return now if is_number(now, 0) else None

    def route(self, service: str, now: Optional[float] = None) -> Dict[str, Any]:
        now = self._checked_now(now)
        if now is None:
            return invalid("now must be a timestamp")

        def choose(data: Dict[str, Any]) -> Dict[str, Any]:
            svc = data.get("services", {}).get(service) if isinstance(service, str) else None
            if svc is None:
                return fail("unknown_service", "configure() has not been called for this service")
            for target in svc["targets"]:
                c = svc["circuits"][target]
                if c["state"] == "open" and now - c["opened_at"] >= svc["recovery_s"]:
                    c["state"] = "half_open"
                if c["state"] != "open":
                    return ok(service=service, target=target, probe=c["state"] == "half_open",
                              failed_over=target != svc["targets"][0])
            return fail("unavailable", "every target's circuit is open", service=service)
        return self._state.update(choose)

    def report(self, service: str, target: str, success: bool, now: Optional[float] = None) -> Dict[str, Any]:
        """Tell the router how a call to `target` went."""
        now = self._checked_now(now)
        if now is None or not isinstance(success, bool):
            return invalid("success must be true or false and now a timestamp")

        def update(data: Dict[str, Any]) -> Dict[str, Any]:
            svc = data.get("services", {}).get(service) if isinstance(service, str) else None
            c = svc["circuits"].get(target) if svc and isinstance(target, str) else None
            if c is None:
                return fail("unknown_target", "no such service or target")
            if success:
                c.update(state="closed", failures=0, opened_at=None)
            else:
                c["failures"] += 1
                if c["state"] == "half_open" or c["failures"] >= svc["failure_threshold"]:
                    c.update(state="open", opened_at=now)
            return ok(service=service, target=target, circuit=dict(c))
        return self._state.update(update)

    def status(self, service: str) -> Dict[str, Any]:
        svc = self._state.load().get("services", {}).get(service) if isinstance(service, str) else None
        return ok(service=service, **svc) if svc else fail("unknown_service", "no such service")
