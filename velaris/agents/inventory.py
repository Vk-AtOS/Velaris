"""
Honest agent inventory, derived statically from each agent's source.

Status rules (heuristics over the code as it is now, nothing hard-coded per agent):
  not_implemented  the source carries the explicit marker (a "not_implemented"
                   result or NotImplementedError), or no method other than
                   __init__/health_check contains any branching, loop or computation
                   (constant/echo stub).
  real             delegates to velaris.intel, or has logic and touches something outside the process
                   (files, database, network, OS, crypto/audio libraries).
  rule_based       has logic, all of it in-memory.

ponytail: static heuristic, cannot tell correct logic from wrong logic; replace
with a declared per-agent status once agents share a base class.
"""
import ast
import logging

from velaris.agents import department_dirs

logger = logging.getLogger("velaris.inventory")

STATUSES = ("real", "rule_based", "not_implemented")
SKIP_METHODS = {"__init__", "health_check", "health"}
LOGIC_NODES = (ast.If, ast.For, ast.While, ast.Try, ast.With, ast.IfExp, ast.BinOp, ast.BoolOp,
               ast.Compare, ast.AugAssign, ast.ListComp, ast.DictComp, ast.SetComp, ast.GeneratorExp)
EXTERNAL_MODULES = {"sqlite3", "subprocess", "urllib", "psutil", "cryptography", "socket", "tarfile",
                    "csv", "requests", "httpx", "whisper", "sounddevice", "pyttsx3", "shutil", "tempfile"}
EXTERNAL_CALLS = {"open", "makedirs"}


def classify(source: str) -> str:
    """Return one of STATUSES for an agent's main.py source."""
    if "not_implemented" in source or "NotImplementedError" in source:
        return "not_implemented"
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        logger.warning("Unparseable agent source counted as not_implemented: %s", e)
        return "not_implemented"
    if any(isinstance(n, ast.ImportFrom) and (n.module or "").startswith("velaris.intel")
           for n in ast.walk(tree)):
        return "real"      # delegates to the tested intelligence core (web, models, memory, trace)
    functions = [n for n in ast.walk(tree)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name not in SKIP_METHODS]
    if not any(isinstance(n, LOGIC_NODES) for f in functions for n in ast.walk(f)):
        return "not_implemented"
    imported = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            imported.update(a.name.split(".")[0] for a in n.names)
        elif isinstance(n, ast.ImportFrom) and n.module:
            imported.add(n.module.split(".")[0])
    calls = {getattr(n.func, "id", getattr(n.func, "attr", None))
             for n in ast.walk(tree) if isinstance(n, ast.Call)}
    if imported & EXTERNAL_MODULES or calls & EXTERNAL_CALLS:
        return "real"
    return "rule_based"


def inventory():
    """{department: {status: [agent names]}} for every departments/<dept>/<AGENT>/main.py."""
    result = {}
    for dept in department_dirs():
        counts = {s: [] for s in STATUSES}
        for agent in sorted(dept.iterdir()):
            main_file = agent / "main.py"
            if main_file.exists():
                counts[classify(main_file.read_text(encoding="utf-8"))].append(agent.name)
        result[dept.name] = counts
    return result


def format_inventory() -> str:
    rows = [(d, *(len(c[s]) for s in STATUSES)) for d, c in inventory().items()]
    rows.append(("TOTAL", *(sum(r[i] for r in rows) for i in (1, 2, 3))))
    lines = [f"{'department':<22}{'real':>6}{'rule-based':>12}{'not-implemented':>17}{'total':>7}"]
    lines += [f"{d:<22}{a:>6}{b:>12}{c:>17}{a + b + c:>7}" for d, a, b, c in rows]
    return "\n".join(lines)
