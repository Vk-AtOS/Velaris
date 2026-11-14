# OPPORTUNITY_RADAR

- **Department:** `executive`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/executive/OPPORTUNITY_RADAR/main.py` (59 lines)

## Purpose

OPPORTUNITY_RADAR: watch the web for new mentions of the things the caller is looking for.

run({"queries": [...], "keywords": [...]?, "limit": 8}):
  * every query goes through the guarded web search (velaris.intel.web.search);
  * results are de-duplicated and compared with the URLs already seen on earlier runs,
    so `new` holds only what has not been reported before;
  * each result lists which supplied keywords appear in its title or snippet.

The radar reports what the search returned, with its URL. It does not judge
whether something is a good opportunity and invents nothing: no queries ->
`needs_data`; a search that returns nothing -> `no_results`.
State: <VELARIS_DATA>/agents/OPPORTUNITY_RADAR/seen.json (owner-only).

## Class `OpportunityRadarAgent`

- `__init__(config)`
- `health_check()`
- `run(payload, search_fn)`

## Depends on

- `velaris.agentkit`

## State and configuration

- state file: `<VELARIS_DATA>/agents/OPPORTUNITY_RADAR/seen.json`

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_executive_stubs.py`
