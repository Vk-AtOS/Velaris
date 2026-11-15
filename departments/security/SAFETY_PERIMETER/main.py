# ================================================================================

_BLOCKED_PREFIXES = ("os.", "subprocess.", "sys.", "socket.", "ctypes.", "shutil.")
_BLOCKED_NAMES = frozenset({"eval", "exec", "compile", "open", "__import__", "input", "breakpoint"})


class SafetyPerimeter:
    """
    Velaris Safety Perimeter
    - Jurisdiction allow-list and a call deny-list, both fail closed (anything that is not a plain, known-good
      value is refused). The gate cannot be switched off from outside.
    - ponytail: a name deny-list is a guard rail, not a sandbox; real isolation is the process sandbox.
    """

    def __init__(self):
        self.allowed_jurisdictions = ["IN", "SG", "EU"]
        self.blocked_syscalls = ["os.system", "subprocess.Popen", "eval", "exec"]

    @property
    def execution_gate_enabled(self) -> bool:
        return True                      # read-only: there is no public switch that turns the gate off

    def check_jurisdiction(self, code):
        return isinstance(code, str) and code in self.allowed_jurisdictions

    def check_syscall(self, call_name):
        if not isinstance(call_name, str) or not call_name.strip():
            return False
        name = call_name.strip().lower()
        if name in _BLOCKED_NAMES or name.startswith(_BLOCKED_PREFIXES):
            return False
        return call_name not in self.blocked_syscalls and name not in {b.lower() for b in self.blocked_syscalls}

    def can_execute(self, jurisdiction_code, syscall_name):
        return self.check_jurisdiction(jurisdiction_code) and self.check_syscall(syscall_name)

# ================================================================================
