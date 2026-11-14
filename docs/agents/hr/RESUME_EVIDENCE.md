# RESUME_EVIDENCE

- **Department:** `hr`
- **Status (static inventory):** `rule_based`
- **Source:** `departments/hr/RESUME_EVIDENCE/main.py` (109 lines)

## Purpose

RESUME_EVIDENCE: résumé facts with their source passages, skills through a reviewed alias table, evidence
against a requisition, and a four-fifths audit aid.

No model reads a résumé here, so nothing in a résumé can instruct anything. The output is evidence for a
person; it states that it makes no hire or reject decision and carries no score and no ranking. Parsed facts are
stored per candidate under agent_dir("RESUME_EVIDENCE") (org-stamped, owner-only) and are removed by
ATS_CORE.erase_candidates; the résumé text itself is not stored, only its hash.

## Class `ResumeEvidence`

Résumé -> facts + evidence. Never a decision about a person.

- `__init__(config)`
- `health_check()`
- `parse_resume(caller, candidate_id, filename, text, content_base64)` — Parse a résumé (plain text, or a file as base64: pdf/docx/txt) into facts with source passages and store them for
- `match_requisition(caller, evidence_id, requisition_id)` — Evidence and gaps of one parsed résumé against a requisition's must/nice skills, with the arithmetic. No decision,
- `get_evidence(caller, evidence_id)` — The stored facts of one résumé (identity data: authorize_read).
- `unknown_skills(caller)` — Skill-list phrases seen in résumés that the table does not know, most frequent first (phrases only, no people).
- `alias_proposals(caller, status)`
- `propose_alias(caller, surface, skill_id, new_skill)` — Queue a phrase for review: map it to an existing skill_id, or name a new skill. It is not used until reviewed.
- `review_alias(caller, proposal_id, approve, esco_id, no_esco_match)` — HR admin approves or rejects a proposal (not their own). Approving needs an ESCO skill URI/UUID from an ESCO release
- `list_skills(caller)`
- `bias_audit(caller, records, stages, min_count)` — Four-fifths impact ratios per funnel step for group labels the caller supplies (not stored). An audit aid.

## Depends on

- `velaris.agentkit`
- `velaris.agentkit.hiring_common`
- `velaris.agentkit.results`
- `velaris.core.access`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `SCREENING_FORMS`
- **platform modules:** `velaris/agentkit/hiring_common.py`, `velaris/agentkit/hiring_resume.py`, `velaris/agentkit/hiring_skills.py`, `velaris/api/allowlist.py`
- **tests:** `velaris/tests/test_hiring_api.py`, `velaris/tests/test_hiring_resume.py`
