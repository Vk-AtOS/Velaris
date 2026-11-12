"""MULTI_TENANCY_GRID: tenants, their quotas, and usage that cannot exceed them.

Each tenant has named quotas (for example "api_calls": 1000, "storage_mb": 500).
consume() adds to a tenant's usage only if the result stays within the quota,
and refuses otherwise without changing anything. One tenant's usage is never
visible to, or counted against, another. An unknown tenant, a suspended tenant
and a resource with no quota are all refused: access is granted by declaration.

run(payload) is the single-call form: {"op": "consume", "tenant": ..., ...}.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from velaris.agentkit.checks import is_name, is_number
from velaris.agentkit.results import fail, invalid, ok
from velaris.agentkit.state import JsonState

NAME = "MULTI_TENANCY_GRID"
OPS = ("create_tenant", "set_quota", "consume", "release", "usage", "suspend", "resume")


class MultiTenancyGridAgent:
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.name = NAME
        self.version = (config or {}).get("version", "1.0.0") if isinstance(config, (dict, type(None))) else "1.0.0"
        self._state = JsonState(NAME)

    def health_check(self) -> Dict[str, Any]:
        return {"agent": NAME, "status": "ok", "version": self.version}

    def create_tenant(self, tenant: str) -> Dict[str, Any]:
        if not is_name(tenant):
            return invalid("tenant must be a short name")

        def add(data: Dict[str, Any]) -> Dict[str, Any]:
            tenants = data.setdefault("tenants", {})
            if tenant in tenants:
                return fail("exists", "tenant already exists")
            tenants[tenant] = {"active": True, "quotas": {}, "used": {}}
            return ok(tenant=tenant)
        return self._state.update(add)

    def _with_tenant(self, tenant: Any, fn) -> Dict[str, Any]:
        def step(data: Dict[str, Any]) -> Dict[str, Any]:
            t = data.get("tenants", {}).get(tenant) if isinstance(tenant, str) else None
            return fn(t) if t is not None else fail("unknown_tenant", "no such tenant")
        return self._state.update(step)

    def set_quota(self, tenant: str, resource: str, limit: float) -> Dict[str, Any]:
        if not is_name(resource) or not is_number(limit, 0):
            return invalid("resource must be a short name and limit a number >= 0")

        def put(t: Dict[str, Any]) -> Dict[str, Any]:
            t["quotas"][resource] = limit
            return ok(tenant=tenant, resource=resource, limit=limit, used=t["used"].get(resource, 0))
        return self._with_tenant(tenant, put)

    def consume(self, tenant: str, resource: str, amount: float = 1.0) -> Dict[str, Any]:
        if not is_number(amount) or amount <= 0:
            return invalid("amount must be a number > 0", allowed=False)

        def take(t: Dict[str, Any]) -> Dict[str, Any]:
            if not t["active"]:
                return fail("suspended", "tenant is suspended", allowed=False)
            if not isinstance(resource, str) or resource not in t["quotas"]:
                return fail("no_quota", "this tenant has no quota for this resource", allowed=False)
            used, limit = t["used"].get(resource, 0), t["quotas"][resource]
            if used + amount > limit:
                return fail("quota_exceeded", f"{used} used of {limit}; {amount} more does not fit",
                            allowed=False, used=used, limit=limit)
            t["used"][resource] = used + amount
            return ok(allowed=True, used=used + amount, limit=limit, remaining=limit - used - amount)
        return self._with_tenant(tenant, take)

    def release(self, tenant: str, resource: str, amount: float = 1.0) -> Dict[str, Any]:
        if not is_number(amount) or amount <= 0:
            return invalid("amount must be a number > 0")

        def give(t: Dict[str, Any]) -> Dict[str, Any]:
            used = t["used"].get(resource, 0) if isinstance(resource, str) else 0
            if amount > used:
                return fail("denied", f"only {used} is in use")
            t["used"][resource] = used - amount
            return ok(used=used - amount)
        return self._with_tenant(tenant, give)

    def _set_active(self, tenant: str, active: bool) -> Dict[str, Any]:
        return self._with_tenant(tenant, lambda t: (t.update(active=active), ok(tenant=tenant, active=active))[1])

    def suspend(self, tenant: str) -> Dict[str, Any]:
        return self._set_active(tenant, False)

    def resume(self, tenant: str) -> Dict[str, Any]:
        return self._set_active(tenant, True)

    def usage(self, tenant: str) -> Dict[str, Any]:
        t = self._state.load().get("tenants", {}).get(tenant) if isinstance(tenant, str) else None
        if t is None:
            return fail("unknown_tenant", "no such tenant")
        return ok(tenant=tenant, active=t["active"], quotas=dict(t["quotas"]), used=dict(t["used"]))

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch {"op": one of OPS, "tenant": ..., "resource": ..., "amount"/"limit": ...}."""
        if not isinstance(payload, dict) or payload.get("op") not in OPS:
            return invalid(f"payload needs an 'op' out of {', '.join(OPS)}")
        op, tenant, resource = payload["op"], payload.get("tenant"), payload.get("resource")
        if op in ("create_tenant", "usage", "suspend", "resume"):
            return getattr(self, op)(tenant)
        if op == "set_quota":
            return self.set_quota(tenant, resource, payload.get("limit"))
        return getattr(self, op)(tenant, resource, payload.get("amount", 1.0))
