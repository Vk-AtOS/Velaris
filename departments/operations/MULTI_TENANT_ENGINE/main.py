# ================================================================================

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