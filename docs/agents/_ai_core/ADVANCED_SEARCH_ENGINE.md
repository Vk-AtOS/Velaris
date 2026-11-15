# ADVANCED_SEARCH_ENGINE

- **Department:** `_ai_core`
- **Status (static inventory):** `real`
- **Source:** `departments/_ai_core/ADVANCED_SEARCH_ENGINE/main.py` (70 lines)

## Purpose

Advanced search engine: keyword search over in-memory datasets, plus live web search and page reading.

AdvancedSearchEngine.register_dataset(name) creates an empty dataset (False if it exists);
add_record(dataset, record) appends a dict (False if the dataset is unknown); names are
lower-cased. search(keyword) is a case-insensitive substring match that scores each record
by the number of fields containing the keyword and returns hits best first; datasets_list()
names the datasets. web_search(query, limit=8) and read_page(url) delegate to velaris.intel.web
(read_page returns a dict whose 'error' key is set for a blocked or unreadable page).
State: in memory only, lost on restart. No input validation: a non-string name or keyword raises.

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
- **tests:** `velaris/tests/test_agents_coverage_b.py`
