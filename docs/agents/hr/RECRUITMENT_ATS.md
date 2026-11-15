# RECRUITMENT_ATS

- **Department:** `hr`
- **Status (static inventory):** `real`
- **Source:** `departments/hr/RECRUITMENT_ATS/main.py` (166 lines)

## Purpose

RECRUITMENT_ATS — Velaris BOS agent for Knackforge
Ported from VKatOS recruitment_tracker. Full 8-stage ATS pipeline.

LEGACY: ATS_CORE is the product with consent, retention and erasure; this older tracker has none of those. Until it is merged into
ATS_CORE or retired (owner decision), every method needs an authenticated Caller (velaris.core.access): changes need the recruiter or
hr_admin role, reads and the CSV export go through authorize_read("candidate") (traced). Every row carries the organisation and
every query filters on it, the acting person is recorded in stage_history, a stage must be one of STAGES and move one step forward
or back, and the database and export live under VELARIS_DATA, never in the working directory. Raises AccessDenied when refused.

## Class `RecruitmentTracker`

- `__init__(db_path)`
- `add(org, name, role, client, email, phone)`
- `move(org, by, candidate_id, new_stage, notes)`
- `stale(org, days)`
- `report(org)`
- `export(org, filename)`

## Class `RecruitmentATSAgent`

ATS pipeline — sourced→screened→shortlisted→interview_scheduled→interviewed→offer_made→offer_accepted→placed.
Ported from VKatOS recruitment_tracker.

- `__init__(config)`
- `health_check()`
- `add_candidate(name, role, client, email, phone)`
- `advance_stage(candidate_id, stage, notes)`
- `get_stale(days)`
- `report()`
- `export_csv(filename)` — Writes a CSV of the organisation's candidates under VELARIS_DATA and returns its path (owner-only file).

## Depends on

- `velaris.agentkit.onboarding_common`
- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_hr_data_legacy.py`, `velaris/tests/test_no_state_in_source_tree.py`
