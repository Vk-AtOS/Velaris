# V1: Runtime Spine, Reorg & Platform Integration

Scope: `main.py`, `README.md`, `requirements.txt`, `docs/`, `velaris/` package, the uncommitted `domains/ → departments/` reorg, and the Knackforge platform integration (`company_ops`, `knackforge_platform/velaris`, `router/velaris_integration`, `shared/event_bus.py`, compose/nginx) plus the AetherOS marketing page.
Repo state: HEAD `142153b` (3 commits total). Working tree has 810 deletions under `domains/` and new untracked `departments/`, `_archived_agents/`, `_archived_domains/`. Everything below describes the working tree unless it says HEAD.

---

## 1. Summary

- **The runtime spine is disconnected from the agents and loads 0 agents.** `python3 main.py` prints `Agents loaded : 0`, `Status : online`. `velaris/agents/router.py:16-27` scans only its own folder, `velaris/agents/`, which holds just `router.py`. It never looked at `domains/` (HEAD) and it doesn't look at `departments/` now. This isn't caused by the reorg; it was already broken at HEAD.
- **The real spine lives inside the agent tree, and it can't import.** `departments/_ai_core/{PRIME,ENGINE,REGISTRY,ORCHESTRIX,SOUL_VELARIS}` are small, real Python classes. They are written for a flat `live/agents/<NAME>/` layout, imported as `velaris.agents.<NAME>.main` or `agents.<NAME>.main`, and neither of those exists. `REGISTRY` raises `FileNotFoundError: departments/agents` when instantiated (verified). `ENGINE`, `PRIME` and `COGNITIVE_LOAD_BALANCER` fail at import (`velaris.agents.*` is missing).
- **The `velaris/` package is thin.** `engine.py`, `flow_engine.py`, `mesh.py` (an in-process dict), `secure.py` (always returns True) and `core/*` (Phase-1 bootstrap logging) total about 260 LOC. It has no HTTP API, no CLI beyond `main.py`, no scheduler, no persistence and no LLM client. requirements.txt lists only `psutil` and `cryptography`, and nothing in `velaris/` imports either one.
- **Tests: 0 pass.** Plain `pytest velaris/tests`: 72 collection errors (`No module named 'velaris'`). With `PYTHONPATH=.`: 48 failed, 70 errors, 0 passed. The tests target four import roots that don't exist (`velaris.agents.<X>`, `live.agents.<X>`, `agents.<X>`, `velaris.agents.agents.*`) and APIs that don't exist (`router.subscribe`, `backend.process`).
- **Reorg:** 343 old agent dirs (19 domains) map to 326 dirs in 16 departments plus 42 archived (368 total). All 343 old names survive. There are 22 new agents (HR, Zoho, comms, PM, ops). Only 106 of the 326 department dirs have a `manifest.json`, so a manifest-driven registry would miss 220. Nothing in Python references `domains/`; only README.md does (stale). The reorg breaks `connectors.*` imports (the folder is `_connectors`), and docs/README counts are stale (docs say 243, README says 343 in `domains/`).
- **Platform:** the only deployed Velaris-like runtime is `company_ops`, a separate FastAPI app on :8100 behind nginx `/api/ops/`. It runs an **older 168-agent copy** (`company_ops/{core,domains,connectors}`), not this repo. `bootstrap.py` reports 168/168 importable. But `POST /agents/{name}/run` does `await instance.run(payload)`, and **no agent has an async `run`** (14 have a sync `run`, the rest have none), so the endpoint returns 500 for every agent. It has no auth (nginx sets none, CORS `*`) and doesn't enforce `hitl_required`. `knackforge_platform/velaris/` is a byte-identical copy of the working tree (Zoho connectors moved to the top-level `_connectors/`), and nothing builds or mounts it. `router/velaris_integration/*` imports from `~/Desktop/Velaris_CORE_V11`, a path that doesn't exist, so it silently falls back to inline **mock classes**, and its "insights" are hard-coded formulas. The event-bus subject `velaris.insight` is declared but has no publishers or subscribers.
- **LLM layer: absent.** No anthropic/openai/bedrock client in the spine or the agents. The only hook is `MEETING_SUMMARIZER`'s optional `config["llm_callable"]`, which nothing wires up. `CALL_TRANSCRIBER` and `LYRA_VOICE_ENGINE` optionally import Whisper, pyttsx3 and sounddevice (local ASR/TTS, guarded by try/except).
- Prior-audit check: 343 main.py at HEAD ✔ (confirmed: `git ls-tree` shows 343 `domains/**/main.py`). "No LLM layer" ✔. "Real core_brain" is only **partly true**: the classes are real but can't run in place. LYRA real Whisper+TTS ✔ (optional imports, 220 LOC). I didn't re-measure the 39% stub figure; that belongs to the agent-plane workers.

## 2. Coverage table

| File | LOC | Purpose | Tag |
|---|---|---|---|
| `main.py` | 20 | Prints `backend.status()` banner ("VELARIS CORE V11 — ONLINE") | REAL but trivial (shows 0 agents) |
| `README.md` | 174 | Vision, hierarchy diagram, 343-agent domain table, `domains/` tree | Stale: describes the `domains/` layout; claims status `active` (code returns `online`, engine.py:24) |
| `requirements.txt` | 2 | psutil, cryptography | DEAD (no spine import uses either; cryptography is used by 3 security agents) |
| `docs/domain_map.md` | 249 | Agent→domain table, "243 agents" (docs/domain_map.md:3) | Stale (pre-commit-142153b count, old domain names) |
| `velaris/__init__.py` | 0 | package marker | n/a |
| `velaris/agents/router.py` | 50 | `AgentRouter`: importlib-scan `velaris/agents/*/main.py`; `publish()` fans out `on_event` | RULE-BASED, effectively HOLLOW: scans an empty folder (router.py:16), swallows errors (router.py:25-27, 45-46) |
| `velaris/backend/engine.py` | 30 | `BackendEngine` list/get/status wrapper over router | REAL wrapper, HOLLOW result |
| `velaris/backend/flow_engine.py` | 28 | `run_flow(name, steps: list[callable])`: call each step, store in mesh, `router.publish('flow_engine_out')` | RULE-BASED (sequential callable runner) |
| `velaris/core/config.py` | 21 | PROJECT_ROOT, `resolve_path`, version `0.1-phase1-bootstrap` | REAL, unused by spine |
| `velaris/core/exceptions.py` | 21 | VelarisError hierarchy | REAL, only `ModuleLoadError` used (loader.py) |
| `velaris/core/loader.py` | 20 | `safe_import`, `initialize_core()` (logs only) | `safe_import` REAL; `initialize_core` STUB. Nothing calls it |
| `velaris/core/main.py` | 23 | `velaris_start()`: logs "ready for Phase-2" | STUB/DEAD (not called from main.py) |
| `velaris/core/utils.py` | 26 | sha256_of_file, file_exists, `log()` = print | REAL |
| `velaris/memory/mesh.py` | 26 | `MemoryMesh`: dict get/set/delete, prints values (mesh.py:13) | RULE-BASED in-proc KV; no persistence; logs every value (data-leak risk) |
| `velaris/security/secure.py` | 21 | `validate()` / `integrity_check()` always `True` (secure.py:12-20) | STUB/HOLLOW |
| `velaris/tests/*.py` | 105 files, ~2.4k LOC | 237 `test_` funcs; 15 files are `run_test()` harnesses with no test funcs | DEAD (0 pass; see §9) |
| `departments/_ai_core/SOUL_VELARIS/main.py` | 31 | `Soul`: identity dict, `get_intent()` returns a fixed mission | TEMPLATE/STUB (says "stub" at :17, :29) |
| `departments/_ai_core/PRIME/main.py` | 62 | `VelarisPrime`: wraps ENGINE; `system_status`, `run_simple_self_test`, `execute` | REAL glue; can't import (:3 `velaris.agents.ENGINE`) |
| `departments/_ai_core/ENGINE/main.py` | 91 | `VelarisEngine.run(agent, method, params)`, `pipeline(steps)` | REAL dynamic dispatch; can't import (:5-7). `__post_init__` (:17) is never called (not a dataclass) → lifecycle/CLB DEAD. `run_with_balance` is a passthrough (:88-90) |
| `departments/_ai_core/REGISTRY/main.py` | 91 | `AgentRegistry`: `listdir(<parent>/../agents)`, reads `manifest.json`, imports `agents.<NAME>.<module>` | REAL logic, wrong layout: path resolves to `departments/agents` → FileNotFoundError (verified) |
| `departments/_ai_core/ORCHESTRIX/main.py` | 66 | `resolve_dependencies` (DFS topo sort, cycle detect), `parallel_groups` | REAL, RULE-BASED, self-contained (only spine piece that works standalone). Note: `parallel_groups` only checks deps inside the same group, not ordering across groups |
| `departments/_ai_core/SCHEDULON/main.py` | 50 | round-robin `distribute_load`, min-load slot | RULE-BASED (not a time scheduler) |
| `departments/_ai_core/AGENT_LIFECYCLE_MANAGER/main.py` | 29 | in-mem state dict | RULE-BASED |
| `departments/_ai_core/COGNITIVE_LOAD_BALANCER/main.py` | 29 | pick first "active" candidate | RULE-BASED; can't import (:5) |
| `departments/_ai_core/HUMAN_APPROVAL_WORKFLOW/main.py` | 43 | in-mem approve/reject requests | RULE-BASED; not wired to anything |
| `knackforge_platform/company_ops/main.py` | 80 | FastAPI: `/health`, `/agents`, `POST /agents/{n}/run`, `/connectors/zoho/status` | REAL service; `run` is broken for every agent (main.py:60, `await` on a sync/missing method) |
| `company_ops/bootstrap.py` | 101 | os.walk manifests + `spec_from_file_location` import check | REAL |
| `company_ops/gen_manifests.py` | 52 | One-shot manifest generator, hardcoded `/Users/apple/Desktop/acq2` (:7) | DEAD (dev script, wrong path) |
| `company_ops/Dockerfile` | 20 | py3.11-slim, uvicorn :8100 | REAL |
| `router/velaris_integration/main.py` | 54 | FastAPI "Velaris Business Autopilot" (:8500 per docstring) `/autopilot/status|trigger` | REAL but not in compose |
| `router/velaris_integration/autopilot.py` | 173 | SQLite loop: auto-send HIGH drafts via WhatsApp, escalate MEDIUM, flag stalls | RULE-BASED, REAL side effects (`bypass_limit=True` :81). Not Velaris agents at all |
| `router/velaris_integration/{cashflow,converta,retenta,logista}_connector.py` | 49-69 | "Velaris" analysis for GAIA heartbeat | TEMPLATE/HOLLOW: import from a missing path → mock class; hard-coded formulas (e.g. cashflow :49-51 `500000*(avg/0.7)`, trend `"+12%"`) |
| `router/velaris_integration/velaris_dashboard_server.py` | 92 | Dashboard API, MockBackend fakes 243 agents (:24); activate/deactivate return canned success (:73-79) | STUB/HOLLOW |
| `router/velaris_integration/business_autopilot_wiring.py` | 57 | business_type→agent list if/else | RULE-BASED |
| `shared/event_bus.py` | 120 | NATS JetStream wrapper; subject `velaris.insight` (:40) | REAL bus; Velaris subject DEAD (0 pub/sub) |

## 3. Runtime architecture (README hierarchy vs code)

| README layer | In code? | Where | State |
|---|---|---|---|
| SOUL_VELARIS | Yes | `departments/_ai_core/SOUL_VELARIS/main.py:12` `Soul` | Stub. Fixed mission string. Nothing calls it (PRIME doesn't reference SOUL) |
| PRIME | Yes | `departments/_ai_core/PRIME/main.py:10` `VelarisPrime` (+ alias `PrimeAgent` :50) | Glue over ENGINE; import broken |
| ENGINE | **Two**: (a) `velaris/backend/engine.py:12` `BackendEngine` (wired to main.py); (b) `departments/_ai_core/ENGINE/main.py:16` `VelarisEngine` (run/pipeline) | (a) works, 0 agents; (b) can't import |
| ORCHESTRIX | Yes | `departments/_ai_core/ORCHESTRIX/main.py:10` | Works standalone. Neither engine calls it |
| REGISTRY | **Two**: (a) `velaris/agents/router.py` (folder scan, no manifest); (b) `departments/_ai_core/REGISTRY/main.py` (manifest-driven) | (a) empty; (b) FileNotFoundError |
| Domain agents | 326 dirs in `departments/*` | see §6 | Not reachable from any spine |

So the README's top-down chain (SOUL→PRIME→ENGINE→ORCHESTRIX/REGISTRY→agents) doesn't exist as running code. SOUL is never linked, ORCHESTRIX is never invoked by ENGINE, and the wired path (`main.py→BackendEngine→AgentRouter`) leads to nothing.

## 4. Agent contract

There is **no base class.** `velaris/agents/agents/base.py` (`BaseAgent`, imported by tests) doesn't exist. The de-facto contract has four parts:
- **Layout:** `departments/<dept>/<AGENT_NAME>/{__init__.py, main.py[, manifest.json]}`.
- **Class:** one class per main.py with a ctor that takes `config: Dict | None` (ENGINE/REGISTRY call `cls(config or {})`, REGISTRY:80; company_ops calls `cls()` with no args, main.py:59). It has a `health_check() -> {"agent", "status":"ok", ...}`, and domain methods are free-form (no common `run`).
- **Manifest** (106 of 326 department dirs), in 4 schemas:
  - 66 × `{name, display_name, version, description, owner, entrypoint "main.py:Class", health_check}`. Many say "Auto-generated placeholder" (e.g. `departments/finance/CASHFLOW_AI/manifest.json`).
  - 21 × `{name, version, domain, entrypoint, description, hitl_required[, tags]}`. This is the company_ops/gen_manifests style (e.g. `hr/PAYROLL_ENGINE`).
  - 19 × `{name, version, author, description}`, which has **no entrypoint**, so REGISTRY's `.split(":")` would KeyError (e.g. `legal_compliance/GOVERNANCE_KERNEL`).
  - 220 dirs have no manifest at all.
- **Invocation:** ENGINE `run(agent, method, params)` → `getattr(inst, method)(**params)`. company_ops expects `async run(payload: dict)`, which no agent implements. router.py expects module-level `on_event(event, data)`, which none implement.

## 5. Control and data flow

- **Wired path (works, does nothing):** `main.py:5` → `velaris.backend.engine.backend` → `AgentRouter()` scans `velaris/agents/*/main.py` (empty) → `status()` = `{online, 0, []}`.
- **FlowEngine:** `flow_engine.run_flow(name, [callables])` runs each callable sequentially and catches per-step errors into `{'error'}` (flow_engine.py:18-25). It then writes `mesh['flow:<name>:results']` and `router.publish('flow_engine_out')`, which no-ops because there are no agents. It is not connected to agents, ORCHESTRIX or ENGINE, and nothing in the repo calls it except a broken test.
- **Intended spine (dead):** `PRIME.execute` → `VelarisEngine.run` → `AgentRegistry.create` → `importlib("agents.<NAME>.main")` → method call. `pipeline()` is a sequential loop with no error isolation (ENGINE:79-84).
- **State:** in-process only (MemoryMesh dict, LifecycleManager dict, HumanApproval dict). Some agents use sqlite (12 `import sqlite3`) or write to `/live/agents/<NAME>` absolute paths (e.g. `security/SECRETS_VAULT/main.py:10`, `security/SIGNED_AUDIT_CHAIN/main.py:11`, `_ai_core/HUMAN_APPROVAL_WORKFLOW/main.py:7`), which don't exist on this machine.
- **Interfaces:** no HTTP API in this repo. CLI = `python main.py` and `python -m velaris.core.main` (logging only). No scheduler or cron (SCHEDULON is a load splitter). No queue or event bus (router.publish is a synchronous in-proc loop).

## 6. Reorg mapping (HEAD `domains/` → working tree)

HEAD has 343 agent dirs across 19 `domains/*` (file counts: frameworks 186, operations 91, security 71, finance 58, neural_ai 48, core_brain 41, infrastructure 38, cognition 37, memory_knowledge 34, business_intelligence 34, sales_crm 32, research_simulation 31, marketing_brand 30, ethics_governance 20, agri_environment 16, self_management 15, local_offline 14, healthcare 10, real_estate 4). The working tree has 326 dirs in `departments/` plus 42 in archive = 368. 11 names were duplicated across old domains; 14 names are duplicated in the new tree (duplicates in `_archived_agents/_duplicates`).

| Old domain (agents) | New location (agents) |
|---|---|
| core_brain (14) | `_ai_core` 14 |
| cognition (18) | `_ai_core` 18 (3 also in `_archived_agents/_duplicates`) |
| self_management (5) | `_ai_core` 5 |
| neural_ai (22) | `_ai_core` 22 (2 dup-archived) |
| frameworks (83) | `_ai_core` 81, `operations` 1, `project_management` 1 (15 dup-archived) |
| security (29) | `security` 29 |
| finance (23) | `finance` 23 |
| business_intelligence (12) | `executive` 12 |
| sales_crm (12) | `sales` 11, `client_success` 1 |
| marketing_brand (12) | `marketing` 11, `sales` 1 (+ `_archived_agents/_misplaced/AUTONOMOUS_SALES_NAVIGATOR_from_marketing_brand`) |
| ethics_governance (8) | `legal_compliance` 7, `_archived_agents/_stubs/ETHICAL_ENGINE` 1 |
| memory_knowledge (13) | `data_knowledge` 13 |
| infrastructure (18) | `it_infrastructure` 18 |
| local_offline (6) | `it_infrastructure` 6 |
| operations (40) | `operations` 21, `project_management` 10, `supply_chain` 6, `it_infrastructure` 2, `hr` 1 |
| research_simulation (13) | `_archived_domains/research_simulation` 11, `project_management` 2 |
| healthcare (5) | `_archived_domains/healthcare` 5 (3 also in `_archived_agents/_healthcare`) |
| agri_environment (8) | `_archived_domains/agri_environment` 8 |
| real_estate (2) | `_archived_domains/real_estate` 2 |

- **New department sizes:** `_ai_core` 131, `security` 29, `it_infrastructure` 26, `operations` 24, `finance` 23, `project_management` 14, `sales` 13, `data_knowledge` 13, `executive` 12, `marketing` 11, `hr` 8, `legal_compliance` 7, `supply_chain` 6, `_connectors` 4, `communications` 4, `client_success` 1.
- **22 new agents (not in HEAD):** ACTION_ITEM_EXTRACTOR, CALL_RECORDER, CALL_TRANSCRIBER, MEETING_SUMMARIZER (communications); ATTENDANCE_MONITOR, EMPLOYEE_METRICS_ENGINE, EMPLOYEE_ONBOARDING, LEAVE_MANAGEMENT, PAYROLL_ENGINE, PERFORMANCE_REVIEW_ENGINE, RECRUITMENT_ATS (hr); OPS_REPORT, SLA_MONITOR, PIPELINE_MONITOR (ops); SPRINT_PLANNER, TIME_TRACKER (PM); WHATSAPP_BRIEFING (sales); ZOHO_CONNECTOR/PAYROLL/PEOPLE/PROJECTS (`_connectors`); plus the renamed `AUTONOMOUS_SALES_NAVIGATOR_from_marketing_brand`. These are 60-210 LOC each and mostly RULE-BASED. Zoho uses real urllib OAuth (`_connectors/ZOHO_CONNECTOR/main.py:38-79`). WhatsApp uses Graph API via optional aiohttp (`sales/WHATSAPP_BRIEFING/main.py:79-93`).
- **Dropped:** nothing was deleted outright. Healthcare, agri, real_estate and most of research_simulation were archived. `_archived_domains/research_simulation/README.md` is the only README in the new trees. 24 `__pycache__` dirs were committed into the untracked trees (`.gitignore` covers them, but they're present on disk).

**Breakages:**
1. Nothing in Python references `domains/` (grep shows hits only in README.md:141-160). The reorg doesn't break any Python path string, **because none of the loaders ever pointed at `domains/` in the first place.**
2. `from connectors.ZOHO_*` (`_connectors/ZOHO_PAYROLL/main.py:5`, `ZOHO_PEOPLE:5`, `ZOHO_PROJECTS:6`, `hr/PAYROLL_ENGINE/main.py:6`, `hr/EMPLOYEE_METRICS_ENGINE:18-20`, `hr/ATTENDANCE_MONITOR:16`): the folder is `_connectors`, so there is no `connectors` package and these imports fail. In company_ops the folder is `connectors/`, so they work there. PAYROLL_ENGINE imports at module top, so it fails to load in this repo.
3. 19 `velaris.agents.<X>` imports remain (ENGINE, PRIME, COGNITIVE_LOAD_BALANCER, INTER_AGENT_COHESION, NEURAL_MESH, and the alias delegators CORE_CONVERGENCE/AEIL/HYPERSYNC/NIRVANA/SANDE/SAGE/CONVERGENCE_BRIDGE `import_module(f"velaris.agents.{comp}.main")`). They were broken before and after the reorg.
4. REGISTRY assumes a flat `<root>/agents/<NAME>` layout, but `departments/<dept>/<NAME>` is two levels deep, so it can't discover agents even if the path were fixed.
5. README and docs describe `domains/` and inconsistent totals (243 / 343). There's no doc for the 16 departments.

## 7. Platform integration

| Component | What | Port/route | Notes |
|---|---|---|---|
| `company_ops` | FastAPI over the **acq2** agent copy (`company_ops/core` 11 + `domains/` 153 in 12 folders: client_services, cognition, communications, delivery, finance, hr, intelligence, memory, neural_ai, operations, sales_crm, security + `connectors/` 4 = 168 manifests, 169 main.py) | :8100 internal; nginx `location /api/ops/` → `company_ops:8100` (nginx.conf:51-52, 139-144); Prometheus job (prometheus.yml:32-34); compose service (docker-compose.yml:267-289), DB `postgresql…/company_ops` (:275) | Not this repo: older layout with a domain-per-folder taxonomy that differs from `departments/`. The Dockerfile copies only `company_ops/`, `shared/`, `security/`. DATABASE_URL is unused by main.py. httpx is used only for the Zoho tokeninfo check (main.py:70-78; passes the refresh token as `access_token`, so the check is semantically wrong) |
| Endpoints | `GET /health`; `GET /agents` (walks manifests, imports **every agent on every request**, main.py:35-36); `POST /agents/{name}/run` (main.py:45-64); `GET /connectors/zoho/status` | via `/api/ops/*` | `run` fails for all agents. No auth on `/api/ops/` (no auth_request; nginx only rate-limits with burst 30). CORS `*` (main.py:20-25). `hitl_required` is printed by bootstrap (:83-84) but never enforced. Agent import executes arbitrary module code in the API process |
| `knackforge_platform/velaris/` | Copy of the working tree (`departments/`, `_archived_*`, `velaris/`, docs) without `.git`. Only diff: Zoho connectors live in top-level `velaris/_connectors/`, and `departments/_connectors/` is empty | none | Not referenced by compose, Dockerfiles or Python (grep). Orphan copy |
| `router/velaris_integration/` | Autopilot (SQLite + WhatsApp) + 4 "connectors" used by `router/src/core/heartbeat.py:24-28,52-55` | Autopilot app says :8500 but isn't in compose | Imports `velaris.agents.<X>` from `VELARIS_ROOT` (default `~/Desktop/Velaris_CORE_V11`, which **doesn't exist**) → mock fallbacks. Insights shown in GAIA briefings are hard-coded heuristics, not agent output |
| Event bus | `shared/event_bus.py:40` `velaris.insight` | NATS :4222 | No producer or consumer anywhere (grep) |
| Compose/nginx "velaris" | none | none | The only Velaris-flavoured service is `company_ops` |

## 8. Plane mapping (spine/integration view)

| Plane | Status | Evidence |
|---|---|---|
| Vision/goal | Doc only | README.md:1-5, 119-125 ("organisational brain", pairs with AetherOS) |
| Framework/architecture | Partial, broken | §3: spine classes exist but don't connect |
| Orchestration | RULE-BASED, unwired | ORCHESTRIX topo sort; ENGINE.pipeline sequential; FlowEngine callable loop |
| LLM / AI reasoning | **Absent** | no LLM client; MEETING_SUMMARIZER `llm_callable` hook unused. Platform `shared/llm_client.py` exists but Velaris doesn't use it |
| Memory | Toy | MemoryMesh dict (mesh.py) |
| SDLC | **Absent** in repo (no CI, no .github, no build, no versioning beyond 3 commits). company_ops README claims a "delivery" domain (AUTONOMOUS_PATCH_ENGINE, ROLLBACK_ENGINE), which is agent-level only |
| STLC (testing) | Present but dead | 105 test files, 0 passing (§9); no pytest config/conftest |
| SRE/observability | Platform only | company_ops `/health` + compose healthcheck + Prometheus scrape. Nothing in velaris itself (print-logging) |
| Security | STUB in spine | `secure.py` always True; agents' security dept is a separate audit. company_ops has no auth |
| Compliance / HITL | Declarative only | `hitl_required` flags in 21 manifests (8 true in company_ops); HUMAN_APPROVAL_WORKFLOW in-mem; no enforcement in any runner |
| Deployment | Platform only | company_ops Dockerfile + compose + nginx. Velaris repo has no Dockerfile |
| Admin control | **Absent** (dashboard server activate/deactivate are canned, velaris_dashboard_server.py:73-79) |
| API management | Minimal | company_ops 4 endpoints behind nginx rate-limit; no versioning, auth, schema or keys |
| Scheduling | **Absent** (autopilot docstring says "every 30 minutes", autopilot.py:5, but no loop or cron in that file; only the manual `/autopilot/trigger`) |
| Integrations | Real-ish | Zoho OAuth (urllib), WhatsApp Graph API (optional aiohttp), Whisper/pyttsx3 (optional) |
| Business functions | Agent dirs per department (§6); not reachable via the spine. company_ops can list them but not run them |

## 9. Test results

- `python3 -m pytest velaris/tests -q`: Python 3.14 has no pytest module. With `/usr/local/bin/pytest` (pytest 9.0.2): **72 collection errors, interrupted** (`ModuleNotFoundError: No module named 'velaris'`, because tests put `velaris/` rather than the repo root on sys.path).
- `--continue-on-collection-errors`: **48 failed, 72 errors, 0 passed**.
- `PYTHONPATH=. … --continue-on-collection-errors`: **48 failed, 70 errors, 0 passed**. Top causes: `live` ×18, `velaris.agents.agents` ×8, `velaris.core_agents` ×7, `velaris.agents.<NAME>` ×~30, `agents.<NAME>` ×~25.
- Import roots used by tests: `velaris.agents.<X>` 58, `live.agents.<X>` 53, `agents.<X>` 44, `velaris.agents.agents.*` 18. None of them exist in HEAD or in the working tree. The tests were written for an earlier `live/agents/` flat tree (V11) and never fixed. API drift: `router.subscribe` and `backend.process` (test_backend_engine.py, test_flow_engine.py) don't exist. 15 files are `run_test()` harnesses that pytest never runs.
- `python3 main.py` runs: 0 agents, status `online`.
- `company_ops/bootstrap.py` (run with PYTHONDONTWRITEBYTECODE=1): 168 manifests, 14 domains, Import OK 168, "READY". That only proves module load plus class presence, not behaviour.

## 10. Reality check vs claims

| Claim | Source | Reality |
|---|---|---|
| "343 domain-classified agents" | README.md:3 | 343 dirs at HEAD; 326 active + 42 archived now. Runtime loads **0** |
| `python main.py` shows all agents loaded, "Status: active" | README.md:99-105 | 0 loaded, "online" |
| SOUL→PRIME→ENGINE→ORCHESTRIX/REGISTRY hierarchy | README.md:11-30 | Classes exist; chain not connected; ENGINE/PRIME/REGISTRY can't import |
| "REGISTRY · Manifest Discovery" | README.md:29 | Manifest REGISTRY points to a nonexistent path; 220/326 dirs lack a manifest; 19 manifests have no entrypoint |
| "velaris/core: ModelInterface + Startup" | README.md:137 | No ModelInterface exists; core is config/log/safe_import |
| "agents/router.py dynamic agent discovery" | README.md:140 | Discovers its own empty folder |
| "~60% fully implemented" | README.md:115 | Not measured here (agent workers); irrelevant at runtime because none load |
| docs: 243 agents | docs/domain_map.md:3 | stale |
| company_ops: "brain discovers and runs all agents dynamically via manifest.json — one call, any domain" | company_ops/README.md:7 | Discovers ✔; **runs ✘** (await bug, all 500) |
| Velaris dashboard "243 agents active" | velaris_dashboard_server.py:24, :54 | MockBackend fabricates agent_0..242 |
| Marketing (`aether_os/vkatos_deploy/products/velaris/index.html`): "Velaris — Enterprise Pipeline Dashboard", "ACTIVE DEPLOYMENT — Private Beta", "Full platform launch Q3 2026", REAL-TIME / MULTI-DOMAIN / ZERO CLOUD / AUDIT READY, Kanban pipeline board, DCSP stall alerts, predictive risk scoring, one-click PDF/Word doc gen "powered by Aether2", immutable audit trail, multi-tenant isolation, file upload for "autonomous RAG" | marketing page | **Describes a different product.** None of Kanban, doc-gen, RAG, multi-tenant, audit trail or a UI exists in velaris_knackforge. The closest real code is `router/velaris_integration/autopilot.py` (stall flagging on GAIA SQLite) plus PIPELINE_MONITOR z-score (company_ops). "Zero cloud" conflicts with compose's Bedrock/Anthropic env (docker-compose.yml:27-36), though Velaris itself doesn't use them |

## 11. Open questions

1. Which tree is canonical for deployment: `velaris_knackforge/departments` (326) or `company_ops/{core,domains,connectors}` (168)? They have diverged in layout and taxonomy, and `knackforge_platform/velaris/` is an unused third copy.
2. Is the intended runtime the `velaris/` package or the `_ai_core` PRIME/ENGINE/REGISTRY? Fixing either needs (a) a registry that walks `departments/*/*` (company_ops `bootstrap.discover_agents` + `spec_from_file_location` already does this and works), (b) manifests for 220 dirs, and (c) dropping the `velaris.agents.*`/`agents.*` import roots.
3. Should `company_ops` `run` call sync methods (most agents) and require auth/HITL before execution? As written it's an unauthenticated arbitrary-import endpoint that always 500s.
4. Is `_connectors` meant to be importable as `connectors`? Rename or add a shim.
5. Where is `Velaris_CORE_V11` / `live/agents` (the V11 tree the tests, router integrations and `/live/agents/*` paths target)? It isn't on this machine (checked `~/Desktop/Velaris_CORE_V11`).
6. Is the reorg to be committed? Archived `__pycache__` dirs should be excluded, and README/docs regenerated.
7. Should the marketing "Velaris" (pipeline dashboard) be renamed or separated from Velaris BOS (agent framework)?
