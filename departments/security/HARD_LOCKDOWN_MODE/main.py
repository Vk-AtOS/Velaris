# ================================================================================

from typing import Dict

from velaris.agentkit.state import JsonState
from velaris.core.access import SECURITY_ADMINS, check_caller

NAME = "HARD_LOCKDOWN_MODE"


class HardLockdownMode:
    """
    Velaris Hard Lockdown Mode
    - Full operational freeze for all agents except core security processes
    - Every action is denied except explicit whitelist
    - Overrides Soft Lockdown
    """

    def __init__(self):
        self._state = JsonState(NAME)       # a restart must not lift a lockdown
        self.whitelist = ["heartbeat", "core_status"]
        self.logs: Dict[int, str] = {}
        self.counter = 0

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
        Returns True only if:
        - Hard Lockdown is disabled, OR
        - action is in whitelist
        """
        if not self.enabled:
            return True

        if action in self.whitelist:
            return True

        self.counter += 1
        self.logs[self.counter] = f"BLOCKED: {action}"
        return False

    def get_logs(self) -> Dict[int, str]:
        return dict(self.logs)

# ================================================================================