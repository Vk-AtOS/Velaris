# EACPE_HUMAN_GUARD

- **Department:** `legal_compliance`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/legal_compliance/EACPE_HUMAN_GUARD/main.py` (184 lines)

## Purpose

EACPE_HUMAN_GUARD: irreversible actions wait for a named person.

Action classes are declared guarded (with the people who may approve them) or
exempt. validate(action) answers for one concrete action, {"class": ...,
"requested_by": ..., <any details>}:

  exempt class          approved, nothing to wait for
  guarded class         approved only if a listed approver - not the requester -
                        approved this exact action (its details are hashed),
                        within APPROVAL_TTL_S. An approval is used once.
  any other class       refused as "unclassified": an action nobody classified is
                        not assumed to be safe
  malformed             refused

Who acts is never an argument: the requester, the approver and whoever changes a class
are the current caller (velaris.core.access). request() and decide() refuse without one;
set_approvers() and exempt() also need the governance admin role. A legacy `by` /
`approver` / `requested_by` value is accepted only when it is the caller's own id.

Out of the box, DEFAULT_GUARDED classes are guarded with no approvers, so they
cannot proceed until someone is named with set_approvers(). Requests, decisions
and use of an approval are recorded in the hash-chained trace; an approval that
cannot be recorded does not count.

## Class `EACPE_HUMAN_GUARDAgent`

- `__init__()`
- `health_check()`
- `set_approvers(action_class, approvers, by)` — Guard `action_class`; only the listed people may approve it. Governance admins only.
- `exempt(action_class, by)` — Declare a class reversible: its actions need no approval. Governance admins only.
- `request(action)` — Ask for approval of one action, as the current caller. Returns the request id the approver acts on.
- `decide(request_id, approver, approve, now)` — The current caller approves or rejects a request. `approver`, if given, must be the caller.
- `validate(action, now)` — May this exact action go ahead now? Consumes the approval it relies on (the requester, as the current caller, only).

## Depends on

- `velaris.agentkit.checks`
- `velaris.agentkit.infra_store`
- `velaris.agentkit.results`
- `velaris.agentkit.state`
- `velaris.core.access`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_aicore_b_prime_vcas.py`, `velaris/tests/test_dept_legal_compliance_stubs.py`, `velaris/tests/test_kan104_unauthenticated_writes.py`, `velaris/tests/test_layer32_eacpe.py`
