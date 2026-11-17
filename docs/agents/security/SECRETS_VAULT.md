# SECRETS_VAULT

- **Department:** `security`
- **Status (static inventory):** `real`
- **Source:** `departments/security/SECRETS_VAULT/main.py` (135 lines)

## Purpose

Secrets vault: stores named secrets as encrypted files.

set_secret(name, secret) seals the secret with AES-256-GCM under the master key that is kept outside VELARIS_DATA
(velaris.core.vault; VELARIS_VAULT_KEY or VELARIS_VAULT_KEY_FILE), bound to the secret's name; without the key it raises
VaultKeyError and stores nothing. get_secret(name) returns the text, None if the secret is absent, and raises a
ValueError (VaultError) if the file was altered or belongs to another name. list_secrets() returns names;
delete_secret(name) returns False if nothing was removed. A name must be 1-128 characters of letters, digits, "_", "-"
or "."; anything else raises ValueError. Files written before encryption (base64 plus an HMAC signature) are refused
unless VELARIS_VAULT_ALLOW_LEGACY=1 and no migration has finished; migrate_legacy() verifies and re-seals them once and
from then on unsealed files are refused for good. There is no caller check here.
State: <VELARIS_DATA>/agents/SECRETS_VAULT/data/<name>.sec, owner-only. vault.key and .sig files exist only for legacy
secrets, and the file legacy.migrated marks a finished migration.

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
- **tests:** `velaris/tests/test_agent_paths.py`, `velaris/tests/test_allowlist_departments.py`, `velaris/tests/test_kan88_vault.py`, `velaris/tests/test_mail_connector.py`, `velaris/tests/test_private_files.py`
