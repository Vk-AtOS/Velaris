# Velaris BOS — organisational brain

Velaris is the organisation-side service of the AetherOS platform: a registry of rule-based and model-assisted business agents
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
| `tools/` | `gen_agent_docs.py` (agent pages, `--check`, `--against`), `check_structure.py` (CI gate) | `python tools/check_structure.py` |

## How many agents are real

`python main.py --inventory` classifies each agent from its source (a static check, not a quality judgement):

| | real | rule-based | not implemented | total |
|---|---|---|---|---|
| all departments | 161 | 173 | 12 | 346 |

"real" means the agent delegates to `velaris.intel` or has logic and touches something outside the process (files, a database, the network,
the OS); "rule-based" means it has logic that stays in memory; "not implemented" means it says so, or has no logic beyond
`__init__` and `health_check`. The rules are in the docstring of `velaris/agents/inventory.py`; they are a heuristic and cannot tell
correct logic from wrong. About half of the agents are real (state kept through `velaris.agentkit.state` counts as touching the outside). The per-department
counts are in the same command's output and in `docs/agents/INDEX.md`.

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
Optional packages (voice, browser rendering, DNS) are imported only where used and the feature says so when they are missing:
`playwright`, `openai-whisper` / `faster-whisper`, `sounddevice`, `pyttsx3`, `dnspython`, `openpyxl` and `python-pptx` (tests only).

## Documents in `docs/`

`docs/agents/` and `docs/DEAD_CODE_REVIEW.md` describe the current code. `docs/archive/` holds dated snapshots (the November
codebase map, the HR research notes, the design brief): they describe the repository as it was on their date and are not kept up to date.

## Licence

Proprietary — VKatOS / Vk-AtOS. All rights reserved.
