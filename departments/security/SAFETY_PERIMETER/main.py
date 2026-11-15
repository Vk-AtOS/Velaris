# ================================================================================

"""Safety perimeter: a static allow-list gate on jurisdiction and syscall name.
SafetyPerimeter.check_jurisdiction(code) is True for IN, SG or EU. check_syscall(call_name) is False
for os.system, subprocess.Popen, eval and exec. can_execute(jurisdiction_code, syscall_name) is True
only when both pass, or always True when execution_gate_enabled is False. It compares exact strings
only, so it is a simple policy check and not a sandbox: it cannot stop code that does not name itself.
State: fixed lists on the instance, nothing persisted, no caller check. Failure: unknown values
simply return False; it never raises, and the gate can be switched off by setting the attribute.
"""
class SafetyPerimeter:
    def __init__(self):
        self.allowed_jurisdictions = ["IN", "SG", "EU"]
        self.blocked_syscalls = ["os.system", "subprocess.Popen", "eval", "exec"]
        self.execution_gate_enabled = True

    def check_jurisdiction(self, code):
        return code in self.allowed_jurisdictions

    def check_syscall(self, call_name):
        return call_name not in self.blocked_syscalls

    def can_execute(self, jurisdiction_code, syscall_name):
        if not self.execution_gate_enabled:
            return True
        if not self.check_jurisdiction(jurisdiction_code):
            return False
        if not self.check_syscall(syscall_name):
            return False
        return True

# ================================================================================