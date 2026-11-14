# HR_TALENT_ENGINE

- **Department:** `hr`
- **Status (static inventory):** `real`
- **Source:** `departments/hr/HR_TALENT_ENGINE/main.py` (137 lines)

## Purpose

HR_TALENT_ENGINE: evidence that a candidate has the skills a role asks for. For a human.

evaluate(candidate, requirements, documents) takes the role's stated requirements
({"must_have": [...], "nice_to_have": [...]}) and, for each skill, reports WHERE it
was found:
  * in the candidate's declared skills (with the self-rating they gave), and
  * in the supplied documents ({"resume": "..."}): the line number and the line.
Matching is whole-term and case-insensitive ("java" is not found in "javascript").

What it deliberately does not do: there is NO score, NO ranking, NO percentage and
NO hire/reject output. `decision` is always None. A skill with no evidence means
"not found in what was supplied", which is a question for the interview, not a
verdict. Education and the cultural flags are not used in matching.

Documents are outside text: each is screened by velaris.intel.guard. A document
the guard blocks is not read, and hidden characters (a known way to stuff a
resume with invisible keywords) are reported to the reviewer.

## Class `CandidateProfile`


## Class `HRTalentEngine`

- `health_check()`
- `validate(c)`
- `evaluate(c, requirements, documents)`

## Depends on

- `velaris.agentkit`
- `velaris.intel`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_hr_stubs.py`
