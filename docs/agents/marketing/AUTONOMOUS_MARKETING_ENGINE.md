# AUTONOMOUS_MARKETING_ENGINE

- **Department:** `marketing`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/marketing/AUTONOMOUS_MARKETING_ENGINE/main.py` (77 lines)

## Purpose

Autonomous marketing engine: templated campaign plans and an audience score from measured numbers (no model, no sending).

generate_campaign(product, audience, budget) returns {product, audience, budget, timestamp, strategy}, where strategy
holds three fixed text templates (email, social, landing_page), and appends it to the history; an empty product or
audience, or a budget that is not a finite number of zero or more, raises ValueError. score_audience(audience) takes
{"size": people, "engagement": 0..1, "conversion": 0..1} and returns 0-100 (engagement 50%, conversion 30%, size 20% on
a log scale where a million people is full marks); anything else, including an audience name, raises ValueError.
suggest_channels(score) returns ["social", "video", "influencers"] above 70, ["email", "social"] above 40, otherwise
["email"]. get_history() returns a copy of the campaigns.
State: the history list is in memory only, lost on restart. Nothing is published or sent anywhere.

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
