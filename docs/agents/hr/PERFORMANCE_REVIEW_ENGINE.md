# PERFORMANCE_REVIEW_ENGINE

- **Department:** `hr`
- **Status (static inventory):** `real`
- **Source:** `departments/hr/PERFORMANCE_REVIEW_ENGINE/main.py` (211 lines)

## Purpose

_No module docstring yet._

## Class `PerformanceReviewEngine`

OKR tracking, 360 reviews (self/peer/manager), and calibration.
All data is stored locally in SQLite; each cycle is a string like "Q3-2026" or "FY2026".

- `__init__(config)`
- `health_check()`
- `set_okr(employee_id, cycle, objective, key_results)`
- `update_okr_progress(okr_id, progress)` — progress: 0.0–1.0
- `get_okrs(employee_id, cycle)`
- `submit_review(employee_id, reviewer_id, review_type, cycle, scores, comments)` — review_type: 'self' | 'peer' | 'manager'
- `get_360_summary(employee_id, cycle)` — Aggregates self/peer/manager scores into one 360 summary.
- `calibrate(cycle, employee_id, raw_score, calibrated_score, calibrated_by)` — Record calibration session adjustment.
- `get_calibration_report(cycle)` — Full calibration table for a review cycle, sorted by calibrated score desc.

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** none found
