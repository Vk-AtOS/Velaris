# V2: `departments/_ai_core/`, the AI core, control hierarchy and framework clusters

Scope: `departments/_ai_core/`, working tree on top of HEAD `142153b`. The directory is **untracked** (`?? departments/_ai_core/`). All 131 `main.py` files match a HEAD copy byte for byte under `domains/{core_brain,cognition,neural_ai,self_management,frameworks/*}/`. HEAD also held 9 duplicate copies that differed (e.g. `frameworks/coherence/CSM_*` vs `frameworks/csm/CSM_*`, `ACTION_MODELING_CORE` in both `aae` and `neural_ai`). The reorg dropped those duplicates.
Method: I read every `main.py` (131), every `manifest.json` (19) and every `__init__.py` (131: 64 empty, 67 identical 5-line "package marker" comment banners). I also ran a smoke harness that loads each file by path and calls `health_check()` (`python3 -I`, no bytecode). The harness skipped the 3 agents that write to `/live`.

---

## 1. Summary

| Metric | Value |
|---|---|
| Agent folders | **131** (281 files: 131 main.py, 131 `__init__.py`, 19 manifest.json) |
| LOC | 3,417 in main.py, 268 in `__init__.py` (banners only) |
| Median main.py | 18 lines. 31 files are byte-identical 12-line templates apart from the name |
| LLM SDK imports (openai/anthropic/bedrock/ollama/httpx) | **0** |
| ML libs | 1 file (`LYRA_VOICE_ENGINE`) has *optional* `whisper`/`pyttsx3`/`sounddevice`/`numpy` behind try/except. None are installed or listed in `requirements.txt` (which has only `psutil`, `cryptography`). Default mode is `"mock"` |
| `random` use | 1 (`NEURAL_CREATIVITY_ENGINE/main.py:33`) |

**Counts by primary tag**

| Tag | Agents | LOC | % agents |
|---|---|---|---|
| STUB/HOLLOW | **104** | 1,896 | 79% |
| RULE-BASED (works, simple heuristics) | 11 | 686 | 8% |
| REAL (working plumbing or algorithm) | 16 | 835 | 12% |
| LLM-DRIVEN | 0 | 0 | 0% |
| ML (real model) | 0 (LYRA_VOICE can load Whisper only if configured *and* installed, and it is neither) | | 0% |

**Liveness overlay: every one of the 131 agents is DEAD at runtime.**
- The entry point `main.py` → `velaris/backend/engine.py` → `velaris/agents/router.py:16-27` scans only `velaris/agents/`. That directory holds nothing but `router.py`. Running `python3 main.py` prints `Agents loaded : 0`.
- Cross-agent imports use three package roots that don't exist in the tree, now or at HEAD: `velaris.agents.X.main`, `agents.X.main`, `live.agents.X.main`.
- So 5 agents fail at import (`ENGINE`, `PRIME`, `COGNITIVE_LOAD_BALANCER`, `NEURAL_MESH`, `INTER_AGENT_COHESION`). `REGISTRY` raises FileNotFoundError on construction. All 6 alias wrappers load no delegate.
- The ~110 tests under `velaris/tests/` that name these agents import via the same missing roots, and `pytest` isn't installed. Nothing in the repo can execute them as written.

Smoke result (load by file path): 126/131 import. 112 instantiate and return `status:"ok"`. 10 have no `health_check`. 3 were skipped because they write to `/live`. 1 raises (REGISTRY). 5 fail import.

---

## 2. Full agent table

Columns: Cluster = name prefix plus HEAD source dir (`fw/x` = `domains/frameworks/x`, `cb` = core_brain, `cog` = cognition, `nai` = neural_ai, `sm` = self_management). "Echo" means the method returns its input wrapped in a constant dict. "HC-only" means the class has `__init__` + a constant `health_check` and nothing else.

| Agent | Cluster | LOC | What it actually does | Tag |
|---|---|---|---|---|
| AAE_POLICY | AAE (fw/aae) | 12 | HC-only template (`:8-12`) | STUB |
| AAE_RUNTIME | AAE | 12 | HC-only | STUB |
| ADAPTIVE_ACTION_ENGINE | AAE | 12 | HC-only. Logger tag "AAE" (`:5`) | STUB |
| ACTION_MODELING_CORE | AAE (also nai) | 21 | `model()` returns hard-coded `["step1","step2"]` (`:16-17`) | STUB |
| ACF_CORE | ACF (fw/acf) | 16 | HC-only | STUB |
| ACF_CONTEXT | ACF | 18 | `contextualize(x)` echo (`:14-15`) | STUB |
| ACF_FUSION | ACF | 18 | `fuse(a,b)` echo | STUB |
| ACF_ROUTER | ACF | 18 | `route(signal)` echo | STUB |
| ASEL | ASEL (fw/asel) | 48 | Alias wrapper that imports `agents.ASEL_*` (`:18-28`). Path doesn't exist, so no delegate | STUB |
| ASEL_EVALUATOR | ASEL | 18 | HC-only | STUB |
| ASEL_EXECUTOR | ASEL | 18 | HC-only | STUB |
| ASEL_PLANNER | ASEL | 18 | HC-only | STUB |
| ASEL_ROUTER | ASEL | 18 | HC-only | STUB |
| ASEL_STRATEGIST | ASEL | 18 | HC-only | STUB |
| CCSF_CORE | CCSF (fw/ccsf) | 12 | HC-only | STUB |
| CCSF_FUSION | CCSF | 12 | HC-only | STUB |
| CCSF_RESOLVER | CCSF | 12 | HC-only | STUB |
| CLBPP_CORE | CLBPP (fw/clbpp) | 19 | HC-only | STUB |
| CLBPP_DISTRIBUTOR | CLBPP | 19 | HC-only | STUB |
| CLBPP_OVERLOAD_MONITOR | CLBPP | 19 | HC-only | STUB |
| CLBPP_PREDICTIVE_BALANCER | CLBPP | 19 | HC-only | STUB |
| COGNITIVE_LOAD_BALANCER | CLBPP (also nai) | 29 | `choose()` returns the first "active" candidate, else the first one. It builds a fresh `LifecycleManager` (`:15`), so state is always "unknown". Import of `velaris.agents...` fails (`:5`) | REAL (broken import) |
| CRK | CRK (fw/crk) | 48 | Alias wrapper → `agents.CRK_*` (`:18-23`), no delegate | STUB |
| CRK_CHAIN / _CONTEXT / _INTENT / _REASONER / _VALIDATOR | CRK | 19 each | HC-only (5 agents) | STUB |
| DSS_CLUSTER_MANAGER / _FAILOVER / _LOAD_BALANCER / _MONITOR / _REPLICATION / _SCALER | DSS (fw/dss) | 20 each | HC-only (6 agents) | STUB |
| EAC_AUDIT / EAC_COMPLIANCE / EAC_CORE | EAC (fw/eac) | 12 each | HC-only (3 agents) | STUB |
| EOF_CORE | EOF (fw/eof) | 18 | `orchestrate(plan)` logs and returns `{"result":"ok"}` (`:15-17`) | STUB |
| EOF_GATEWAY | EOF | 18 | `route(src,dst,payload)` logs the payload at DEBUG and returns `routed:True` (`:15-17`) | STUB |
| EOF_POLICY | EOF | 18 | `evaluate(policy)` always returns `compliant: True` (`:15-17`) | STUB |
| MCFE_CORE | MCFE (fw/mcfe) | 16 | HC-only | STUB |
| MCFE_CLASSIFIER | MCFE | 23 | `DOMAINS[hash(text)%8]` (`:19`). The comment says "deterministic" (`:18`), but `hash()` is salted per process. Effectively random | STUB |
| MCFE_FIELDGEN | MCFE | 18 | `generate_field` echo | STUB |
| MCFE_ROUTER | MCFE | 18 | `route` echo | STUB |
| MPC_CORE / MPC_FUSION / MPC_PREPROC | MPC (fw/mpc) | 12 each | HC-only (3 agents) | STUB |
| UIE_CORE | UIE (fw/uie) | 16 | HC-only | STUB |
| UIE_REASONER / UIE_SEMANTICS / UIE_SIGNAL | UIE | 18 each | Echo (`reason`/`interpret`/`process`) | STUB |
| VCAS_CORE | VCAS (fw/vcas) | 16 | HC-only | STUB |
| VCAS_AUTOPILOT | VCAS | 18 | `execute(task)` echo, `executed:True` | STUB |
| VCAS_ROUTER | VCAS | 18 | `route(task)` echo | STUB |
| VCAS_SUPERVISOR | VCAS | 18 | `approve(task)` always `approved:True` | STUB |
| VHOE_ANALYTICS / _CORE / _OPTIMIZER / _ROUTER | VHOE (fw/vhoe) | 12 each | HC-only (4 agents) | STUB |
| VPSE_CORE / _MODELER / _SCENARIO | VPSE (fw/vpse) | 12 each | HC-only (3 agents) | STUB |
| COHERENCE_SYNC_CORE | CSG (fw/coherence) | 12 | HC-only. Logger tag "CSG" (`:5`) | STUB |
| CSG_STATEALIGN / CSG_TEMPORAL | CSG | 12 each | HC-only | STUB |
| CSM_CORE | CSM (fw/coherence + fw/csm) | 16 | HC-only | STUB |
| CSM_LINKER / CSM_POLICY / CSM_REASONER | CSM | 18 each | Echo (`link`, `generate_policy`→`"generated"`, `quick_strategy`→`"ok"`) | STUB |
| MRF_EVAL / MRF_REFLECT | MRF (fw/coherence) | 12 each | HC-only | STUB |
| RCI_CONTEXT / RCI_CORE / RCI_STREAM | RCI (fw/coherence) | 12 each | HC-only | STUB |
| FSCL | coherence/cog | 48 | Alias → `agents.{SOUL_VELARIS,PRIME,ENGINE}` (`:18`), no delegate | STUB |
| GCK | coherence/cog | 48 | Alias → `agents.GLOBAL_STATE_MAP`, listed twice (`:18`). That agent lives in `data_knowledge` | STUB |
| INTER_AGENT_COHESION | coherence/cog | 30 | Thin put/get/query facade over `MEMORY_FABRIC` (`:22-29`). Import `velaris.agents.MEMORY_FABRIC` fails (`:5`). Real file is `departments/data_knowledge/MEMORY_FABRIC` | REAL (broken import) |
| CORE_CONVERGENCE | cog | 45 | Alias → `velaris.agents.{EOF_*,ENGINE}` (`:16-21`), no delegate | STUB |
| AEIL | nai | 45 | Alias → finance/exec econ agents (`ECON_INTEL_CORE`, `MARKET_GAP_ANALYZER`, `ECONOVA`, `:16`), no delegate | STUB |
| ALK_ADAPT / ALK_EVO | ALK (nai) | 12 each | HC-only | STUB |
| AUTO_LEARN_CORE | ALK (nai) | 12 | HC-only. Logger tag "ALK" (`:5`) | STUB |
| AIIE_KERNEL | AIIE (nai) | 15 | HC-only | STUB |
| META_REASONING_CORE | cog | 12 | HC-only (logger "MRC") | STUB |
| INTENT_SYNTHESIZER | cog (AIIE pipeline) | 18 | `synthesize()` returns a constant `"refined_goal"` (`:14-15`) | STUB |
| DECISION_GRAPH_ENGINE | cog (AIIE) | 18 | Copies `plan["plan"]` into `graph.steps` (`:14-15`) | STUB |
| HYPER_REASONER | cog (AIIE) | 18 | Echo, `validated:True` | STUB |
| RECURSIVE_GOAL_PLANNER | cog (AIIE) | 18 | Echo `{"expanded": plan}` | STUB |
| SELF_DIRECTED_TASKER | cog (AIIE) | 18 | Echo, `task_ready:True` | STUB |
| CAUSALITY_RESOLVER | cog (quantum chain) | 16 | Echo | STUB |
| HYPERSTATE_SYNTHESIZER | cog (quantum) | 16 | Echo | STUB |
| DECISION_COLLAPSE_ENGINE | cog (quantum) | 16 | Echo `{"final_decision": hyper}` | STUB |
| META_REINFORCEMENT_CORE | cog (neural-gov chain) | 16 | Echo, no RL | STUB |
| NEURAL_POLICY_MESH | nai (neural-gov) | 17 | Echo | STUB |
| NEURAL_ALIGNMENT_ENGINE | nai (neural-gov) | 16 | Echo | STUB |
| BEHAVIOR_SHAPING_NETWORK | nai (neural-gov) | 16 | Echo | STUB |
| SELF_CORRECTION_ENGINE | sm (neural-gov) | 16 | Echo | STUB |
| NEURAL_CONSTRAINT_FIELD | nai (neural-gov) | 16 | Echo | STUB |
| NEURAL_DRIFT_MONITOR | nai | 21 | `run(payload)` echo. Manifest says "Auto-generated placeholder" | STUB |
| LOCAL_EMBEDDING_ENGINE | nai | 13 | "Embedding" is a 1-element list holding the first 4 hex digits of sha256 (`:12`) | STUB |
| SOUL_VELARIS | cb | 31 | Static identity dict plus a hard-coded mission string (`:28-30`). Docstring admits "guardrail checks (stub)… real policy logic must be defined by you" (`:17-18`). No guardrail method exists | STUB |
| SOUL_CORE_EXT | cb (Layer-3 kernel) | 25 | `update()` returns `{"updated":True}` and stores nothing | STUB |
| PERSONALITY_MOD | cb (L3) | 25 | Same template as SOUL_CORE_EXT | STUB |
| CONTEXTUAL_SELF_MODEL | sm (L3) | 25 | Same template | STUB |
| SELF_CONSISTENCY | sm (L3) | 20 | `check()` always returns `True` (`:18-20`) | STUB |
| AGENT_LIFECYCLE | cb | 21 | `run` echo. Manifest: "Auto-generated placeholder" | STUB |
| SELF_HISTORY | sm (L3) | 24 | In-memory event list: `record`/`last` | REAL (trivial) |
| SELF_IDENTITY | sm (L3) | 26 | In-memory identity dict get/set | REAL (trivial) |
| AGENT_LIFECYCLE_MANAGER | cb | 29 | In-memory `states[agent]` set/get (`:23-29`) | REAL (trivial) |
| AGENT_EVOLUTION | nai | 29 | Records metrics. `propose()` returns "tune-params" once >5 records exist (`:24-29`) | RULE-BASED |
| ENGINE | cb | 91 | `run(agent,method,params)` via REGISTRY plus sequential `pipeline()`. Import fails (`:5-7`) | REAL (broken) |
| REGISTRY | cb | 91 | Scans `<dir>/../../agents` for `manifest.json` and imports `agents.<name>.<mod>` (`:23-27,65-76`). Path doesn't exist, so it raises | REAL (broken) |
| PRIME | cb | 62 | Wraps ENGINE: `system_status`, `execute`, and a self-test pipeline on VIGILIS/CUSTOS/PRAETOR (`:39-44`). Import fails (`:3`) | REAL (broken) |
| ORCHESTRIX | cb | 66 | DFS topological sort with cycle detection (`:20-45`) plus `parallel_groups` (has a bug, see §4) | REAL |
| NAVARCH | cb | 57 | Correct Dijkstra with heapq (`:21-50`). `sequence_steps` is a passthrough | REAL |
| SCHEDULON | cb | 50 | Greedy least-loaded bin assignment (`:22-37`) and min-load worker pick (`:39-49`) | REAL |
| STRATEGOS | cb | 51 | Score = `(benefit-cost)/(1+risk)`, then rank and pick best (`:20-51`). Divides by zero when risk is -1 | RULE-BASED |
| AUTONOMOUS_PATCH_ENGINE | cb | 61 | Shallow dict merge of `patch["changes"]` plus a JSON history log at the hard-coded `/live/agents/...` (`:15-16,44-57`). Doesn't patch code | REAL (trivial, hard-coded path) |
| AUTONOMOUS_RESEARCH_ENGINE | cb | 75 | In-memory keyword substring match, score = number of matching fields, "summary" = top 3 docs joined (`:32-74`) | RULE-BASED |
| HUMAN_APPROVAL_WORKFLOW | cog | 43 | In-memory PENDING→APPROVED/REJECTED state machine keyed by uuid (`:12-42`). No approver auth, no persistence | REAL |
| HFAL | cog | 61 | "Human-Friendly Auth Layer": token = sha256(user+pin)[:12], unsalted PIN hash, JSON file at `/live/agents/HFAL/sessions.db` (`:17-18,43-53`) | REAL (insecure) |
| LONG_RUN_STABILITY_SIMULATOR | cog | 61 | `stability = 100-(10·pvariance+drift)` over a supplied series (`:18-41`) | RULE-BASED |
| MCD | cog | 21 | "Master Control Dashboard": a 3-entry route dict plus string template `render()` (`:5-14`). No server | RULE-BASED (trivial) |
| ADVANCED_SEARCH_ENGINE | nai | 50 | In-memory substring search with field-count scoring (`:31-46`) | RULE-BASED |
| MULTILINGUAL_BRAIN | nai | 34 | Word-by-word dictionary substitution (`:22-30`). No dictionaries ship | RULE-BASED |
| NEURAL_CREATIVITY_ENGINE | nai | 53 | `random.choice` from 3 user-filled pools → "X performing Y in Z style". Docstring: "NOT an ML model" (`:9`) | RULE-BASED |
| LOCAL_BIOMETRICS_INTERFACE | nai | 53 | sha256 exact-string "templates". `verify` returns True when no supplied key overlaps the template (`:35-42`) | RULE-BASED (insecure) |
| LYRA | nai | 39 | 3 presets. `transform` adds ✨ or a `"[TECH]/n"` prefix (typo for `\n`, `:36`) | RULE-BASED |
| LYRA_VOICE_ENGINE | nai | 220 | Optional mic (sounddevice), Whisper ASR and pyttsx3 TTS. Keyword intent → engine name. Execution is **simulated** (`:164-170`) | RULE-BASED (ML optional, inert) |
| MODEL_REGISTRY_CANARY | nai | 79 | JSON registry `name:version` → {active, canary%, checksum} at `/live/agents/...` (`:16-78`). No traffic split, no checksum verification | REAL (trivial) |
| NEURAL_MESH | nai | 36 | `route`/`broadcast` writes context to MEMORY_FABRIC and returns `ok`. **Delivers nothing** (`:24-37`). Import fails (`:3`) | REAL (broken, hollow routing) |

(Rows that group several agents cover 2–6 identical agents each. All 131 folders are covered.)

---

## 3. Framework clusters

None of the cluster acronyms are expanded anywhere in code, docstrings or manifests. The only hints come from logger tags and debug strings. No cluster has a coordinator that calls its members. The 3 clusters with an alias "head" (ASEL, CRK, and CORE_CONVERGENCE for EOF) delegate through dead import paths. Every cluster is **just named files**.

| Cluster | Meaning per code | Members (n) | Works as a system? |
|---|---|---|---|
| AAE | "Adaptive Action Engine" (logger tag `ADAPTIVE_ACTION_ENGINE/main.py:5`) | ADAPTIVE_ACTION_ENGINE, AAE_POLICY, AAE_RUNTIME, ACTION_MODELING_CORE (4) | No. 3 HC-only, 1 hard-coded plan |
| ACF | not defined ("Context/Fusion/Router" by member name) | ACF_CORE, _CONTEXT, _FUSION, _ROUTER (4) | No. Echo methods |
| ASEL | not defined (Planner/Executor/Router/Strategist/Evaluator) | ASEL + 5 (6) | No. Head alias → `agents.ASEL_*` (dead path). Members are HC-only |
| CLBPP | not defined. Member COGNITIVE_LOAD_BALANCER suggests "Cognitive Load Balancing…" | CLBPP_CORE, _DISTRIBUTOR, _OVERLOAD_MONITOR, _PREDICTIVE_BALANCER, COGNITIVE_LOAD_BALANCER (5) | No. 4 HC-only, CLB broken import |
| CRK | not defined (Chain/Context/Intent/Reasoner/Validator) | CRK + 5 (6) | No. Same alias pattern as ASEL |
| VCAS | "Autopilot" per strings (`VCAS_AUTOPILOT:13`, `VCAS_ROUTER` returns `autopilot_route`) | CORE, AUTOPILOT, ROUTER, SUPERVISOR (4) | No. Supervisor approves everything |
| VHOE | not defined | ANALYTICS, CORE, OPTIMIZER, ROUTER (4) | No. All 12-line templates |
| VPSE | not defined ("Scenario/Modeler") | CORE, MODELER, SCENARIO (3) | No. Templates |
| MCFE | not defined. CLASSIFIER = "Domain Classifier" (`:15`), FIELDGEN = "Field Generator" | CORE, CLASSIFIER, FIELDGEN, ROUTER (4) | No. Classifier uses salted `hash()` |
| MPC | not defined (Preproc/Fusion) | CORE, FUSION, PREPROC (3) | No. Templates |
| UIE | not defined (Signal/Semantics/Reasoner) | CORE, REASONER, SEMANTICS, SIGNAL (4) | No. Echo |
| DSS | not defined. Members read as distributed-systems SRE (cluster/failover/LB/monitor/replication/scaler) | 6 | No. HC-only |
| CCSF | not defined | CORE, FUSION, RESOLVER (3) | No. Templates |
| EOF | not defined (orchestrate/gateway/policy) | CORE, GATEWAY, POLICY (3). Head alias CORE_CONVERGENCE | No. POLICY always compliant |
| EAC | not defined (Audit/Compliance) | AUDIT, COMPLIANCE, CORE (3) | No. Templates |
| CSG | logger "CSG" on COHERENCE_SYNC_CORE | COHERENCE_SYNC_CORE, CSG_STATEALIGN, CSG_TEMPORAL (3) | No |
| CSM | not defined | CORE, LINKER, POLICY, REASONER (4) | No. Echo |
| MRF | not defined (Eval/Reflect) | 2 | No |
| RCI | not defined (Context/Core/Stream) | 3 | No |
| ALK | logger "ALK" on AUTO_LEARN_CORE → "Auto-Learn K…" | AUTO_LEARN_CORE, ALK_ADAPT, ALK_EVO (3) | No. Templates, no learning |
| Coherence misc | n/a | FSCL, GCK, INTER_AGENT_COHESION (+ CODEX, which moved to `operations/`) | No |

**Implied pipelines exist only in tests.**
- `velaris/tests/test_AI_IE_layer.py:23-44`: INITIATIVE_ENGINE → INTENT_SYNTHESIZER → ACTION_MODELING_CORE → DECISION_GRAPH_ENGINE → HYPER_REASONER → RECURSIVE_GOAL_PLANNER → SELF_DIRECTED_TASKER → VELOCITY_LOOP.
- `test_layer5_neuralgov.py`: NEURAL_POLICY_MESH → ALIGNMENT → META_REINFORCEMENT → BEHAVIOR_SHAPING → GOVERNANCE_ADAPTATION_LOOP → SELF_CORRECTION → CONSTRAINT_FIELD → SANITY_VERIFIER.
- `test_layer6_quantum.py`: …CAUSALITY_RESOLVER → HYPERSTATE → DECISION_COLLAPSE.

The parameter names in the agents (`validated`, `aligned`, `optimized`, `corrected`) match these chains, so they were designed as pipelines. But each step is an echo, and the tests import `live.agents.*`, which doesn't exist. Several chain members (INITIATIVE_ENGINE, VELOCITY_LOOP, SANITY_VERIFIER, QREASON_*) live outside `_ai_core`.

---

## 4. Control hierarchy (SOUL_VELARIS → PRIME → ENGINE → ORCHESTRIX/REGISTRY)

All five live here. Real call graph: **PRIME → ENGINE → REGISTRY (+ AGENT_LIFECYCLE_MANAGER, COGNITIVE_LOAD_BALANCER imports)**.
- **SOUL_VELARIS is not called by anything.** Only the FSCL alias names it.
- **ORCHESTRIX is not called by anything.** Neither ENGINE nor PRIME imports it.

| Node | Real? | Evidence |
|---|---|---|
| SOUL_VELARIS | Stub | Returns a constant mission (`:28-30`). Its manifest promises "ethical guardrails". None exist |
| PRIME (`VelarisPrime`, `PrimeAgent` compat alias) | Logic is real but thin. **Fails at import** | `from velaris.agents.ENGINE.main import VelarisEngine` (`:3`). `velaris/agents/` has no ENGINE. The self-test targets security agents in `departments/security/{VIGILIS,CUSTOS,PRAETOR}` (`:43`) |
| ENGINE (`VelarisEngine`) | Logic is real (reflective `getattr` dispatch, sequential pipeline). **Fails at import** | `:5-7` imports. `__post_init__` (`:17-19`) is never called because the class is not a dataclass, so `lifecycle`/`clb` are never set. `run_with_balance` ignores the load balancer (`:88-90`) |
| REGISTRY (`AgentRegistry`) | Logic is real. **Breaks on construction** | `agents_path = abspath(_ai_core/../agents)` = `departments/agents` (`:24-25`), which doesn't exist → `os.listdir` raises (`:39`). See details below |
| ORCHESTRIX | Real algorithm, unused | Topo sort is correct. **Bug:** `parallel_groups` (`:55-61`) puts a task in the *first* group that lacks its direct deps. For A, B←A, C←B it yields `[[A,C],[B]]`, so C runs before its dependency B |
| Supporting: NAVARCH, SCHEDULON, STRATEGOS | Real, small, unused | Dijkstra, greedy bin-pack, linear score |
| AGENT_LIFECYCLE_MANAGER / COGNITIVE_LOAD_BALANCER | Trivial and disconnected | CLB news up its own LM (`COGNITIVE_LOAD_BALANCER:15`), so it never sees states set elsewhere |
| MCD ("Master Control Dashboard") | Not a dashboard | A dict of 3 route names and an HTML template string |

REGISTRY details. Even with the path fixed it would still fail:
1. Only 19/131 agents have a `manifest.json`.
2. The 6 "Layer 3 Self-Identity Kernel" manifests have no `entrypoint`, so `KeyError` at `:69`.
3. It imports `agents.<name>` (`:72`), a root that doesn't exist.
4. `create()` passes a positional config (`:80`), which raises TypeError for no-arg classes.

**Alias layer.** "Safe delegator generated by velaris_fix_alias_layers.sh"; the script is not in the repo. Covers AEIL, ASEL, CORE_CONVERGENCE, CRK, FSCL, GCK. Problems:
- They import non-existent roots.
- They swallow every error (`except Exception: continue`).
- Even when a module loads, they call `health_check`/methods on the *module*, not a class instance. Those are class methods, so delegation can never work, and they fall back to a constant `ok`.
- The test `velaris/tests/test_alias_layers.py` checks only that `"agent" in h`.

---

## 5. Notable components in detail

**LYRA_VOICE_ENGINE** (`LYRA_VOICE_ENGINE/main.py`, 220 LOC, the only non-trivial "AI" file)
- Optional deps via try/except (`:11-24`): `sounddevice`, `pyttsx3`, `whisper`. None are installed or in `requirements.txt`.
- `LyraVoiceConfig` (`:26-33`) defaults to `mode="mock"`, `asr_backend=None`.
- Whisper `"small"` loads only if `asr_backend=="whisper"` (`:51-55`).
- `listen()` records `recording_seconds` of 16 kHz mono int16 via `sd.rec` (`:60-72`).
- `transcribe()`:
  - mock mode returns `"mock command <sha256(wake_word)%1000>"`, a constant (`:75-77`)
  - real mode writes a temp WAV and calls `model.transcribe` (`:82-98`). `np` arr is computed and unused (`:84-85`)
  - all errors → `""`
- `speak()` uses pyttsx3, else falls back to `print` (`:103-115`).
- `interpret_intent()` is keyword `if/elif` routing (`:117-135`): infra/server/vm → it_infra, balance/grid → grid, status/health → itsm, simulate/portfolio → portfolio, else customer.
- `run_once()` maps the domain to an engine name (`IT_INFRA_ENGINE`, `GRID_BALANCE_ENGINE` (archived), `ITSM_ENGINE`, `PORTFOLIO_SIM_ENGINE`, `CUSTOMER_BEHAVIOR_ENGINE`) and **returns a fabricated "Simulated execution" result without calling anything** (`:157-173`).
- `run_loop()` accepts an external `handler` callback (`:175-205`), which is the one real integration seam.
- The wake word is never checked.
- Verdict: a working voice I/O shell with keyword NLU. ML-capable only if someone installs Whisper and sets the backend. No downstream wiring.

**LYRA** (personality engine): 3 presets, string decoration only. It is not connected to LYRA_VOICE_ENGINE.

**Memory.** `MEMORY_FABRIC` is *not* in `_ai_core`; it's in `departments/data_knowledge/MEMORY_FABRIC`. In this scope, memory amounts to:
- in-memory lists/dicts: SELF_HISTORY, SELF_IDENTITY, AGENT_EVOLUTION.history
- two broken consumers: NEURAL_MESH, INTER_AGENT_COHESION
- JSON files under hard-coded `/live/agents/*`: HFAL, AUTONOMOUS_PATCH_ENGINE, MODEL_REGISTRY_CANARY

No vector store. LOCAL_EMBEDDING_ENGINE returns 1 int. QUANTUM_BRIDGE is in `_archived_domains/research_simulation/`, outside scope.

**Learning.** None.
- ALK_*/AUTO_LEARN_CORE/META_REINFORCEMENT_CORE/MRF_* are templates or echoes.
- AGENT_EVOLUTION's "proposal" is `len(records)>5`.
- NEURAL_DRIFT_MONITOR echoes.

**Security-relevant (real but weak)**
- HFAL: deterministic 12-hex token from user+PIN and an unsalted SHA-256 PIN, so anyone who knows user+PIN can derive the token. Bare `except:` (`:32`).
- LOCAL_BIOMETRICS_INTERFACE: `verify(user, {})` returns **True**, an auth bypass (`:38-42`). Matching is exact-hash, so real biometric samples would never match.
- HUMAN_APPROVAL_WORKFLOW: anyone can pass any `approver` string. State is lost on restart.
- Many agents log full payloads at DEBUG on a StreamHandler (EOF_GATEWAY `:16`, NEURAL_MESH `:27`, ENGINE `:52,65`). That's a data-leak risk if they're ever wired up.
- Bare `except:` also appears in AUTONOMOUS_PATCH_ENGINE `:29` and MODEL_REGISTRY_CANARY `:30`.

---

## 6. Plane mapping

| Plane | Agents in `_ai_core` | Reality |
|---|---|---|
| Control / orchestration | PRIME, ENGINE, REGISTRY, ORCHESTRIX, SCHEDULON, NAVARCH, STRATEGOS, EOF_*, CORE_CONVERGENCE, VCAS_* | Real algorithms exist in ORCHESTRIX, NAVARCH and SCHEDULON. The control chain fails at import. Nothing is wired to the entry point |
| SDLC | AUTONOMOUS_PATCH_ENGINE, AGENT_EVOLUTION, alias layer | Dict patching only. No code generation or CI |
| STLC | ~110 tests in `velaris/tests` (e.g. `test_layer25_aae.py`, `test_engine.py`, `test_orchestrix.py`), LONG_RUN_STABILITY_SIMULATOR | Tests assert `health_check()=="ok"` or echo shapes. Import roots `agents.`/`live.agents.`/`velaris.agents.X` are missing. pytest isn't installed. 0 runnable |
| SRE / observability | DSS_* (6), CLBPP_* (5), NEURAL_DRIFT_MONITOR, LONG_RUN_STABILITY_SIMULATOR, `health_check` on 121 agents | Every health_check returns a constant `"ok"`, which is not a signal. DSS and CLBPP are hollow |
| Compliance / governance | EAC_* (3), EOF_POLICY, SOUL_VELARIS, VCAS_SUPERVISOR, NEURAL_POLICY_MESH, HUMAN_APPROVAL_WORKFLOW | Hollow or always-approve. HUMAN_APPROVAL is the only real HITL primitive (in-memory) |
| Security / identity | HFAL, LOCAL_BIOMETRICS_INTERFACE, SELF_IDENTITY | Real but insecure (see §5) |
| Deployment / release | MODEL_REGISTRY_CANARY | Bookkeeping only. No rollout or traffic split. Hard-coded `/live` paths assume an unexisting container layout |
| Admin control | MCD, PRIME.system_status, AGENT_LIFECYCLE_MANAGER, HUMAN_APPROVAL_WORKFLOW | No UI and no HTTP. MCD is a dict |
| API management | EOF_GATEWAY, ACF_ROUTER, VCAS_ROUTER, VHOE_ROUTER, MCFE_ROUTER, ASEL_ROUTER, NEURAL_MESH | No HTTP server, auth, rate limiting or schema anywhere in scope. Routers echo |
| Business-function | LYRA_VOICE_ENGINE (routes to it_infra/itsm/finance/marketing engine *names*), AEIL (→ finance/executive econ agents), STRATEGOS | Simulated or dead |
| Data / knowledge | ADVANCED_SEARCH_ENGINE, AUTONOMOUS_RESEARCH_ENGINE, MULTILINGUAL_BRAIN, LOCAL_EMBEDDING_ENGINE, MCFE_CLASSIFIER, INTER_AGENT_COHESION | In-memory substring search. Fake embedding and classifier |
| Persona / self-model | SOUL_*, SELF_*, PERSONALITY_MOD, CONTEXTUAL_SELF_MODEL, LYRA | Stubs plus 2 trivial dicts |
| LLM / AI inference | none | **No LLM layer, confirmed.** Only optional, inert Whisper/pyttsx3 |

---

## 7. Reality check vs README

| README claim | Finding |
|---|---|
| "343 domain-classified agents… one unified intelligence layer" | `_ai_core` holds 131 of them. 79% are STUB. The runtime router loads **0** agents (`python3 main.py` prints "Agents loaded : 0") |
| Hierarchy SOUL_VELARIS → PRIME → ENGINE → ORCHESTRIX/REGISTRY | SOUL and ORCHESTRIX aren't connected. PRIME→ENGINE→REGISTRY exists in code but can't import or construct |
| Cross-domain frameworks ACF/AAE/ASEL/CLBPP/CRK/VCAS/VHOE/VPSE/MCFE/MPC/UIE/DSS/CCSF/EOF "upgraded" (HEAD commit msg) | 74 framework files, 0 with real logic (CLB is the exception and is broken). No acronym is defined. No cluster has working intra-cluster calls |
| "LYRA voice" (README:81) | Voice I/O shell exists. ASR/TTS are optional and uninstalled, default is mock, and execution is simulated |
| "model registry canary", "local biometrics" (README:81) | Both exist as small JSON/in-memory classes. Canary has no rollout. Biometrics is insecure |
| `main.py` "boots ENGINE" (README:133) | It doesn't. `main.py` boots `velaris/backend/engine.py` → router, not `_ai_core/ENGINE` |
| Prior audit "~39% stubs, no LLM layer" | No LLM layer: confirmed. Stub rate for **this slice is ~79% by count (55% by LOC)**, much worse than the repo-wide 39% |

---

## 8. Open questions

1. Where was the original `/live/agents/` (or `agents/`) package root that every import, the REGISTRY path, and the `/live/agents/*` data dirs assume? Is the reorg meant to add a shim (e.g. `velaris/agents/__init__` path hook pointing at `departments/*`)?
2. Does `velaris_fix_alias_layers.sh` exist anywhere? It generated the 6 broken alias wrappers.
3. Acronym meanings (ACF, ASEL, CLBPP, CRK, VCAS, VHOE, VPSE, MCFE, MPC, UIE, DSS, CCSF, EOF, EAC, CSG, CSM, MRF, RCI, FSCL, GCK, AEIL, AIIE) aren't defined in code. Is there a design doc outside the repo?
4. Why do only 19 of 131 agents have manifests when REGISTRY discovery depends on them? Were manifests lost in the `Canonical_final` merge (HEAD `142153b`)?
5. Should `_ai_core` be committed as is? It's untracked. The 9 dropped HEAD duplicates differed in content; confirm which copy was intended.
6. Is LYRA_VOICE_ENGINE meant to call the real `departments/*` engines via `run_loop(handler=...)`? Nothing supplies a handler today.
