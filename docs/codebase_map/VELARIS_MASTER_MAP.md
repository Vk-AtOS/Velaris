# Velaris BOS — Master Codebase Map

Repo: `/Users/apple/Desktop/Knackforge/velaris_knackforge` · HEAD `142153b` · **working tree has an uncommitted reorg** (`domains/` → `departments/` + `_archived_*`) · Mapped 2026-11-08
Method: 5 parallel workers read every file (~20K LOC: 326 department agents, 96 archived files, the `velaris/` runtime, 105 test files, platform integration in `knackforge_platform/`). Evidence with `file:line` lives in `sections/V1…V5`. Lead re-verified: `python3 main.py` → `Agents loaded : 0`.

| § | File | Scope |
|---|---|---|
| V1 | `sections/V1_runtime_integration.md` | main.py, velaris/ runtime, tests, reorg mapping, company_ops / knackforge_platform integration, marketing page |
| V2 | `sections/V2_ai_core.md` | departments/_ai_core (131 agents, framework clusters, SOUL/PRIME/ENGINE/ORCHESTRIX/REGISTRY) |
| V3 | `sections/V3_business_depts_a.md` | finance, hr, operations, supply_chain, project_management, communications (79 agents) |
| V4 | `sections/V4_business_depts_b.md` | security, it_infrastructure, legal_compliance, data_knowledge, executive, sales, marketing, client_success, _connectors (116) |
| V5 | `sections/V5_archives_reorg.md` | _archived_agents, _archived_domains, full reorg ledger, git history, count reconciliation |

Other copies: `velaris_organized` (same git history, older — used by Sept audit), `knackforge_platform/velaris` (identical to this working tree, unused), `knackforge_platform/company_ops` (older 168-agent deployed copy).

---

## 1. Vision and goal

- **README:** "Velaris BOS (Business Operating System) — Organisational Brain. 343 domain-classified agents. One unified intelligence layer for AI-native enterprises." Every business function (cash-flow forecasting → zero-trust security) is an independently deployable agent; together a "structured, auditable, extensible AI brain".
- **Declared hierarchy:** SOUL_VELARIS (identity/intent) → PRIME (controller) → ENGINE (registry + pipeline) → ORCHESTRIX (task ordering) / REGISTRY (manifest discovery) → domain agents, plus cross-domain frameworks (ACF, AAE, ASEL, CLBPP, CRK, VCAS, VHOE, VPSE, MCFE, MPC, UIE, DSS, CCSF, EOF).
- **Marketing (vkatos.com/products/velaris):** describes a *different product* — an "Enterprise Pipeline Dashboard" (Kanban, stall alerts, doc generation, RAG, multi-tenant, zero-cloud, private beta, Q3 2026). None of it exists in this repo.
- **Reality:** a library of 326 mostly-small Python agent files with no working loader, no API, no LLM, no ML (except optional Whisper), and 0 passing tests.

---

## 2. Framework & architecture

### 2.1 What exists
```
main.py ──► velaris/core (config, loader, logging) ──► velaris/agents/router.py
                                                       scans only velaris/agents/ (contains router.py) → 0 agents
velaris/backend/engine.py, flow_engine.py   thin, unused by agents
velaris/memory  MemoryMesh = in-process dict
velaris/security secure.py → always True
velaris/tests   105 files importing velaris.agents.X / live.agents.X / agents.X — paths that don't exist

departments/<16 depts>/<AGENT>/main.py   326 agents, no base class, 4 incompatible contracts
   _ai_core (131) · finance 23 · hr 8 · operations 24 · supply_chain 6 · project_management 14 · communications 4
   security · it_infrastructure · legal_compliance · data_knowledge · executive · sales · marketing · client_success · _connectors (116)
_archived_agents/ (40 files), _archived_domains/ (56 files)
```

### 2.2 Declared hierarchy vs code (V1, V2)
| Component | Location | Status |
|---|---|---|
| SOUL_VELARIS | `_ai_core/SOUL_VELARIS` | STUB — fixed mission string, nothing calls it |
| PRIME | `_ai_core/PRIME` | fails to import |
| ENGINE | `_ai_core/ENGINE` | fails to import; lifecycle/load-balancer in `__post_init__` on a non-dataclass never runs |
| REGISTRY | `_ai_core/REGISTRY` | crashes on construction (`departments/agents` missing); only 19 manifests in _ai_core, 106/326 overall, 4 formats |
| ORCHESTRIX | `_ai_core/ORCHESTRIX` | topological sort correct; `parallel_groups` bug orders C before B |
| Framework clusters | `_ai_core/*` | named files only; acronyms undefined in code; wrapper agents return fixed "ok" |

### 2.3 Agent contract
No base class. ENGINE calls methods by name; `company_ops` expects `async run(payload)`; `router.py` expects `on_event`; agents mostly expose sync `run`/`health`. 19 folders have no entrypoint. Several agents hard-code `/live/agents/...` paths (fail on macOS / any host without `/live`).

### 2.4 Platform integration (V1)
- **`knackforge_platform/company_ops`:** FastAPI on :8100, nginx `/api/ops/`. Runs an older 168-agent copy, not this repo. All 168 load, but `POST /agents/{name}/run` awaits an async `run` that no agent has → 500 for every agent. No auth, CORS `*`, `hitl_required` never enforced.
- **`router/velaris_integration`:** imports from `~/Desktop/Velaris_CORE_V11` (absent) → falls back to mocks and hard-coded formulas; dashboard fakes 243 agents.
- **Event bus:** `velaris.insight` subject has no publishers or subscribers.

---

## 3. Agent inventory (326 live in `departments/`)

| Slice | Agents | REAL | RULE-BASED | ML | LLM | STUB/HOLLOW | DEAD |
|---|---|---|---|---|---|---|---|
| _ai_core (V2) | 131 | 16 | 11 | 0 | 0 | 104 | 0 |
| Business A (V3) | 79 | 15 | 43 | 1 | 0 | 15 | 5 |
| Business B (V4) | 116 | 15 | 45 | 0 | 0 | 52 | 4 |
| **Total** | **326** | **46 (14%)** | **99 (30%)** | **1** | **0** | **171 (52%)** | **9** |

- **Stub + dead = 55%** (prior audit: 39% repo-wide; this measure is stricter).
- **Hash-noise defect:** ≥19 rule-based scorers (15 in V3, 4 in V4) plus all 12 archived vertical engines add `sha256(id) % N` into business scores — identical cases with different IDs get different results (credit risk up to 500/1000; clinical protocol choice; ITSM priority; property value up to 199,999).
- **REAL business logic worth keeping (V3):** India statutory payroll (EPF/ESI/PT — no ₹15k EPF ceiling), leave management, 360 reviews with calibration, onboarding, recruitment pipeline, z-score anomaly detection, SLA breach tracking, sprint velocity, billable utilisation, Markowitz portfolio, EOQ/reorder point, local record→Whisper→summary meeting chain. Real in V2: NAVARCH (Dijkstra), SCHEDULON, HUMAN_APPROVAL_WORKFLOW (in-memory). Real in V4: Zoho OAuth refresh, WhatsApp Cloud API send, psutil probe, JSON event log.
- **All 16 working V3 agents and 21 new agents overall are untracked** (added 2026-09-10, ported from VKatOS) — they exist only in the uncommitted working tree.

---

## 4. Planes

| Plane | Status | Evidence |
|---|---|---|
| **SDLC** | ABSENT | no build/codegen/release tooling; README is the only spec |
| **STLC (testing)** | BROKEN | 105 test files, 0 pass (72 collection errors; 48 fail / 70 error with PYTHONPATH); import obsolete `live/agents` layout; pytest not installed for system Python |
| **SRE** | SIMULATED | IT infra: 20/26 stubs; scaling/failover agents are 16-line health checks; IT_INFRA_ENGINE fakes VMs (degraded when `hash(id)%7==0`); real only psutil CPU/RAM + JSON event log. Platform-side: company_ops /health |
| **Security** | STUB / UNSAFE | `velaris/security/secure.py` always True; ZERO_TRUST_PIPELINE.verify always True; VIGILIS accepts forged `"SIG:"+reversed(msg)`; SECRETS_VAULT = base64 with key beside data; LOCAL_BIOMETRICS verify(user, {}) → True; HFAL token = unsalted hash(user+PIN); EXECUTION_SANDBOX `exec` escapable; ROLLBACK_ENGINE path traversal. No hard-coded secrets found |
| **Compliance / governance** | NOT ENFORCED | SIGNED_AUDIT_CHAIN writes `"/n"` → verify_chain always fails, no hash links; EACPE_* ethics/HITL guards return "approved"; GOVERNANCE_KERNEL only checks policy ID exists; 3 manifests declare HITL with no enforcement; Zoho payroll/appraisal data pulled with `hitl_required:false` |
| **Deployment** | PLATFORM ONLY | no Dockerfile/CI here; deployed via knackforge_platform docker-compose as `company_ops` (older copy) |
| **Admin control** | ABSENT | no admin API/UI; HUMAN_APPROVAL_WORKFLOW in-memory only |
| **API management** | PLATFORM ONLY | company_ops REST (`/agents`, `/agents/{name}/run` → 500), no auth, CORS `*` |
| **Integrations** | PARTIAL / BROKEN | ZOHO_CONNECTOR real OAuth (no retries); People/Payroll/Projects connectors import `connectors.*` but folder is `_connectors` → dead, and that takes down HR PAYROLL_ENGINE / ATTENDANCE_MONITOR / EMPLOYEE_METRICS_ENGINE; WhatsApp send real |
| **AI / intelligence** | ABSENT | 0 LLM calls anywhere; only ML = optional Whisper (not in requirements); LYRA voice defaults to mock mode; LOCAL_EMBEDDING_ENGINE returns one integer; MCFE uses per-process `hash()` |
| **Memory / knowledge** | STUB | MemoryMesh dict; MEMORY_FABRIC in data_knowledge (rule-based) |
| **Business planes** | Finance (calculator library, nothing persisted) · HR (most real, 7/8) · Ops (3 real, 5 dead) · Supply chain (all hash-noised) · PMO (2 real) · Comms (3 real + Whisper) · Sales (formula calculators, no CRM) · Marketing (templated text + `random` scores) · Exec (strategy agents all stubs) · Client success / Legal (thin) |

---

## 5. Reorg & history (V5)

- **History:** `f126110` 243 agents/15 domains → `97d83d8` reclassify 13 (still 243) → `142153b` 343 (commit message overstates: 100 new + 45 modified, not "163 merged").
- **Uncommitted reorg is a pure move:** 343 HEAD folders (332 unique; 11 CORE_V11 duplicates) → 305 moved byte-identical into `departments/`, 0 modified, 38 archived (11 duplicates, 1 stub, 26 out of scope: agri 8, healthcare 5, real estate 2, research/quantum 11), **0 lost**. Plus 21 new agents → 326 in 16 departments. `_ai_core` absorbs 131 (40%).
- **Lost in reorg:** 30 of 31 domain/framework README files (documentation only).
- **Misplacements:** HEARTLINE_MONITOR (agent heartbeat, not healthcare) and PLANT_SIM_ENGINE (manufacturing, not agri) wrongly archived; VMRK, LOGISTA, COHORTUS and ~14 platform/SRE agents misfiled.
- **New breakage from reorg:** `connectors.*` → `_connectors`; `router.py:18` skips `_`-prefixed dirs, so pointing it at `departments/` would still skip `_ai_core` and `_connectors`.
- **Counts:** README 343 matches HEAD; ASCII diagram numbers and `docs/domain_map.md` (243) are stale.

---

## 6. Priority fix list

| P | Issue | Location |
|---|---|---|
| P0 | Loader finds 0 agents; point router at `departments/` incl. `_`-dirs; one agent contract/base class | `velaris/agents/router.py:16-26` |
| P0 | Remove hash/random noise from all scorers | ≥19 department agents + archived verticals |
| P0 | Security stubs that return True / forgeable signatures / base64 vault / biometrics bypass | ZERO_TRUST_PIPELINE, VIGILIS:106-111, SECRETS_VAULT, LOCAL_BIOMETRICS:38-42, HFAL, EXECUTION_SANDBOX |
| P1 | Commit the reorg (as `git mv` renames + archive + 21 new agents + README rewrite); restore per-domain READMEs | working tree |
| P1 | `connectors` package path | `_connectors/ZOHO_*`, hr agents |
| P1 | Fix imports `velaris.agents.X`/`live.agents.X`/`/live/...` paths; make tests importable | _ai_core, tests |
| P1 | company_ops `run` contract (500 on every agent), add auth, enforce HITL | knackforge_platform/company_ops |
| P2 | SIGNED_AUDIT_CHAIN newline + hash links; GOVERNANCE_KERNEL rule eval; EACPE guards | security/legal_compliance |
| P2 | ORCHESTRIX parallel_groups; ENGINE dataclass; REGISTRY path + manifests | _ai_core |
| P3 | Align marketing page / pitch with code; update README counts | vkatos_deploy, README |

## 7. What works today
ORCHESTRIX topological sort, NAVARCH routing, India payroll/leave/review/recruitment logic (once `connectors` path fixed), portfolio/EOQ maths, Zoho OAuth refresh, WhatsApp send, local Whisper meeting transcription (if installed). Each works standalone when imported directly — not as a system.

## 8. Open questions
1. Is Velaris meant to be an LLM-driven agent system (then an LLM layer must be built) or a deterministic business-rules library?
2. Should `company_ops` be rebased onto this repo's `departments/` layout?
3. Where did the original `/live/agents` package root go, and is the missing `velaris_fix_alias_layers.sh` recoverable?
4. What do the framework acronyms (ACF, ASEL, CRK, …) stand for — keep or collapse into a few real modules?
5. Commit the reorg now, or after fixing the loader?
