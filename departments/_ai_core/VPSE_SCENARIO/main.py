"""VPSE_SCENARIO: recomputes outcomes under what-if changes to their drivers.

run(base, formulas, scenarios):
  base       driver values, e.g. {"price": 100, "units": 50, "cost": 3000}
  formulas   outcomes as arithmetic over drivers and other outcomes, e.g.
             {"revenue": "price * units", "profit": "revenue - cost"}
  scenarios  [{"name": "price cut", "changes": {"price": {"pct": -10}, "units": {"pct": 15}}}]
             a change is {"pct": n}, {"add": n} or {"set": n}

Formulas are parsed, not executed: only numbers, names, + - * / ** %,
parentheses and min / max / abs / round are accepted, so a formula cannot run
code. They are evaluated in dependency order; a formula that refers to itself
through others is an error. Each scenario returns its outcomes and the change
against the base case; a scenario whose arithmetic fails (say, a division by
zero it causes) is reported as an error without hiding the others.
"""
import ast
import operator
from typing import Any, Callable, Dict, List, Optional

from velaris.agentkit import graph as graph
from velaris.agentkit.checks import ident, number
from velaris.agentkit.results import health, invalid

NAME = "VPSE_SCENARIO"
MAX_FORMULA = 300
_BIN: Dict[type, Callable[[float, float], float]] = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.Mod: operator.mod, ast.Pow: operator.pow}
_FUNCS: Dict[str, Callable[..., float]] = {"min": min, "max": max, "abs": abs, "round": round}


class FormulaError(ValueError):
    pass


def _parse(formula: Any) -> ast.AST:
    if not isinstance(formula, str) or not formula.strip() or len(formula) > MAX_FORMULA:
        raise FormulaError(f"a formula is text of at most {MAX_FORMULA} characters")
    try:
        tree = ast.parse(formula.strip(), mode="eval").body
    except SyntaxError as e:
        raise FormulaError(f"cannot parse {formula!r}") from e
    for node in ast.walk(tree):
        allowed = (isinstance(node, (ast.BinOp, ast.UnaryOp, ast.Name, ast.Load, ast.USub, ast.UAdd, *_BIN))
                   or (isinstance(node, ast.Constant) and number(node.value) is not None)
                   or (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                       and node.func.id in _FUNCS and not node.keywords))
        if not allowed:
            raise FormulaError(f"{formula!r} uses something other than arithmetic")
    return tree


def _names(tree: ast.AST) -> set:
    called = {id(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and id(n) not in called}


def _eval(node: ast.AST, values: Dict[str, float]) -> float:
    if isinstance(node, ast.Constant):
        return float(node.value)
    if isinstance(node, ast.Name):
        if node.id not in values:
            raise FormulaError(f"unknown name '{node.id}'")
        return values[node.id]
    if isinstance(node, ast.UnaryOp):
        value = _eval(node.operand, values)
        return -value if isinstance(node.op, ast.USub) else value
    if isinstance(node, ast.Call):
        return float(_FUNCS[node.func.id](*[_eval(a, values) for a in node.args]))      # type: ignore[attr-defined]
    left, right = _eval(node.left, values), _eval(node.right, values)                    # type: ignore[attr-defined]
    if isinstance(node.op, ast.Pow) and abs(right) > 10:                                 # type: ignore[attr-defined]
        raise FormulaError("exponents above 10 are not allowed")
    try:
        return float(_BIN[type(node.op)](left, right))                                   # type: ignore[attr-defined]
    except (ZeroDivisionError, OverflowError, TypeError, ValueError) as e:
        raise FormulaError(f"arithmetic failed: {e}") from e


def _apply(base: Dict[str, float], changes: Any) -> Dict[str, float]:
    if not isinstance(changes, dict):
        raise FormulaError("'changes' must map driver names to a change")
    drivers = dict(base)
    for name, change in changes.items():
        if name not in base:
            raise FormulaError(f"unknown driver '{name}'")
        if not isinstance(change, dict) or len(change) != 1 or next(iter(change)) not in ("pct", "add", "set") \
                or number(next(iter(change.values()))) is None:
            raise FormulaError(f"change to '{name}' must be one of {{'pct': n}}, {{'add': n}}, {{'set': n}}")
        kind, amount = next(iter(change.items()))
        drivers[name] = {"pct": base[name] * (1 + amount / 100), "add": base[name] + amount, "set": float(amount)}[kind]
    return drivers


class VPSE_SCENARIOAgent:
    def health_check(self):
        return health(NAME)

    def run(self, base: Dict[str, Any], formulas: Dict[str, str],
            scenarios: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        if not isinstance(base, dict) or not base or any(number(v) is None for v in base.values()):
            return invalid("base must map driver names to numbers")
        if not isinstance(formulas, dict) or not formulas:
            return invalid("formulas must map outcome names to arithmetic")
        scenarios = [] if scenarios is None else scenarios
        if not isinstance(scenarios, list) or any(not isinstance(s, dict) or ident(s.get("name")) is None
                                                  for s in scenarios):
            return invalid("each scenario needs a 'name' and 'changes'")
        clash = sorted(set(base) & set(formulas))
        if clash:
            return invalid(f"{clash} are both drivers and outcomes")
        try:
            trees = {name: _parse(f) for name, f in formulas.items()}
            ordered = graph.order({n: sorted(_names(t) & set(trees)) for n, t in trees.items()})
            if ordered["cycle"]:
                raise FormulaError("formulas refer to each other in a circle: " + " -> ".join(ordered["cycle"]))

            def outcomes(drivers: Dict[str, float]) -> Dict[str, float]:
                values = dict(drivers)
                for name in ordered["order"]:
                    values[name] = _eval(trees[name], values)
                return {n: round(values[n], 6) for n in formulas}

            start = {k: float(v) for k, v in base.items()}
            base_out = outcomes(start)
            results = []
            for s in scenarios:
                drivers = _apply(start, s.get("changes", {}))        # a malformed change fails the whole call
                try:
                    out = outcomes(drivers)
                except FormulaError as e:                             # e.g. this scenario divides by zero
                    results.append({"name": s["name"], "status": "error", "reason": str(e), "outcomes": None})
                    continue
                results.append({"name": s["name"], "status": "ok", "outcomes": out,
                                "delta": {n: round(out[n] - base_out[n], 6) for n in out},
                                "delta_pct": {n: round((out[n] - base_out[n]) / base_out[n] * 100, 3)
                                              if base_out[n] else None for n in out}})
        except FormulaError as e:
            return invalid(str(e))
        return {"status": "ok", "base": base_out, "scenarios": results, "evaluation_order": ordered["order"]}
