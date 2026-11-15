"""RESOURCE_ORCHESTRATOR: named resource pools with hard capacity.

A pool is a countable resource (GPU slots, API calls per day, licence seats).
allocate() grants an owner a share only if the pool still has room; nothing is
ever over-committed and a refused request changes nothing. Grants survive a
restart, so capacity held by a crashed owner stays held until release().
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from velaris.agentkit.checks import is_name, is_number
from velaris.agentkit.results import fail, invalid, ok
from velaris.agentkit.state import JsonState
from velaris.core.access import INFRA_ADMINS, check_caller

NAME = "RESOURCE_ORCHESTRATOR"


class RESOURCE_ORCHESTRATORAgent:
    def __init__(self, name: str = NAME) -> None:
        self.name = name
        self._state = JsonState(NAME)

    def health_check(self) -> Dict[str, Any]:
        return {"agent": self.name, "status": "ok", "version": "1.0.0"}

    def define_pool(self, pool: str, capacity: float) -> Dict[str, Any]:
        """Create a pool or change its capacity (never below what is already granted). Infra admins only."""
        _, refused = check_caller(NAME, "define_pool", {"pool": str(pool)[:64], "capacity": str(capacity)[:32]}, roles=INFRA_ADMINS)
        if refused:
            return refused
        if not is_name(pool) or not is_number(capacity, 0):
            return invalid("pool must be a short name and capacity a number >= 0")

        def define(data: Dict[str, Any]) -> Dict[str, Any]:
            p = data.setdefault("pools", {}).setdefault(pool, {"capacity": capacity, "grants": {}})
            used = sum(p["grants"].values())
            if capacity < used:
                return fail("denied", f"{used} is already granted; capacity cannot drop below that")
            p["capacity"] = capacity
            return ok(pool=pool, capacity=capacity, used=used)
        return self._state.update(define)

    def allocate(self, pool: str, owner: str, amount: float) -> Dict[str, Any]:
        if not is_name(owner) or not is_number(amount) or amount <= 0:
            return invalid("owner must be a short name and amount a number > 0")

        def grant(data: Dict[str, Any]) -> Dict[str, Any]:
            p = data.get("pools", {}).get(pool) if isinstance(pool, str) else None
            if p is None:
                return fail("unknown_pool", "define_pool() has not been called for this pool")
            free = p["capacity"] - sum(p["grants"].values())
            if amount > free:
                return fail("denied", f"requested {amount}, only {free} free", free=free)
            p["grants"][owner] = p["grants"].get(owner, 0) + amount
            return ok(pool=pool, owner=owner, granted=p["grants"][owner], free=free - amount)
        return self._state.update(grant)

    def release(self, pool: str, owner: str, amount: Optional[float] = None) -> Dict[str, Any]:
        """Give back `amount` of an owner's grant, or all of it when amount is omitted. The owner or an infra admin."""
        _, refused = check_caller(NAME, "release", {"pool": str(pool)[:64], "owner": str(owner)[:64]}, roles=INFRA_ADMINS,
                                  also=owner if isinstance(owner, str) else None)
        if refused:
            return refused
        if amount is not None and (not is_number(amount) or amount <= 0):
            return invalid("amount must be a number > 0")

        def free(data: Dict[str, Any]) -> Dict[str, Any]:
            p = data.get("pools", {}).get(pool) if isinstance(pool, str) else None
            if p is None or not isinstance(owner, str) or owner not in p["grants"]:
                return fail("unknown_grant", "this owner holds nothing in this pool")
            held = p["grants"][owner]
            if amount is not None and amount > held:
                return fail("denied", f"owner holds {held}, cannot release {amount}")
            left = 0 if amount is None else held - amount
            if left:
                p["grants"][owner] = left
            else:
                del p["grants"][owner]
            return ok(pool=pool, owner=owner, released=held - left, still_held=left)
        return self._state.update(free)

    def usage(self, pool: str) -> Dict[str, Any]:
        p = self._state.load().get("pools", {}).get(pool) if isinstance(pool, str) else None
        if p is None:
            return fail("unknown_pool", "no such pool")
        used = sum(p["grants"].values())
        return ok(pool=pool, capacity=p["capacity"], used=used, free=p["capacity"] - used, grants=dict(p["grants"]))
