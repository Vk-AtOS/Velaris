# ADVANCED_SEARCH_ENGINE

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/ADVANCED_SEARCH_ENGINE/main.py` (60 lines)

## Purpose

_No module docstring yet._

## Class `AdvancedSearchEngine`

Velaris Advanced Search Engine (Offline)
- Keyword search across multiple datasets
- Weighted scoring
- Multi-index registry

- `__init__()`
- `register_dataset(name)`
- `add_record(dataset, record)`
- `search(keyword)`
- `datasets_list()`
- `web_search(query, limit)` — Live web search (public search APIs; results screened by the guard).
- `read_page(url)` — One web page as clean markdown. Check 'error': a blocked or unreadable page has no text.

## Depends on

- `velaris.intel`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** `velaris/api/allowlist.py`
- **tests:** none found
