# HUMAN_APPROVAL_WORKFLOW

- **Department:** `_ai_core`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/_ai_core/HUMAN_APPROVAL_WORKFLOW/main.py` (65 lines)

## Purpose

HUMAN_APPROVAL_WORKFLOW: an in-memory approval request book.

Who asks and who approves is the current caller (velaris.core.access), never the
argument: the stored requester and approver are the caller's id. request_approval()
returns "" and approve()/reject() return False when there is no caller, when the
requester/approver argument is missing, empty or names someone other than the caller,
or when the caller would decide their own request.

## Class `HumanApproval`

- `__init__()`
- `request_approval(requester, action, meta)`
- `approve(req_id, approver)`
- `reject(req_id, approver, reason)`
- `status(req_id)`

## Depends on

- `velaris.agentkit.checks`
- `velaris.core.access`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_security_review_fixes.py`, `velaris/tests/test_security_review_round2.py`
