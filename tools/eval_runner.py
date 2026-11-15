"""Run every agent's eval set against a model and publish the scores (KAN-45).

    python3.11 tools/eval_runner.py                              # offline: the FakeModel plays back each case's expectation
    python3.11 tools/eval_runner.py --model anthropic:claude-sonnet-4-6 [--departments hr finance] [--agents ORACLE]

Writes evals/scores/<model>.json (per agent) and evals/scores/<model>.md (table per department). An agent counts as `ready`
(LLM-native in the Confluence status classes) only when a REAL model passed at least --threshold of its cases; the offline run
proves the harness, the eval format and the scorer fit together and never marks anything ready. A real model needs a key or
Ollama (see docs/model_providers.md): that is the owner's input, nothing here fakes it. Exit 1 when any case ran and failed.
"""
import argparse
import json
import os
import re
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from velaris.agentkit.harness import Harness  # noqa: E402
from velaris.agentkit.harness_eval import run_evalset  # noqa: E402
from velaris.agentkit.harness_spec import ROOT, eval_path, load_json  # noqa: E402
from velaris.backend.engine import backend  # noqa: E402
from velaris.intel.llm import LLM  # noqa: E402

SCORES = ROOT / "evals" / "scores"


def run_all(model, departments=None, agents=None, threshold=0.9):
    rows = {}
    for agent in sorted(backend.list_agents()):
        dept = backend.router.departments[agent]
        if (departments and dept not in departments) or (agents and agent not in agents):
            continue
        if not eval_path(dept, agent).exists():
            rows[agent] = {"department": dept, "error": "no eval set"}
            continue
        h = Harness.for_agent(agent, backend, llm=LLM() if model else None, models=[model] if model else None)
        res = run_evalset(h, load_json(eval_path(dept, agent)), model=model)
        rows[agent] = {"department": dept, "status": h.entry["status"], "cases": res["cases"], "passed": res["passed"],
                       "rate": res["rate"], "ready": bool(model and h.entry["status"] != "not_harnessed" and res["rate"] >= threshold),
                       "failed": [r["id"] + ": " + "; ".join(r["failures"])[:200] for r in res["results"] if not r["passed"]]}
    return rows


def markdown(model, rows, threshold):
    by = defaultdict(list)
    for a, r in rows.items():
        by[r["department"]].append(r)
    lines = [f"# Eval scores: {model or 'fake:oracle (offline)'}", "",
             "Offline scores prove the harness and the eval format only; no agent is LLM-ready from them." if not model else
             f"An agent is ready when this model passed at least {threshold:.0%} of its cases.", "",
             "| department | agents | harnessed | cases | passed | rate | ready | failing agents |", "|---|---|---|---|---|---|---|---|"]
    for d in sorted(by):
        rs = [r for r in by[d] if "cases" in r]
        cases, passed = sum(r["cases"] for r in rs), sum(r["passed"] for r in rs)
        bad = sorted(a for a, r in rows.items() if r["department"] == d and (r.get("passed", 0) < r.get("cases", 0)))
        lines.append(f"| {d} | {len(by[d])} | {sum(r.get('status') != 'not_harnessed' for r in rs)} | {cases} | {passed} | "
                     f"{(passed / cases if cases else 0):.1%} | {sum(r.get('ready', False) for r in rs)} | {', '.join(bad[:6]) or '-'} |")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default=None, help='"provider:model"; omit for the offline FakeModel')
    ap.add_argument("--departments", nargs="*")
    ap.add_argument("--agents", nargs="*")
    ap.add_argument("--threshold", type=float, default=0.9)
    ap.add_argument("--out-dir", type=Path, default=SCORES)
    a = ap.parse_args(argv)
    if a.model is None:       # offline run: its trace and usage go to a throwaway directory under a throwaway key, never to VELARIS_DATA
        os.environ["VELARIS_DATA"] = tempfile.mkdtemp(prefix="velaris_eval_")
        os.environ["VELARIS_VAULT_KEY"] = "dGVzdC12YXVsdC1rZXktMzItYnl0ZXMtLi4uLi4uLi4="
    rows = run_all(a.model, a.departments, a.agents, a.threshold)
    name = re.sub(r"[^A-Za-z0-9._-]+", "-", a.model or "fake-oracle")
    a.out_dir.mkdir(parents=True, exist_ok=True)
    (a.out_dir / f"{name}.json").write_text(json.dumps({"model": a.model or "fake:oracle", "threshold": a.threshold, "agents": rows},
                                                       indent=1, sort_keys=True) + "\n", encoding="utf-8")
    table = markdown(a.model, rows, a.threshold)
    (a.out_dir / f"{name}.md").write_text(table, encoding="utf-8")
    print(table)
    return 1 if any(r.get("passed", 0) < r.get("cases", 0) or "error" in r for r in rows.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
