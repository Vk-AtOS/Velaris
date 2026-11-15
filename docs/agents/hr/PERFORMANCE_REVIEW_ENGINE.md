# PERFORMANCE_REVIEW_ENGINE

- **Department:** `hr`
- **Status (static inventory):** `real`
- **Source:** `departments/hr/PERFORMANCE_REVIEW_ENGINE/main.py` (301 lines)

## Purpose

_No module docstring yet._

## Class `PerformanceReviewEngine`

OKR tracking, 360 reviews (self/peer/manager), and calibration.
All data is stored in SQLite under VELARIS_DATA; each cycle is a string like "Q3-2026" or "FY2026".
Every method needs an authenticated Caller (velaris.core.access; AccessDenied otherwise): you act on your own records, HR
administrators on anyone's; the reviewer and the calibrator are the caller, never an argument; scores are 0 to 5; rows carry
and filter on the organisation. Nothing here is a hiring, firing or pay decision: the suggested rating is for a person to weigh.

- `__init__(config)`
- `health_check()`
- `set_okr(employee_id, cycle, objective, key_results)`
- `update_okr_progress(okr_id, progress)` — progress: 0.0–1.0
- `get_okrs(employee_id, cycle)`
- `submit_review(employee_id, reviewer_id, review_type, cycle, scores, comments)` — review_type: 'self' | 'peer' | 'manager'
- `get_360_summary(employee_id, cycle)` — Aggregates self/peer/manager scores into one 360 summary.
- `calibrate(cycle, employee_id, raw_score, calibrated_score, calibrated_by)` — Record calibration session adjustment (HR administrators; the person calibrating is the caller).
- `get_calibration_report(cycle)` — Full calibration table for a review cycle, sorted by calibrated score desc.
- `dsr_export(org, subject_id, links)` — The subject's performance data. The person themselves get their OKRs and the scores of reviews about them, with peer and
- `dsr_erase(org, subject_id, on, links)` — Delete this person's OKRs, reviews and calibration rows when the registry says so. It has no retention row for performance

## Depends on

- `velaris.agentkit`
- `velaris.agentkit.onboarding_common`
- `velaris.core.access`
- `velaris.core.sealed_sqlite`
- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `EMPLOYEE_RECORDS`
- **platform modules:** `velaris/core/backfill_org.py`
- **tests:** `velaris/tests/test_hr_data_legacy.py`, `velaris/tests/test_hr_data_records.py`, `velaris/tests/test_kan113_sqlite_versions.py`, `velaris/tests/test_no_state_in_source_tree.py`
