# FEASIBILITY_ENGINE

- **Department:** `project_management`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/project_management/FEASIBILITY_ENGINE/main.py` (115 lines)

## Purpose

FEASIBILITY_ENGINE: a scored feasibility checklist where every criterion shows its evidence.

assess(project) rates five criteria from 0 to 4; weights are in CRITERIA and in the result.

  technical, resources, compliance   rated by the caller, each WITH evidence text;
                                     a rating without evidence does not count
  financial   computed when project["budget"] = {"required", "available"} is given:
              4 if required <= available, 2 if within 10% over, else 0
  schedule    computed when project["schedule"] = {"effort_person_days", "people", "working_days"}:
              load = effort / (people x working days); 4 if <= 80%, 3 if <= 100%, 1 if <= 120%, else 0
              (either may instead be rated by the caller with evidence)

  score = sum(weight x rating / 4), 0-100
  verdict: insufficient_evidence if any criterion is unrated or lacks evidence;
           not_feasible if a must-pass criterion is rated 0, or score < 50;
           feasible_with_conditions for 50-69; feasible from 70.

The compliance rating is the caller's own judgement with their evidence. The
engine checks no law.

## Class `FEASIBILITY_ENGINEAgent`

- `__init__(name)`
- `health_check()`
- `assess(project)`

## Depends on

- `velaris.agentkit`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_project_management_stubs.py`, `velaris/tests/test_layer14_aeil.py`
