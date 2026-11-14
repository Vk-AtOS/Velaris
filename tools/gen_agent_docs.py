"""Generate one reference page per Velaris agent, straight from the code.

Everything on a page is read from source (AST + grep), nothing is invented:
  - purpose: the module docstring (or "(no docstring)")
  - class, public methods with signatures and first docstring line
  - state: JsonState files, env vars, velaris.* modules it imports
  - uses: other agents / velaris modules it imports
  - called by: other agents, velaris modules and tests that reference its name
  - status: velaris.agents.inventory.classify

Run from the repo root:  python3.11 tools/gen_agent_docs.py
Writes docs/agents/<department>/<AGENT>.md and docs/agents/INDEX.md.
"""
import ast
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from velaris.agents.inventory import classify  # noqa: E402

OUT = ROOT / "docs" / "agents"


def first_line(doc):
    return doc.strip().splitlines()[0] if doc and doc.strip() else ""


def sig(fn):
    a = fn.args
    names = [x.arg for x in a.posonlyargs + a.args if x.arg != "self"]
    names += [f"*{a.vararg.arg}"] if a.vararg else []
    names += [x.arg for x in a.kwonlyargs]
    names += [f"**{a.kwarg.arg}"] if a.kwarg else []
    return f"{fn.name}({', '.join(names)})"


def main():
    agents = {}
    for f in sorted(ROOT.glob("departments/*/*/main.py")):
        agents[f.parent.name] = f
    src_files = [p for p in list(ROOT.glob("velaris/**/*.py")) + list(ROOT.glob("departments/**/*.py"))
                 if "__pycache__" not in p.parts]
    texts = {p: p.read_text(errors="replace") for p in src_files}
    name_re = {n: re.compile(rf"\b{re.escape(n)}\b") for n in agents}
    callers = defaultdict(lambda: {"agent": set(), "platform": set(), "test": set()})
    for p, t in texts.items():
        own = p.parent.name if p.name == "main.py" and p.parent.name in agents else None
        kind = "test" if "tests" in p.parts or p.name.startswith("test_") else (
            "agent" if own else "platform")
        label = own or str(p.relative_to(ROOT))
        for n, rx in name_re.items():
            if n != own and rx.search(t):
                callers[n][kind].add(label)

    by_dept = defaultdict(list)
    for name, f in agents.items():
        src = f.read_text(errors="replace")
        dept = f.parent.parent.name
        try:
            tree = ast.parse(src)
        except SyntaxError as e:
            print("skip", name, e)
            continue
        doc = ast.get_docstring(tree)
        classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
        lines = [f"# {name}", "", f"- **Department:** `{dept}`",
                 f"- **Status (static inventory):** `{classify(src)}`",
                 f"- **Source:** `departments/{dept}/{name}/main.py` ({src.count(chr(10)) + 1} lines)", ""]
        lines += ["## Purpose", "", doc.strip() if doc else "_No module docstring yet._", ""]
        for c in classes:
            lines += [f"## Class `{c.name}`", ""]
            if ast.get_docstring(c):
                lines += [ast.get_docstring(c).strip(), ""]
            for m in c.body:
                if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
                        not m.name.startswith("_") or m.name == "__init__"):
                    d = first_line(ast.get_docstring(m))
                    lines.append(f"- `{sig(m)}`" + (f" — {d}" if d else ""))
            lines.append("")
        imps = sorted({(n.module or "") for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
                       and (n.module or "").startswith(("velaris", "departments"))})
        state = sorted(set(re.findall(r"JsonState\(\s*[\w\"']+\s*,\s*[\"']([^\"']+)[\"']", src)))
        env = sorted(set(re.findall(r"environ(?:\.get)?\(\s*[\"'](\w+)[\"']|getenv\(\s*[\"'](\w+)[\"']", src)))
        env = sorted({a or b for a, b in env})
        lines += ["## Depends on", ""] + ([f"- `{i}`" for i in imps] or ["- nothing from velaris.*"]) + [""]
        lines += ["## State and configuration", ""]
        lines += [f"- state file: `<VELARIS_DATA>/agents/{name}/{s}`" for s in state] or ["- keeps no files of its own"]
        lines += [f"- env var: `{e}`" for e in env] + [""]
        c = callers[name]
        lines += ["## Called by", ""]
        for k, title in (("agent", "other agents"), ("platform", "platform modules"), ("test", "tests")):
            vals = sorted(c[k])
            lines.append(f"- **{title}:** " + (", ".join(f"`{v}`" for v in vals[:12]) +
                                              (f" (+{len(vals) - 12} more)" if len(vals) > 12 else "")
                                              if vals else "none found"))
        lines.append("")
        d = OUT / dept
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{name}.md").write_text("\n".join(lines))
        by_dept[dept].append((name, classify(src), first_line(doc)))

    idx = ["# Velaris agent reference", "",
           f"{sum(len(v) for v in by_dept.values())} agents, generated from source by `tools/gen_agent_docs.py`.", ""]
    for dept in sorted(by_dept):
        idx += [f"## {dept} ({len(by_dept[dept])})", "", "| Agent | Status | Purpose |", "|---|---|---|"]
        idx += [f"| [{n}]({dept}/{n}.md) | {s} | {p.replace('|', '/')} |" for n, s, p in sorted(by_dept[dept])]
        idx.append("")
    (OUT / "INDEX.md").write_text("\n".join(idx))
    print("wrote", sum(len(v) for v in by_dept.values()), "pages")


if __name__ == "__main__":
    main()
