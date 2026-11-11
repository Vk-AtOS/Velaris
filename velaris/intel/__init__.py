"""Velaris intelligence core.

Real, tested capabilities that department agents call. Everything here follows
three rules:
  1. Models propose, code decides. A model's output never authorises an action.
  2. Every external call (model, web, memory write) is appended to the trace.
  3. Text that came from outside (web pages, documents, tool output) is data,
     never instructions, and is screened before a model sees it.

Modules: llm (model gateway + embeddings), trace (hash-chained log),
guard, web, memory, council, research, workflow (import and analyse an
existing automation), process_mining (how work actually flows, from event logs),
flow (agent runs that pause for a person's approval and survive a restart),
docs (company documents: ingest, search, cited answers).
Try them:  python3.11 -m velaris.intel --help
"""
