# MEMORY_CLOUD_EXPAND

- **Department:** `data_knowledge`
- **Status (static inventory):** `real`
- **Source:** `departments/data_knowledge/MEMORY_CLOUD_EXPAND/main.py` (161 lines)

## Purpose

MEMORY_CLOUD_EXPAND: move a scope's memories between Velaris installations as a checked file.

There is no cloud service behind this agent and it opens no connection. What it
does is the part that can be exact:

  export_scope(scope)       writes every currently valid memory of the scope to a
                            bundle file in this agent's directory: one JSON header
                            (scope, count, sha256 of the body, and an HMAC-SHA256 of
                            the rest of the header) and one JSON line per memory.
  verify_bundle(path)       checks the HMAC, the checksum and the count.
  import_bundle(path, ...)  verifies, then replays each memory through
                            MemoryStore.remember(), so imported text is screened,
                            masked and deduplicated like any other.

Bundles are read only from this agent's own directory (a bare file name, or a path
that resolves inside it; symbolic links are refused), and only bundles signed with this
installation's key (agent_dir/bundle.key) are accepted: to move a bundle between
installations, both must hold the same key file. Exporting and importing a scope need a
governance admin of the organisation the scope belongs to (velaris.core.access.may_write_scope).
  sync_meta / meta          a persistent index of what has been placed where,
                            kept by the operator who carries the bundle.

Copying the bundle to another machine or bucket is the operator's step.

## Class `MEMORY_CLOUD_EXPANDAgent`

- `__init__()`
- `health_check()`
- `sync_meta(meta)` — Merge entries into the placement index ({key: JSON value}).
- `meta()`
- `export_scope(scope, bundle)`
- `verify_bundle(path)`
- `import_bundle(path, scope)` — Verify a bundle and store its memories under `scope` (which may differ from the exported one).

## Depends on

- `velaris.agentkit`
- `velaris.agentkit.checks`
- `velaris.agentkit.infra_store`
- `velaris.agentkit.results`
- `velaris.agentkit.state`
- `velaris.core.access`
- `velaris.intel.memory`
- `velaris.intel.paths`

## State and configuration

- state file: `<VELARIS_DATA>/agents/MEMORY_CLOUD_EXPAND/index.json`

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_data_knowledge_stubs.py`, `velaris/tests/test_memory_substrate.py`
