# Dead-code review (Velaris half of KAN-171)

Evidence generated 15 Nov 2026 from the code at the branch tip. Reproduce: `python3.11 tools/gen_agent_docs.py` (the "Called by"
section of each page under `docs/agents/`) for agents, and the module scan described below for `velaris/`.

## Result

| Area | Count | Decision |
|---|---|---|
| Agents with no other agent and no platform module that names them, only tests | 201 of 346 | KEEP. Agents are reached by the router loader and the HTTP allowlist by name; "no caller" does not mean unreachable. They are the candidates for the LLM-native tool wave (KAN-4). Every one has a behavioural test (KAN-61). |
| Agents named in no test and no code | 0 | (was 36 before KAN-61) |
| `velaris/` modules (non-test) that no production file imports | 6 | 1 deleted, 5 kept (below) |
| Security controls written but not connected | 0 found in Velaris | `velaris/security/secure.py` is a deny-everything stub nobody calls; kept, see below |

## Modules with no production importer (name, evidence, decision)

Method: for each of the 135 non-test, non-`__init__` modules under `velaris/`, search every `.py` file outside `velaris/tests`
for an import of the dotted name, `from <package> import <module>` or a relative import, and for the module name as a string.

| Module | Evidence | Decision |
|---|---|---|
| `velaris/backend/flow_engine.py` | Imported only by its own test (`test_flow_engine.py`); the real flow engine is `velaris/intel/flow.py`. It swallowed every step error and published on the router. | DELETED with its test. |
| `velaris/security/secure.py` | Imported only by two tests (`test_security_engine.py`, `test_loader_and_fail_closed.py`) that pin its fail-closed behaviour (validate and integrity_check both deny). | KEPT: a deny-by-default control pinned by tests; deleting it would remove the only test that says "the stub denies". Wire it in or remove it together with those tests when the owner decides the Phase 2 security design. |
| `velaris/control/desktop.py` | Documented stub for macOS accessibility automation; referenced by `velaris/control/__init__.py` docstring and its surface test. | KEPT: part of the control-surface design (stub on purpose). |
| `velaris/control/replay.py` | Record/replay with no model; tests only. | KEPT: feature module awaiting its caller (not proven dead, the hits in agent code are the word "replayed"). |
| `velaris/control/testing.py` | Test doubles, used by the test suite by design. | KEPT (untested-by-design means not applicable: it IS test support). |
| `velaris/agentkit/hiring_testkit.py` | Test support for hiring tests. | KEPT. |

## Agents with no code caller, by department (tests only)

**_ai_core** (46): ACF_CORE (rule_based), ADAPTIVE_ACTION_ENGINE (rule_based), AEIL (not_implemented), AGENT_EVOLUTION (rule_based), AIIE_KERNEL (real), ALK_ADAPT (rule_based), ALK_EVO (rule_based), AUTONOMOUS_PATCH_ENGINE (real), BEHAVIOR_SHAPING_NETWORK (rule_based), CAUSALITY_RESOLVER (rule_based), CCSF_CORE (rule_based), CLBPP_CORE (rule_based), CONTEXTUAL_SELF_MODEL (rule_based), CORE_CONVERGENCE (not_implemented), DECISION_COLLAPSE_ENGINE (rule_based), DSS_REPLICATION (rule_based), DSS_SCALER (rule_based), EAC_CORE (rule_based), FSCL (not_implemented), GCK (not_implemented), HFAL (real), HUMAN_APPROVAL_WORKFLOW (rule_based), HYPERSTATE_SYNTHESIZER (rule_based), INTER_AGENT_COHESION (rule_based), LOCAL_BIOMETRICS_INTERFACE (rule_based), LOCAL_EMBEDDING_ENGINE (real), LONG_RUN_STABILITY_SIMULATOR (rule_based), LYRA_VOICE_ENGINE (real), MCD (rule_based), META_REINFORCEMENT_CORE (rule_based), MODEL_REGISTRY_CANARY (real), MULTILINGUAL_BRAIN (rule_based), NAVARCH (rule_based), NEURAL_ALIGNMENT_ENGINE (rule_based), NEURAL_CONSTRAINT_FIELD (rule_based), NEURAL_CREATIVITY_ENGINE (rule_based), NEURAL_DRIFT_MONITOR (rule_based), NEURAL_MESH (rule_based), NEURAL_POLICY_MESH (rule_based), PERSONALITY_MOD (rule_based), SCHEDULON (rule_based), SELF_CONSISTENCY (real), SELF_HISTORY (rule_based), SELF_IDENTITY (rule_based), SOUL_CORE_EXT (rule_based), VHOE_CORE (rule_based)

**client_success** (1): LOGISTA (rule_based)

**communications** (3): ACTION_ITEM_EXTRACTOR (real), CALL_RECORDER (real), MEETING_SUMMARIZER (real)

**data_knowledge** (9): CHROMOS (rule_based), EPISODIC_MEMORY (rule_based), MEMORY_CLOUD_EXPAND (real), MEMORY_DRIFT_DETECTOR (real), MEMORY_MESH (real), MEMORY_REALLOCATOR (rule_based), SHORTTERM_MEMORY (rule_based), STREAM_PROCESSOR (rule_based), TEMPORAL_SNAPSHOTS (real)

**executive** (10): BUSINESS_DNA (rule_based), BUSINESS_MODEL_ENGINE (rule_based), COMPETITIVE_SCANNER (real), INSIGHTA (rule_based), OPPORTUNITY_RADAR (rule_based), ORACLE (rule_based), PROBABILIS (rule_based), REALMEX (rule_based), STOCHASTIX (rule_based), VIRALYTICA (rule_based)

**finance** (16): BANKING_LOGIC_ENGINE (rule_based), CASHFLOW_AI (rule_based), CLAIMS_ASSESSMENT_ENGINE (rule_based), CREDIT_RISK_ENGINE (rule_based), ECONOMIC_INTELLIGENCE_MESH (rule_based), FINANCIAL_AI_ENGINE (rule_based), FORECASTA (rule_based), FORMULA (rule_based), INSURANCE_POLICY_ENGINE (rule_based), LEDGERON (rule_based), MACRO_ECON_MODEL (rule_based), METRIX (rule_based), NEURAL_ECONOMY (rule_based), RISKON (rule_based), STOCKMARKET_SIGNAL_ENGINE (rule_based), VALORA (rule_based)

**hr** (5): ATTENDANCE_MONITOR (rule_based), EMPLOYEE_METRICS_ENGINE (rule_based), EMPLOYEE_ONBOARDING (real), HR_TALENT_ENGINE (real), RECRUITMENT_ATS (real)

**it_infrastructure** (16): COMPUTE_KERNEL (rule_based), COMPUTE_SCALER (rule_based), DISTRIBUTED_FABRIC (rule_based), ENERGY_MANAGER (rule_based), LATENCY_CONTROLLER (rule_based), LOAD_DISTRIBUTOR (rule_based), MULTI_TENANCY_GRID (rule_based), NETWORK_OPTIMIZER (rule_based), OFFLINE_EXECUTION_ENGINE (rule_based), OFFLINE_REGISTRY (real), OFFLINE_RUNTIME_PACKAGER (real), PARALLEL_CORE (rule_based), RESOURCE_OPTIMIZER (rule_based), RESOURCE_ORCHESTRATOR (rule_based), SYSTEM_TELEMETRY (rule_based), THROUGHPUT_MANAGER (rule_based)

**legal_compliance** (6): EACPE_ALIGNMENT (real), EACPE_HUMAN_GUARD (rule_based), EACPE_PROTOCOL (rule_based), GOVERNANCE_ADAPTATION_LOOP (rule_based), GOVERNANCE_KERNEL (rule_based), LEGAL_INTELLIGENCE_ENGINE (rule_based)

**marketing** (10): ADAPTIVE_BRANDING (rule_based), ARTESIA (rule_based), AUTONOMOUS_MARKETING_ENGINE (rule_based), BRAND_NARRATIVE (rule_based), BUSINESS_FUNNEL_DESIGNER (rule_based), CREATIVA (rule_based), CREATIVE_ENGINE (real), CREATIVE_HOLODECK (rule_based), IMAGINA (rule_based), VMRK (real)

**operations** (24): BUSINESS_AUTOPILOT (rule_based), BUSINESS_OPS_ENGINE (rule_based), CODEX (rule_based), CONNECTOR_LAYER (rule_based), CONVERGENCE_BRIDGE (not_implemented), DYNAMICA (rule_based), FABRICA (rule_based), FLUXOR (rule_based), GENEFLOW (rule_based), HELIX (rule_based), HYPERSYNC (not_implemented), MULTI_TENANT_ENGINE (rule_based), NIRVANA (not_implemented), OPERATUS (rule_based), OPS_REPORT (real), OPTIMA (rule_based), PIPELINE_MONITOR (real), POLARIS (rule_based), QUALITY_CONTROL_ENGINE (rule_based), SAGE (not_implemented), SANDE (not_implemented), SKILLPACK_LOADER (real), SLA_MONITOR (real), WORKFLOW_ANALYST (real)

**project_management** (13): ACTION_SANDBOX (rule_based), BUDGET_GUARDRAILS (rule_based), DIGITAL_TWIN_XR_ENGINE (rule_based), DRY_RUN_SIMULATION (real), EXECUTION_SANDBOX (rule_based), FAILPATH_CONTROL_ENGINE (rule_based), FEASIBILITY_ENGINE (rule_based), ROLLBACK_ENGINE (real), SIMULON (rule_based), SPRINT_PLANNER (real), SUCCESSOR_KEY_MODULE (rule_based), TACTICIAN (rule_based), TIME_TRACKER (real)

**sales** (13): AMPLIFEX (rule_based), ATTRACTA (rule_based), AUTONOMOUS_SALES_NAVIGATOR (rule_based), COHORTUS (rule_based), CONVERTA (rule_based), DOMAIN_ADVISOR (rule_based), DOMAIN_EXPANSION (rule_based), DOMAIN_MASTERY (rule_based), DOMAIN_REFINER (rule_based), DOMAIN_SCOUT (rule_based), RETENTA (rule_based), TARGETA (rule_based), WHATSAPP_BRIEFING (real)

**security** (23): AEGIS (rule_based), AGENT_CONTAINMENT_MODES (rule_based), ARGUS (rule_based), AUDITOR (rule_based), COGNITIVE_INTENT_FIREWALL (real), COMPLIANCE_GUARD (rule_based), CYBER_RISK_ENGINE (rule_based), DECISION_FIREWALL (rule_based), DEEP_AUDIT_ENGINE (real), HARD_LOCKDOWN_MODE (rule_based), IDENTITY_FRAMEWORK (real), MFA_RECOVERY_WORKFLOW (rule_based), OVERSIGHT_MONITOR (rule_based), OVERWATCH (rule_based), OWNER_VERIFICATION (rule_based), PIN_UNLOCK_LAYER (rule_based), SAFETY_PERIMETER (rule_based), SELF_AUDIT (real), SENTINELDNA (rule_based), SIGNED_AUDIT_CHAIN (real), SOFT_LOCKDOWN_MODE (rule_based), THREAT_DETECTION_MESH (rule_based), ZERO_TRUST_PIPELINE (real)

**supply_chain** (6): FLEET_HEALTH_ENGINE (rule_based), INVENTORY_DECISION_ENGINE (rule_based), MACHINE_LIFECYCLE_ENGINE (rule_based), ROUTE_OPTIMIZATION_ENGINE (rule_based), SUPPLY_CHAIN_ENGINE (rule_based), WAREHOUSE_FLOW_ENGINE (rule_based)

## Not covered here

The AetherOS items of KAN-171 (core/approval, core/sandbox, core/bootstrap, ...) belong to the AetherOS worktree. The independent
check on the ticket already corrected one claim (core/services/pipeline_service.py is live). The Confluence table the ticket asks
for needs the Atlassian write tools and the owner's decision on the 201 agents.

## Re-check on main, 22 Nov 2026 (KAN-171 final pass)

Re-derived with an import graph over every tracked `.py` file plus string, config and doc search. Agents under `departments/` are
loaded by name, so all 346 stay KEEP (documented one page each under `docs/agents/`, candidates for the KAN-4 tool wave). Result:

| Module | Evidence | Decision |
|---|---|---|
| `velaris/core/main.py`, `velaris/core/loader.py`, `velaris/core/config.py` | Phase-1 bootstrap stubs: `velaris_start()` only logs, `initialize_core()` only logs, `PROJECT_ROOT` and `VELARIS_CONFIG` have no reader. No importer, no test, no string reference, not in README or deploy docs (only the archived code map calls them stub or dead). | DELETED. `exceptions.py` (used by `access.py`) and `utils.py` (used by VIGILIS) stay. |
| everything else flagged by the graph under `velaris/agentkit`, `velaris/intel`, `velaris/control`, `tools/` | Imported by agents loaded by name, or by tools and tests. | KEEP (library or tool). |
