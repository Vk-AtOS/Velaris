"""Generate the harness entry (manifest.json) and eval set (evals/<dept>/<AGENT>.json) of every agent in the given departments,
from the code (KAN-35). What cannot be derived is not invented: a stub, an unreachable agent or one without callable methods
becomes `not_harnessed` with the reason.

    python3.11 tools/gen_harness.py --wave KAN-36 executive project_management      # write
    python3.11 tools/gen_harness.py --check executive                               # exit 1 if a file would change

A hand-checked entry (`"reviewed": true`) is kept whole; hand-written eval cases (id starting `hand-`) are kept. Agents that had
no manifest.json get a minimal one (name, entrypoint, description) so the harness entry has a home.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from velaris.agentkit.harness_derive import derive_entry, derive_evalset  # noqa: E402
from velaris.agentkit.harness_spec import eval_path, manifest_path  # noqa: E402
from velaris.agents import department_dirs  # noqa: E402
from velaris.backend.engine import backend  # noqa: E402


def dump(path: Path, data: dict) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def build(agent: str, department: str, wave: str, force: bool = False):
    """(manifest path, manifest text, eval path, eval text) as they should be."""
    mp, ep = manifest_path(department, agent), eval_path(department, agent)
    manifest = json.loads(mp.read_text(encoding="utf-8")) if mp.exists() else {}
    if not manifest:
        manifest = {"name": agent, "version": "0.1.0", "description": "", "entrypoint": f"main.py:{backend.agent_class(agent).__name__}"}
    old = manifest.get("harness", {})
    entry = derive_entry(agent, department, backend, manifest, wave or old.get("wave", ""))
    if old.get("reviewed") and not (force and old.get("reason_code") != "unsafe"):
        entry = old                       # a hand-checked entry is kept as it is; check_agent still holds it to the code
    if not manifest.get("description"):
        manifest["description"] = entry["purpose"]
    manifest["harness"] = entry
    evals = derive_evalset(agent, entry, backend.agent_class(agent))
    if ep.exists():
        evals["cases"] += [c for c in json.loads(ep.read_text(encoding="utf-8"))["cases"] if c["id"].startswith("hand-")]
    return mp, dump(mp, manifest), ep, dump(ep, evals)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("departments", nargs="+")
    ap.add_argument("--wave", default="")
    ap.add_argument("--agents", nargs="*", help="only these agents")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--force", action="store_true", help="derive again even where a person reviewed the entry (their `unsafe` verdicts stay)")
    a = ap.parse_args(argv)
    known = {d.name for d in department_dirs()}
    if set(a.departments) - known:
        ap.error(f"unknown departments {sorted(set(a.departments) - known)}")
    changed = 0
    for dept in a.departments:
        for agent in sorted(p.name for p in (Path(department_dirs()[0]).parent / dept).iterdir() if (p / "main.py").exists()):
            if a.agents and agent not in a.agents:
                continue
            mp, mtext, ep, etext = build(agent, dept, a.wave, a.force)
            for path, text in ((mp, mtext), (ep, etext)):
                if not path.exists() or path.read_text(encoding="utf-8") != text:
                    changed += 1
                    if a.check:
                        print(f"would change {path}")
                    else:
                        path.parent.mkdir(parents=True, exist_ok=True)
                        path.write_text(text, encoding="utf-8")
    print(f"{changed} files {'differ' if a.check else 'written'}")
    return 1 if a.check and changed else 0


if __name__ == "__main__":
    sys.exit(main())
