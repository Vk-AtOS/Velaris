# POLICY_ACKS

- **Department:** `hr`
- **Status (static inventory):** `real`
- **Source:** `departments/hr/POLICY_ACKS/main.py` (256 lines)

## Purpose

POLICY_ACKS: policy documents with versions, per-employee acknowledgement evidence, reminders and a compliance report.

  * Publishing a policy creates the next version of its key, stores the exact text with its SHA-256, and supersedes
    the previous version: everyone in the audience must acknowledge the new one.
  * An employee acknowledges for themselves only: their identity is the Caller's employee id, never an argument. They send the
    SHA-256 of the text they were shown; if it is not the current text's hash the acknowledgement is refused ("you saw an
    older version"). The evidence record keeps who, which version, the text hash and the time, and its own hash.
  * The audience is resolved from the employee master (EMPLOYEE_RECORDS, read-only through onboarding_directory).
    If nobody can be resolved the report says so rather than showing 100%.
  * Reminders are drafted, never sent.
An acknowledgement shows the employee was given the text and said they read it; it is not proof they understood it and
it is not a signature. Whether a policy binds an employee (contract, notice) is a question for a lawyer.

## Class `PolicyAcks`

Versioned policies and acknowledgement evidence. See the module docstring.

- `__init__(config)`
- `health_check()`
- `publish_policy(policy_key, title, text, effective_date, due_days, departments, employee_ids)` — Publish the next version of a policy (HR administrators). Audience: everyone, or the listed departments, or the listed
- `retire_policy(policy_key, reason)` — Retire a policy: nobody needs to acknowledge it any more (HR administrators). Evidence is kept.
- `get_policy(policy_key, version)` — The text and hash of a policy (the current version unless `version` is given).
- `list_policies()`
- `acknowledge(policy_key, seen_text_sha256)` — Acknowledge the current version of a policy FOR YOURSELF. Send the SHA-256 of the text you were shown.
- `pending_for_employee(employee_id)` — What this employee still has to acknowledge (the employee themselves or an HR administrator).
- `compliance_report(policy_key)` — Per current policy: audience size, acknowledged, pending (with due dates), percentage (HR administrators).
- `reminders_due(within_days)` — Drafted reminders for pending acknowledgements that are overdue or due within `within_days` (HR administrators). Not sent.
- `ack_evidence(org, employee_id, policy_key)` — The current published version of a policy and this employee's acknowledgements of that key (any version).
- `dsr_export(org, employee_id, links)`
- `dsr_erase(org, employee_id, on, links)` — Anonymise this person's acknowledgements (the counts stay) when the registry allows; otherwise hold.

## Depends on

- `velaris.agentkit`
- `velaris.agentkit.onboarding_common`
- `velaris.agentkit.results`
- `velaris.core.access`
- `velaris.intel`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `EMPLOYEE_RECORDS`, `ONBOARDING_FLOW`
- **platform modules:** `velaris/agentkit/hr_wiring.py`, `velaris/agentkit/onboarding_adapters.py`, `velaris/agentkit/onboarding_checklists.py`, `velaris/agentkit/onboarding_common.py`, `velaris/agentkit/onboarding_directory.py`, `velaris/api/allowlist.py`, `velaris/orchestration/autonomy.py`
- **tests:** `velaris/tests/test_hr_data_traces.py`, `velaris/tests/test_hr_wiring.py`, `velaris/tests/test_onboarding_flow.py`, `velaris/tests/test_onboarding_records.py`
