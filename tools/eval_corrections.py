"""Run the per-agent evaluation sets built from approver corrections (KAN-25) and print the pass rate over time.

    VELARIS_PRIME_URL=https://prime.example VELARIS_PRIME_API_KEY=... \\
        python3.11 tools/eval_corrections.py --model ollama:llama3.1:8b [--agent payables] [--report report.md]
    python3.11 tools/eval_corrections.py --model fake:x --cases cases.json     # cases from a file instead of Prime

Each run appends to <VELARIS_DATA>/agents/corrections_eval/history.jsonl; --report writes the markdown table of every
run so far (paste it into the Confluence page). Exits 1 when there are no cases or no case could be run.
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from velaris.intel import corrections_eval  # noqa: E402


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--model", required=True, help='"provider:model"')
    p.add_argument("--agent")
    p.add_argument("--cases", type=Path, help="a JSON file of cases instead of asking Prime")
    p.add_argument("--report", type=Path)
    a = p.parse_args(argv)
    if a.cases:
        cases = json.loads(a.cases.read_text(encoding="utf-8"))
    else:
        url, key = os.environ.get("VELARIS_PRIME_URL", ""), os.environ.get("VELARIS_PRIME_API_KEY", "")
        if not (url and key):
            print("set VELARIS_PRIME_URL and VELARIS_PRIME_API_KEY, or pass --cases", file=sys.stderr)
            return 2
        cases = corrections_eval.fetch_cases(url, key, a.agent)
    if a.agent:
        cases = [c for c in cases if c["agent"] == a.agent]
    if not cases:
        print("no good-example corrections to evaluate yet", file=sys.stderr)
        return 1
    result = corrections_eval.run(cases, a.model)
    print(json.dumps(result, indent=2))
    table = corrections_eval.report(a.agent)
    if a.report:
        a.report.write_text(table + "\n", encoding="utf-8")
    print(table)
    return 0 if any(r["total"] > r["errors"] for r in result.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
