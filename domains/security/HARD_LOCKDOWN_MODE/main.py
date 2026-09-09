# ================================================================================

from typing import Dict


class HardLockdownMode:
    """
    Velaris Hard Lockdown Mode
    - Full operational freeze for all agents except core security processes
    - Every action is denied except explicit whitelist
    - Overrides Soft Lockdown
    """

    def __init__(self):
        self.enabled = False
        self.whitelist = ["heartbeat", "core_status"]
        self.logs: Dict[int, str] = {}
        self.counter = 0

    def enable(self):
        self.enabled = True

    def disable(self):
        self.enabled = False

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