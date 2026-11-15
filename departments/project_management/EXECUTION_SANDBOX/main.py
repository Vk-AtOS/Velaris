# ================================================================================

import ast
import math
import operator
from typing import Any, Dict, List, Optional

MAX_CODE = 2000          # characters
MAX_NODES = 300          # AST nodes: the whole program is bounded, so run time is bounded without a timer
MAX_LOG = 500
MAX_ITEMS = 10_000       # longest list / range
MAX_BITS = 1024          # largest integer any step may produce

_BIN = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
        ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod}
_CMP = {ast.Eq: operator.eq, ast.NotEq: operator.ne, ast.Lt: operator.lt, ast.LtE: operator.le,
        ast.Gt: operator.gt, ast.GtE: operator.ge}


class Refused(ValueError):
    """The code uses something outside the tiny arithmetic language."""


def _range(n):
    if not isinstance(n, int) or isinstance(n, bool) or not 0 <= n <= MAX_ITEMS:
        raise Refused(f"range() takes an integer from 0 to {MAX_ITEMS}")
    return list(range(n))


_FUNCS = {"abs": abs, "min": min, "max": max, "sum": sum, "range": _range}


class ExecutionSandbox:
    """
    Velaris Execution Sandbox: a tiny ARITHMETIC language, not Python.
    - Statements: `name = expression` and bare expressions; `_` holds the result
    - Expressions: numbers, lists/tuples of numbers, names assigned earlier, + - * / // %, comparisons,
      and/or/not, `a if c else b`, and abs/min/max/sum/range
    - Everything else (attributes, imports, strings, loops, comprehensions, lambdas, calls to anything else)
      is refused before anything runs. The code is interpreted node by node, never handed to exec, so there is
      no object graph to climb out through; size, integer width and list length are capped, and every call
      starts with empty variables (nothing persists between calls).
    - ponytail: need loops or real programs? Run them in the process sandbox (OFFLINE_SANDBOX), not here.
    """

    def __init__(self):
        self.last_result: Optional[Any] = None
        self.last_error: Optional[str] = None
        self.execution_log: List[Dict[str, Any]] = []

    # ---- interpreter ----------------------------------------------------------------------------
    def _num(self, v):
        if isinstance(v, int) and not isinstance(v, bool) and v.bit_length() > MAX_BITS:
            raise Refused("number too large")
        if isinstance(v, float) and not math.isfinite(v):
            raise Refused("result is not a finite number")
        return v

    def _ev(self, n: ast.AST, env: Dict[str, Any]) -> Any:
        if isinstance(n, ast.Constant):
            if isinstance(n.value, (int, float)) and not isinstance(n.value, bool):
                return self._num(n.value)
            raise Refused("only numbers are allowed")
        if isinstance(n, ast.Name):
            if n.id not in env:
                raise Refused(f"unknown name {n.id!r}")
            return env[n.id]
        if isinstance(n, (ast.List, ast.Tuple)):
            if len(n.elts) > MAX_ITEMS:
                raise Refused("list too long")
            return [self._ev(e, env) for e in n.elts]
        if isinstance(n, ast.BinOp) and type(n.op) in _BIN:
            a, b = self._ev(n.left, env), self._ev(n.right, env)
            if isinstance(a, list) or isinstance(b, list):
                raise Refused("arithmetic on lists is not allowed")
            return self._num(_BIN[type(n.op)](a, b))
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, (ast.USub, ast.UAdd, ast.Not)):
            v = self._ev(n.operand, env)
            return (not v) if isinstance(n.op, ast.Not) else self._num(-v if isinstance(n.op, ast.USub) else +v)
        if isinstance(n, ast.BoolOp):
            vals = [self._ev(v, env) for v in n.values]
            return all(vals) if isinstance(n.op, ast.And) else any(vals)
        if isinstance(n, ast.Compare) and all(type(o) in _CMP for o in n.ops):
            left = self._ev(n.left, env)
            for op, right in zip(n.ops, (self._ev(c, env) for c in n.comparators)):
                if not _CMP[type(op)](left, right):
                    return False
                left = right
            return True
        if isinstance(n, ast.IfExp):
            return self._ev(n.body if self._ev(n.test, env) else n.orelse, env)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in _FUNCS and not n.keywords:
            return self._num(_FUNCS[n.func.id](*[self._ev(a, env) for a in n.args]))
        raise Refused(f"{type(n).__name__} is not allowed here")

    def _run(self, code: str) -> Any:
        if not isinstance(code, str) or len(code) > MAX_CODE:
            raise Refused(f"code must be text of at most {MAX_CODE} characters")
        tree = ast.parse(code)
        if sum(1 for _ in ast.walk(tree)) > MAX_NODES:
            raise Refused("program too large")
        env: Dict[str, Any] = {}
        result = None
        for st in tree.body:
            if isinstance(st, ast.Assign) and len(st.targets) == 1 and isinstance(st.targets[0], ast.Name) \
                    and not st.targets[0].id.startswith("__"):
                result = env[st.targets[0].id] = self._ev(st.value, env)
            elif isinstance(st, ast.Expr):
                result = self._ev(st.value, env)
            else:
                raise Refused(f"{type(st).__name__} statements are not allowed")
        return env.get("_", result)

    def safe_exec(self, code: str) -> Dict[str, Any]:
        entry = {"code": code if isinstance(code, str) else repr(code)[:200], "status": "", "result": None, "error": None}
        try:
            entry["result"] = self._run(code)
            entry["status"] = "OK"
            self.last_result = entry["result"]
        except (Refused, SyntaxError, ValueError, TypeError, ArithmeticError, RecursionError, MemoryError) as e:
            entry["status"] = "ERROR"           # the program is refused or fails: that is the result, not a crash
            entry["error"] = f"{type(e).__name__}: {e}"[:300]
            self.last_error = entry["error"]
        self.execution_log = (self.execution_log + [entry])[-MAX_LOG:]
        return entry

    def get_last_result(self):
        return self.last_result

    def get_last_error(self):
        return self.last_error

    def get_log(self):
        return list(self.execution_log)

# ================================================================================
