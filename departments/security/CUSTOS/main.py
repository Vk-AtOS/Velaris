import logging

logger = logging.getLogger("CUSTOS")
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(asctime)s - CUSTOS - %(levelname)s - %(message)s"))
logger.addHandler(handler)

class CustosAgent:
    def __init__(self, config=None):
        self.config = config or {}
        self.roles = self.config.get("roles", {})
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
