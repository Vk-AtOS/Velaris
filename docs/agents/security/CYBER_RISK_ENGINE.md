# CYBER_RISK_ENGINE

- **Department:** `security`
- **Status (static inventory):** `real`
- **Source:** `departments/security/CYBER_RISK_ENGINE/main.py` (128 lines)

## Purpose

CYBER_RISK_ENGINE: a residual-risk score for a declared asset, by a stated formula.

Inputs are what the caller declares: the asset's criticality, its exposure
points (open ports, public endpoints, external integrations, ...), which
controls are in place, and optionally the threats in play with a likelihood each.

    exposure      = exposure_points / MAX_EXPOSURE                         (0..1)
    threat        = 1 - product(1 - likelihood_i)                          (0 when none declared)
    likelihood    = 1 - (1 - exposure) * (1 - threat)
    impact        = CRITICALITY_IMPACT[criticality]                        (0.25 .. 1.0)
    inherent      = 100 * likelihood * impact
    effectiveness = sum(CONTROL_WEIGHTS of controls in place) / 100        (0..1)
    residual      = inherent * (1 - MAX_CONTROL_REDUCTION * effectiveness)

Controls never remove more than MAX_CONTROL_REDUCTION of the risk. Bands: residual
>= 70 critical, >= 40 high, >= 15 medium, else low. The same inputs always give
the same score; the asset id plays no part in it. The weights are this engine's
declared model, not a measurement of any real network.

## Class `AssetProfile`


## Class `CyberRiskEngine`

- `__init__()`
- `health_check()`
- `validate(p)`
- `compute_risk(p, threats)`
- `register(p, threats)` — Score an asset and keep the result in the risk register (latest assessment per asset).
- `top_risks(n)` — The n highest-scoring registered assets, worst first.

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agentkit.state`
- `velaris.core.access`

## State and configuration

- state file: `<VELARIS_DATA>/agents/CYBER_RISK_ENGINE/register.json`

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_security_stubs.py`, `velaris/tests/test_kan104_unauthenticated_writes.py`
