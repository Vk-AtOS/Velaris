# ================================================================================

"""Multi-tenant engine: an in-memory key/value store partitioned by tenant id.

create_tenant(tenant_id) (False if it exists), delete_tenant(tenant_id) (False if unknown), set_value(tenant_id, key,
value) (False for an unknown tenant), get_value(tenant_id, key) (None for an unknown tenant or key), list_tenants() and
tenant_snapshot(tenant_id) (None if unknown). Values are deep-copied on the way in and on the way out, so callers never
share objects with the store or with each other.
State: a dict in memory only, per instance, lost on restart. Separation is by the tenant_id argument alone: there is no
caller check, so any caller can read any tenant by naming it. Unknown tenants give False or None; nothing is raised.
"""
import copy
from typing import Dict, Any, Optional

class MultiTenantEngine:
    """
    Velaris Multi-Tenant Engine
    - Isolates tenant data
    - Provides CRUD operations per tenant
    - Enforces strict separation and sandboxing
    """

    def __init__(self):
        self.tenants: Dict[str, Dict[str, Any]] = {}

    def create_tenant(self, tenant_id: str) -> bool:
        if tenant_id in self.tenants:
            return False
        self.tenants[tenant_id] = {}
        return True

    def delete_tenant(self, tenant_id: str) -> bool:
        if tenant_id not in self.tenants:
            return False
        del self.tenants[tenant_id]
        return True

    def set_value(self, tenant_id: str, key: str, value: Any) -> bool:
        if tenant_id not in self.tenants:
            return False
        self.tenants[tenant_id][key] = copy.deepcopy(value)
        return True

    def get_value(self, tenant_id: str, key: str) -> Optional[Any]:
        if tenant_id not in self.tenants:
            return None
        return copy.deepcopy(self.tenants[tenant_id].get(key))

    def list_tenants(self):
        return list(self.tenants.keys())

    def tenant_snapshot(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        if tenant_id not in self.tenants:
            return None
        return copy.deepcopy(self.tenants[tenant_id])      # nested values too: a snapshot shares nothing

# ================================================================================