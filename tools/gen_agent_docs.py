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

  --check          write nothing; exit 1 and list the pages that differ from what the code generates (CI, KAN-54)
  --against DIR    compare the generated facts (public methods, state files, velaris dependencies) with pages exported
                   from elsewhere (e.g. Confluence as DIR/<AGENT>.md or .html); report an agent whose page misses a fact
                   or has no page; exit 1 on drift
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


def build():
    """({relative path: page text}, {agent: {methods, state, deps}}) read from the code."""
    pages, facts = {}, {}
    agents = {}
    for f in sorted(ROOT.glob("departments/*/*/main.py")):
        agents[f.parent.name] = f
    src_files = [p for p in list(ROOT.glob("velaris/**/*.py")) + list(ROOT.glob("departments/**/*.py"))
                 if "__pycache__" not in p.parts]
    texts = {p: p.read_text(errors="replace") for p in src_files}
    any_name = re.compile(r"\b(" + "|".join(re.escape(n) for n in sorted(agents, key=len, reverse=True)) + r")\b")   # one pass per file
    callers = defaultdict(lambda: {"agent": set(), "platform": set(), "test": set()})
    for p, t in texts.items():
        own = p.parent.name if p.name == "main.py" and p.parent.name in agents else None
        kind = "test" if "tests" in p.parts or p.name.startswith("test_") else (
            "agent" if own else "platform")
        label = own or str(p.relative_to(ROOT))
        for n in set(any_name.findall(t)) - {own}:
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
        pages[f"{dept}/{name}.md"] = "\n".join(lines)
        facts[name] = {"methods": sorted({m.name for c in classes for m in c.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                                          and not m.name.startswith("_")}),
                       "state": state, "deps": imps}
        by_dept[dept].append((name, classify(src), first_line(doc)))

    idx = ["# Velaris agent reference", "",
           f"{sum(len(v) for v in by_dept.values())} agents, generated from source by `tools/gen_agent_docs.py`.", ""]
    for dept in sorted(by_dept):
        idx += [f"## {dept} ({len(by_dept[dept])})", "", "| Agent | Status | Purpose |", "|---|---|---|"]
        idx += [f"| [{n}]({dept}/{n}.md) | {s} | {p.replace('|', '/')} |" for n, s, p in sorted(by_dept[dept])]
        idx.append("")
    pages["INDEX.md"] = "\n".join(idx)
    return pages, facts


def stale(pages):
    """Paths whose committed text differs from what the code generates, plus committed pages for agents that are gone."""
    out = [r for r, t in sorted(pages.items()) if not (OUT / r).is_file() or (OUT / r).read_text() != t]
    out += [str(p.relative_to(OUT)) + " (agent no longer exists)" for p in sorted(OUT.glob("*/*.md")) if str(p.relative_to(OUT)) not in pages]
    return out


def drift(facts, exported):
    """{agent: [what is missing]} for facts absent from the exported page text; exported maps agent -> page text (or None if no page)."""
    report = {}
    for name, f in sorted(facts.items()):
        text = exported.get(name)
        if text is None:
            report[name] = ["no page"]
            continue
        missing = [f"method {m}" for m in f["methods"] if not re.search(rf"\b{re.escape(m)}\b", text)]
        missing += [f"state file {x}" for x in f["state"] if x not in text]
        missing += [f"dependency {d}" for d in f["deps"] if d not in text]
        if missing:
            report[name] = missing
    return report


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    pages, facts = build()
    if "--check" in argv:
        bad = stale(pages)
        print("\n".join(f"STALE {b}" for b in bad) or f"docs/agents is current ({len(pages)} pages)")
        return 1 if bad else 0
    if "--against" in argv:
        folder = Path(argv[argv.index("--against") + 1])
        exported = {n: (next(iter(sorted(folder.glob(f"{n}.*"))), None)) for n in facts}
        exported = {n: (p.read_text(errors="replace") if p else None) for n, p in exported.items()}
        report = drift(facts, exported)
        for n, items in report.items():
            print(f"DRIFT {n}: " + "; ".join(items[:8]) + (f" (+{len(items) - 8} more)" if len(items) > 8 else ""))
        print(f"{len(report)} of {len(facts)} pages drift")
        return 1 if report else 0
    for p in OUT.glob("*/*.md"):
        if str(p.relative_to(OUT)) not in pages:
            p.unlink()      # the agent is gone or moved
    for rel, text in pages.items():
        (OUT / rel).parent.mkdir(parents=True, exist_ok=True)
        (OUT / rel).write_text(text)
    print("wrote", len(facts), "pages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
