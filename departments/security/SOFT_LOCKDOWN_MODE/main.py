# ================================================================================

from typing import Dict

from velaris.agentkit.state import JsonState
from velaris.core.access import SECURITY_ADMINS, check_caller

NAME = "SOFT_LOCKDOWN_MODE"


class SoftLockdownMode:
    """
    Velaris Soft Lockdown Mode
    - Restricts high-risk actions, but allows normal operations
    - Tracks lockdown Enable/Disable state
    - Logs attempted restricted actions
    """

    def __init__(self):
        self._state = JsonState(NAME)       # a restart must not lift a lockdown
        self.logs: Dict[int, str] = {}
        self.counter: int = 0
        self.restricted_actions = [
            "modify_core",
            "install_external",
            "change_security",
            "access_sensitive"
        ]

    @property
    def enabled(self) -> bool:
        return bool(self._state.load().get("enabled", False))

    def _set(self, value: bool) -> bool:
        # Turning a lockdown ON is allowed to any authenticated caller (the safe direction);
        # turning it OFF needs a security admin. Both are traced.
        _, refused = check_caller(NAME, "enable" if value else "disable", {},
                                  roles=None if value else SECURITY_ADMINS)
        if refused:
            return False
        self._state.update(lambda d: d.__setitem__("enabled", value))
        return True

    def enable(self) -> bool:
        return self._set(True)

    def disable(self) -> bool:
        return self._set(False)

    def is_enabled(self) -> bool:
        return self.enabled

    def attempt(self, action: str) -> bool:
        """
        Returns True if action is allowed.
        Logs and blocks restricted actions when Soft Lockdown is enabled.
        """
        if self.enabled and action in self.restricted_actions:
            self.counter += 1
            self.logs[self.counter] = f"Blocked: {action}"
            return False
        return True

    def get_logs(self) -> Dict[int, str]:
        return dict(self.logs)

# ================================================================================