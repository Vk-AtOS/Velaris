"""Count what the Velaris agents really do, from the code and the eval scores (VEL-80).

    python3.11 tools/count_agents.py             # table
    python3.11 tools/count_agents.py --markdown  # the README table (velaris/tests/test_count_agents.py checks it)
    python3.11 tools/count_agents.py --json

Measures (each one is a static reading or a file, nothing is run):
  static            the inventory heuristic (velaris/agents/inventory.py): real / rule_based / not_implemented.
                    "real" also counts file, database, network or persisted-state access; it says nothing about correctness.
  model_in_file     agents whose own main.py calls a model-gateway method (complete, chat, embed) or builds LLM().
  model_reach       agents whose main.py, or a velaris module it imports directly (one import hop), makes such a call.
                    The name test is textual, so a helper such as biz_language.complete counts as a model call.
  real_model_ready  agents marked ready: true in a real-model score file (evals/scores/<model>.json, not fake-*).
"""
import argparse
import ast
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from velaris.agents.inventory import STATUSES, inventory  # noqa: E402

logger = logging.getLogger("tools.count_agents")
GATEWAY_CALLS = {"complete", "chat", "embed", "LLM"}


def _tree(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"))


def _calls_gateway(tree: ast.AST) -> bool:
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            f = n.func
            if (f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)) in GATEWAY_CALLS:
                return True
    return False


def _velaris_imports(tree: ast.AST) -> set:
    out = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            out.update(a.name for a in n.names)
        elif isinstance(n, ast.ImportFrom) and n.module and not n.level:
            out.add(n.module)
            out.update(f"{n.module}.{a.name}" for a in n.names)
    return {m for m in out if m.startswith("velaris")}


def _modules() -> dict:
    """{dotted module name: file} for every velaris module outside the tests."""
    out = {}
    for p in (ROOT / "velaris").rglob("*.py"):
        rel = p.relative_to(ROOT)
        if "tests" in rel.parts or "__pycache__" in rel.parts:
            continue
        parts = list(rel.with_suffix("").parts)
        out[".".join(parts[:-1] if parts[-1] == "__init__" else parts)] = p
    return out


def _module_for(dotted: str, modules: dict):
    parts = dotted.split(".")
    for i in range(len(parts), 0, -1):
        if ".".join(parts[:i]) in modules:
            return ".".join(parts[:i])
    return None


def _model_eval_agents() -> set:
    """Agents that a real (non-fake) model passed. A file that cannot be read is logged and skipped."""
    ready = set()
    for f in sorted((ROOT / "evals" / "scores").glob("*.json")):
        if f.stem.startswith("fake"):
            continue
        try:
            agents = json.loads(f.read_text(encoding="utf-8")).get("agents", {})
        except (OSError, ValueError) as e:
            logger.warning("score file %s unreadable, ignored: %s", f.name, e)
            continue
        ready.update(name for name, row in agents.items() if isinstance(row, dict) and row.get("ready") is True)
    return ready


def count() -> dict:
    modules = _modules()
    static = inventory()
    per_dept = {d: {s: len(v) for s, v in c.items()} for d, c in static.items()}
    totals = {s: sum(c[s] for c in per_dept.values()) for s in STATUSES}
    agents = sum(totals.values())
    in_file = one_hop = 0
    for main in sorted((ROOT / "departments").glob("*/*/main.py")):
        tree = _tree(main)
        if _calls_gateway(tree):
            in_file += 1
            one_hop += 1
            continue
        hops = {_module_for(m, modules) for m in _velaris_imports(tree)} - {None}
        if any(_calls_gateway(_tree(modules[h])) for h in hops):
            one_hop += 1
    return {"agents": agents, "static": totals, "departments": per_dept, "model_in_file": in_file,
            "model_reach": one_hop, "real_model_ready": len(_model_eval_agents())}


def markdown(c: dict) -> str:
    n = c["agents"]
    rows = [
        ("static heuristic: real (file, database, network or persisted state)", c["static"]["real"]),
        ("static heuristic: rule-based (logic kept in memory)", c["static"]["rule_based"]),
        ("static heuristic: not implemented", c["static"]["not_implemented"]),
        ("calls a model-gateway method in its own main.py", c["model_in_file"]),
        ("reaches a model call through one velaris module it imports", c["model_reach"]),
        ("passed an eval with a real model (ready: true)", c["real_model_ready"]),
    ]
    return "\n".join(["| measure | agents | of |", "|---|---|---|"] + [f"| {k} | {v} | {n} |" for k, v in rows])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--markdown", action="store_true")
    args = ap.parse_args()
    c = count()
    if args.json:
        print(json.dumps(c, indent=2, sort_keys=True))
    elif args.markdown:
        print(markdown(c))
    else:
        print(f"agents: {c['agents']}")
        print(markdown(c))


if __name__ == "__main__":
    main()
