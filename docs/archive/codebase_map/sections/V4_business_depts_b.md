# V4 — Business Departments B: Security, IT Infra, Legal/Compliance, Data/Knowledge, Executive, Sales, Marketing, Client Success, Connectors

Scope: `departments/{security,it_infrastructure,legal_compliance,data_knowledge,executive,sales,marketing,client_success,_connectors}`. This is the **working tree**: `departments/` is untracked (`??`), and 810 `domains/*` files show as `D`. HEAD is 142153b. I read every `main.py`, manifest and non-empty `__init__.py` (the non-empty ones only contain a "package marker" comment banner).

Provenance: 111 of the 116 agents are **byte-identical** to `HEAD:domains/<old>/<AGENT>/main.py` (I diffed each one, with 0 differences). So the reorg is a pure move. The 5 that don't exist anywhere in git are `sales/WHATSAPP_BRIEFING` and the 4 `_connectors/ZOHO_*`. Those 5 are new, uncommitted code, ported from VKatOS/Knackforge work.

Old domain → new department mapping:
- security(29) → security
- infrastructure(17) + local_offline(7) + operations(IT_INFRA_ENGINE, ITSM_ENGINE) → it_infrastructure
- ethics_governance(7 of 8) → legal_compliance. ETHICAL_ENGINE went to `_archived_agents/_stubs`.
- memory_knowledge → data_knowledge
- business_intelligence → executive
- sales_crm + marketing_brand/AUTONOMOUS_SALES_NAVIGATOR → sales
- marketing_brand → marketing
- sales_crm/LOGISTA → client_success

---

## 1. Summary

**116 agent directories, about 4.6K Python LOC. No LLM calls, no ML models, no network I/O anywhere, except `ZOHO_CONNECTOR` (urllib) and `WHATSAPP_BRIEFING` (aiohttp, optional).** There's no grep hit for openai/anthropic/sklearn/torch/numpy/requests/httpx.

**Nothing in this scope is wired into the runtime:**
- `velaris/agents/router.py:17-26` only scans `velaris/agents/*/main.py`, and that directory contains only `router.py`.
- Running `python3 main.py` prints **`Agents loaded : 0`**.
- 70 of the 106 test files import `velaris.agents.<AGENT>.main` (e.g. `velaris/tests/test_aegis.py:4`, `test_vigilis.py`, `test_custos.py`, `test_governance_kernel.py`). Those paths don't exist, so they all fail on import. No file in `departments/` is imported by any other code.

Import smoke test: I loaded every module with `importlib` and no instantiation. 112 OK, 4 FAIL:
- `RESOURCE_OPTIMIZER`: `psutil` isn't installed, although it is in `requirements.txt`.
- `ZOHO_PAYROLL`, `ZOHO_PEOPLE`, `ZOHO_PROJECTS`: `No module named 'connectors'`.

10 more agents hard-code `/live/agents/...` and will raise on instantiation on any host without a writable `/live` (it's absent on this Mac):
- DEEP_AUDIT_ENGINE, IDENTITY_FRAMEWORK, SECRETS_VAULT, SECURE_ACTION_TOKENS, SIGNED_AUDIT_CHAIN
- TELEMETRY_SPINE, OFFLINE_RUNTIME_PACKAGER
- TEMPORAL_SNAPSHOTS, MEMORY_DRIFT_DETECTOR
- VMRK (which doesn't even call `makedirs`)

Tag legend:
- **REAL**: does real I/O or crypto (files, HTTP, psutil, HMAC/PBKDF2).
- **RULE**: deterministic in-memory logic that works, but is toy-sized.
- **STUB/HOLLOW**: only `health_check`, returns a constant or echoes its input, or produces output unrelated to its name or claim.
- **DEAD**: can't import or instantiate as written.
- **LLM / ML**: none found.

| Department | Agents | REAL | LLM | ML | RULE | STUB/HOLLOW | DEAD |
|---|---|---|---|---|---|---|---|
| security | 29 | 5 | 0 | 0 | 20 | 4 | 0* |
| it_infrastructure | 26 | 4 | 0 | 0 | 2 | 20 | 0* |
| legal_compliance | 7 | 0 | 0 | 0 | 1 | 6 | 0 |
| data_knowledge | 13 | 4 | 0 | 0 | 5 | 4 | 0* |
| executive | 12 | 0 | 0 | 0 | 6 | 6 | 0 |
| sales | 13 | 1 | 0 | 0 | 7 | 5 | 0 |
| marketing | 11 | 0 | 0 | 0 | 3 | 7 | 1 (VMRK) |
| client_success | 1 | 0 | 0 | 0 | 1 | 0 | 0 |
| _connectors | 4 | 1 | 0 | 0 | 0 | 0 | 3 |
| **Total** | **116** | **15 (13%)** | **0** | **0** | **45 (39%)** | **52 (45%)** | **4 (3%)** |

\* Counted under REAL, but the `/live` hard-coding makes them DEAD on any non-provisioned host, and `RESOURCE_OPTIMIZER` is DEAD without psutil.

**Effectively, 100% of the scope is DEAD at the system level, because nothing loads it.**

On "~39% stubs" from the prior audit: in my scope, 45% are STUB/HOLLOW and a further 39% are toy RULE code. The README says "~60% fully implemented (>40 lines)". Only 56/116 (48%) are over 40 lines here, and most of that is logging boilerplate (5–8 lines per file).

Recurring anti-patterns:
1. **Hash-of-ID "deterministic entropy" injected into scores**, so a risk, priority or value score shifts by up to 30–50% depending only on the string ID:
   - `CYBER_RISK_ENGINE/main.py:51,60` (adds `sha256(id)%500` to a 0–1000 scale)
   - `ITSM_ENGINE/main.py:57-59` (+0–150)
   - `CUSTOMER_BEHAVIOR_ENGINE/main.py:67-69` (+0–300)
   - `IT_INFRA_ENGINE/main.py:80` (VM "health" = `seed % 7 == 0`)
   - `AUTONOMOUS_MARKETING_ENGINE/main.py:34` (audience score = `sum(ord(c)) % 100`)
2. **Approve-everything gates**:
   - `ZERO_TRUST_PIPELINE:20`, `SANITY_VERIFIER:13`, `EACPE_ALIGNMENT:15`, `EACPE_HUMAN_GUARD:15`, `EACPE_PROTOCOL:15` and `OFFLINE_SANDBOX:12` all return True or "safe".
   - `velaris/security/secure.py` `validate()` / `integrity_check()` also return True.
3. **State only in memory**, so it's lost on restart. This covers all the lockdown and containment modes, RBAC, rate limits and threat scores.
4. **5 bare `except:` clauses**: `DEEP_AUDIT_ENGINE:30`, `IDENTITY_FRAMEWORK:31`, `TELEMETRY_SPINE:30`, `TEMPORAL_SNAPSHOTS:30`, `MEMORY_DRIFT_DETECTOR:30`.
5. Logging setup is duplicated in every file. It sets `logger.setLevel(DEBUG)` and adds a handler at import, and many files skip the `if not logger.handlers` guard, so log lines are duplicated if a module is re-imported.

---

## 2. Per-department agent tables
LOC is `main.py` line count. Lines like "a.py:12" are `<AGENT>/main.py:<line>`.

### 2.1 security (29)
| Agent | LOC | What it actually does | In → Out | Tag |
|---|---|---|---|---|
| AEGIS | 45 | Per-source sliding-window rate limit (default 5 events / 10s), plus additive threat score dict (:23-45) | source → bool / int | RULE |
| AGENT_CONTAINMENT_MODES | 44 | Maps an agent to SANDBOX/ISOLATION/FULL_LOCK. `allowed_actions` returns a fixed list (:35-43). Enforced nowhere. | agent, mode → list | RULE |
| ARGUS | 48 | Heartbeat-timeout check and "signature version changed" check (:28-48) | source → bool | RULE |
| AUDITOR | 44 | Checks that required steps are present, and substring-scans logs for banned terms (:20-44) | lists → bool / list | RULE |
| COGNITIVE_INTENT_FIREWALL | 47 | Substring keyword classifier into SAFE/RISKY/BLOCKED (:13-36). "skill" matches "kill", so BLOCKED is a false positive. | text → {intent} | RULE |
| COMPLIANCE_GUARD | 44 | Rule registry checking required and forbidden dict keys on an action (:28-43) | action dict → status | RULE |
| CUSTOS | 31 | Role → set(perms) RBAC lookup (:20-31). The manifest claims "authentication", but there is none. | role, action → bool | RULE |
| CYBER_RISK_ENGINE | 94 | Exposure × criticality, minus control weights, **plus hash noise** (:51-60). Tiers it low…critical. | AssetProfile → score / tier | RULE |
| DECISION_FIREWALL | 25 | Set blocklist (:19-25) | key → bool | RULE (trivial) |
| DEEP_AUDIT_ENGINE | 59 | SHA-256 checksums appended to `/live/.../audit_log.json`. `detect_drift` compares against the **first** entry for a name, not the latest (:53-58). | name, data → entry / bool | RULE + file |
| HARD_LOCKDOWN_MODE | 47 | When enabled, denies everything except `heartbeat` and `core_status`, and logs to an in-memory dict (:29-43) | action → bool | RULE |
| IDENTITY_FRAMEWORK | 74 | PBKDF2-SHA256 at 200k iterations with a 16B salt, stored in a JSON file `/live/.../identity.db` (:39-48). The compare is non-constant-time `==` (:48). No lockout, sessions or MFA. | user, pw → bool | REAL |
| MFA_RECOVERY_WORKFLOW | 53 | 6-digit code from `random` (not `secrets`), stored as unsalted SHA-256 (:24-27). No expiry or attempt limit. The reset token is also from `random` (:35). `reset_credentials` is **simulated**: it only deletes the token (:42-52). | user → code / token | RULE (insecure) |
| OVERSIGHT_MONITOR | 24 | Appends to a list and returns the last entry | entry → — | STUB |
| OVERWATCH | 57 | Metric baseline, then abs-diff drift above a tolerance (:27-47) | metrics → bool / deltas | RULE |
| OWNER_VERIFICATION | 50 | "Biometric" check = exact SHA-256 equality of fingerprint, face and voice strings (:31-38). Real biometric captures never match byte-for-byte. Single owner only. | strings → bool | RULE (hollow concept) |
| PIN_UNLOCK_LAYER | 43 | Unsalted SHA-256 PIN, so a 4–6 digit PIN space is trivially brute-forced. Lock state is in memory. | user, pin → bool | RULE |
| PRAETOR | 32 | Z-score of the last value against the series, threshold 3.0 (:20-32) | list → bool | RULE (stat) |
| SAFETY_PERIMETER | 23 | Static jurisdiction allowlist IN/SG/EU and syscall-name blocklist (:5-22). Never hooked to execution. | code, name → bool | RULE |
| SANITY_VERIFIER | 16 | `verify()` returns `{"final_safe_output": True}` (:13) | — | STUB |
| SECRETS_VAULT | 80 | Writes **base64, not encryption** to `/live/.../data/<name>.sec`, plus an HMAC integrity tag. The key file sits next to the data (:10-61). `name` isn't sanitised, so path traversal is possible (:29-33). | name, secret → file | REAL (mislabelled) |
| SECURE_ACTION_TOKENS | 57 | HMAC-SHA256 capability token `b64(action:ts).sig` with a TTL of 60s (:33-56). No nonce, so it can be **replayed within the TTL**. No subject binding. | action → token / validate | REAL |
| SELF_AUDIT | 25 | `update` returns `{"updated":True}` and `snapshot` returns its name | — | STUB |
| SENTINELDNA | 40 | SHA-256 of JSON baseline vs. new data (drift check) | data → bool | RULE |
| SIGNED_AUDIT_CHAIN | 53 | HMAC-signed append-only log. **Bug: writes the literal `"/n"` instead of `"\n"` (:39)**, so all entries land on one line and `verify_chain()` returns False once anything has been appended (the sig keeps a trailing "/n"). Also not a chain: there's no prev-hash link, so deleting or reordering lines can't be detected. | actor, action → line | REAL (broken) |
| SOFT_LOCKDOWN_MODE | 47 | Blocks 4 named actions when enabled (:18-43) | action → bool | RULE |
| THREAT_DETECTION_MESH | 61 | +10 per exact key/value signature match, mapped to LOW/MED/HIGH (:30-53) | event → level | RULE |
| VIGILIS | 130 | RSA-2048 PSS sign/verify via `cryptography`. **Auth bypass:** on *any* verify exception, including InvalidSignature, it falls back to accepting `b"SIG:"+msg[::-1][:32]` (:106-111). `evaluate_policy` ignores `config["policies"]` (:118) and only checks a `untrusted_source` flag. | msg → sig / bool | REAL (unsafe) |
| ZERO_TRUST_PIPELINE | 20 | `verify(token)` **always returns True** (:18-20) | token → True | STUB |

### 2.2 it_infrastructure (26)
| Agent | LOC | What it does | Tag |
|---|---|---|---|
| COMPUTE_KERNEL, COMPUTE_SCALER, DISTRIBUTED_FABRIC, ENERGY_MANAGER, FAILOVER_ROUTER, LATENCY_CONTROLLER, LOAD_DISTRIBUTOR, LOCAL_ACCELERATOR, NETWORK_OPTIMIZER, PARALLEL_CORE, RESOURCE_ORCHESTRATOR, SYSTEM_TELEMETRY, THROUGHPUT_MANAGER (13) | 16 each | Identical template: `__init__` and `health_check()` only (e.g. `COMPUTE_SCALER/main.py:10-16`). Zero behaviour. | STUB |
| CLOUD_HANDOFF_CONTROLLER | 13 | `sync()` returns `{"synced":True}` (:11-12) | STUB |
| LOCAL_AUTONOMY_CORE | 12 | `ping()` returns `{"local":True}` | STUB |
| LOCAL_ROUTER | 13 | `route()` returns `"offline"`, commented "always offline for now" (:12) | STUB |
| LOCAL_REGISTRY_CACHE | 13 | `update()` replaces a dict | STUB |
| MULTI_TENANCY_GRID | 21 | `run()` echoes the payload. Manifest: "Auto-generated placeholder". | STUB |
| OFFLINE_EXECUTION_ENGINE | 13 | `execute(task)` returns `{"executed":task}` | STUB |
| OFFLINE_SANDBOX | 13 | `safe(p)` returns `{"safe":True}`. No sandboxing at all. | STUB |
| IT_INFRA_ENGINE | 88 | Validates region, VM type and CIDR, then **fabricates** a provisioning result (IDs, `10.0.x.y` IPs, `"status":"provisioned"`) with no cloud API (:44-72). `health_check` marks a VM "degraded" iff `seed%7==0` (:74-87). | RULE (simulated) |
| ITSM_ENGINE | 88 | ITIL-style impact × urgency × priority + history flags + hash noise → P1–P4 and SLA hours 4/8/24/72 (:47-86) | RULE |
| TELEMETRY_SPINE | 61 | JSON event log at `/live/.../telemetry.log`. Rewrites the whole file on every `record` (O(n)). Has query-by-type and counts (:37-60). | REAL (file) |
| OFFLINE_REGISTRY | 30 | JSON KV store at `/tmp/velaris_offline_registry.json` | REAL (trivial) |
| OFFLINE_RUNTIME_PACKAGER | 50 | Real `tarfile` bundling of a directory that has `agents/` and `tests/` (:22-49). That layout no longer matches the repo. | REAL |
| RESOURCE_OPTIMIZER | 13 | `psutil.cpu_percent()` and memory % (:11-12). The **only real host telemetry in scope**. Import fails without psutil. | REAL |

### 2.3 legal_compliance (7)
| Agent | LOC | What it does | Tag |
|---|---|---|---|
| EACPE_ALIGNMENT | 15 | `align()` returns `{"aligned":True}` | STUB |
| EACPE_HUMAN_GUARD | 15 | `validate(action)` returns `{"approved":True}`. "Human safety" is rubber-stamped. | STUB |
| EACPE_PROTOCOL | 15 | `evaluate_protocol()` returns `{"protocol_safe":True}` | STUB |
| GOVERNANCE_ADAPTATION_LOOP | 16 | Echoes its input as `adaptive_policy` | STUB |
| GOVERNANCE_KERNEL | 26 | `evaluate_request(pid, req)` returns `pid in self.policies`. **It ignores both the request and the rule content** (:23-26). | STUB |
| POLICY_CONTROLLER | 24 | In-memory dict put/get | STUB |
| LEGAL_INTELLIGENCE_ENGINE | 58 | In-memory category → rule → text store with substring search. Ships **no** legal content. | RULE |

### 2.4 data_knowledge (13)
| Agent | LOC | What it does | Tag |
|---|---|---|---|
| GLOBAL_STATE_MAP, MEMORY_REALLOCATOR, STREAM_PROCESSOR | 16 | health_check only | STUB |
| MEMORY_CLOUD_EXPAND | 23 | `dict.update`, despite "cloud" in the name. No remote. | STUB |
| CHROMOS | 49 | Canonical-JSON SHA-256 schema hashing and change detection | RULE |
| EPISODIC_MEMORY | 23 | List append and list | RULE (trivial) |
| SHORTTERM_MEMORY | 25 | `deque(maxlen=100)` | RULE (trivial) |
| MEMORY_MESH | 42 | Dict of nodes | RULE (trivial) |
| MEMORY_FABRIC | 59 | Dict buckets, plus an appended "repair" shim class `MemoryFabric` that duplicates the logger setup (:26-58) | RULE (trivial) |
| LONGTERM_MEMORY | 32 | JSON KV in `/tmp/velaris_longterm.json` | REAL (file) |
| LOCAL_MEMORY_STORE | 16 | JSON KV in **CWD** `local_store.json`. Open file handles are never closed (:11-15). | REAL (file) |
| TEMPORAL_SNAPSHOTS | 65 | Labelled JSON snapshots at `/live/...` with restore and compare. Labels aren't unique; `restore` returns the first match. | REAL (file) |
| MEMORY_DRIFT_DETECTOR | 69 | Fraction of keys changed, scaled to 0–100, → STABLE/DRIFT/SEVERE (:44-68). Stored in `/live/...`. | REAL (file) |

No vector store, embeddings, RAG, DB or knowledge graph here. "Memory" means Python dicts and JSON files.

### 2.5 executive (12)
| Agent | LOC | What it does | Tag |
|---|---|---|---|
| BUSINESS_DNA, OPPORTUNITY_RADAR, STRATEGIC_INTEL | 21 | `run()` echoes the payload. Manifests say "Auto-generated placeholder". | STUB |
| BUSINESS_MODEL_ENGINE, COMPETITIVE_SCANNER, MARKET_GAP_ANALYZER | 15 | health_check only | STUB |
| INSIGHTA | 53 | Endpoint slope, mean shift, `1/(1+var)` | RULE |
| ORACLE | 51 | "Monte Carlo": p = 0.5 + sum(factors), then N coin flips (:24-41). This just adds noise to a number it already computed. It calls global `random.seed()` as a side effect (:16). | RULE (toy) |
| PROBABILIS | 43 | Bernoulli trials, callback MC, mean | RULE |
| REALMEX | 51 | Merges a list of dicts. "Reality score" = element count (:37-43). | RULE (hollow) |
| STOCHASTIX | 48 | Gaussian random walks and mean of finals | RULE |
| VIRALYTICA | 54 | shares/views, geometric growth, mean delta | RULE |

None of these read any business data source. Every input is a caller-supplied list or dict.

### 2.6 sales (13)
| Agent | LOC | What it does | Tag |
|---|---|---|---|
| DOMAIN_ADVISOR, DOMAIN_EXPANSION, DOMAIN_MASTERY, DOMAIN_REFINER, DOMAIN_SCOUT | 12 | health_check only. Not even sales-related. | STUB |
| AMPLIFEX | 45 | reach × 1.2, audience × (1+r), mean | RULE |
| ATTRACTA | 48 | Weighted emotional/logical blend, engagement/impressions, mean sentiment | RULE |
| AUTONOMOUS_SALES_NAVIGATOR | 48 | Lead score 0.4·budget + 0.3·interest + 0.3·fit, P(close) = score/100, 3-tier strategy text (:26-43) | RULE |
| COHORTUS | 45 | Round-robin role assignment and fixed-size chunking. This is team coordination, not sales. | RULE |
| CONVERTA | 48 | conv/visits, (first − last)/first leakage, rate × (1 − leak) | RULE |
| RETENTA | 47 | churn = min(1, days × 0.05), mean sessions, decay | RULE |
| TARGETA | 48 | Variance as "segmentation quality" (dubious), dot-product match | RULE |
| WHATSAPP_BRIEFING | 140 | SQLite `daily_metrics` (CWD `briefing_data.db`), daily rollup text, and a **real WhatsApp Cloud API POST** to `graph.facebook.com/v17.0/{phone_id}/messages` with a Bearer token from config (:71-96). Without config it falls back to "preview". | REAL |

Bugs in WHATSAPP_BRIEFING:
- It logs with `utcnow()` (:34) but queries by local `datetime.now()` date (:40-43). In IST, metrics logged between 00:00 and 05:30 land on the wrong day.
- It reports `"sent"` for any HTTP status, including 4xx (:91-93).
- v17.0 of the Graph API is old.
- `asyncio.run` inside `send_briefing` (:129) breaks when called from a running event loop (e.g. FastAPI).

There's no CRM and no pipeline store. Nothing reads Zoho CRM.

### 2.7 marketing (11)
| Agent | LOC | What it does | Tag |
|---|---|---|---|
| ADAPTIVE_BRANDING, BRAND_NARRATIVE | 21 | `run()` echoes the payload ("Auto-generated placeholder") | STUB |
| CREATIVA | 48 | f-strings like `"{c} 2.0"`, `"Advanced {c}"`; novelty = unique count × 1.2 | HOLLOW |
| CREATIVE_ENGINE | 34 | `"Unique concept based on {theme}"` plus `random.randint(50,100)` as the "creative_score" | HOLLOW |
| IMAGINA | 50 | `"{seed} - vision layer {i}"`, plus fixed scenario templates | HOLLOW |
| ARTESIA | 46 | `"{a}-{b} Fusion"`, sum of attributes | HOLLOW |
| AUTONOMOUS_MARKETING_ENGINE | 47 | Campaign = 3 f-strings. Audience score = `sum(ord(c))%100` (:34). | HOLLOW |
| CREATIVE_HOLODECK | 49 | Picks from 4×4×4×4 fixed lists into a sentence. It honestly says "not a generative model" (:11). | RULE |
| BUSINESS_FUNNEL_DESIGNER | 59 | Per-stage conversion % and drop-off between stages | RULE |
| CUSTOMER_BEHAVIOR_ENGINE | 96 | RFM-ish weighted score + flag weights + **hash noise of 0–300** → 4 tiers (:54-95) | RULE |
| VMRK | 32 | HMAC-SHA256 sign/verify. It's a security primitive filed under marketing. `KEY_PATH=/live/agents/VMRK/vmrk.key` and there's no `makedirs` (:9-19), so it raises FileNotFoundError on a fresh host. | DEAD |

### 2.8 client_success (1)
| Agent | LOC | What it does | Tag |
|---|---|---|---|
| LOGISTA | 43 | `min(available, demand)` allocation and cheapest route by `min()`. This is logistics, misfiled under client success. | RULE |

### 2.9 _connectors (4)
| Agent | LOC | What it does | Tag |
|---|---|---|---|
| ZOHO_CONNECTOR | 79 | Real OAuth2 refresh-token flow, plus GET/POST helpers via urllib. See §5. | REAL |
| ZOHO_PEOPLE | 80 | Employees, attendance, leave, appraisal endpoints, plus an attendance summary | DEAD (import) |
| ZOHO_PAYROLL | 61 | Payslip, YTD, statutory-deduction filter, CTC | DEAD (import, plus `config.get` on None at :23) |
| ZOHO_PROJECTS | 70 | Projects, tasks by owner, timelogs, completion / on-time summary | DEAD (import, plus `config.get` on None at :24) |

---

## 3. Security, compliance & governance: what is actually enforced

**Short answer: nothing is enforced at runtime.**
- No agent in scope is loaded (router = 0 agents).
- No middleware calls these classes.
- The platform-level `velaris/security/secure.py` is itself a "Phase 2 Stub" whose `validate()` and `integrity_check()` return True.

Each class below is a library primitive that a caller would have to invoke voluntarily.

| Concern | Claimed by | Reality |
|---|---|---|
| **Authentication** | CUSTOS manifest ("authentication"), IDENTITY_FRAMEWORK, PIN_UNLOCK_LAYER, OWNER_VERIFICATION, MFA_RECOVERY_WORKFLOW | Only IDENTITY_FRAMEWORK does sound password hashing (PBKDF2 200k). Storage is a plaintext JSON file. There are no sessions, no JWT/OIDC/SAML and no lockout. PINs use unsalted SHA-256. "Biometrics" are exact string-hash equality. MFA recovery uses the non-crypto `random` module and only *simulates* the credential reset (`MFA_RECOVERY_WORKFLOW/main.py:42-52`). No TOTP/WebAuthn exists. |
| **Authorization** | CUSTOS, AGENT_CONTAINMENT_MODES, DECISION_FIREWALL | In-memory role → perm sets and mode → action lists. Not persisted and not consulted by anything. |
| **Zero-trust** | ZERO_TRUST_PIPELINE (README headline) | `verify()` returns `True` (`ZERO_TRUST_PIPELINE/main.py:18-20`). No mTLS, no identity-aware proxy, no per-request policy. |
| **Signing / integrity** | VIGILIS, SECURE_ACTION_TOKENS, VMRK, SENTINELDNA, CHROMOS | Real HMAC-SHA256 in SECURE_ACTION_TOKENS and VMRK. VIGILIS RSA-PSS is real but **bypassable**: the fallback accepts `"SIG:"+reversed(msg)[:32]` whenever real verification throws (`VIGILIS/main.py:106-111`). Keys are raw files on disk with default permissions; there's no KMS or HSM. |
| **Secrets management** | SECRETS_VAULT | Base64 plus HMAC. **Not encrypted at rest**, and the key is co-located with the data. Name path traversal is possible. Nothing uses it; the Zoho/WhatsApp creds come from env/config instead. |
| **Audit trail** | SIGNED_AUDIT_CHAIN, DEEP_AUDIT_ENGINE, AUDITOR, OVERSIGHT_MONITOR, SELF_AUDIT | SIGNED_AUDIT_CHAIN is **broken** (the `"/n"` bug makes `verify_chain()` always fail after the first append) and isn't hash-linked. DEEP_AUDIT_ENGINE stores checksums in JSON and its drift check compares against the oldest entry. OVERSIGHT_MONITOR and SELF_AUDIT are stubs. Nobody emits audit events. |
| **Threat detection** | AEGIS, ARGUS, PRAETOR, THREAT_DETECTION_MESH, CYBER_RISK_ENGINE, OVERWATCH | Textbook primitives (sliding window, z-score, key/value signature match, baseline diff). No data feeds: no log ingestion, SIEM, IDS or network tap. CYBER_RISK_ENGINE's scores are partly a hash of the asset ID. |
| **Lockdown / containment** | SOFT_LOCKDOWN_MODE, HARD_LOCKDOWN_MODE, AGENT_CONTAINMENT_MODES, SAFETY_PERIMETER, OFFLINE_SANDBOX | Boolean flags and string lists in memory. No process isolation. SAFETY_PERIMETER's syscall blocklist is a list of names that is never checked against real calls. OFFLINE_SANDBOX returns `safe:True`. |
| **Prompt / intent firewall** | COGNITIVE_INTENT_FIREWALL | Substring matching against 11 keywords. Trivially evaded, with false positives ("skill" → BLOCKED). |
| **Policy engine** | GOVERNANCE_KERNEL, POLICY_CONTROLLER, COMPLIANCE_GUARD, VIGILIS.evaluate_policy | GOVERNANCE_KERNEL returns "is the policy ID registered?" and never evaluates the rule. VIGILIS ignores configured policies. COMPLIANCE_GUARD (required/forbidden field check) is the only working rule evaluator. No OPA/Rego/Cedar. |
| **Ethics / HITL** | EACPE_ALIGNMENT, EACPE_HUMAN_GUARD, EACPE_PROTOCOL, GOVERNANCE_ADAPTATION_LOOP | All return approved/aligned/safe = True. **Human-in-the-loop is a rubber stamp.** The connector manifests set `"hitl_required": false`. |
| **Regulatory compliance** (GDPR / DPDP / SOC2 / ISO) | README "compliance alignment, legal intelligence" | No regulation content, controls mapping, retention, DSAR or consent handling anywhere. LEGAL_INTELLIGENCE_ENGINE is an empty dict. SAFETY_PERIMETER hard-codes an IN/SG/EU allowlist with no rationale. |

Security defects worth a ticket if this code is ever wired in:
1. VIGILIS signature-forgery fallback (:84-88, :106-111).
2. ZERO_TRUST_PIPELINE and SANITY_VERIFIER always return True.
3. SIGNED_AUDIT_CHAIN `"/n"` bug (:39), and the missing hash chain.
4. SECRETS_VAULT isn't encrypted, plus path traversal (:29-46).
5. MFA_RECOVERY uses `random` with unsalted, non-expiring codes (:24-38).
6. IDENTITY_FRAMEWORK non-constant-time compare (:48); PIN_UNLOCK unsalted SHA-256.
7. SECURE_ACTION_TOKENS can be replayed within the TTL.
8. Bare `except:` in the 5 files listed in §1.

No hard-coded secrets or API keys exist in scope. Zoho creds come from config or env `ZOHO_CLIENT_ID`, `ZOHO_CLIENT_SECRET`, `ZOHO_REFRESH_TOKEN`, `ZOHO_ORG_ID`, `ZOHO_PORTAL_ID` (`ZOHO_CONNECTOR/main.py:23-25`, `ZOHO_PAYROLL:23`, `ZOHO_PROJECTS:24`). WhatsApp creds come from config keys only (`WHATSAPP_BRIEFING:72-74`).

---

## 4. IT infrastructure / SRE: real or simulated?

**Almost entirely simulated or empty.**
- **Monitoring / telemetry:**
  - `RESOURCE_OPTIMIZER` reads real CPU and RAM % via psutil (:11-12). It's 13 lines, and broken here because psutil isn't installed.
  - `TELEMETRY_SPINE` is a real but naive JSON-file event store. It loads and saves the whole array on every write, has no rotation, no schema and no export (no Prometheus/OTel), and lives at `/live/...`.
  - `SYSTEM_TELEMETRY` is an empty stub.
  - ARGUS heartbeat and PRAETOR anomaly detection exist as primitives but have no data feed.
- **Scaling / load / failover:** COMPUTE_SCALER, LOAD_DISTRIBUTOR, FAILOVER_ROUTER, LATENCY_CONTROLLER, THROUGHPUT_MANAGER, RESOURCE_ORCHESTRATOR, DISTRIBUTED_FABRIC, PARALLEL_CORE and NETWORK_OPTIMIZER are **all 16-line health_check-only stubs**. No k8s, Docker, cloud SDK or autoscaler code.
- **Provisioning:** IT_INFRA_ENGINE produces fake VM inventories with fabricated IPs and `"provisioned"` status. VM "health" is `hash % 7`, so it's deterministic and fake. It makes no AWS/GCP/Azure/DO calls.
- **ITSM / incident:** ITSM_ENGINE is a usable priority-matrix calculator (P1–P4 with SLA hours), but it adds up to 150 points of ID-hash noise and has no ticket store, no on-call, no paging and no integration (Jira/ServiceNow/Zoho Desk).
- **Offline / edge:** LOCAL_ROUTER always returns `"offline"`. OFFLINE_EXECUTION_ENGINE and OFFLINE_SANDBOX echo. OFFLINE_REGISTRY is a `/tmp` JSON file. OFFLINE_RUNTIME_PACKAGER does real tarring, but it expects an `agents/` + `tests/` layout that this repo doesn't have.
- **Multi-tenancy:** MULTI_TENANCY_GRID is an echo placeholder. No tenant isolation exists anywhere in scope.
- **Not present:** health endpoints, SLOs/error budgets, alerting, backups/DR, CI/CD, IaC, log shipping, tracing.

---

## 5. Connectors in detail

**ZOHO_CONNECTOR (`_connectors/ZOHO_CONNECTOR/main.py`), REAL:**
- Real OAuth2 *refresh_token* grant: POST to `https://accounts.zoho.{dc}/oauth/v2/token` (:18, :38-58). The DC defaults to `in` (:22).
- Caches the access token until `expires_in - 60s` (:39).
- GET/POST with the `Authorization: Zoho-oauthtoken <tok>` header (:60-79). Timeouts are 15/30s.

Gaps in ZOHO_CONNECTOR:
- No handling of Zoho error JSON: a failed refresh returns `{"error":...}`, so `result["access_token"]` raises KeyError (:55).
- No HTTPError handling, no 401 re-auth, no retry/backoff on Zoho rate limits, no pagination helper.
- No initial auth-code exchange; you must supply a refresh token out of band.
- `health_check` only checks that config is present (no live ping).
- Not thread-safe.

**ZOHO_PEOPLE, ZOHO_PAYROLL, ZOHO_PROJECTS: real HTTP intent, DEAD as written.**
- All three do `from connectors.ZOHO_CONNECTOR.main import ZohoConnector` (PAYROLL:5, PEOPLE:5, PROJECTS:6). No `connectors` package exists. The directory is `departments/_connectors/` with no `__init__.py` at that level, and the underscore name isn't importable as `connectors`. **The import fails** (confirmed).
- PAYROLL:23 and PROJECTS:24 call `config.get(...)` on the raw `config` param, which defaults to None, so they raise AttributeError when built without config.
- `health_check()` in all three returns `"ok"` unconditionally (it doesn't check the connector).

Endpoint plausibility (I didn't verify these live; flagged for the lead):

| Connector | Endpoint | Assessment |
|---|---|---|
| PROJECTS | `projectsapi.zoho.in/restapi/portal/{portal}/projects/…` | Matches the documented Zoho Projects REST v1 shape |
| PEOPLE | `BASE = https://people.zoho.in/api` + `/forms/employee/getRecords` | Zoho People's documented paths are under `/people/api/...`, so it likely 404s |
| PEOPLE | `getAttendanceEntries` | Documented under `/people/api/attendance/...`, not `/forms/attendance/` |
| PAYROLL | `payroll.zoho.in/api/v1/payslips`, `/employees/{id}/ytd` | Unverified; Zoho Payroll's public API surface is limited, so it may be invented |

Logic bugs in the sub-connectors:
- `ZOHO_PROJECTS.get_task_summary` on-time rate = `(completed - overdue)/completed` (:69). `overdue` counts only *non-closed* tasks, so the formula mixes populations and can go negative.
- `ZOHO_PEOPLE` attendance `IsLate == "true"` string matching (:68) is fragile.

Data sensitivity: PAYROLL pulls salary, EPF/ESI/TDS and CTC, and PEOPLE pulls appraisals. These are PII and comp data. There's no masking, no audit, and `hitl_required:false`.

**WHATSAPP_BRIEFING (in sales), REAL:** a real Meta Graph API send (see §2.6). It's the only outbound messaging in scope.

**No other connectors exist**: none for CRM (Zoho CRM / HubSpot / Salesforce), email, Slack, ticketing, cloud providers, or a SIEM.

---

## 6. Plane mapping

| Plane | Agents in this scope | Status |
|---|---|---|
| **Security** | AEGIS, ARGUS, PRAETOR, THREAT_DETECTION_MESH, CYBER_RISK_ENGINE, COGNITIVE_INTENT_FIREWALL, VIGILIS, IDENTITY_FRAMEWORK, PIN_UNLOCK_LAYER, OWNER_VERIFICATION, MFA_RECOVERY_WORKFLOW, SECRETS_VAULT, SECURE_ACTION_TOKENS, VMRK (misfiled in marketing), SENTINELDNA, ZERO_TRUST_PIPELINE, lockdown/containment set | Primitives only. Not wired. Zero-trust is a stub. Several primitives are unsafe (§3). |
| **Compliance / governance** | COMPLIANCE_GUARD, AUDITOR, SIGNED_AUDIT_CHAIN, DEEP_AUDIT_ENGINE, OVERSIGHT_MONITOR, SELF_AUDIT, GOVERNANCE_KERNEL, POLICY_CONTROLLER, GOVERNANCE_ADAPTATION_LOOP, LEGAL_INTELLIGENCE_ENGINE, EACPE_* | ~70% stub. The audit chain is broken. No regulation content. HITL is a rubber stamp. |
| **SRE / observability** | RESOURCE_OPTIMIZER, TELEMETRY_SPINE, SYSTEM_TELEMETRY, ARGUS, OVERWATCH, ITSM_ENGINE, FAILOVER_ROUTER, LATENCY_CONTROLLER, THROUGHPUT_MANAGER | 1 real psutil probe and 1 JSON log; the rest is stubs |
| **Deployment / infra** | IT_INFRA_ENGINE (simulated), COMPUTE_*, LOAD_DISTRIBUTOR, DISTRIBUTED_FABRIC, CLOUD_HANDOFF_CONTROLLER, OFFLINE_RUNTIME_PACKAGER, MULTI_TENANCY_GRID, LOCAL_*/OFFLINE_* | Simulated or empty. The packager is the only real artefact producer. |
| **Admin control** | CUSTOS (RBAC), AGENT_CONTAINMENT_MODES, SOFT/HARD_LOCKDOWN_MODE, DECISION_FIREWALL, OWNER_VERIFICATION (single-owner model) | In-memory toggles. No admin API, UI or persistence. |
| **API management** | AEGIS (rate limiting), SECURE_ACTION_TOKENS (capability tokens), ZOHO_CONNECTOR (outbound client) | No gateway, API keys, quotas or versioning. There's no inbound API in scope at all. |
| **Sales** | AUTONOMOUS_SALES_NAVIGATOR, CONVERTA, RETENTA, TARGETA, ATTRACTA, AMPLIFEX, WHATSAPP_BRIEFING. COHORTUS is team coordination and DOMAIN_* are stubs. | Formula calculators fed by caller-supplied numbers. No CRM/pipeline data source. WhatsApp briefing is the one real workflow. |
| **Marketing** | BUSINESS_FUNNEL_DESIGNER, CUSTOMER_BEHAVIOR_ENGINE, CREATIVE_HOLODECK, plus hollow creative agents (CREATIVA, CREATIVE_ENGINE, IMAGINA, ARTESIA, AUTONOMOUS_MARKETING_ENGINE, BRAND_*) | The "creative/generative" agents are f-string templates. With no LLM layer, this is where an LLM is most obviously missing. |
| **Executive / strategy** | ORACLE, PROBABILIS, STOCHASTIX, REALMEX, INSIGHTA, VIRALYTICA, plus STRATEGIC_INTEL / OPPORTUNITY_RADAR / BUSINESS_DNA / COMPETITIVE_SCANNER / MARKET_GAP_ANALYZER / BUSINESS_MODEL_ENGINE (stubs) | Generic stats or random toys. Every strategy-named agent is a stub. |
| **Data / knowledge** | CHROMOS, *_MEMORY, MEMORY_FABRIC / MESH / DRIFT_DETECTOR, TEMPORAL_SNAPSHOTS, STREAM_PROCESSOR (stub), GLOBAL_STATE_MAP (stub) | Dicts and JSON files. No DB, vector store, streaming or lineage. |
| **HR / people data (via connectors)** | ZOHO_PEOPLE, ZOHO_PAYROLL, ZOHO_PROJECTS (+ base) | Real HTTP design, but the imports are broken post-reorg |
| **Client success** | LOGISTA (actually logistics) | Effectively empty plane |
| SDLC / STLC | none in scope. The stale tests in `velaris/tests` target non-existent `velaris.agents.*` paths. | — |

---

## 7. Reality check vs README

| README claim | Finding |
|---|---|
| "343 domain-classified agents… every business function is an agent" | 116 here. 52 stub/hollow, 45 toy rules, 15 do real I/O, 4 can't import. **0 are loaded by the runtime.** |
| "One unified intelligence layer" / "organisational brain" | No inter-agent calls, no shared bus in use (router `publish` iterates over 0 agents), no LLM, no ML. Each agent is an isolated class. |
| security: "Zero-trust, audit trails, threat detection, lockdown modes, secrets, biometrics" | Zero-trust = `return True`. Audit chain is broken. Secrets aren't encrypted. Biometrics = string-hash equality. Threat detection = toy primitives with no feed. Lockdown = in-memory boolean. |
| ethics_governance: "Policy enforcement, ethical assessment, compliance alignment, legal intelligence" | 6 of 7 are stubs that approve everything. "Legal intelligence" is an empty dict. ETHICAL_ENGINE was archived as a stub. |
| sales_crm: "Lead conversion, churn prediction, pipeline management" | Churn = `days × 0.05`. No pipeline management or CRM integration. |
| marketing_brand: "creative generation, autonomous marketing" | f-string templates and `random.randint` scores |
| operations/infrastructure: "Distributed compute, scaling, telemetry spine, ITSM, IT infra, multi-tenant" | Scaling and distributed compute are empty stubs. IT infra is simulated. Multi-tenant is an echo placeholder. Telemetry is a JSON file. |
| "auditable" | No agent emits audit events. The audit chain can't verify. |
| "independently deployable agent" | No packaging, service wrapper, API or Dockerfile per agent. 10 hard-code `/live` paths, and the Zoho sub-connectors depend on a non-existent `connectors` package. |
| "~60% fully implemented (>40 lines)" | 48% are over 40 lines here, and line count mostly reflects logging boilerplate. By behaviour, about 13% do anything beyond in-memory arithmetic. |
| `python main.py` "shows all agents loaded… Status: active" | It prints `Agents loaded : 0`, `Status : online`. |

The prior audit (Sept 2026: ~39% stubs, no LLM layer) is **confirmed and understated** for this slice: 45% stub/hollow, and no LLM anywhere.

**Genuinely useful seeds:**
- ZOHO_CONNECTOR (OAuth refresh)
- WHATSAPP_BRIEFING (real send plus SQLite)
- IDENTITY_FRAMEWORK (PBKDF2)
- SECURE_ACTION_TOKENS / VMRK (HMAC)
- ITSM_ENGINE (if the hash noise is removed)
- COMPLIANCE_GUARD
- BUSINESS_FUNNEL_DESIGNER
- AEGIS (rate limiter)

---

## 8. Open questions
1. Is a `connectors` package (or a `sys.path` shim) expected to exist? Was `_connectors` meant to be renamed back, or should the imports become relative? Until then, 3 of 4 Zoho connectors are dead.
2. Where are `/live/agents/*` meant to be provisioned (Docker volume on VPS?), and by whom? 10 agents in scope depend on it.
3. Will the router be pointed at `departments/` (and recurse two levels), or will agents be copied into `velaris/agents/`? Who updates the 70 stale test imports?
4. Were the Zoho People/Payroll endpoint paths tested against a live Knackforge Zoho org (the `.in` DC)? People paths appear to be missing the `/people/` prefix.
5. Is the "deterministic entropy" (hash-of-ID added to scores) intentional, e.g. for test reproducibility? It makes risk, ITSM and customer scores partly arbitrary.
6. Should VMRK move to security, LOGISTA to supply_chain/operations, COHORTUS to hr/project_management, and DOMAIN_* (non-sales stubs) to `_archived_agents/_stubs`?
7. Is HITL intended for connectors that pull payroll and appraisal PII (`hitl_required:false`)?
8. Should SECRETS_VAULT be replaced by real encryption (Fernet/KMS), given `cryptography` is already in `requirements.txt`?
9. WHATSAPP_BRIEFING and the Zoho connectors are untracked new code. Are they meant to land in the next commit with the reorg, or separately?
