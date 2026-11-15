# SECRETS_VAULT

- **Department:** `security`
- **Status (static inventory):** `real`
- **Source:** `departments/security/SECRETS_VAULT/main.py` (131 lines)

## Purpose

Secrets vault: stores named secrets as files with an HMAC integrity check.

set_secret(name, secret) writes the base64 of the secret (encoded, not encrypted) and an HMAC-SHA256 signature made with
a 64-byte key. get_secret(name) returns the text, None if the secret is absent, and raises ValueError("Integrity check
failed") if the stored data no longer matches its signature. list_secrets() returns names; delete_secret(name) returns False
if nothing was removed. A name must be 1-128 characters of letters, digits, "_", "-" or "."; anything else raises ValueError.
There is no caller check here. State: <VELARIS_DATA>/agents/SECRETS_VAULT/ with vault.key and data/<name>.sec and .sig,
all owner-only files; the key is created on first use.

## Class `SecretsVault`

- `__init__()`
- `key()` — The OLD HMAC key. Only the one-time legacy migration uses it (never created otherwise); delete vault.key
- `set_secret(name, secret)` — Encrypt and store. Without the master key (VELARIS_VAULT_KEY[_FILE]) this raises VaultKeyError: fail closed.
- `get_secret(name)`
- `migrate_legacy()` — One-time: seal every old base64+HMAC secret (needs VELARIS_VAULT_ALLOW_LEGACY=1), then refuse unsealed
- `list_secrets()`
- `delete_secret(name)`

## Depends on

- `velaris.core`
- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `JOB_POSTINGS`
- **platform modules:** `departments/_connectors/JIRA/atlassian.py`, `velaris/mail/connector.py`
- **tests:** `velaris/tests/test_agent_paths.py`, `velaris/tests/test_kan88_vault.py`, `velaris/tests/test_mail_connector.py`, `velaris/tests/test_private_files.py`
