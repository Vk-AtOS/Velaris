# Velaris BOS — organisational brain

Velaris is the organisation-side service of the AetherOS platform: a registry of business agents (mostly rule-based, a few able to call a model)
(one folder per agent), an HTTP API the AetherOS gateway calls with signed requests, and a public app for forms and links.
One deployment serves one organisation (`VELARIS_ORG`). Everything stateful lives under `VELARIS_DATA`.

Every number below can be reproduced with the command next to it. Nothing here is a target: it is what the code does today.

## What is in the repository

| Path | What it is | Reproduce |
|---|---|---|
| `departments/<department>/<AGENT>/main.py` | the agents: 346 in 16 departments | `python main.py` prints `Agents loaded : 346`, `Agents failed : 0` |
| `velaris/agents` | the router that finds agents in `departments/` by name, and the inventory | `python main.py --inventory` |
| `velaris/api` | the HTTP API (`python -m velaris.api`, port 8730) and the public app (`python -m velaris.api.public`, port 8731) | `deploy/README.md` |
| `velaris/core` | access control (`access.py`), configuration, the vault for personal-data keys, file locks, the Prime client | `ls velaris/core` |
| `velaris/agentkit` | helpers the agents share: JSON state, results, hiring and HR records, checks | `ls velaris/agentkit` |
| `velaris/intel` | model gateway, documents and search, memory, flows with human approval, web fetch | `ls velaris/intel` |
| `velaris/control` | the control layer: scripted, approved work on files, a terminal, a browser | `ls velaris/control` |
| `velaris/chat`, `velaris/mail` | company chat and company email | `ls velaris/chat velaris/mail` |
| `velaris/backend`, `velaris/memory`, `velaris/security` | the agent engine, an in-process key/value mesh, a deny-by-default security stub | `ls velaris` |
| `deploy/` | Dockerfile, compose, nginx, Kubernetes, systemd, backup and smoke scripts | `deploy/README.md` |
| `docs/agents/` | one generated page per agent (purpose, methods, state, dependencies, callers) | `python tools/gen_agent_docs.py` |
| `tools/` | `gen_agent_docs.py` (agent pages, `--check`, `--against`), `check_structure.py` (CI gate), `count_agents.py` (the counts below) | `python tools/count_agents.py` |

## What the 346 agents actually do

`python main.py --inventory` classifies each agent from its source (a static check, not a quality judgement):

| | real | rule-based | not implemented | total |
|---|---|---|---|---|
| all departments | 161 | 173 | 12 | 346 |


Most agents are deterministic code. Only a small number can reach a language model, and no agent has a passing score from a real
model yet. `python3.11 tools/count_agents.py` computes every figure below from the code and `evals/scores/`
(`velaris/tests/test_count_agents.py` fails if this table is out of date):

| measure | agents | of |
|---|---|---|
| static heuristic: real (file, database, network or persisted state) | 161 | 346 |
| static heuristic: rule-based (logic kept in memory) | 173 | 346 |
| static heuristic: not implemented | 12 | 346 |
| calls a model-gateway method in its own main.py | 7 | 346 |
| reaches a model call through one velaris module it imports | 23 | 346 |
| passed an eval with a real model (ready: true) | 0 | 346 |

What each row does and does not show:

- The three static rows are the inventory above (rules in `velaris/agents/inventory.py`). "real" is a heuristic about
  where an agent's code touches the outside (files, database, network, OS, persisted state). It does not show that the logic is correct,
  and it counts a file write the same as a business decision.
- The two model rows are static too: they show which agents can call a model, not that a model is configured or that its answers are good.
- The eval row is the only quality evidence. `evals/scores/` holds the offline `fake-oracle` run, which proves the harness and the eval
  format work and marks nothing ready. A real-model run needs an API key or a local Ollama (`docs/model_providers.md`).
- The per-department counts are in `python main.py --inventory` and `docs/agents/INDEX.md`.

## Departments (agents per department, from `--inventory`)

`_ai_core` 133 (reasoning, memory and governance frameworks: ACF, AAE, ASEL, CRK, VCAS and the like, PRIME, ENGINE, REGISTRY),
`security` 29, `it_infrastructure` 26, `finance` 25, `operations` 25, `hr` 20, `data_knowledge` 14, `project_management` 14,
`sales` 13, `executive` 12, `marketing` 11, `legal_compliance` 7, `_connectors` 6 (Jira, Confluence, Zoho), `supply_chain` 6,
`communications` 4, `client_success` 1. The old `domains/` layout, the 19-domain table and the archived vertical folders
(healthcare, agriculture, real estate, research simulation) no longer exist; they are in git history under the tag
`archive/pre-reorg`.

## Run it

```bash
pip install -r requirements.txt -c deploy/constraints.txt   # pinned, audited set
python main.py                 # loads every agent and prints the status
python main.py --inventory     # real / rule-based / not implemented per department
python -m pytest -q            # the test suite (count: python -m pytest --collect-only -q | tail -1)
python deploy/smoke.py         # starts the API with dummy credentials and checks that signed requests are judged correctly
```

The API needs `VELARIS_ORG`, `VELARIS_API_SECRET` and `VELARIS_IDENTITY_PUBLIC_KEY`; see `deploy/README.md` for every setting,
the single-worker rule and the backup and restore scripts.

## Checks that run in CI (`.github/workflows/ci.yml`)

tests and smoke, `ruff` (real errors only), `tools/check_structure.py` (file size, broad excepts, unresolved imports, import cycles),
`pip-audit` on `deploy/constraints.txt`, `gitleaks` (allowlist `.gitleaks.toml`, three reviewed test fixtures), and the test that
fails when `docs/agents/` no longer matches the code (`python tools/gen_agent_docs.py --check`).

## Dependencies

`requirements.txt` lists exactly what the code imports unconditionally (`velaris/tests/test_requirements.py` enforces it).
Optional packages (voice, browser rendering) are imported only where used and the feature says so when they are missing:
`playwright`, `openai-whisper` / `faster-whisper`, `sounddevice`, `pyttsx3`, `openpyxl` and `python-pptx` (tests only).

## Documents in `docs/`

`docs/agents/` and `docs/DEAD_CODE_REVIEW.md` describe the current code. `docs/archive/` holds dated snapshots (the November
codebase map, the HR research notes, the design brief): they describe the repository as it was on their date and are not kept up to date.

## Licence

Proprietary — VKatOS / Vk-AtOS. All rights reserved.
