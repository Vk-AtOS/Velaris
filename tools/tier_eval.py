"""Run the tiering evaluation (KAN-19): every task in velaris/intel/tiereval_tasks.json on every model given.

    python3.11 tools/tier_eval.py --models ollama:llama3.1:8b anthropic:claude-sonnet-4-6 --out results.json --table results.md
    python3.11 tools/tier_eval.py --models gw:model --tasks my_tasks.json --classes classifier chat

Needs a model that answers (an API key in the environment, a running Ollama, or a provider registered in
velaris.intel.providers). Nothing is faked here: with no model the run records `error` for every task and
exits 1, so an empty table is never mistaken for a result. Fixtures are synthetic: no real person's data.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from velaris.intel import tiereval  # noqa: E402


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--models", nargs="+", required=True, help='"provider:model" names')
    p.add_argument("--tasks", type=Path, default=tiereval.TASKS_FILE)
    p.add_argument("--classes", nargs="*", choices=tiereval.CLASSES, help="only these task classes")
    p.add_argument("--out", type=Path, help="write every reply and score here (JSON)")
    p.add_argument("--table", type=Path, help="write the markdown results table here")
    a = p.parse_args(argv)
    tasks = [t for t in tiereval.load_tasks(a.tasks) if not a.classes or t["class"] in a.classes]
    results = tiereval.run(a.models, tasks)
    summary = tiereval.summarise(results)
    table = tiereval.markdown(summary)
    if a.out:
        a.out.write_text(json.dumps({"summary": summary, "results": results}, indent=2, ensure_ascii=False), encoding="utf-8")
    if a.table:
        a.table.write_text(table + "\n", encoding="utf-8")
    print(table)
    return 0 if any(s["ran"] for s in summary.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
