"""Structure gate for CI (KAN-174): fails on a new rule violation, prints the rest.

Fails (exit 1) on: a syntax error, a bare `except:`, `except Exception: pass` (or BaseException), a Python file over
600 lines, a module-level import that does not resolve to a file in the repo / the standard library / an installed
package, and a top-level import cycle between velaris modules.
Reports only (no failure): imports inside functions (counted by file).

Run from the repo root:  python3.11 tools/check_structure.py
`velaris.agents.<NAME>.main` imports are skipped: velaris/agents/__init__.py resolves them from departments/ at runtime.
"""
import ast
import importlib.util
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
MAX_LINES = 600
SKIP = {".git", "__pycache__", "node_modules"}


def files():
    return sorted(p for p in ROOT.rglob("*.py") if not SKIP & set(p.relative_to(ROOT).parts))


def module_name(p: Path):
    parts = list(p.relative_to(ROOT).with_suffix("").parts)
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def resolves(name: str) -> bool:
    if name.startswith("velaris.agents.") and name.count(".") >= 2:
        return True          # alias loader
    try:
        return importlib.util.find_spec(name) is not None
    except (ImportError, ValueError, AttributeError):
        return False


def main() -> int:
    problems, graph, inner = [], defaultdict(set), defaultdict(int)
    mods = {module_name(p): p for p in files()}
    for p in files():
        rel = p.relative_to(ROOT)
        text = p.read_text(encoding="utf-8")
        if text.count("\n") + 1 > MAX_LINES:
            problems.append(f"{rel}: {text.count(chr(10)) + 1} lines (limit {MAX_LINES})")
        try:
            tree = ast.parse(text)
        except SyntaxError as e:
            problems.append(f"{rel}:{e.lineno}: syntax error")
            continue
        top = {id(n) for n in tree.body}
        for n in ast.walk(tree):
            if isinstance(n, ast.ExceptHandler):
                broad = n.type is None or (isinstance(n.type, ast.Name) and n.type.id in ("Exception", "BaseException"))
                if n.type is None:
                    problems.append(f"{rel}:{n.lineno}: bare except")
                elif broad and all(isinstance(b, ast.Pass) for b in n.body):
                    problems.append(f"{rel}:{n.lineno}: except {n.type.id}: pass")
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                if id(n) not in top:
                    inner[str(rel)] += 1
                    continue
                if isinstance(n, ast.ImportFrom) and n.level:
                    continue
                names = [a.name for a in n.names] if isinstance(n, ast.Import) else [n.module]
                for name in names:
                    if name and not resolves(name):
                        problems.append(f"{rel}:{n.lineno}: import {name} does not resolve")
                    if name in mods and name != module_name(p):
                        graph[module_name(p)].add(name)
    # top-level import cycles: Tarjan-free DFS, report each strongly connected pair once
    seen, stack, cycles = set(), [], set()

    def dfs(m):
        stack.append(m)
        for d in sorted(graph.get(m, ())):
            if d in stack:
                cycles.add(tuple(sorted(stack[stack.index(d):])))
            elif d not in seen:
                dfs(d)
        stack.pop()
        seen.add(m)

    for m in sorted(graph):
        if m not in seen:
            dfs(m)
    problems += [f"import cycle: {' <-> '.join(c)}" for c in sorted(cycles)]
    print(f"imports inside functions (report only): {sum(inner.values())} in {len(inner)} files")
    for line in problems:
        print("FAIL", line)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
