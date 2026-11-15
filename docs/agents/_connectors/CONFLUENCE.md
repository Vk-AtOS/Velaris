# CONFLUENCE

- **Department:** `_connectors`
- **Status (static inventory):** `real`
- **Source:** `departments/_connectors/CONFLUENCE/main.py` (220 lines)

## Purpose

CONFLUENCE connector: Atlassian Confluence Cloud (API token + account email).

Read-only: search (CQL), get_page_markdown, list_spaces.
Consequential: ingest_space writes into the company document library (DOCUMENT_LIBRARY /
velaris.intel.docs), Velaris's own store (nothing in the customer's Confluence changes). It is an
`act` rule in velaris.api.allowlist and refuses to run outside an approved flow step, like the
Jira writes (atlassian.refuse_unless_approved).

Endpoints: GET /wiki/rest/api/search?cql= (v1 CQL search), GET /wiki/api/v2/spaces,
GET /wiki/api/v2/pages/{id}?body-format=storage, GET /wiki/api/v2/spaces/{id}/pages?body-format=storage.
Pages come back in "storage format" (XHTML with ac:/ri: macros) and are converted with
velaris.intel.web_markdown. Macro bodies other than plain text are rendered as text only
(ponytail: code and table-of-contents macros lose their special form; map macros if that bites).
Scope: only the spaces in config confluence_spaces / vault ATLASSIAN_CONFLUENCE_SPACES can be read or
ingested (see atlassian.py); empty means nothing. CQL is wrapped in `space in (...) AND (...)`, a page is
returned only if its spaceId belongs to an in-scope space, list_spaces shows only those, and the API
requires the atlassian_reader role for the reads. ingest_space also skips pages with view restrictions
(own or inherited from a parent, GET /wiki/rest/api/content/{id}/restriction/byOperation/read) so restricted
content never enters the shared library; if the restriction check fails the page is skipped.
Page text is data: it is screened by velaris.intel.guard; a page that reads like instructions is
withheld from the results and from the library, and said so.

## Class `ConfluenceConnector`

- `__init__(config, library, **client_args)`
- `health_check()`
- `search(cql, limit)` — CQL search, paged up to `limit` (1-500). Titles and excerpts are screened.
- `get_page_markdown(page_id)` — One page as markdown (version, space and title included).
- `list_spaces(limit)`
- `ingest_space(space_key, scope, max_pages)` — Copy the pages of a space into the document library under `scope`, as markdown.

## Depends on

- `velaris.agents.DOCUMENT_LIBRARY.main`
- `velaris.agents.JIRA.atlassian`
- `velaris.intel`
- `velaris.intel.web_markdown`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** `departments/_connectors/JIRA/atlassian.py`, `velaris/api/allowlist.py`
- **tests:** `velaris/tests/atlassian_kit.py`, `velaris/tests/test_atlassian_connectors.py`, `velaris/tests/test_atlassian_scope.py`
