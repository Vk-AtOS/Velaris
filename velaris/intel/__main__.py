"""Try the intelligence core from a terminal:  python3.11 -m velaris.intel <command> ...

  search "query"                      web search
  read URL                            one page as markdown
  research "question"                 cited report from the web
  council "question" -m A -m B ...    several models, one answer (models are "provider:name")
  remember SCOPE "text"               store durable facts
  recall SCOPE "query"                retrieve them
  ingest SCOPE FILE                   add a document (PDF, Word, Excel, PowerPoint, CSV, HTML, text) to a library
  ask SCOPE "question"                answer from that library, with citations
  workflow FILE.json                  analyse an n8n workflow export
  trace                               verify the hash-chained log
  trace-rebaseline                    re-sign the trace head after verifying the whole chain (install/upgrade)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="python3.11 -m velaris.intel", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("search").add_argument("query")
    sub.add_parser("read").add_argument("url")
    sub.add_parser("research").add_argument("question")
    c = sub.add_parser("council")
    c.add_argument("question")
    c.add_argument("-m", "--model", action="append", required=True)
    for name in ("remember", "recall", "ingest", "ask"):
        s = sub.add_parser(name)
        s.add_argument("scope")
        s.add_argument("text")
    sub.add_parser("workflow").add_argument("file")
    sub.add_parser("trace")
    sub.add_parser("trace-rebaseline")
    a = p.parse_args(argv)

    # imported here so `--help` works even when a module's dependency is missing
    from velaris.intel import council, docs, memory, research, trace, web, workflow

    if a.cmd == "search":
        out = web.search(a.query)
    elif a.cmd == "read":
        page = web.scrape(a.url)
        print(page.markdown or f"could not read the page: {page.error}")
        return 0 if page.ok else 1
    elif a.cmd == "research":
        result = research.research(a.question)
        print(result.report)
        print(f"\n[stopped because: {result.stopped_because}; learnings kept: {len(result.learnings)}, "
              f"rejected: {result.rejected_learnings}]", file=sys.stderr)
        return 0
    elif a.cmd == "council":
        out = council.council(a.question, models=a.model).to_dict()
    elif a.cmd == "remember":
        out = memory.MemoryStore().remember(a.text, scope=a.scope, source="cli")
    elif a.cmd == "recall":
        out = [m.to_dict() for m in memory.MemoryStore().recall(a.text, scope=a.scope)]
    elif a.cmd == "ingest":
        out = docs.DocStore().ingest_file(a.text, scope=a.scope)
    elif a.cmd == "ask":
        out = docs.DocStore().ask(a.text, scope=a.scope)
    elif a.cmd == "workflow":
        wf = workflow.load(Path(a.file).read_text(encoding="utf-8"))
        out = {"analysis": workflow.analyse(wf), "plan": workflow.to_plan(wf),
               "permissions_to_approve": workflow.required_permissions(wf)}
    elif a.cmd == "trace-rebaseline":
        out = trace.rebaseline()
    else:
        out = trace.verify()
    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
