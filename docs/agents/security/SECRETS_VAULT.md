# SECRETS_VAULT

- **Department:** `security`
- **Status (static inventory):** `real`
- **Source:** `departments/security/SECRETS_VAULT/main.py` (76 lines)

## Purpose

_No module docstring yet._

## Class `SecretsVault`

- `__init__()`
- `set_secret(name, secret)`
- `get_secret(name)`
- `list_secrets()`
- `delete_secret(name)`

## Depends on

- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `JOB_POSTINGS`
- **platform modules:** `departments/_connectors/JIRA/atlassian.py`, `velaris/mail/connector.py`
- **tests:** `velaris/tests/test_agent_paths.py`, `velaris/tests/test_mail_connector.py`, `velaris/tests/test_private_files.py`
