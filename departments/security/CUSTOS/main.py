"""Custos: minimal in-memory role-based access check.

CustosAgent(config; "roles", "permissions"): health_check(); define_role(role, perms)
sets the role's permission set; assign_permission(role, permission) adds one (creating the
role if needed); check_access(role, action) is True if the action is in the role's set.
State: in memory only (self.roles), lost on restart. A "roles" config may map to lists or
sets; both are stored as sets.
Failure: an unknown role or action returns False (deny); it does not identify callers.
"""

import logging

logger = logging.getLogger("CUSTOS")

class CustosAgent:
    def __init__(self, config=None):
        self.config = config or {}
        self.roles = {r: set(p) for r, p in (self.config.get("roles") or {}).items()}   # lists seeded by callers become sets
        self.permissions = self.config.get("permissions", {})

    def health_check(self):
        status = {"agent": "CUSTOS", "status": "ok", "version": "0.1.0"}
        logger.debug("Health: %s", status)
        return status

    def define_role(self, role, perms):
        self.roles[role] = set(perms)
        return True

    def assign_permission(self, role, permission):
        self.roles.setdefault(role, set()).add(permission)
        return True

    def check_access(self, role, action):
        allowed = action in self.roles.get(role, set())
        logger.debug("Check access: role=%s action=%s allowed=%s", role, action, allowed)
        return allowed
