# ZOHO_CONNECTOR

- **Department:** `_connectors`
- **Status (static inventory):** `real`
- **Source:** `departments/_connectors/ZOHO_CONNECTOR/main.py` (90 lines)

## Purpose

Zoho connector: OAuth2 base client that other Zoho agents use to call Zoho REST APIs.

Config (or the ZOHO_CLIENT_ID, ZOHO_CLIENT_SECRET, ZOHO_REFRESH_TOKEN environment variables): client_id, client_secret,
refresh_token and dc (data centre, default "in"). get(url, params) and post(url, payload) send the request with a
Zoho-oauthtoken header and return the decoded JSON; the access token is fetched from the refresh token on first use and
reused until a minute before it expires. health_check() returns status "ok" or "unconfigured" and makes no network call.
Credentials are not checked up front: a call with missing or wrong ones, or any network or HTTP error, raises the
urllib exception (or a KeyError if the token reply has no access_token). Timeouts are 15 s (token) and 30 s (calls).
State: the access token and its expiry are held in memory only.

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
