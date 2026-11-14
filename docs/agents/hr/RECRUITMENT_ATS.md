# RECRUITMENT_ATS

- **Department:** `hr`
- **Status (static inventory):** `real`
- **Source:** `departments/hr/RECRUITMENT_ATS/main.py` (151 lines)

## Purpose

RECRUITMENT_ATS — Velaris BOS agent for Knackforge
Ported from VKatOS recruitment_tracker. Full 8-stage ATS pipeline.

## Class `RecruitmentTracker`

- `__init__(db_path)`
- `add(name, role, client, email, phone)`
- `move(candidate_id, new_stage, notes)`
- `stale(days)`
- `report()`
- `export(filename)`

## Class `RecruitmentATSAgent`

ATS pipeline — sourced→screened→shortlisted→interview_scheduled→interviewed→offer_made→offer_accepted→placed.
Ported from VKatOS recruitment_tracker.

- `__init__(config)`
- `health_check()`
- `add_candidate(name, role, client, email, phone)`
- `advance_stage(candidate_id, stage, notes)`
- `get_stale(days)`
- `report()`
- `export_csv(filename)`

## Depends on

- nothing from velaris.*

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** none found
