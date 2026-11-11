# ================================================================================

from typing import Dict


class SoftLockdownMode:
    """
    Velaris Soft Lockdown Mode
    - Restricts high-risk actions, but allows normal operations
    - Tracks lockdown Enable/Disable state
    - Logs attempted restricted actions
    """

    def __init__(self):
        self.enabled: bool = False
        self.logs: Dict[int, str] = {}
        self.counter: int = 0
        self.restricted_actions = [
            "modify_core",
            "install_external",
            "change_security",
            "access_sensitive"
        ]

    def enable(self):
        self.enabled = True

    def disable(self):
        self.enabled = False

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