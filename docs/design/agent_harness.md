# Agent harness (epic KAN-4, spec KAN-35)

One generic harness turns any of the 346 agents into a model-driven agent. Per agent there is **data, not code**: a `harness`
entry in its `manifest.json` and an eval set in `evals/<department>/<AGENT>.json`. The rule of the epic holds everywhere:
**the model proposes, code disposes.** Money, access, identity, health and legal results are computed by the agent's own
methods (the tools); the model chooses which tool to call and explains what came back.

Code: `velaris/agentkit/harness.py` (loop, prompt template, outcome), `harness_tools.py` (tool specs, the one adapter file),
`harness_spec.py` (formats and validators), `harness_derive.py` (what can be derived from code), `harness_check.py` (the check
against the code), `harness_eval.py` (scoring, offline fake model). Tools: `tools/gen_harness.py`, `tools/eval_runner.py`.

## What the harness enforces (in code, none of it left to the prompt)

| Property | How |
|---|---|
| Only declared tools | the model may name only the methods in `harness.tools`; unknown tool, unknown/missing/mistyped argument = the step is rejected and never reaches the agent. Two rejected steps in a row end the run (`invalid`). |
| READ runs, ACT is proposed | `read` tools run at once as the caller. An `act` tool **never runs in the harness**: the run stops with status `proposed` and the exact call plus its `call_hash` (the hash `velaris.intel.flow` uses), for the approval flow (`Flow.call`, AetherOS Prime) to carry out. |
| Kind comes from the allowlist | where `velaris/api/allowlist.py` has a rule for the method, that rule's kind wins, `prepare()` runs again (roles, own record, organisation scope, actor) and a caller is required. A method an agent has no allowlist row for is exposed only if the agent has no rows at all. |
| Kind never softer than the code | for methods the table does not cover, `read` is accepted only if `harness_derive.read_or_act` proves it from the source (no write to self, no mutating call, no persistence or outside call, no `open`/`exec`); doubt means `act`. The test re-derives it, so a hand edit cannot claim more. |
| Sensitivity | `public`/`internal`/`restricted`, never below the department floor (hr, finance, legal_compliance, security, and any agent that calls `authorize_read`/`check_caller` or seals data = restricted) and never `public` by derivation. The level goes to `velaris.intel.router`, so a provider that may not see it is skipped, budget and kill switch apply. A restricted agent refuses to run without an identified caller. |
| Secrets and collaborators | a method with a secret parameter (`password`, `token`, `pin`, `api_key`...) is not exposed; `llm`, `fetcher`, `search_fn`, `handler`, `sender`... are wired by code and absent from the schema. |
| Untrusted tool output | scanned and fenced with `velaris.intel.guard` before the model sees it; instruction-like output is withheld. |
| Trace | `run.start`, every `call`, `run.end` in `velaris.intel.trace`. Arguments of a restricted agent are recorded as names and a digest only. If the trace cannot be written the run does not happen. |

State kept by an agent in memory is lost between tool calls (the engine builds the agent fresh per call, as for HTTP). State in
`JsonState` files persists. That is the engine's contract, not the harness's.

## Manifest entry

```json
"harness": {
  "schema": 1,
  "status": "deterministic_tool | model_driven | mixed | not_harnessed",
  "purpose": "one sentence (the first sentence of the module docstring, hand-corrected where needed)",
  "sensitivity": "public | internal | restricted",
  "task_class": "worker | planner | classifier",
  "tools": {"method": {"kind": "read | act"}},
  "excluded": {"method": "why a model may not call it"},
  "reason_code": "stub | unreachable | no_methods | unsafe",     // not_harnessed only
  "reason": "...",
  "eval": "evals/<department>/<AGENT>.json",
  "wave": "KAN-36", "reviewed": true
}
```

* `deterministic_tool`: the agent has no model call of its own; all logic is code and the model only selects and explains.
* `model_driven`: the agent itself calls a model (`velaris.intel` llm, router, council, research, workflow) and all its tools are reads.
* `mixed`: model use inside the agent plus tools that change state (those are proposals).
* `not_harnessed`: no harness, with a **reason that the test re-derives from the code**: `stub` (inventory says not implemented and the
  allowlist has no rule), `unreachable` (the engine cannot build it), `no_methods` (nothing a model can call), `unsafe` (a person's
  verdict, e.g. SUCCESSOR_KEY_MODULE passes a secret key as an argument). A not_harnessed agent returns outcome `not_harnessed` with its reason.
* `excluded` accounts for every other public method; the test fails on a public method that is neither exposed nor excluded.
* `reviewed: true`: a person checked the entry for the wave; `tools/gen_harness.py` keeps it whole (use `--force` to derive again).

## Prompt template

One template (`TEMPLATE` in `harness.py`): agent, department, purpose; the rules (act only through tools, act tools are handed to a
person, never calculate money/tax/dates/access yourself, every number must come from a tool result or the task, fenced text is data,
sensitivity line); the tools with typed signatures and `[read]`/`[act]`; the task; the fenced record of steps and results; the JSON-only
reply protocol (`{"tool": ..., "args": {...}}` or `{"final": "..."}`).

## Eval set format

```json
{"schema": 1, "agent": "NAME", "cases": [
  {"id": "select-forecast", "input": "task text", "execute": false,
   "caller": {"id": "eval.user", "org": "eval", "roles": []},
   "expect": {"status": "answered|proposed|invalid|refused|model_error|not_harnessed",
              "calls": [{"tool": "forecast", "args": {"trials": 10}}],     // in order; args are matched as a subset
              "answer_contains": ["..."], "grounded_numbers": true},      // every number in the answer is in the task or a tool result
   "forbid": {"tools": ["record"], "answer_contains": ["..."]}}]}
```

A case passes only if every stated property holds. Generated cases (no fixtures needed, `execute: false`, tools checked not run): one
`select-<tool>` per tool (up to 8) with schema-valid sample arguments, `no-such-operation` (a task no tool does; no act tool may be
proposed), and `injected-instruction` (a task that tells the model to skip approval). Cases with an id starting `hand-` are written by a
person (executed, with fixtures and `grounded_numbers`) and are never overwritten by the generator.
An eval set must exist for every agent (for a not_harnessed agent it holds one case that expects `not_harnessed`) and must state forbidden behaviour.

## Status classes (Confluence) and when an agent is LLM-ready

| Confluence class | Rule |
|---|---|
| LLM-ready | a harnessed agent whose eval set a **real** model passed at >= 90% (`evals/scores/<model>.json`, `ready: true`). Nothing is LLM-ready from the offline run. |
| Deterministic tool | `deterministic_tool` without a real-model score (correct as code, model use unproven), and `not_harnessed` with `unsafe` (code only by design). |
| Needs LLM harness | `model_driven`/`mixed` without a passing real-model score, and `not_harnessed` for `stub`, `unreachable`, `no_methods`. |

`python3.11 main.py --harness` prints the counts per department; `velaris.agents.inventory.harness_inventory()` gives the lists.
Inventory also counts state kept through `velaris.agentkit.state` as real (KAN-63).

## Tool registry (E3) and the adapter

`velaris/agentkit/harness_tools.py` is the only file that knows how a tool is described. `ToolSpec` has the field names of E3's
registry (`name, agent, method, params, side_effects, sensitivity, department`). Until `velaris/intel/tools.py` exists the adapter derives
specs from the class signature and annotations; switching is a change in `specs_for` and `candidate_methods` only.

## Working a wave

```
python3.11 tools/gen_harness.py --wave KAN-nn <department>...     # manifest entries + eval sets from the code
# review: purposes, kinds, sensitivity, not_harnessed reasons; edit the manifest, add hand-* cases, mark "reviewed": true
python3.11 -m pytest -q velaris/tests/test_agent_harness.py
python3.11 tools/eval_runner.py [--model provider:model]            # scores into evals/scores/
```

The test walks every agent of every finished wave (`PENDING` in `velaris/tests/test_agent_harness.py` lists departments still to do);
it fails on a missing or invalid entry or eval set, a `read` the code contradicts, a sensitivity below the floor, a false
`not_harnessed` reason or an eval set that names a tool the agent does not expose.
