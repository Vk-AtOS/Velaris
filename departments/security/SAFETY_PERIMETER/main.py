# ================================================================================

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