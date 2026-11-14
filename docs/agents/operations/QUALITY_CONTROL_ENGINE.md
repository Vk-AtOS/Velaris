# QUALITY_CONTROL_ENGINE

- **Department:** `operations`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/operations/QUALITY_CONTROL_ENGINE/main.py` (134 lines)

## Purpose

QUALITY_CONTROL_ENGINE: a batch checked against a u-chart and explicit disposition rules.

Control chart (defects per unit, the right chart for defect counts on samples of varying size):
  u      = total defects in the batch / sample size
  u-bar  = total defects / total units over the history batches (the baseline)
  limits = u-bar +/- 3 x sqrt(u-bar / n) for this batch's n; the lower limit is floored at 0
  rule 1   the point is beyond a 3-sigma limit
  rule 2   8 points in a row (this batch and the 7 before it) on one side of u-bar
The chart needs at least MIN_HISTORY earlier batches; fewer -> chart is `needs_data`.
With fewer than 20 the limits are flagged provisional.

Disposition, first rule that applies (the result names it):
  D1 hold         any critical defect
  D2 hold         a regulatory flag is raised (safety, traceability or documentation)
  D3 investigate  the chart signals above the centre line (rule 1 high, or rule 2 high)
  D4 accept       none of the above
inspection_rigour and process_stability have no defined unit and are not used.

## Class `QCInput`


## Class `QualityControlEngine`

- `health_check()`
- `validate(q)`
- `assess(q, history)`

## Depends on

- `velaris.agentkit`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_operations_stubs.py`
