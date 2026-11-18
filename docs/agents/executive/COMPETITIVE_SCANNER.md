# COMPETITIVE_SCANNER

- **Department:** `executive`
- **Status (static inventory):** `real`
- **Source:** `departments/executive/COMPETITIVE_SCANNER/main.py` (89 lines)

## Purpose

COMPETITIVE_SCANNER: read competitors' public pages and report what changed.

scan(competitors=[{"name", "url"}], fields=None):
  * each URL is fetched through velaris.intel.web.scrape (public addresses only, robots
    obeyed, text screened by the guard);
  * the page's title, description, size and a SHA-256 of its text are reported, with
    `changed` against the hash stored at the previous scan;
  * with `fields` ({name: description}), a model pulls those values out through
    web.extract, which drops any value the page text does not support. Without a model
    the extraction is `not_configured`; the change report still works.

The agent holds no competitor knowledge of its own: a page it cannot read is
reported as an error, never filled in. No competitors supplied -> `needs_data`.
State: <VELARIS_DATA>/agents/COMPETITIVE_SCANNER/snapshots.json (owner-only).

## Class `COMPETITIVE_SCANNERAgent`

- `__init__(name)`
- `health_check()`
- `scan(competitors, fields, llm, fetcher)`

## Depends on

- `velaris.agentkit`
- `velaris.intel`

## State and configuration

- state file: `<VELARIS_DATA>/agents/COMPETITIVE_SCANNER/snapshots.json`

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_executive_stubs.py`, `velaris/tests/test_kan106_business_agents.py`, `velaris/tests/test_layer14_aeil.py`
