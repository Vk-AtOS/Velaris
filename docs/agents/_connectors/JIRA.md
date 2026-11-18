# JIRA

- **Department:** `_connectors`
- **Status (static inventory):** `real`
- **Source:** `departments/_connectors/JIRA/main.py` (182 lines)

## Purpose

JIRA connector: Atlassian Jira Cloud REST API v3 (API token + account email, HTTP Basic).

Read-only (safe to call without approval):   search_issues, get_issue, get_transitions, list_projects
Consequential (change the customer's Jira): create_issue, transition_issue
  These two are `act` rules in velaris.api.allowlist: the API turns a call into a flow step that
  waits for approval (Prime or local) and runs it afterwards. The methods themselves refuse any call
  that is not running inside an approved flow step (atlassian.refuse_unless_approved), whatever
  arguments it carries; there is no approval parameter to forge. Each run is traced.

Scope: only the projects in config jira_projects / vault ATLASSIAN_JIRA_PROJECTS can be read or changed (see
atlassian.py); empty means nothing. Every JQL is wrapped in `project in (...) AND (...)`, issue keys and the
issue's real project are checked, and list_projects returns only those projects. The API additionally
requires the atlassian_reader role (velaris.core.access) for the reads.

Issue text (summary, description) is data: it is screened by velaris.intel.guard and withheld when
it reads like instructions to a model; the level is returned beside it.

Endpoints: GET /rest/api/3/search/jql (token-paged: nextPageToken; the older /rest/api/3/search is
deprecated by Atlassian and being removed), GET /rest/api/3/issue/{key}, GET/POST
/rest/api/3/issue/{key}/transitions, POST /rest/api/3/issue, GET /rest/api/3/project/search.
ponytail: parameter and field names follow Atlassian's published API as understood when this was
written; the first call against a real site should be checked against the live response.

## Class `JiraConnector`

- `__init__(config, **client_args)`
- `health_check()`
- `search_issues(jql, max_results, fields)` — Issues matching a JQL query, token-paged up to max_results (1-1000).
- `get_issue(key)`
- `get_transitions(key)` — The transitions the issue can take now: needed to pick the id for transition_issue.
- `list_projects(max_results)`
- `create_issue(project_key, summary, issue_type, description)` — CONSEQUENTIAL. Creates an issue in the customer's Jira.
- `transition_issue(key, transition_id)` — CONSEQUENTIAL. Moves an issue through its workflow (ids from get_transitions).

## Depends on

- `velaris.agents.JIRA.atlassian`
- `velaris.intel`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `CONFLUENCE`, `JOB_POSTINGS`
- **platform modules:** `departments/_connectors/JIRA/atlassian.py`, `velaris/api/allowlist.py`, `velaris/intel/tools.py`
- **tests:** `velaris/tests/atlassian_kit.py`, `velaris/tests/test_atlassian_connectors.py`, `velaris/tests/test_atlassian_oauth.py`, `velaris/tests/test_atlassian_scope.py`, `velaris/tests/test_intel_tools.py`
