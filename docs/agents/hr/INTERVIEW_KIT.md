# INTERVIEW_KIT

- **Department:** `hr`
- **Status (static inventory):** `real`
- **Source:** `departments/hr/INTERVIEW_KIT/main.py` (269 lines)

## Purpose

INTERVIEW_KIT: structured interviews and what can honestly be said about them.

Questions are tagged by competency; a rubric gives each competency anchored 1-5 descriptors; a kit lists the competencies and questions
for a requisition; a panel names who interviews whom. Each interviewer submits one scorecard per application, once, with evidence per
competency, before seeing anyone else's (enforced: others' cards are hidden until the caller has submitted their own, or until the whole
panel has submitted and the caller holds a hiring role). Aggregation, agreement (kappa, alpha: velaris.agentkit.hiring_stats) and
calibration are arithmetic over human ratings. This agent makes no automated judgement of a person: no overall score, no recommendation,
no ranking, and the output says so. Interviewer identity is the authenticated Caller.

## Class `InterviewKit`

Question banks, rubrics, kits, independent scorecards, aggregation, agreement, calibration, work samples.

- `__init__(config)`
- `health_check()`
- `define_rubric(caller, competency, description, anchors)` — A competency with a written behavioural anchor at each level 1 to 5.
- `add_question(caller, text, competency, follow_ups)` — A job-related question tagged with an existing competency.
- `list_questions(caller, competency)`
- `create_kit(caller, requisition_id, competencies, question_ids)` — The interview kit of a requisition: which competencies are scored and which questions are asked. One kit per requisition.
- `get_kit(caller, requisition_id)` — The kit with its rubric anchors and questions: what an interviewer prepares from.
- `assign_panel(caller, application_id, interviewer_ids)` — Name who interviews this application. Only they can submit a scorecard for it.
- `submit_scorecard(caller, application_id, ratings)` — Your own scorecard, once, locked on submit. ratings: [{"competency", "score" 1-5, "evidence", "question_id"?}] for EVERY
- `scorecards(caller, application_id)` — The scorecards of an application, aggregated with every interviewer's evidence. Hidden until you have submitted yours (or the
- `agreement_report(caller, requisition_id, competency)` — Alpha, pairwise weighted kappa and leniency offsets over submitted scorecards (all, or one requisition / competency).
- `calibration_report(caller)` — Per competency: how well interviewers agree (alpha), so a rubric with poor agreement is visibly broken and gets rewritten.
- `create_work_sample(caller, title, brief, checklist, time_limit_min, ai_tools_allowed)` — A work-sample task with a checklist of observable things to look for. Say whether AI tools are allowed (then score the
- `list_work_samples(caller)`
- `review_work_sample(caller, application_id, work_sample_id, checks, notes)` — Your review of a submitted work sample: for every checklist item, met or not with the evidence you saw. The result is a count
- `work_sample_reviews(caller, application_id)`

## Depends on

- `velaris.agentkit`
- `velaris.agentkit.hiring_common`
- `velaris.agentkit.results`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** `velaris/agentkit/hiring_common.py`, `velaris/agentkit/hiring_kit.py`, `velaris/api/allowlist.py`, `velaris/orchestration/autonomy.py`
- **tests:** `velaris/tests/test_hiring_api.py`, `velaris/tests/test_hiring_kit.py`
