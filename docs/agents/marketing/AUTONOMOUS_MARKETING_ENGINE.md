# AUTONOMOUS_MARKETING_ENGINE

- **Department:** `marketing`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/marketing/AUTONOMOUS_MARKETING_ENGINE/main.py` (66 lines)

## Purpose

_No module docstring yet._

## Class `AutonomousMarketingEngine`

Velaris Autonomous Marketing Engine (AME)
- Generates marketing campaigns
- Scores audiences from MEASURED data: {"size": people, "engagement": 0..1, "conversion": 0..1}
- Produces multi-channel strategy outputs
- Offline-safe, no external requests

- `__init__()`
- `generate_campaign(product, audience, budget)`
- `score_audience(audience)` — 0-100: engagement 50%, conversion 30%, size 20% (log scale, a million people is full marks).
- `suggest_channels(score)`
- `get_history()`

## Depends on

- `velaris.agentkit.checks`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_agents_coverage_b.py`, `velaris/tests/test_kan94_sales_marketing.py`
