# V3 — Business Departments A: Finance · HR · Operations · Supply Chain · PMO · Communications

Scope: `departments/{finance,hr,operations,supply_chain,project_management,communications}` in the **working tree** (uncommitted `domains/ → departments/` reorg; HEAD 142153b). 79 agent dirs, 182 files (excl. `__pycache__`), 144 `.py`, ~6.2K LOC. I read every `main.py`, every manifest (38) and every `__init__.py`. `__init__.py` files are empty or a 4-line "package marker" comment banner, with no logic. Paths below are relative to `departments/` unless stated.

Tag legend:
- **REAL**: a working, end-to-end feature with persistence (SQLite) or a live integration.
- **RULE-BASED**: a stateless or in-memory deterministic calculator.
- **⚠hash**: a RULE-BASED engine that adds `sha256(id) % N` "det_entropy" noise into the score or decision.
- **ML**: local model inference.
- **LLM-DRIVEN**: calls an LLM.
- **STUB/HOLLOW**: health_check, echo, or trivial dict-wrapping with no domain logic.
- **DEAD**: cannot do anything at runtime.
- **BROKEN**: the logic is real, but in the current tree it fails on import or instantiation.

---

## 1. Summary

| Dept | Agents | REAL | RULE-BASED (of which ⚠hash) | ML | LLM | STUB/HOLLOW | DEAD | LOC (py) |
|---|---|---|---|---|---|---|---|---|
| finance | 23 | 0 | 18 (7) | 0 | 0 | 5 | 0 | 1411 |
| hr | 8 | 7 (3 BROKEN) | 1 (1) | 0 | 0 | 0 | 0 | 1197 |
| operations | 24 | 3 | 10 (1) | 0 | 0 | 6 | 5 | 1413 |
| supply_chain | 6 | 0 | 6 (6) | 0 | 0 | 0 | 0 | 606 |
| project_management | 14 | 2 | 8 (0) | 0 | 0 | 4 | 0 | 919 |
| communications | 4 | 3 | 0 | 1 | 0 | 0 | 0 | 648 |
| **Total** | **79** | **15** | **43 (15)** | **1** | **0** | **15** | **5** | **~6.2K** |

Headline findings:
- **No LLM calls anywhere in scope.** No openai, anthropic, langchain or HTTP-to-LLM calls. The only "LLM" reference is a dead hook: `communications/MEETING_SUMMARIZER/main.py:119` sets `self._llm = None`, and `config["llm_callable"]` is never read.
- **The only ML is optional local Whisper**, in `communications/CALL_TRANSCRIBER/main.py:49-58`. `whisper` and `faster_whisper` are not in `requirements.txt`, which lists only psutil and cryptography.
- **Stub or dead share: 20/79 (25%).** Another 15 RULE-BASED engines are toy scorers whose output is perturbed by an ID hash. Counting both, **35/79 (44%) are non-credible as business logic.** That is consistent with the prior audit's ~39% stubs.
- **Provenance split is stark.** All 16 REAL/ML agents are untracked in git, added on 10 Sep 2026 and "Ported from VKatOS" for "Knackforge". The other 63 were moved from HEAD `domains/*` (61 from `domains/operations` or `domains/finance`; CODEX and ACTION_SANDBOX from `domains/frameworks/*`, identical apart from banner lines). **Every working business feature in this scope exists only in the uncommitted working tree.**
- **Nothing in scope is reachable at runtime.**
  - `velaris/agents/router.py:16-24` only scans `velaris/agents/*/main.py`, and that directory contains only `router.py`. So zero department agents load, and failures are swallowed at `router.py:25-27`.
  - `velaris/tests/test_treasurix.py:4` imports `velaris.agents.TREASURIX`, which does not exist.
  - No agent implements `on_event` for `router.publish` (`router.py:38-47`).
- **The reorg broke the Zoho path.**
  - The working-tree agents import `from connectors.ZOHO_*.main ...`, but the connectors now live at `departments/_connectors/ZOHO_*`, and there is no top-level `connectors/` package. The connectors themselves import `from connectors.ZOHO_CONNECTOR.main` too (`_connectors/ZOHO_PEOPLE/main.py:5`, `ZOHO_PAYROLL:5`, `ZOHO_PROJECTS:6`).
  - Verified failures: `hr/PAYROLL_ENGINE` fails at **import** (`main.py:6`, ModuleNotFoundError). `ATTENDANCE_MONITOR` (`:16`) and `EMPLOYEE_METRICS_ENGINE` (`:18-20`) fail at **instantiation**.

---

## 2. Per-department agent tables

Inputs and outputs are Python method arguments and dicts. No agent exposes HTTP, CLI or events. LOC is `main.py` lines.

### 2.1 finance (23)

| Agent | LOC | What it actually does | I/O | Tag |
|---|---|---|---|---|
| BANKING_LOGIC_ENGINE | 90 | Validates an account (`:27-41`). `process_transaction` checks the overdraft limit (`:60-77`). `apply_interest` multiplies interest by `sha256(account_id)%1000/1000` (`:49-50`), so **interest depends on the ID hash: a correctness defect.** | AccountProfile → balance dict | RULE-BASED ⚠hash |
| CASHFLOW_AI | 21 | `run()` echoes its payload (`:19-21`). Manifest says "Auto-generated placeholder". | payload → payload | STUB |
| CLAIMS_ASSESSMENT_ENGINE | 107 | Weighted document and history scores plus severity plus a hash term (`:61-66`). Thresholds give approve, manual review or reject. Payout = amount × (1 − risk/1000) (`:69-79`). | ClaimCase → decision, payout | RULE-BASED ⚠hash |
| CREDIT_RISK_ENGINE | 99 | A DTI, history, delinquency and exposure score, plus a base term of `hash%500` (`:52-61`). The hash term can contribute up to half of the 0–1000 scale, then the score is tiered. | BorrowerProfile → score, tier | RULE-BASED ⚠hash |
| ECON_INTEL_CORE | 15 | health_check only. | — | STUB |
| ECONOMIC_INTELLIGENCE_MESH | 44 | In-memory indicator list. Trend = mean of first differences, classified into OPPORTUNITY, STABLE or RISK (`:21-36`). | name, value → summary | RULE-BASED |
| ECONOVA | 45 | Elasticity × Δprice. Linear demand projection. Mean of macro metrics (`:21-45`). | floats → float | RULE-BASED |
| FINANCIAL_AI_ENGINE | 44 | Growth %. Hand-rolled OLS one-step forecast (`:19-32`). Margin minus 0.2·debt health bands. No AI. | lists → float, band | RULE-BASED |
| FISCALIS | 49 | Budget dict, cost sum, next month = last × (1+g) (`:21-49`). | — | RULE-BASED |
| FORECASTA | 52 | Compound growth series, average slope, rolling mean (`:26-52`). | — | RULE-BASED |
| FORMULA | 44 | Builds `{title, pillars}`, counts unique items, merges two dicts. Nothing finance-related; misfiled. | — | HOLLOW |
| INSURANCE_POLICY_ENGINE | 101 | Premium = (SA/1000)·(age/30)·type·tenure + health loadings + `hash%300/100` (`:57-70`). Manual review if ≥250k. | PolicyApplication → premium | RULE-BASED ⚠hash (the noise is small, ≤3) |
| LEDGERON | 43 | In-memory per-account ledger, balance = Σ, exact-match reconcile (`:21-43`). Not double-entry and not persisted. | tx → balance, match | RULE-BASED |
| MACRO_ECON_MODEL | 85 | Linear index of GDP, inflation, unemployment, rates, deficit and FX, plus `hash(country)%200` (`:48-57`). Only us, uk, in, eu and jp are supported. | MacroInput → index, tier | RULE-BASED ⚠hash |
| METRIX | 55 | Weighted KPI. Max-normalisation. Mean normalised score. | dict → float | RULE-BASED |
| NEURAL_ECONOMY | 21 | Echo stub, "Auto-generated placeholder". | — | STUB |
| PORTFOLIO_SIM_ENGINE | 101 | **Correct** Markowitz mean and variance over a correlation matrix (`:60-77`), Sharpe with rf=2% (`:80-82`), volatility tiers. The hash is returned but **not** mixed into the maths (`:78`). | weights, μ, σ, ρ → return, vol, Sharpe | RULE-BASED (best in finance) |
| PRICING_OPTIMIZER | 15 | health_check only. It duplicates the name of PRICING_OPTIMIZER_ENGINE. | — | STUB |
| PRICING_OPTIMIZER_ENGINE | 82 | Additive price = cost + demand·20 − competition·15 + season·50 + 100/elasticity + constraints + `hash%500` (`:57-67`). The hash can add up to ₹500 to the price. No optimisation is done. | PricingInput → price | RULE-BASED ⚠hash |
| RISKON | 68 | Population σ, Σ\|exposure\|, weighted risk score that mixes units (σ + currency amounts) (`:26-59`). | — | RULE-BASED |
| STOCKMARKET_SIGNAL_ENGINE | 78 | pct·2 + volΔ/1000 + `hash(symbol+sector)%200−100` (`:43-51`), mapped to a buy/sell band. **The hash can swing the signal by up to ±100, a full band.** | MarketSnapshot → signal | RULE-BASED ⚠hash |
| TREASURIX | 55 | Net cashflow Σin − Σout, runway = reserves/burn, reserve ratio (`:21-55`). The only finance agent with a test (`velaris/tests/test_treasurix.py`), and that test has a broken import path. | — | RULE-BASED |
| VALORA | 57 | Weighted valuation score, A/B compare, shift (`:25-57`). | — | RULE-BASED |

### 2.2 hr (8)

| Agent | LOC | What it actually does | I/O | Tag |
|---|---|---|---|---|
| ATTENDANCE_MONITOR | 62 | Calls Zoho People `get_attendance` for each employee. Buckets each into present, absent or late (`IsLate=="true"`) (`:23-42`). Counts non-Present days against a threshold (`:44-62`). Bugs: `config.get` runs on raw `config` (`:18`) and crashes if `None`; `shift_start` is never used. | employee_ids, dates → buckets, flags | REAL · **BROKEN** (`:16` import) |
| EMPLOYEE_METRICS_ENGINE | 183 | Builds a per-employee monthly profile from Zoho People (attendance, leave, appraisal), Payroll (payslip, statutory) and Projects (tasks, timelogs) (`:36-119`). Scorecard = 0.3·attendance% + 0.5·delivery% + 0.2·(perf×20) (`:134-141`). Org heatmap gives avg/min/max/at-risk below 70 and top 3 (`:153-183`). The manifest says `hitl_required: true` ("salary needs approval"), but **no gate exists in code**. Cost is O(employees × projects) API calls. | ids, month → profile, scorecard, heatmap | REAL · **BROKEN** (`:18-20`) |
| EMPLOYEE_ONBOARDING | 151 | SQLite with an 11-step checklist and day offsets 1–90 (`:13-25`). Onboard creates the tasks; there are complete-step, overdue and progress % functions (`:46-113`). The DB defaults to CWD `employee_onboarding.db`. | name, role → id, progress | REAL |
| HR_TALENT_ENGINE | 105 | Candidate score = (exp·20 + edu weight + Σskill·15 + culture flags)·role demand + `hash%150` (`:70-79`), then tiered. | CandidateProfile → score | RULE-BASED ⚠hash |
| LEAVE_MANAGEMENT | 175 | SQLite at `__file__/leaves.db` (`:16`). India entitlements: CL 12, SL 12, EL 15, ML 182, PL 15 (`:15`). Business-day count is Mon–Fri only, with no holiday calendar (`:51-60`). Covers apply with a balance check, approve or reject with `used += days`, pending list and history (`:99-175`). Gap: with no seeded balance row, apply **skips the balance check** (`:112`). | emp, type, dates → request, balance | REAL |
| PAYROLL_ENGINE | 157 | India statutory, FY25-26 (`:15-24`): EPF 12%/12% of basic with **no ₹15k wage ceiling**, ESI 0.75%/3.25% if gross ≤ ₹21k, PT slabs 0/150/200. `compute` returns gross, deductions, net and CTC monthly/annual (`:69-92`). Also bulk compute and an org statutory liability roll-up (`:100-128`), plus Zoho payslip, statutory and YTD passthroughs gated on `zoho_enabled` (`:131-144`). | salary parts → payslip dict | REAL (rule-based) · **BROKEN** (`:6` top-level import kills the whole module, local maths included) |
| PERFORMANCE_REVIEW_ENGINE | 210 | SQLite holding OKRs (with progress), 360 reviews (self, peer, manager), and calibration (`:21-51`). Summary weights are self 0.2, peer 0.4, manager 0.4, renormalised over the types present (`:150-185`). Five rating bands (`:62-71`). | scores → weighted rating | REAL |
| RECRUITMENT_ATS | 150 | SQLite 8-stage pipeline with stage history, stale-candidate detection, placement rate and CSV export (`:14-108`). `move()` **does not validate** `new_stage` against STAGES (`:48-68`). It has a "client" field, which suggests a staffing-agency origin. | candidate → stage moves, report | REAL |

### 2.3 operations (24)

| Agent | LOC | What it actually does | Tag |
|---|---|---|---|
| BUSINESS_AUTOPILOT | 21 | Echo `run()`, "Auto-generated placeholder". | STUB |
| BUSINESS_OPS_ENGINE | 47 | In-memory task list (PENDING/DONE) and a KPI dict. | RULE-BASED (trivial) |
| CODEX | 51 | sha256 of a sorted-JSON rule set, used for change detection. Platform plumbing; misfiled. | RULE-BASED |
| CONNECTOR_LAYER | 52 | Connector registry. `request()` returns `{"echo": True}` and does no IO ("Lockdown mode", `:38-51`). | HOLLOW |
| CONVERGENCE_BRIDGE | 45 | Alias delegator to `velaris.agents.{ORCHESTRIX,…}` (`:16-26`). Those modules do not exist (they are now in `departments/_ai_core`), so `run()` always raises and health returns a fake "ok". | DEAD |
| DYNAMICA | 48 | Linear list generator and an update-callable loop. | HOLLOW |
| FABRICA | 47 | Wraps a list as `{count, layers}`; dict merge. | HOLLOW |
| FLUXOR | 60 | Mean load, spike test last > avg·1.5, and ±1 "balancing". | RULE-BASED (trivial) |
| GENEFLOW | 39 | Dict key diff. `apply_migration` is inconsistent with its own diff output: lists vs dicts (`:31-37`). | RULE-BASED (platform, misfiled) |
| HELIX | 40 | sha256 signature store and verify. | RULE-BASED (platform, misfiled) |
| HYPERSYNC | 45 | Alias delegator, same as CONVERGENCE_BRIDGE (`:16`). | DEAD |
| MULTI_TENANT_ENGINE | 46 | In-memory dict-of-dicts per tenant. No real isolation. | RULE-BASED (platform, misfiled) |
| NIRVANA | 45 | Alias delegator (`:16`). | DEAD |
| OPERATUS | 40 | `execute_workflow` marks every step "done" without executing anything (`:20-29`). | HOLLOW |
| OPS_REPORT | 148 | SQLite daily log by category plus blockers, rendered as a text or dict report (`:14-105`). Minor issue: it stores UTC timestamps but filters on a local date (`:36`, `:56-59`). | REAL |
| OPTIMA | 56 | Weighted CTR/CVR/ROI score. Marketing logic misfiled under ops. | RULE-BASED (trivial) |
| PIPELINE_MONITOR | 127 | SQLite stage-duration log. Risk is a **z-score over the last 30 observations of the same stage** mapped to 0.1/0.35/0.65/0.8/0.95. With fewer than 3 observations it compares against a configured baseline × 1.2 (`:44-65`). Also a morning briefing and a dashboard. | REAL (statistical rule) |
| POLARIS | 50 | Weighted impact, longevity and alignment; rank. | RULE-BASED (trivial) |
| QUALITY_CONTROL_ENGINE | 94 | Defect and regulatory penalties against rigour and stability bonuses, plus `hash%200` (`:61-70`). `sample_size` is validated but **never used** in the score. | RULE-BASED ⚠hash |
| SAGE | 45 | Alias delegator to STRATEGOS etc. | DEAD |
| SANDE | 45 | Alias delegator to LOCAL_* modules. | DEAD |
| SKILLPACK_LOADER | 52 | Writes JSON skillpacks to the hard-coded `/live/agents/SKILLPACK_LOADER/skillpacks` (`:15-19`). `makedirs` fails on macOS, which has a read-only root. | RULE-BASED (platform, misfiled; env-broken) |
| SLA_MONITOR | 128 | SQLite commitments with deadlines. `scan()` records breaches, de-duplicated within 1 h (`:46-69`). The dashboard shows ok, due_soon (<1 h) or breached. | REAL |
| VELOCITY_LOOP | 18 | `accelerate()` returns a constant `{"final":"ready_for_approval"}`. | STUB |

### 2.4 supply_chain (6). All moved from HEAD `domains/operations`; none has a manifest.

| Agent | LOC | What it actually does | Tag |
|---|---|---|---|
| FLEET_HEALTH_ENGINE | 112 | Mileage, engine hours, fault weights and wear %, times a usage factor, plus `hash%250` (`:71-86`), then tiered. | RULE-BASED ⚠hash |
| INVENTORY_DECISION_ENGINE | 113 | **Textbook calculations, correct:** safety stock = z·σ·√L with z=1.65 (~95%), ROP = d·L + SS, EOQ = √(2DS/H) (`:64-73`). It then applies a constraint multiplier and a capacity cap (`:76-87`). The *decision* comes from an arbitrary sum of ROP/10 + SS/10 + EOQ/10 + `hash%200` (`:91-98`). Has a bare `except:` (`:73`). | RULE-BASED ⚠hash (metrics real, decision noise) |
| MACHINE_LIFECYCLE_ENGINE | 106 | Age, hours, maintenance weights (preventive −20), component age and load, plus `hash%250` (`:64-80`). `CURRENT_YEAR = 2025` is hard-coded (`:17`), so **any machine installed in 2026 fails validation** (today is 2026-11). | RULE-BASED ⚠hash |
| ROUTE_OPTIMIZATION_ENGINE | 83 | Greedy nearest-neighbour TSP weighted by traffic factor (`:45-66`). Starts at the lexicographic min location, not a depot. `time_windows` are validated but **ignored**. `hash%300` is added to `total_cost` (`:68-70`). A missing distance pair raises KeyError. | RULE-BASED ⚠hash |
| SUPPLY_CHAIN_ENGINE | 79 | ROP = SS + avg·L, which is real (`:48-50`). The "stability" score is `hash%500` + 300 − penalties (`:52-57`), so it is **dominated by noise**. | RULE-BASED ⚠hash |
| WAREHOUSE_FLOW_ENGINE | 89 | Flow ratio, efficiency penalty and congestion flags, plus `hash%250` (`:55-66`). | RULE-BASED ⚠hash |

### 2.5 project_management (14)

| Agent | LOC | What it actually does | Tag |
|---|---|---|---|
| ACTION_SANDBOX | 24 | `sandbox_execute` returns `{"result":"simulated"}`. | STUB |
| BUDGET_GUARDRAILS | 47 | Per-category limits. `record_spend` blocks any overrun or unknown category; reports remaining and blocked (`:18-46`). In-memory only. | RULE-BASED (genuine guardrail logic) |
| DIGITAL_TWIN_XR_ENGINE | 57 | A dict store with diff and merge. There is no XR. | RULE-BASED (trivial) |
| DRY_RUN_SIMULATION | 81 | Dry-run/live toggle that logs to `/live/agents/DRY_RUN_SIMULATION/dryrun.log` (`:15-16`). "Live" also performs no action (`:55-69`). Env-broken on macOS. | RULE-BASED (hollow semantics) |
| EXECUTION_SANDBOX | 53 | `exec(code)` with `__builtins__={}` (`:17-34`). **Not a sandbox:** the classic `().__class__.__base__.__subclasses__()` escape works. This is a security finding; route it to the security plane. | RULE-BASED (unsafe) |
| FAILPATH_CONTROL_ENGINE | 46 | Registry of failure code to handler name, plus history. Never invokes a handler. | RULE-BASED (trivial) |
| FEASIBILITY_ENGINE | 15 | health_check only. | STUB |
| INITIATIVE_ENGINE | 18 | `propose()` returns the constant `"autonomous_insight"`. | STUB |
| ROLLBACK_ENGINE | 67 | JSON snapshot files and log under `/live/agents/ROLLBACK_ENGINE` (`:15-17`). Two bare `except:` (`:30`, `:57`). The `name` argument has no sanitisation, so path traversal is possible. | RULE-BASED (env-broken) |
| SIMULON | 48 | Linear list generator and callable iteration, a duplicate of DYNAMICA. | HOLLOW |
| SPRINT_PLANNER | 169 | SQLite sprints (unique project+number) and tasks with a status enum (`:19-47`). Kanban board, story-point velocity %, close sprint, velocity trend vs target (`:65-169`). The manifest's "Zoho Projects sync ready" claim is false: there is no Zoho code. | REAL |
| SUCCESSOR_KEY_MODULE | 40 | In-memory unsalted sha256 of a single successor key, with set-once, verify and wipe. A security/governance item, misfiled under PMO. | RULE-BASED |
| TACTICIAN | 58 | Bernoulli Monte Carlo of `base+Σmodifiers`, which has an analytic answer, and "needed = target − current" (`:25-53`). Calls `random.seed` globally (`:16-18`). | RULE-BASED (trivial) |
| TIME_TRACKER | 164 | SQLite timelogs and active timers. Starting a timer auto-stops the previous one (`:64-100`). Manual log with a 0–24 h guard. Weekly utilisation = billable/40 h; team and project roll-ups (`:121-164`). "Zoho timelog sync ready" is false. | REAL |

### 2.6 communications (4). All new and untracked; they form a local meeting-intelligence pipeline.

| Agent | LOC | What it actually does | Tag |
|---|---|---|---|
| CALL_RECORDER | 153 | Spawns `ffmpeg` with an avfoundation, dshow or alsa input chosen by OS, writing 16 kHz mono PCM WAV (`:61-102`). Sessions are a module-global dict under a lock (`:18-19`), so they are lost on restart. Duration = bytes/32000. Health probes `ffmpeg -version`. | REAL |
| CALL_TRANSCRIBER | 118 | Lazy-loads openai-whisper or faster-whisper (CPU int8) and returns text plus timestamped segments; `transcribe_and_save` writes JSON (`:49-113`). The manifest claims Tamil support, which is just the Whisper `language` argument. The dependency is not in requirements. | **ML** (local) |
| MEETING_SUMMARIZER | 198 | Regex decision and action signals (`:20-38`). Extractive summary = top-5 sentences by keyword count, in original order (`:84-104`). Persists to `meetings.db` (`:150-166`). The LLM hook is dead (`:119`). | REAL (rule-based NLP) |
| ACTION_ITEM_EXTRACTOR | 179 | Regex action signals, owner patterns ("X will", "assigned to X") and due hints (ISO date, "by Oct 15", weekday words). Persists to `action_items.db`. **Crash bug at `:74`:** `datetime.timedelta` is called on the `datetime` *class*, so any segment containing "today", "tomorrow", "next week" or "eod" raises AttributeError; I verified this. Weekday and month hints are stored as strings like "friday" or "oct 15", so `get_overdue()` (`:171-179`, lexical `< today`) never flags them. | REAL (rule-based NLP) · buggy |

---

## 3. Notable real business logic in detail

1. **India statutory payroll** (`hr/PAYROLL_ENGINE/main.py:14-128`). Computes EPF employee and employer at 12% of basic, ESI 0.75%/3.25% when gross ≤ ₹21,000, and PT slabs (≤10k: 0, ≤15k: 150, else 200). It returns net pay, monthly and annual CTC, and an org-level `total_compliance_liability`. It is the most compliance-relevant code in scope. Gaps:
   - No EPF ₹15k wage ceiling and no EPS/EDLI split.
   - The PT slab is a single state's, approximate.
   - TDS is only an input; there is no tax-regime computation.
   - It currently fails to import (§1).
2. **Leave lifecycle** (`hr/LEAVE_MANAGEMENT/main.py`). India entitlement table, a pending → approved/rejected state machine with an idempotence guard (`:138-140`), and balance consumption on approval (`:145-149`). Business days are Mon–Fri with no holiday calendar or half days.
3. **360 performance plus calibration** (`hr/PERFORMANCE_REVIEW_ENGINE/main.py:150-200`). Weighted 20/40/40 composite renormalised over the review types present, a 5-band rating, and an auditable calibration table (raw vs calibrated, by whom, when).
4. **Employee 360 data fusion** (`hr/EMPLOYEE_METRICS_ENGINE/main.py:36-183`). The only cross-system aggregation in scope: Zoho People + Payroll + Projects into a 30/50/20 composite scorecard and an org heatmap. This is a "Knackforge internal dashboard" feature.
5. **Statistical pipeline anomaly detection** (`operations/PIPELINE_MONITOR/main.py:44-65`). Rolling z-score per stage with stepwise risk levels and a cold-start baseline. It is directly reusable for SDLC/SRE stage-duration monitoring.
6. **SLA breach tracking** (`operations/SLA_MONITOR/main.py:46-89`). Deadline commitments, breach records de-duplicated per hour, due-soon window.
7. **Delivery metrics.** Sprint velocity vs target (`project_management/SPRINT_PLANNER/main.py:149-169`) and billable utilisation against a 40 h target (`project_management/TIME_TRACKER/main.py:121-142`).
8. **Quant finance and supply chain maths that is correct:**
   - Markowitz portfolio variance and Sharpe (`finance/PORTFOLIO_SIM_ENGINE/main.py:60-82`).
   - EOQ, safety stock and ROP (`supply_chain/INVENTORY_DECISION_ENGINE/main.py:64-73`).
   - OLS forecast (`finance/FINANCIAL_AI_ENGINE/main.py:19-32`).
   - Runway and reserve ratio (`finance/TREASURIX`).
   - Budget hard caps (`project_management/BUDGET_GUARDRAILS`).
9. **Local meeting-intelligence chain.** CALL_RECORDER (ffmpeg) → CALL_TRANSCRIBER (Whisper) → MEETING_SUMMARIZER and ACTION_ITEM_EXTRACTOR (regex). It is privacy-preserving and runs on-device.

**Systemic anti-pattern, "det_entropy":** 15 engines add `int(sha256(id)[:N],16) % K` into business scores. The result is reproducible but **semantically arbitrary**: two identical borrowers or claims with different IDs get different tiers or decisions. Examples: `finance/CREDIT_RISK_ENGINE:52` (up to 500 of 1000), `finance/STOCKMARKET_SIGNAL_ENGINE:49` (±100), `supply_chain/SUPPLY_CHAIN_ENGINE:52` (up to 500), `finance/BANKING_LOGIC_ENGINE:49-50` (scales the interest amount itself). It looks like generator scaffolding meant to "vary" outputs. **These scores and decisions should not be trusted for any real decision until the term is removed.**

---

## 4. Cross-agent dependencies and data flow

- **No agent imports another agent.** The only intra-repo imports are HR → `connectors.ZOHO_*` (PAYROLL_ENGINE `:6`, ATTENDANCE_MONITOR `:16`, EMPLOYEE_METRICS_ENGINE `:18-20`), and that path is broken (§1).
- **The alias delegators** (SAGE, SANDE, NIRVANA, HYPERSYNC, CONVERGENCE_BRIDGE) intend to forward to `velaris.agents.{STRATEGOS, LOCAL_*, SELF_CORRECTION_ENGINE, COHERENCE_SYNC_CORE, ORCHESTRIX, …}`. Those targets now live in `departments/_ai_core`, `it_infrastructure`, `security` and `executive`, so `import_module` always fails. The exception is silently swallowed (`except Exception: continue`, e.g. `operations/SAGE/main.py:24-25`) and health still reports "ok".
- **Implicit, docstring-only contracts:**
  - CALL_RECORDER returns `filepath` → `CallTranscriber.transcribe(filepath)` → `{text, segments}` → `MeetingSummarizer.summarize(transcript)` (`MEETING_SUMMARIZER:127` says "output from CALL_TRANSCRIBER") and `ActionItemExtractor.extract_from_segments(segments)`. No orchestrator wires them together.
  - ACTION_ITEM_EXTRACTOR and MEETING_SUMMARIZER duplicate the action-signal regexes and do not share code.
- **Shared state:** none across agents. Each SQLite agent owns a private DB:
  - Written next to the source file (`__file__`): `leaves.db`, `reviews.db`, `sprints.db`, `timelog.db`, `meetings.db`, `action_items.db`.
  - Relative to CWD (cwd-dependent): `employee_onboarding.db`, `recruitment.db`, `ops_data.db`, `pipeline_data.db`, `sla_data.db`.
  - Written to the absolute path `/live/agents/...`: SKILLPACK_LOADER, DRY_RUN_SIMULATION, ROLLBACK_ENGINE.
  - Employee IDs are free strings with no shared employee master. LEAVE, PERFORMANCE, TIME_TRACKER and ONBOARDING (integer autoincrement) cannot be joined reliably.
- **Natural joins that are missing:**
  - TIME_TRACKER hours vs EMPLOYEE_METRICS Zoho timelogs.
  - LEAVE_MANAGEMENT vs ATTENDANCE_MONITOR absence streaks.
  - SPRINT_PLANNER vs ZOHO_PROJECTS.
  - PAYROLL vs TREASURIX burn or runway.
  - BUDGET_GUARDRAILS vs FISCALIS budgets. Two separate budget dicts exist with no link.
- **Duplicates:** PRICING_OPTIMIZER (stub) and PRICING_OPTIMIZER_ENGINE; DYNAMICA and SIMULON; ECON_INTEL_CORE, ECONOMIC_INTELLIGENCE_MESH and MACRO_ECON_MODEL; METRIX, VALORA, OPTIMA and POLARIS (the same weighted-sum pattern); CODEX and HELIX (the same sha256 store).

---

## 5. External integrations

| Integration | Where | Status |
|---|---|---|
| **Zoho People** (attendance, leave, appraisal, employees) | `_connectors/ZOHO_PEOPLE/main.py` (80 LOC; BASE `people.zoho.in/api`), used by ATTENDANCE_MONITOR and EMPLOYEE_METRICS_ENGINE | Code is real: urllib plus OAuth refresh-token flow in `_connectors/ZOHO_CONNECTOR/main.py:18-52` (env `ZOHO_REFRESH_TOKEN`, etc.). **Unreachable**: package path `connectors.` does not exist after the reorg. India data centre is hard-coded. |
| **Zoho Payroll** (payslip, YTD, statutory, CTC) | `_connectors/ZOHO_PAYROLL/main.py` (`payroll.zoho.in/api/v1`), used by PAYROLL_ENGINE (opt-in `zoho_enabled`) and EMPLOYEE_METRICS_ENGINE | Same: broken import. |
| **Zoho Projects** (projects, tasks, timelogs) | `_connectors/ZOHO_PROJECTS/main.py`, used by EMPLOYEE_METRICS_ENGINE | Same. The "Zoho sync ready" claims in SPRINT_PLANNER, TIME_TRACKER and ACTION_ITEM_EXTRACTOR are unimplemented. |
| **ffmpeg** (system binary) | CALL_RECORDER `subprocess.Popen` (`:87`) | Real; needs ffmpeg on PATH. On macOS it needs the microphone TCC permission. |
| **Whisper / faster-whisper** (local model) | CALL_TRANSCRIBER `:49-58` | Real; optional dependency not declared in requirements. |
| LLM providers, banks, market data, ERP, Jira, Slack | — | **None.** CONNECTOR_LAYER "requests" are echoes. STOCKMARKET, MACRO and PRICING take caller-supplied numbers only. |

---

## 6. Plane mapping

| Plane | Agents (tag) | Assessment |
|---|---|---|
| **Finance** | TREASURIX, FISCALIS, LEDGERON, FORECASTA, FINANCIAL_AI_ENGINE, METRIX, VALORA, RISKON, PORTFOLIO_SIM (RULE-BASED); BANKING, CREDIT_RISK, CLAIMS, INSURANCE, MACRO, PRICING_ENGINE, STOCKMARKET (⚠hash); CASHFLOW_AI, NEURAL_ECONOMY, ECON_INTEL_CORE, PRICING_OPTIMIZER (STUB); FORMULA (HOLLOW) | A calculator library. No GL, AP/AR, invoicing, tax/GST, bank feeds or persistence. "Banking", "insurance" and "stock signal" are fintech-vertical demos, not an enterprise finance function. **Payroll lives in HR.** |
| **HR** | PAYROLL, LEAVE, PERFORMANCE_REVIEW, ONBOARDING, RECRUITMENT_ATS, ATTENDANCE, EMPLOYEE_METRICS (REAL); HR_TALENT (⚠hash) | **The most real plane in scope**, India- and Knackforge-specific. Three of the agents are blocked by the connector path. |
| **Operations** | OPS_REPORT, SLA_MONITOR, PIPELINE_MONITOR (REAL); QC (⚠hash); FLUXOR, BUSINESS_OPS, OPTIMA, POLARIS (trivial); 5 DEAD aliases; 6 STUB/HOLLOW; platform utilities CODEX, HELIX, GENEFLOW, MULTI_TENANT, SKILLPACK, CONNECTOR_LAYER | About half is mis-homed platform plumbing (§6a). The three REAL agents are generic ops tooling. |
| **Supply chain** | all 6 (⚠hash) | Formula demos. Inventory maths is correct, but every decision or tier is hash-perturbed. No supplier, PO, ERP or WMS data. |
| **PMO / delivery** | SPRINT_PLANNER, TIME_TRACKER (REAL); BUDGET_GUARDRAILS (genuine); others are trivial or stubs | Sprint and utilisation tracking is real. "Feasibility" and "initiative" are stubs. |
| **Communications** | CALL_RECORDER, CALL_TRANSCRIBER (ML), MEETING_SUMMARIZER, ACTION_ITEM_EXTRACTOR | A real local pipeline, but not orchestrated, and the extractor has a crash bug. |

**6a. Cross-plane items (misfiled; the lead should re-home them):**
- **SRE / observability:** PIPELINE_MONITOR (z-score anomaly), SLA_MONITOR, FLUXOR (spike detection), FAILPATH_CONTROL_ENGINE, ROLLBACK_ENGINE, DRY_RUN_SIMULATION.
- **Security:** EXECUTION_SANDBOX (escapable `exec`), SUCCESSOR_KEY_MODULE (unsalted single key), ROLLBACK_ENGINE (path traversal via `name`), HELIX and CODEX (integrity hashes).
- **Compliance:** PAYROLL_ENGINE (EPF, ESI and PT liability), LEAVE_MANAGEMENT (statutory leave), PERFORMANCE_REVIEW calibration audit trail, QUALITY_CONTROL regulatory flags. CALL_RECORDER records audio but has **no consent capture**, which raises DPDP and GDPR questions.
- **Admin control / tenancy:** MULTI_TENANT_ENGINE (in-memory, no isolation), SKILLPACK_LOADER (capability injection), BUDGET_GUARDRAILS (spend governance).
- **API management / integration:** CONNECTOR_LAYER (echo-only registry); `_connectors/ZOHO_*`, which is outside my scope but used by HR.
- **SDLC:** SPRINT_PLANNER, TIME_TRACKER, PIPELINE_MONITOR (its stage names in `__main__` are requirements_review, code_review and qa_testing), GENEFLOW (schema diff).
- **Deployment:** nothing in scope. The hard-coded `/live/agents/...` paths imply a Linux container layout that does not exist in the repo.
- **HITL:** manifests declare `hitl_required: true` for PAYROLL, EMPLOYEE_METRICS and PERFORMANCE_REVIEW. **No agent code enforces it**, and nothing in scope reads the flag.

---

## 7. Reality check vs README claims

| Claim | Evidence | Verdict |
|---|---|---|
| "343 domain-classified agents" | This scope has 79 directories, of which 20 are stub or dead, 15 are hash-noise toys and 15 are REAL. Only 38/79 have manifests, in two incompatible schemas: old `display_name/owner/health_check` vs new `domain/hitl_required/tags`. Old manifests literally say "Auto-generated placeholder" (CASHFLOW_AI, NEURAL_ECONOMY, BUSINESS_AUTOPILOT). | Inflated: counts directories, not capabilities. |
| "Every business function as an agent" | Finance has no GL, AP/AR, invoicing or tax. Supply chain has no procurement or suppliers. Ops is half platform utilities. | Partial. HR and delivery are closest. |
| "Organisational brain" / AI-native | 0 LLM calls, one optional local Whisper, no learning, no shared memory, no inter-agent messaging. The router loads 0 agents (`velaris/agents/router.py:16`). | **Not supported.** It is a library of independent Python classes. |
| "Intelligence" names (NEURAL_ECONOMY, FINANCIAL_AI_ENGINE, CASHFLOW_AI, BUSINESS_AUTOPILOT) | Respectively: echo stub, hand-written OLS, echo stub, echo stub. | Misleading naming. |
| Manifest "Zoho sync ready" (SPRINT_PLANNER, TIME_TRACKER, ACTION_ITEM_EXTRACTOR) | No Zoho code in those files. | False. |
| Manifest "LLM optional" (MEETING_SUMMARIZER) | The hook is never wired (`:119`). | False. |
| Prior audit: "~39% stubs, no LLM layer" | My measurement: 25% stub or dead, 44% including hash-noise toys; no LLM confirmed. | **Confirmed (directionally).** |
| Reorg integrity | Zoho imports broken. Alias delegators point at the removed `velaris.agents.*`. The TREASURIX test imports a non-existent path. All REAL code is untracked. | **Reorg incomplete. Commit risk is high.** |

---

## 8. Open questions

1. **Connector path.** Is `departments/_connectors` meant to become importable as `connectors` (via a shim or `sys.path`), or should the imports be rewritten? Until then PAYROLL, ATTENDANCE and EMPLOYEE_METRICS are dead.
2. **Loader.** Which component is meant to discover `departments/**/main.py`? `velaris/agents/router.py` scans only its own directory. Another section (core/runtime) should confirm whether any loader references `departments/` or `domains/`. Grep finds none in `velaris/`.
3. **det_entropy.** Is the hash noise intentional, for example demo variety, or generator residue? It should be removed before any scoring agent is used.
4. **Untracked work.** The 16 REAL/ML agents and `_connectors` were added on 10 Sep 2026 and are uncommitted. Will they be committed with the reorg, and is VKatOS (the port source) available for provenance or licensing?
5. **HITL.** Where is `hitl_required` supposed to be enforced: the backend, router or orchestrator? Nothing in scope reads it.
6. **Persistence.** There are 11 scattered SQLite files plus `/live/agents` paths, but the stack notes mention PostgreSQL. Is there a target data layer and an employee master ID?
7. **Compliance scope for payroll.** Should it add the EPF wage ceiling, EPS/EDLI, state-specific PT and new-vs-old regime TDS? Is it the system of record or only a Zoho mirror?
8. **Recording consent.** CALL_RECORDER has no consent or notice step and keeps sessions only in memory. Is there a policy owner?
9. **Fintech engines.** Are BANKING, INSURANCE, CLAIMS, CREDIT and STOCKMARKET in scope for a Knackforge BOS, or are they generator artefacts that should go to `_archived_agents`?
10. **Re-homing.** Should the ~14 platform, SRE and security agents now under operations and project_management (§6a) move to `_ai_core`, `it_infrastructure` or `security`?
