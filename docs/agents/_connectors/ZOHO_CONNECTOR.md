# ZOHO_CONNECTOR

- **Department:** `_connectors`
- **Status (static inventory):** `real`
- **Source:** `departments/_connectors/ZOHO_CONNECTOR/main.py` (80 lines)

## Purpose

_No module docstring yet._

## Class `ZohoConnector`

OAuth2 base connector for all Zoho APIs.
Handles token refresh automatically.
Config keys: client_id, client_secret, refresh_token, dc (data center: com/in/eu)

- `__init__(config)`
- `health_check()`
- `get(url, params)`
- `post(url, payload)`

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own
- env var: `ZOHO_CLIENT_ID`
- env var: `ZOHO_CLIENT_SECRET`
- env var: `ZOHO_REFRESH_TOKEN`

## Called by

- **other agents:** `ZOHO_PAYROLL`, `ZOHO_PEOPLE`, `ZOHO_PROJECTS`
- **platform modules:** none found
- **tests:** `velaris/tests/test_loader_and_fail_closed.py`
