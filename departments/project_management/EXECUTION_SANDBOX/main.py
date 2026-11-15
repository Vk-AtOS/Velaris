# ================================================================================

import ast
import traceback
from typing import Any, Dict, Optional

class ExecutionSandbox:
    """
    Velaris Execution Sandbox
    - Safe code execution environment
    - Blocks dangerous builtins
    - Tracks executed operations
    """

    def __init__(self):
        self.safe_globals = {
            "abs": abs,
            "min": min,
            "max": max,
            "sum": sum,
            "range": range,
            "__builtins__": {}
        }
        self.safe_locals = {}
        self.last_result: Optional[Any] = None
        self.last_error: Optional[str] = None
        self.execution_log = []

    def safe_exec(self, code: str) -> Dict[str, Any]:
        entry = {"code": code, "status": "", "result": None, "error": None}
        try:
            ast.parse(code)
            exec(code, self.safe_globals, self.safe_locals)
            entry["status"] = "OK"
            entry["result"] = self.safe_locals.get("_")
            self.last_result = entry["result"]
        except Exception:      # any failure of the sandboxed code is the result, recorded in full below
            entry["status"] = "ERROR"
            entry["error"] = traceback.format_exc()
            self.last_error = entry["error"]
        self.execution_log.append(entry)
        return entry

    def get_last_result(self):
        return self.last_result

    def get_last_error(self):
        return self.last_error

    def get_log(self):
        return list(self.execution_log)

# ================================================================================