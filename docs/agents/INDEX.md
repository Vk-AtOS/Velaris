# Velaris agent reference

346 agents, generated from source by `tools/gen_agent_docs.py`.

## _ai_core (133)

| Agent | Status | Purpose |
|---|---|---|
| [AAE_POLICY](_ai_core/AAE_POLICY.md) | rule_based | AAE policy: decides whether a proposed action may run. |
| [AAE_RUNTIME](_ai_core/AAE_RUNTIME.md) | real | AAE runtime: runs one approved action, once, and keeps a record of it. |
| [ACF_CONTEXT](_ai_core/ACF_CONTEXT.md) | real | ACF context: wraps a raw input in a screened envelope before anything acts on it. |
| [ACF_CORE](_ai_core/ACF_CORE.md) | rule_based | ACF core: the intake pipeline that chains the other three ACF agents. |
| [ACF_FUSION](_ai_core/ACF_FUSION.md) | rule_based | ACF fusion: merges two records about the same thing and reports where they disagree. |
| [ACF_ROUTER](_ai_core/ACF_ROUTER.md) | real | ACF router: sends a signal to a destination by declared rules. |
| [ACTION_MODELING_CORE](_ai_core/ACTION_MODELING_CORE.md) | rule_based | Action modelling core: orders the actions needed for an intent by their preconditions. |
| [ADAPTIVE_ACTION_ENGINE](_ai_core/ADAPTIVE_ACTION_ENGINE.md) | rule_based | Adaptive action engine: tries the action that has worked best for this kind of situation. |
| [ADVANCED_SEARCH_ENGINE](_ai_core/ADVANCED_SEARCH_ENGINE.md) | real |  |
| [AEIL](_ai_core/AEIL.md) | rule_based | Alias wrapper agent: AEIL |
| [AGENT_EVOLUTION](_ai_core/AGENT_EVOLUTION.md) | rule_based |  |
| [AGENT_LIFECYCLE](_ai_core/AGENT_LIFECYCLE.md) | rule_based | Agent lifecycle: message-style front for AGENT_LIFECYCLE_MANAGER. |
| [AGENT_LIFECYCLE_MANAGER](_ai_core/AGENT_LIFECYCLE_MANAGER.md) | rule_based | Agent lifecycle manager: the state machine for every agent's operational state. |
| [AIIE_KERNEL](_ai_core/AIIE_KERNEL.md) | real | AIIE kernel: runs the initiative pipeline stage by stage and stops at the first stage that does not pass. |
| [ALK_ADAPT](_ai_core/ALK_ADAPT.md) | rule_based | ALK adapt: nudges a numeric setting toward the value that brings a metric to its target. |
| [ALK_EVO](_ai_core/ALK_EVO.md) | rule_based | ALK evo: champion/challenger selection between named versions of a configuration. |
| [ASEL](_ai_core/ASEL.md) | rule_based | Alias wrapper agent: ASEL |
| [ASEL_EVALUATOR](_ai_core/ASEL_EVALUATOR.md) | rule_based | ASEL evaluator: says whether an executed plan achieved what it was for. |
| [ASEL_EXECUTOR](_ai_core/ASEL_EXECUTOR.md) | rule_based | ASEL executor: runs the steps of a plan in dependency order through caller-supplied handlers. |
| [ASEL_PLANNER](_ai_core/ASEL_PLANNER.md) | rule_based | ASEL planner: schedules a set of dependent tasks (critical path method). |
| [ASEL_ROUTER](_ai_core/ASEL_ROUTER.md) | rule_based | ASEL router: decides which handler carries out each plan step. |
| [ASEL_STRATEGIST](_ai_core/ASEL_STRATEGIST.md) | rule_based | ASEL strategist: picks one option from several by weighted multi-criteria scoring. |
| [AUTONOMOUS_PATCH_ENGINE](_ai_core/AUTONOMOUS_PATCH_ENGINE.md) | real |  |
| [AUTONOMOUS_RESEARCH_ENGINE](_ai_core/AUTONOMOUS_RESEARCH_ENGINE.md) | real |  |
| [AUTO_LEARN_CORE](_ai_core/AUTO_LEARN_CORE.md) | rule_based | Auto-learn core: a ledger of which option worked, per context. |
| [BEHAVIOR_SHAPING_NETWORK](_ai_core/BEHAVIOR_SHAPING_NETWORK.md) | rule_based | Behaviour shaping: forces a proposed set of settings inside declared limits. |
| [CAUSALITY_RESOLVER](_ai_core/CAUSALITY_RESOLVER.md) | rule_based | Causality resolver: merges observed cause-to-effect paths into one graph and ranks root causes. |
| [CCSF_CORE](_ai_core/CCSF_CORE.md) | rule_based | CCSF core: one agreed view of an entity that several systems each hold a copy of. |
| [CCSF_FUSION](_ai_core/CCSF_FUSION.md) | rule_based | CCSF fusion: merges snapshots of one entity reported by any number of systems. |
| [CCSF_RESOLVER](_ai_core/CCSF_RESOLVER.md) | rule_based | CCSF resolver: settles conflicting field values by a declared strategy per field. |
| [CLBPP_CORE](_ai_core/CLBPP_CORE.md) | rule_based | CLBPP core: the workload ledger for a pool of workers (people, queues or agents). |
| [CLBPP_DISTRIBUTOR](_ai_core/CLBPP_DISTRIBUTOR.md) | rule_based | CLBPP distributor: assigns a batch of tasks to workers without overfilling anyone. |
| [CLBPP_OVERLOAD_MONITOR](_ai_core/CLBPP_OVERLOAD_MONITOR.md) | rule_based | CLBPP overload monitor: flags a worker whose utilisation stays high. |
| [CLBPP_PREDICTIVE_BALANCER](_ai_core/CLBPP_PREDICTIVE_BALANCER.md) | rule_based | CLBPP predictive balancer: forecasts each worker's utilisation and plans moves ahead of overload. |
| [COGNITIVE_LOAD_BALANCER](_ai_core/COGNITIVE_LOAD_BALANCER.md) | rule_based |  |
| [COHERENCE_SYNC_CORE](_ai_core/COHERENCE_SYNC_CORE.md) | rule_based | Coherence sync core: detects when copies of the same state have drifted apart, and says how to fix each. |
| [CONTEXTUAL_SELF_MODEL](_ai_core/CONTEXTUAL_SELF_MODEL.md) | rule_based | Contextual self model: the platform's own record of facts about itself, with per-context overrides. |
| [CONTROL_LAYER](_ai_core/CONTROL_LAYER.md) | rule_based | CONTROL_LAYER: narrow, scripted work in files, a terminal or a browser, logged and mostly reversible. |
| [CORE_CONVERGENCE](_ai_core/CORE_CONVERGENCE.md) | rule_based | Alias wrapper agent: CORE_CONVERGENCE |
| [CRK](_ai_core/CRK.md) | rule_based | Alias wrapper agent: CRK |
| [CRK_CHAIN](_ai_core/CRK_CHAIN.md) | rule_based | CRK chain: puts the steps of an argument in dependency order and seals them. |
| [CRK_CONTEXT](_ai_core/CRK_CONTEXT.md) | real | CRK context: turns raw facts into a screened fact set that rules can safely run on. |
| [CRK_INTENT](_ai_core/CRK_INTENT.md) | real | CRK intent: names what a short request is asking for, from a fixed list of intents. |
| [CRK_REASONER](_ai_core/CRK_REASONER.md) | rule_based | CRK reasoner: forward-chaining rule inference over a set of facts. |
| [CRK_VALIDATOR](_ai_core/CRK_VALIDATOR.md) | rule_based | CRK validator: checks every step of an argument against fixed rules and names the first that fails. |
| [CSG_STATEALIGN](_ai_core/CSG_STATEALIGN.md) | rule_based | CSG state align: compares the state something should have with the state it has, and produces the fix. |
| [CSG_TEMPORAL](_ai_core/CSG_TEMPORAL.md) | rule_based | CSG temporal: checks that a sequence of timestamped events is consistent in time. |
| [CSM_CORE](_ai_core/CSM_CORE.md) | rule_based | CSM core: a register of numeric goals, reviewed with the other CSM agents. |
| [CSM_LINKER](_ai_core/CSM_LINKER.md) | rule_based | CSM linker: a register of named relationships between things (goals, policies, owners, accounts). |
| [CSM_POLICY](_ai_core/CSM_POLICY.md) | rule_based | CSM policy: builds a checkable policy from a short specification, and checks records against it. |
| [CSM_REASONER](_ai_core/CSM_REASONER.md) | rule_based | CSM reasoner: a quick read of where a goal stands and what posture to take. |
| [DECISION_COLLAPSE_ENGINE](_ai_core/DECISION_COLLAPSE_ENGINE.md) | rule_based | Decision collapse engine: reduces several scored options to one decision, or says it cannot. |
| [DECISION_GRAPH_ENGINE](_ai_core/DECISION_GRAPH_ENGINE.md) | rule_based | Decision graph engine: turns a plan into a dependency graph and checks it can be followed. |
| [DSS_CLUSTER_MANAGER](_ai_core/DSS_CLUSTER_MANAGER.md) | rule_based | DSS cluster manager: the registry of worker nodes for the DSS family. |
| [DSS_FAILOVER](_ai_core/DSS_FAILOVER.md) | rule_based | DSS failover: keeps one primary node and promotes a standby when it goes down. |
| [DSS_LOAD_BALANCER](_ai_core/DSS_LOAD_BALANCER.md) | rule_based | DSS load balancer: weighted least-load node selection with health checks and shedding. |
| [DSS_MONITOR](_ai_core/DSS_MONITOR.md) | rule_based | DSS monitor: classifies each node as healthy, degraded or down. |
| [DSS_REPLICATION](_ai_core/DSS_REPLICATION.md) | rule_based | DSS replication: decides which nodes hold the copies of a key, and audits the result. |
| [DSS_SCALER](_ai_core/DSS_SCALER.md) | rule_based | DSS scaler: decides how many nodes the cluster should run (target tracking). |
| [EAC_AUDIT](_ai_core/EAC_AUDIT.md) | real | EAC_AUDIT: the compliance family's view of the audit trail. |
| [EAC_COMPLIANCE](_ai_core/EAC_COMPLIANCE.md) | rule_based | EAC_COMPLIANCE: a register of compliance controls and the check of a record against them. |
| [EAC_CORE](_ai_core/EAC_CORE.md) | rule_based | EAC_CORE: one compliance assessment, end to end. |
| [ENGINE](_ai_core/ENGINE.md) | rule_based |  |
| [EOF_CORE](_ai_core/EOF_CORE.md) | rule_based | EOF_CORE: turns a plan into ordered, policy-checked hand-offs. |
| [EOF_GATEWAY](_ai_core/EOF_GATEWAY.md) | real | EOF_GATEWAY: a durable message hand-off between agents. |
| [EOF_POLICY](_ai_core/EOF_POLICY.md) | rule_based | EOF_POLICY: checks one record (a plan step, an action) against one declared policy. |
| [FSCL](_ai_core/FSCL.md) | rule_based | Alias wrapper agent: FSCL |
| [GCK](_ai_core/GCK.md) | rule_based | Alias wrapper agent: GCK |
| [HFAL](_ai_core/HFAL.md) | real |  |
| [HUMAN_APPROVAL_WORKFLOW](_ai_core/HUMAN_APPROVAL_WORKFLOW.md) | rule_based | HUMAN_APPROVAL_WORKFLOW: an in-memory approval request book. |
| [HYPERSTATE_SYNTHESIZER](_ai_core/HYPERSTATE_SYNTHESIZER.md) | rule_based | HYPERSTATE_SYNTHESIZER: merges several partial state snapshots into one, reporting conflicts. |
| [HYPER_REASONER](_ai_core/HYPER_REASONER.md) | rule_based | HYPER_REASONER: structural validation of a decision graph before anything is planned from it. |
| [INTENT_SYNTHESIZER](_ai_core/INTENT_SYNTHESIZER.md) | real | INTENT_SYNTHESIZER: turns a loosely worded idea into a structured intent that can be planned. |
| [INTER_AGENT_COHESION](_ai_core/INTER_AGENT_COHESION.md) | rule_based | INTER_AGENT_COHESION: a shared board where agents leave facts for each other without overwriting each other. |
| [LOCAL_BIOMETRICS_INTERFACE](_ai_core/LOCAL_BIOMETRICS_INTERFACE.md) | rule_based |  |
| [LOCAL_EMBEDDING_ENGINE](_ai_core/LOCAL_EMBEDDING_ENGINE.md) | real | LOCAL_EMBEDDING_ENGINE: text to vectors without sending anything off the machine, and similarity search. |
| [LONG_RUN_STABILITY_SIMULATOR](_ai_core/LONG_RUN_STABILITY_SIMULATOR.md) | rule_based |  |
| [LYRA](_ai_core/LYRA.md) | rule_based |  |
| [LYRA_VOICE_ENGINE](_ai_core/LYRA_VOICE_ENGINE.md) | real |  |
| [MCD](_ai_core/MCD.md) | rule_based |  |
| [MCFE_CLASSIFIER](_ai_core/MCFE_CLASSIFIER.md) | real | MCFE_CLASSIFIER: which subject domain is a piece of text about? |
| [MCFE_CORE](_ai_core/MCFE_CORE.md) | real | MCFE_CORE: one pass over an incoming text: domain, fields, department. |
| [MCFE_FIELDGEN](_ai_core/MCFE_FIELDGEN.md) | rule_based | MCFE_FIELDGEN: the fields a record of a given domain needs, and their values found in a text. |
| [MCFE_ROUTER](_ai_core/MCFE_ROUTER.md) | rule_based | MCFE_ROUTER: which department handles a subject domain. |
| [META_REASONING_CORE](_ai_core/META_REASONING_CORE.md) | real | META_REASONING_CORE: draft, check against a rubric, revise, re-check; keep the best attempt. |
| [META_REINFORCEMENT_CORE](_ai_core/META_REINFORCEMENT_CORE.md) | rule_based | META_REINFORCEMENT_CORE: picks between options from their recorded outcomes (UCB1 bandit). |
| [MODEL_COUNCIL](_ai_core/MODEL_COUNCIL.md) | real | Model council agent: several models answer, review each other blind, one answer comes back. |
| [MODEL_REGISTRY_CANARY](_ai_core/MODEL_REGISTRY_CANARY.md) | real |  |
| [MPC_CORE](_ai_core/MPC_CORE.md) | rule_based | MPC_CORE: clean every source's record (MPC_PREPROC), then merge them (MPC_FUSION). |
| [MPC_FUSION](_ai_core/MPC_FUSION.md) | rule_based | MPC_FUSION: merges records about the same thing from several sources into one, field by field. |
| [MPC_PREPROC](_ai_core/MPC_PREPROC.md) | real | MPC_PREPROC: cleans raw records so that records from different sources can be compared. |
| [MRF_EVAL](_ai_core/MRF_EVAL.md) | real | MRF_EVAL: scores a piece of output (a draft, an answer, a JSON reply) against a stated rubric. |
| [MRF_REFLECT](_ai_core/MRF_REFLECT.md) | real | MRF_REFLECT: turns an evaluation's failures into revision instructions, and optionally has a model apply them. |
| [MULTILINGUAL_BRAIN](_ai_core/MULTILINGUAL_BRAIN.md) | rule_based |  |
| [NAVARCH](_ai_core/NAVARCH.md) | rule_based |  |
| [NEURAL_ALIGNMENT_ENGINE](_ai_core/NEURAL_ALIGNMENT_ENGINE.md) | rule_based | NEURAL_ALIGNMENT_ENGINE: does a proposed piece of work serve a declared company objective? |
| [NEURAL_CONSTRAINT_FIELD](_ai_core/NEURAL_CONSTRAINT_FIELD.md) | rule_based | NEURAL_CONSTRAINT_FIELD: evaluates declared constraints over a proposed action. |
| [NEURAL_CREATIVITY_ENGINE](_ai_core/NEURAL_CREATIVITY_ENGINE.md) | rule_based |  |
| [NEURAL_DRIFT_MONITOR](_ai_core/NEURAL_DRIFT_MONITOR.md) | rule_based | NEURAL_DRIFT_MONITOR: has a numeric measure moved away from its baseline? |
| [NEURAL_MESH](_ai_core/NEURAL_MESH.md) | rule_based |  |
| [NEURAL_POLICY_MESH](_ai_core/NEURAL_POLICY_MESH.md) | rule_based | NEURAL_POLICY_MESH: every registered policy must agree before an intent goes ahead. |
| [ORCHESTRIX](_ai_core/ORCHESTRIX.md) | rule_based |  |
| [PERSONALITY_MOD](_ai_core/PERSONALITY_MOD.md) | rule_based | PERSONALITY_MOD: the house style for messages agents send, and the code that applies it. |
| [PRIME](_ai_core/PRIME.md) | real | PRIME: the Velaris controller, and the one place that decides what an agent or person may do. |
| [RCI_CONTEXT](_ai_core/RCI_CONTEXT.md) | rule_based | RCI_CONTEXT: builds a bounded "current context" from a stream of events. |
| [RCI_CORE](_ai_core/RCI_CORE.md) | real | RCI_CORE: the way events get into the running context, and the way the context is read. |
| [RCI_STREAM](_ai_core/RCI_STREAM.md) | real | RCI_STREAM: durable, append-only event streams with offsets. |
| [RECURSIVE_GOAL_PLANNER](_ai_core/RECURSIVE_GOAL_PLANNER.md) | real | RECURSIVE_GOAL_PLANNER: flattens a nested goal into a dependency-ordered task list. |
| [REGISTRY](_ai_core/REGISTRY.md) | real |  |
| [SCHEDULON](_ai_core/SCHEDULON.md) | rule_based |  |
| [SELF_CONSISTENCY](_ai_core/SELF_CONSISTENCY.md) | real | SELF_CONSISTENCY: ask the same question N times and measure how far the answers agree. |
| [SELF_CORRECTION_ENGINE](_ai_core/SELF_CORRECTION_ENGINE.md) | rule_based | SELF_CORRECTION_ENGINE: repairs a record against a declared schema and says what it changed. |
| [SELF_DIRECTED_TASKER](_ai_core/SELF_DIRECTED_TASKER.md) | rule_based | SELF_DIRECTED_TASKER: works through an ordered task list, releasing tasks as their dependencies finish. |
| [SELF_HISTORY](_ai_core/SELF_HISTORY.md) | rule_based |  |
| [SELF_IDENTITY](_ai_core/SELF_IDENTITY.md) | rule_based | SELF_IDENTITY: who this Velaris installation is, as a recorded, versioned fact sheet. |
| [SOUL_CORE_EXT](_ai_core/SOUL_CORE_EXT.md) | rule_based | SOUL_CORE_EXT: versioned operating settings for this Velaris instance. |
| [SOUL_VELARIS](_ai_core/SOUL_VELARIS.md) | rule_based | SOUL_VELARIS: the company's charter for its agents, and the check of an action against it. |
| [STRATEGOS](_ai_core/STRATEGOS.md) | rule_based |  |
| [UIE_CORE](_ai_core/UIE_CORE.md) | rule_based | UIE_CORE: a raw message in, a decision about the next step out. |
| [UIE_REASONER](_ai_core/UIE_REASONER.md) | rule_based | UIE_REASONER: decides what should happen next with an interpreted request. |
| [UIE_SEMANTICS](_ai_core/UIE_SEMANTICS.md) | rule_based | UIE_SEMANTICS: turns a message into a structured request frame. |
| [UIE_SIGNAL](_ai_core/UIE_SIGNAL.md) | real | UIE_SIGNAL: first contact with an incoming message, before anything tries to interpret it. |
| [VCAS_AUTOPILOT](_ai_core/VCAS_AUTOPILOT.md) | real | VCAS_AUTOPILOT: runs a task through a registered handler, once, and only with an approval. |
| [VCAS_CORE](_ai_core/VCAS_CORE.md) | real | VCAS_CORE: submit a task, and it runs on autopilot only when it is allowed to. |
| [VCAS_ROUTER](_ai_core/VCAS_ROUTER.md) | rule_based | VCAS_ROUTER: can this task run on autopilot at all? |
| [VCAS_SUPERVISOR](_ai_core/VCAS_SUPERVISOR.md) | rule_based | VCAS_SUPERVISOR: says whether a task may run, by asking PRIME. |
| [VHOE_ANALYTICS](_ai_core/VHOE_ANALYTICS.md) | rule_based | VHOE_ANALYTICS: how the work actually went, from completed-work records. |
| [VHOE_CORE](_ai_core/VHOE_CORE.md) | rule_based | VHOE_CORE: one planning pass over the work queue. |
| [VHOE_OPTIMIZER](_ai_core/VHOE_OPTIMIZER.md) | rule_based | VHOE_OPTIMIZER: assigns a whole queue of work to a pool of workers. |
| [VHOE_ROUTER](_ai_core/VHOE_ROUTER.md) | rule_based | VHOE_ROUTER: assigns one piece of work to the person or agent best placed to take it. |
| [VPSE_CORE](_ai_core/VPSE_CORE.md) | rule_based | VPSE_CORE: projects a series forward and shows what each scenario does to every future period. |
| [VPSE_MODELER](_ai_core/VPSE_MODELER.md) | rule_based | VPSE_MODELER: fits a straight-line trend to a numeric series and projects it forward. |
| [VPSE_SCENARIO](_ai_core/VPSE_SCENARIO.md) | rule_based | VPSE_SCENARIO: recomputes outcomes under what-if changes to their drivers. |

## _connectors (6)

| Agent | Status | Purpose |
|---|---|---|
| [CONFLUENCE](_connectors/CONFLUENCE.md) | real | CONFLUENCE connector: Atlassian Confluence Cloud (API token + account email). |
| [JIRA](_connectors/JIRA.md) | real | JIRA connector: Atlassian Jira Cloud REST API v3 (API token + account email, HTTP Basic). |
| [ZOHO_CONNECTOR](_connectors/ZOHO_CONNECTOR.md) | real |  |
| [ZOHO_PAYROLL](_connectors/ZOHO_PAYROLL.md) | rule_based |  |
| [ZOHO_PEOPLE](_connectors/ZOHO_PEOPLE.md) | rule_based |  |
| [ZOHO_PROJECTS](_connectors/ZOHO_PROJECTS.md) | rule_based |  |

## client_success (1)

| Agent | Status | Purpose |
|---|---|---|
| [LOGISTA](client_success/LOGISTA.md) | rule_based |  |

## communications (4)

| Agent | Status | Purpose |
|---|---|---|
| [ACTION_ITEM_EXTRACTOR](communications/ACTION_ITEM_EXTRACTOR.md) | real |  |
| [CALL_RECORDER](communications/CALL_RECORDER.md) | real |  |
| [CALL_TRANSCRIBER](communications/CALL_TRANSCRIBER.md) | real |  |
| [MEETING_SUMMARIZER](communications/MEETING_SUMMARIZER.md) | real |  |

## data_knowledge (14)

| Agent | Status | Purpose |
|---|---|---|
| [CHROMOS](data_knowledge/CHROMOS.md) | rule_based |  |
| [DOCUMENT_LIBRARY](data_knowledge/DOCUMENT_LIBRARY.md) | real | Document library agent: a company's files, searchable and answerable with citations. |
| [EPISODIC_MEMORY](data_knowledge/EPISODIC_MEMORY.md) | rule_based | EPISODIC_MEMORY: a durable, time-ordered log of what happened. |
| [GLOBAL_STATE_MAP](data_knowledge/GLOBAL_STATE_MAP.md) | rule_based | GLOBAL_STATE_MAP: one shared, versioned map of state that several agents read and write. |
| [LOCAL_MEMORY_STORE](data_knowledge/LOCAL_MEMORY_STORE.md) | rule_based | LOCAL_MEMORY_STORE: a small key-value store on this machine's disk. |
| [LONGTERM_MEMORY](data_knowledge/LONGTERM_MEMORY.md) | real |  |
| [MEMORY_CLOUD_EXPAND](data_knowledge/MEMORY_CLOUD_EXPAND.md) | real | MEMORY_CLOUD_EXPAND: move a scope's memories between Velaris installations as a checked file. |
| [MEMORY_DRIFT_DETECTOR](data_knowledge/MEMORY_DRIFT_DETECTOR.md) | real |  |
| [MEMORY_FABRIC](data_knowledge/MEMORY_FABRIC.md) | rule_based |  |
| [MEMORY_MESH](data_knowledge/MEMORY_MESH.md) | real | MEMORY_MESH: which memory node serves which scope, and recall across several scopes. |
| [MEMORY_REALLOCATOR](data_knowledge/MEMORY_REALLOCATOR.md) | rule_based | MEMORY_REALLOCATOR: divide a RAM budget among declared consumers. |
| [SHORTTERM_MEMORY](data_knowledge/SHORTTERM_MEMORY.md) | rule_based | SHORTTERM_MEMORY: bounded working memory per session. |
| [STREAM_PROCESSOR](data_knowledge/STREAM_PROCESSOR.md) | rule_based | STREAM_PROCESSOR: tumbling-window aggregation over event streams. |
| [TEMPORAL_SNAPSHOTS](data_knowledge/TEMPORAL_SNAPSHOTS.md) | real |  |

## executive (12)

| Agent | Status | Purpose |
|---|---|---|
| [BUSINESS_DNA](executive/BUSINESS_DNA.md) | rule_based | BUSINESS_DNA: the company profile register. |
| [BUSINESS_MODEL_ENGINE](executive/BUSINESS_MODEL_ENGINE.md) | rule_based | BUSINESS_MODEL_ENGINE: revenue-model analysis of the revenue streams the caller supplies. |
| [COMPETITIVE_SCANNER](executive/COMPETITIVE_SCANNER.md) | real | COMPETITIVE_SCANNER: read competitors' public pages and report what changed. |
| [INSIGHTA](executive/INSIGHTA.md) | rule_based |  |
| [MARKET_GAP_ANALYZER](executive/MARKET_GAP_ANALYZER.md) | rule_based | MARKET_GAP_ANALYZER: coverage analysis of customer needs against offerings. |
| [OPPORTUNITY_RADAR](executive/OPPORTUNITY_RADAR.md) | rule_based | OPPORTUNITY_RADAR: watch the web for new mentions of the things the caller is looking for. |
| [ORACLE](executive/ORACLE.md) | rule_based |  |
| [PROBABILIS](executive/PROBABILIS.md) | rule_based |  |
| [REALMEX](executive/REALMEX.md) | rule_based |  |
| [STOCHASTIX](executive/STOCHASTIX.md) | rule_based |  |
| [STRATEGIC_INTEL](executive/STRATEGIC_INTEL.md) | rule_based | STRATEGIC_INTEL: a cited research brief on a strategic question. |
| [VIRALYTICA](executive/VIRALYTICA.md) | rule_based |  |

## finance (25)

| Agent | Status | Purpose |
|---|---|---|
| [BANKING_LOGIC_ENGINE](finance/BANKING_LOGIC_ENGINE.md) | rule_based | BANKING_LOGIC_ENGINE: arithmetic on one bank account. |
| [CASHFLOW_AI](finance/CASHFLOW_AI.md) | rule_based | CASHFLOW_AI: cash-flow projection from dated receivables and payables. |
| [CLAIMS_ASSESSMENT_ENGINE](finance/CLAIMS_ASSESSMENT_ENGINE.md) | rule_based | CLAIMS_ASSESSMENT_ENGINE: explicit rule evaluation of an insurance claim. |
| [CREDIT_RISK_ENGINE](finance/CREDIT_RISK_ENGINE.md) | rule_based | CREDIT_RISK_ENGINE: a points scorecard over a borrower's declared figures. |
| [ECONOMIC_INTELLIGENCE_MESH](finance/ECONOMIC_INTELLIGENCE_MESH.md) | rule_based |  |
| [ECONOVA](finance/ECONOVA.md) | rule_based |  |
| [ECON_INTEL_CORE](finance/ECON_INTEL_CORE.md) | rule_based | ECON_INTEL_CORE: a sourced register of economic indicators, plus cited research. |
| [FINANCIAL_AI_ENGINE](finance/FINANCIAL_AI_ENGINE.md) | rule_based |  |
| [FISCALIS](finance/FISCALIS.md) | rule_based |  |
| [FORECASTA](finance/FORECASTA.md) | rule_based |  |
| [FORMULA](finance/FORMULA.md) | rule_based |  |
| [GST_ENGINE](finance/GST_ENGINE.md) | rule_based | GST_ENGINE: GST on outward supplies of services by an IT services company registered in Tamil Nadu. |
| [INSURANCE_POLICY_ENGINE](finance/INSURANCE_POLICY_ENGINE.md) | rule_based | INSURANCE_POLICY_ENGINE: underwriting clauses and premium from a supplied rate table. |
| [LEDGERON](finance/LEDGERON.md) | rule_based |  |
| [MACRO_ECON_MODEL](finance/MACRO_ECON_MODEL.md) | rule_based | MACRO_ECON_MODEL: standard derived indicators from macro figures the caller supplies. |
| [METRIX](finance/METRIX.md) | rule_based |  |
| [NEURAL_ECONOMY](finance/NEURAL_ECONOMY.md) | rule_based | NEURAL_ECONOMY: unit economics calculator. There is no neural network here. |
| [PORTFOLIO_SIM_ENGINE](finance/PORTFOLIO_SIM_ENGINE.md) | rule_based |  |
| [PRICING_OPTIMIZER](finance/PRICING_OPTIMIZER.md) | rule_based | PRICING_OPTIMIZER: the dictionary-in, dictionary-out front for PRICING_OPTIMIZER_ENGINE. |
| [PRICING_OPTIMIZER_ENGINE](finance/PRICING_OPTIMIZER_ENGINE.md) | rule_based | PRICING_OPTIMIZER_ENGINE: profit-maximising price, by two stated methods. |
| [RISKON](finance/RISKON.md) | rule_based |  |
| [STOCKMARKET_SIGNAL_ENGINE](finance/STOCKMARKET_SIGNAL_ENGINE.md) | rule_based | STOCKMARKET_SIGNAL_ENGINE: standard technical indicators on a supplied price series. |
| [TDS_ENGINE](finance/TDS_ENGINE.md) | rule_based | TDS_ENGINE: tax deducted at source under the Income-tax Act, 2025 (tax year 2026-27 onward). |
| [TREASURIX](finance/TREASURIX.md) | rule_based |  |
| [VALORA](finance/VALORA.md) | rule_based |  |

## hr (20)

| Agent | Status | Purpose |
|---|---|---|
| [ATS_CORE](hr/ATS_CORE.md) | rule_based | ATS_CORE: requisitions, candidates, applications, pipeline, decision log, duplicates, erasure. |
| [ATTENDANCE_MONITOR](hr/ATTENDANCE_MONITOR.md) | rule_based |  |
| [EMPLOYEE_METRICS_ENGINE](hr/EMPLOYEE_METRICS_ENGINE.md) | rule_based |  |
| [EMPLOYEE_ONBOARDING](hr/EMPLOYEE_ONBOARDING.md) | real | EMPLOYEE_ONBOARDING — Velaris BOS agent for Knackforge |
| [EMPLOYEE_RECORDS](hr/EMPLOYEE_RECORDS.md) | real | EMPLOYEE_RECORDS: the employee master, joining and leaving, and the data subject's export and erasure. |
| [ESIGN](hr/ESIGN.md) | real | ESIGN: signing requests with a ceremony, evidence per signer, a hash-chain seal and a verifier. |
| [HR_TALENT_ENGINE](hr/HR_TALENT_ENGINE.md) | real | HR_TALENT_ENGINE: evidence that a candidate has the skills a role asks for. For a human. |
| [INTERVIEW_KIT](hr/INTERVIEW_KIT.md) | rule_based | INTERVIEW_KIT: structured interviews and what can honestly be said about them. |
| [INTERVIEW_RECORD](hr/INTERVIEW_RECORD.md) | rule_based | INTERVIEW_RECORD: a consent-gated, replayable record of an interview for a human reviewer. |
| [INTERVIEW_SCHEDULER](hr/INTERVIEW_SCHEDULER.md) | rule_based | INTERVIEW_SCHEDULER: who can interview when, bookings, invitations as drafts, self-scheduling, reminders, no-shows. |
| [JOB_POSTINGS](hr/JOB_POSTINGS.md) | real | JOB_POSTINGS: publish a requisition without paying anyone. |
| [LEAVE_MANAGEMENT](hr/LEAVE_MANAGEMENT.md) | real |  |
| [OFFER_LETTERS](hr/OFFER_LETTERS.md) | real | OFFER_LETTERS: generate, approve, version, send, expire and record the outcome of an offer letter. |
| [ONBOARDING_FLOW](hr/ONBOARDING_FLOW.md) | real | ONBOARDING_FLOW: a checklist-and-task flow for a new joiner, plus minimal-data capture of the paperwork. |
| [PAYROLL_ENGINE](hr/PAYROLL_ENGINE.md) | rule_based |  |
| [PERFORMANCE_REVIEW_ENGINE](hr/PERFORMANCE_REVIEW_ENGINE.md) | real |  |
| [POLICY_ACKS](hr/POLICY_ACKS.md) | real | POLICY_ACKS: policy documents with versions, per-employee acknowledgement evidence, reminders and a compliance report. |
| [RECRUITMENT_ATS](hr/RECRUITMENT_ATS.md) | real | RECRUITMENT_ATS — Velaris BOS agent for Knackforge |
| [RESUME_EVIDENCE](hr/RESUME_EVIDENCE.md) | rule_based | RESUME_EVIDENCE: résumé facts with their source passages, skills through a reviewed alias table, evidence |
| [SCREENING_FORMS](hr/SCREENING_FORMS.md) | rule_based | SCREENING_FORMS: intake forms and the staff side of candidate intake. |

## it_infrastructure (26)

| Agent | Status | Purpose |
|---|---|---|
| [CLOUD_HANDOFF_CONTROLLER](it_infrastructure/CLOUD_HANDOFF_CONTROLLER.md) | rule_based | CLOUD_HANDOFF_CONTROLLER: a durable outbox for work that has to leave this machine. |
| [COMPUTE_KERNEL](it_infrastructure/COMPUTE_KERNEL.md) | rule_based | COMPUTE_KERNEL: admission queue for compute jobs. |
| [COMPUTE_SCALER](it_infrastructure/COMPUTE_SCALER.md) | rule_based | COMPUTE_SCALER: decides how many replicas a workload group should have. |
| [DISTRIBUTED_FABRIC](it_infrastructure/DISTRIBUTED_FABRIC.md) | rule_based | DISTRIBUTED_FABRIC: which node owns which key (consistent hashing). |
| [ENERGY_MANAGER](it_infrastructure/ENERGY_MANAGER.md) | rule_based | ENERGY_MANAGER: decide how hard to work given the machine's power source. |
| [FAILOVER_ROUTER](it_infrastructure/FAILOVER_ROUTER.md) | rule_based | FAILOVER_ROUTER: send a service's traffic to its first working target. |
| [ITSM_ENGINE](it_infrastructure/ITSM_ENGINE.md) | rule_based | ITSM_ENGINE: an IT ticket and incident store with priority, SLA clocks and an audit trail. |
| [IT_INFRA_ENGINE](it_infrastructure/IT_INFRA_ENGINE.md) | rule_based | IT_INFRA_ENGINE: validate an infrastructure request, plan it, and judge reported VM health. |
| [LATENCY_CONTROLLER](it_infrastructure/LATENCY_CONTROLLER.md) | rule_based | LATENCY_CONTROLLER: keep an operation inside its latency objective. |
| [LOAD_DISTRIBUTOR](it_infrastructure/LOAD_DISTRIBUTOR.md) | rule_based | LOAD_DISTRIBUTOR: picks which backend gets the next request. |
| [LOCAL_ACCELERATOR](it_infrastructure/LOCAL_ACCELERATOR.md) | rule_based | LOCAL_ACCELERATOR: an on-disk result cache that makes repeated work instant. |
| [LOCAL_AUTONOMY_CORE](it_infrastructure/LOCAL_AUTONOMY_CORE.md) | real | LOCAL_AUTONOMY_CORE: can this node keep working with no outside help? |
| [LOCAL_REGISTRY_CACHE](it_infrastructure/LOCAL_REGISTRY_CACHE.md) | rule_based | LOCAL_REGISTRY_CACHE: an offline copy of "which agents exist and where". |
| [LOCAL_ROUTER](it_infrastructure/LOCAL_ROUTER.md) | rule_based | LOCAL_ROUTER: should this task run on this machine or be handed to the cloud? |
| [MULTI_TENANCY_GRID](it_infrastructure/MULTI_TENANCY_GRID.md) | rule_based | MULTI_TENANCY_GRID: tenants, their quotas, and usage that cannot exceed them. |
| [NETWORK_OPTIMIZER](it_infrastructure/NETWORK_OPTIMIZER.md) | rule_based | NETWORK_OPTIMIZER: best path through a declared network. |
| [OFFLINE_EXECUTION_ENGINE](it_infrastructure/OFFLINE_EXECUTION_ENGINE.md) | rule_based | OFFLINE_EXECUTION_ENGINE: a durable, replay-safe journal of local command runs. |
| [OFFLINE_REGISTRY](it_infrastructure/OFFLINE_REGISTRY.md) | real |  |
| [OFFLINE_RUNTIME_PACKAGER](it_infrastructure/OFFLINE_RUNTIME_PACKAGER.md) | real |  |
| [OFFLINE_SANDBOX](it_infrastructure/OFFLINE_SANDBOX.md) | real | OFFLINE_SANDBOX: run a small allow-list of read-only commands, contained as a process. |
| [PARALLEL_CORE](it_infrastructure/PARALLEL_CORE.md) | rule_based | PARALLEL_CORE: run one function over many inputs on a bounded thread pool. |
| [RESOURCE_OPTIMIZER](it_infrastructure/RESOURCE_OPTIMIZER.md) | rule_based | RESOURCE_OPTIMIZER: how many parallel workers this machine can take right now. |
| [RESOURCE_ORCHESTRATOR](it_infrastructure/RESOURCE_ORCHESTRATOR.md) | rule_based | RESOURCE_ORCHESTRATOR: named resource pools with hard capacity. |
| [SYSTEM_TELEMETRY](it_infrastructure/SYSTEM_TELEMETRY.md) | rule_based | SYSTEM_TELEMETRY: host metrics for the machine Velaris runs on. |
| [TELEMETRY_SPINE](it_infrastructure/TELEMETRY_SPINE.md) | real |  |
| [THROUGHPUT_MANAGER](it_infrastructure/THROUGHPUT_MANAGER.md) | rule_based | THROUGHPUT_MANAGER: token-bucket rate limits. |

## legal_compliance (7)

| Agent | Status | Purpose |
|---|---|---|
| [EACPE_ALIGNMENT](legal_compliance/EACPE_ALIGNMENT.md) | real | EACPE_ALIGNMENT: is a proposed action inside the mandate its agent was given? |
| [EACPE_HUMAN_GUARD](legal_compliance/EACPE_HUMAN_GUARD.md) | rule_based | EACPE_HUMAN_GUARD: irreversible actions wait for a named person. |
| [EACPE_PROTOCOL](legal_compliance/EACPE_PROTOCOL.md) | rule_based | EACPE_PROTOCOL: did a case follow its required procedure? |
| [GOVERNANCE_ADAPTATION_LOOP](legal_compliance/GOVERNANCE_ADAPTATION_LOOP.md) | rule_based | GOVERNANCE_ADAPTATION_LOOP: learns from human overrides which rules need review. Proposes; never applies. |
| [GOVERNANCE_KERNEL](legal_compliance/GOVERNANCE_KERNEL.md) | rule_based | GOVERNANCE_KERNEL: a thin front door to POLICY_CONTROLLER's versioned policy store and decision. |
| [LEGAL_INTELLIGENCE_ENGINE](legal_compliance/LEGAL_INTELLIGENCE_ENGINE.md) | rule_based |  |
| [POLICY_CONTROLLER](legal_compliance/POLICY_CONTROLLER.md) | rule_based | POLICY_CONTROLLER: a versioned policy store with a deterministic decision that names its rule. |

## marketing (11)

| Agent | Status | Purpose |
|---|---|---|
| [ADAPTIVE_BRANDING](marketing/ADAPTIVE_BRANDING.md) | rule_based | ADAPTIVE_BRANDING: rewrite one brand message for a channel and audience, then check it. |
| [ARTESIA](marketing/ARTESIA.md) | rule_based |  |
| [AUTONOMOUS_MARKETING_ENGINE](marketing/AUTONOMOUS_MARKETING_ENGINE.md) | rule_based |  |
| [BRAND_NARRATIVE](marketing/BRAND_NARRATIVE.md) | rule_based | BRAND_NARRATIVE: a short company narrative written from supplied facts only. |
| [BUSINESS_FUNNEL_DESIGNER](marketing/BUSINESS_FUNNEL_DESIGNER.md) | rule_based |  |
| [CREATIVA](marketing/CREATIVA.md) | rule_based |  |
| [CREATIVE_ENGINE](marketing/CREATIVE_ENGINE.md) | real | CREATIVE_ENGINE: campaign ideas, variations and blends, drafted by a model. |
| [CREATIVE_HOLODECK](marketing/CREATIVE_HOLODECK.md) | rule_based |  |
| [CUSTOMER_BEHAVIOR_ENGINE](marketing/CUSTOMER_BEHAVIOR_ENGINE.md) | rule_based | CUSTOMER_BEHAVIOR_ENGINE: descriptive metrics and a rule-based segment for one customer account. |
| [IMAGINA](marketing/IMAGINA.md) | rule_based |  |
| [VMRK](marketing/VMRK.md) | real |  |

## operations (25)

| Agent | Status | Purpose |
|---|---|---|
| [BUSINESS_AUTOPILOT](operations/BUSINESS_AUTOPILOT.md) | rule_based | BUSINESS_AUTOPILOT: threshold rules over business metrics that PROPOSE actions. |
| [BUSINESS_OPS_ENGINE](operations/BUSINESS_OPS_ENGINE.md) | rule_based |  |
| [CODEX](operations/CODEX.md) | rule_based |  |
| [CONNECTOR_LAYER](operations/CONNECTOR_LAYER.md) | rule_based |  |
| [CONVERGENCE_BRIDGE](operations/CONVERGENCE_BRIDGE.md) | rule_based | Alias wrapper agent: CONVERGENCE_BRIDGE |
| [DYNAMICA](operations/DYNAMICA.md) | rule_based |  |
| [FABRICA](operations/FABRICA.md) | rule_based |  |
| [FLUXOR](operations/FLUXOR.md) | rule_based |  |
| [GENEFLOW](operations/GENEFLOW.md) | rule_based |  |
| [HELIX](operations/HELIX.md) | rule_based |  |
| [HYPERSYNC](operations/HYPERSYNC.md) | rule_based | Alias wrapper agent: HYPERSYNC |
| [MULTI_TENANT_ENGINE](operations/MULTI_TENANT_ENGINE.md) | rule_based |  |
| [NIRVANA](operations/NIRVANA.md) | rule_based | Alias wrapper agent: NIRVANA |
| [OPERATUS](operations/OPERATUS.md) | rule_based |  |
| [OPS_REPORT](operations/OPS_REPORT.md) | real | OPS_REPORT — Velaris BOS agent for Knackforge |
| [OPTIMA](operations/OPTIMA.md) | rule_based |  |
| [PIPELINE_MONITOR](operations/PIPELINE_MONITOR.md) | real | PIPELINE_MONITOR — Velaris BOS agent for Knackforge |
| [POLARIS](operations/POLARIS.md) | rule_based |  |
| [QUALITY_CONTROL_ENGINE](operations/QUALITY_CONTROL_ENGINE.md) | rule_based | QUALITY_CONTROL_ENGINE: a batch checked against a u-chart and explicit disposition rules. |
| [SAGE](operations/SAGE.md) | rule_based | Alias wrapper agent: SAGE |
| [SANDE](operations/SANDE.md) | rule_based | Alias wrapper agent: SANDE |
| [SKILLPACK_LOADER](operations/SKILLPACK_LOADER.md) | real |  |
| [SLA_MONITOR](operations/SLA_MONITOR.md) | real | SLA_MONITOR — Velaris BOS agent for Knackforge |
| [VELOCITY_LOOP](operations/VELOCITY_LOOP.md) | rule_based | VELOCITY_LOOP: where one piece of work lost its time. |
| [WORKFLOW_ANALYST](operations/WORKFLOW_ANALYST.md) | real | Workflow analyst agent: understand a company's existing automation and how work really flows. |

## project_management (14)

| Agent | Status | Purpose |
|---|---|---|
| [ACTION_SANDBOX](project_management/ACTION_SANDBOX.md) | rule_based | ACTION_SANDBOX: apply an action to a COPY of some state and report what would change. |
| [BUDGET_GUARDRAILS](project_management/BUDGET_GUARDRAILS.md) | rule_based |  |
| [DIGITAL_TWIN_XR_ENGINE](project_management/DIGITAL_TWIN_XR_ENGINE.md) | rule_based |  |
| [DRY_RUN_SIMULATION](project_management/DRY_RUN_SIMULATION.md) | real |  |
| [EXECUTION_SANDBOX](project_management/EXECUTION_SANDBOX.md) | rule_based |  |
| [FAILPATH_CONTROL_ENGINE](project_management/FAILPATH_CONTROL_ENGINE.md) | rule_based |  |
| [FEASIBILITY_ENGINE](project_management/FEASIBILITY_ENGINE.md) | rule_based | FEASIBILITY_ENGINE: a scored feasibility checklist where every criterion shows its evidence. |
| [INITIATIVE_ENGINE](project_management/INITIATIVE_ENGINE.md) | rule_based | INITIATIVE_ENGINE: rank proposed initiatives by RICE and keep the register. |
| [ROLLBACK_ENGINE](project_management/ROLLBACK_ENGINE.md) | real |  |
| [SIMULON](project_management/SIMULON.md) | rule_based |  |
| [SPRINT_PLANNER](project_management/SPRINT_PLANNER.md) | real |  |
| [SUCCESSOR_KEY_MODULE](project_management/SUCCESSOR_KEY_MODULE.md) | rule_based |  |
| [TACTICIAN](project_management/TACTICIAN.md) | rule_based |  |
| [TIME_TRACKER](project_management/TIME_TRACKER.md) | real |  |

## sales (13)

| Agent | Status | Purpose |
|---|---|---|
| [AMPLIFEX](sales/AMPLIFEX.md) | rule_based |  |
| [ATTRACTA](sales/ATTRACTA.md) | rule_based |  |
| [AUTONOMOUS_SALES_NAVIGATOR](sales/AUTONOMOUS_SALES_NAVIGATOR.md) | rule_based |  |
| [COHORTUS](sales/COHORTUS.md) | rule_based |  |
| [CONVERTA](sales/CONVERTA.md) | rule_based |  |
| [DOMAIN_ADVISOR](sales/DOMAIN_ADVISOR.md) | rule_based | DOMAIN_ADVISOR: rule-based observations about each sales vertical, from deal records. |
| [DOMAIN_EXPANSION](sales/DOMAIN_EXPANSION.md) | rule_based | DOMAIN_EXPANSION: how much of each vertical's market the company has, and what is left. |
| [DOMAIN_MASTERY](sales/DOMAIN_MASTERY.md) | rule_based | DOMAIN_MASTERY: how the company actually performs in each sales vertical. |
| [DOMAIN_REFINER](sales/DOMAIN_REFINER.md) | rule_based | DOMAIN_REFINER: clean up free-text vertical labels against a canonical list. |
| [DOMAIN_SCOUT](sales/DOMAIN_SCOUT.md) | rule_based | DOMAIN_SCOUT: find public sources about a sales vertical the company is considering. |
| [RETENTA](sales/RETENTA.md) | rule_based |  |
| [TARGETA](sales/TARGETA.md) | rule_based |  |
| [WHATSAPP_BRIEFING](sales/WHATSAPP_BRIEFING.md) | real | WHATSAPP_BRIEFING — Velaris BOS agent for Knackforge |

## security (29)

| Agent | Status | Purpose |
|---|---|---|
| [AEGIS](security/AEGIS.md) | rule_based |  |
| [AGENT_CONTAINMENT_MODES](security/AGENT_CONTAINMENT_MODES.md) | rule_based |  |
| [ARGUS](security/ARGUS.md) | rule_based |  |
| [AUDITOR](security/AUDITOR.md) | rule_based |  |
| [COGNITIVE_INTENT_FIREWALL](security/COGNITIVE_INTENT_FIREWALL.md) | real |  |
| [COMPLIANCE_GUARD](security/COMPLIANCE_GUARD.md) | rule_based |  |
| [CUSTOS](security/CUSTOS.md) | rule_based |  |
| [CYBER_RISK_ENGINE](security/CYBER_RISK_ENGINE.md) | rule_based | CYBER_RISK_ENGINE: a residual-risk score for a declared asset, by a stated formula. |
| [DECISION_FIREWALL](security/DECISION_FIREWALL.md) | rule_based | DECISION_FIREWALL: a persistent block list of decision keys. |
| [DEEP_AUDIT_ENGINE](security/DEEP_AUDIT_ENGINE.md) | real |  |
| [HARD_LOCKDOWN_MODE](security/HARD_LOCKDOWN_MODE.md) | rule_based |  |
| [IDENTITY_FRAMEWORK](security/IDENTITY_FRAMEWORK.md) | real |  |
| [MFA_RECOVERY_WORKFLOW](security/MFA_RECOVERY_WORKFLOW.md) | rule_based |  |
| [OVERSIGHT_MONITOR](security/OVERSIGHT_MONITOR.md) | rule_based |  |
| [OVERWATCH](security/OVERWATCH.md) | rule_based |  |
| [OWNER_VERIFICATION](security/OWNER_VERIFICATION.md) | rule_based |  |
| [PIN_UNLOCK_LAYER](security/PIN_UNLOCK_LAYER.md) | rule_based |  |
| [PRAETOR](security/PRAETOR.md) | rule_based |  |
| [SAFETY_PERIMETER](security/SAFETY_PERIMETER.md) | rule_based |  |
| [SANITY_VERIFIER](security/SANITY_VERIFIER.md) | real | SANITY_VERIFIER: last check on an agent's output, and a check of the runtime configuration. |
| [SECRETS_VAULT](security/SECRETS_VAULT.md) | real |  |
| [SECURE_ACTION_TOKENS](security/SECURE_ACTION_TOKENS.md) | real |  |
| [SELF_AUDIT](security/SELF_AUDIT.md) | real | SELF_AUDIT: Velaris inspecting its own installation. |
| [SENTINELDNA](security/SENTINELDNA.md) | rule_based |  |
| [SIGNED_AUDIT_CHAIN](security/SIGNED_AUDIT_CHAIN.md) | real |  |
| [SOFT_LOCKDOWN_MODE](security/SOFT_LOCKDOWN_MODE.md) | rule_based |  |
| [THREAT_DETECTION_MESH](security/THREAT_DETECTION_MESH.md) | rule_based |  |
| [VIGILIS](security/VIGILIS.md) | real | VIGILIS: signatures, a deny-by-default policy check, and a file-integrity watch. |
| [ZERO_TRUST_PIPELINE](security/ZERO_TRUST_PIPELINE.md) | real | ZERO_TRUST_PIPELINE: every request is checked for identity, device, context and policy; the default is deny. |

## supply_chain (6)

| Agent | Status | Purpose |
|---|---|---|
| [FLEET_HEALTH_ENGINE](supply_chain/FLEET_HEALTH_ENGINE.md) | rule_based | FLEET_HEALTH_ENGINE: a vehicle's condition from its usage, wear and service records. |
| [INVENTORY_DECISION_ENGINE](supply_chain/INVENTORY_DECISION_ENGINE.md) | rule_based | INVENTORY_DECISION_ENGINE: reorder point, safety stock and order quantity for one item. |
| [MACHINE_LIFECYCLE_ENGINE](supply_chain/MACHINE_LIFECYCLE_ENGINE.md) | rule_based | MACHINE_LIFECYCLE_ENGINE: where a machine is in its life, from usage and maintenance records. |
| [ROUTE_OPTIMIZATION_ENGINE](supply_chain/ROUTE_OPTIMIZATION_ENGINE.md) | rule_based | ROUTE_OPTIMIZATION_ENGINE: a round trip through every location, by a real heuristic. |
| [SUPPLY_CHAIN_ENGINE](supply_chain/SUPPLY_CHAIN_ENGINE.md) | rule_based | SUPPLY_CHAIN_ENGINE: a replenishment plan by simulating a reorder-point policy. |
| [WAREHOUSE_FLOW_ENGINE](supply_chain/WAREHOUSE_FLOW_ENGINE.md) | rule_based | WAREHOUSE_FLOW_ENGINE: one period of warehouse flow, worked through as arithmetic. |
