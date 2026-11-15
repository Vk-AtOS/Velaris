# OFFER_LETTERS

- **Department:** `hr`
- **Status (static inventory):** `real`
- **Source:** `departments/hr/OFFER_LETTERS/main.py` (471 lines)

## Purpose

OFFER_LETTERS: generate, approve, version, send, expire and record the outcome of an offer letter.

Rules enforced in code (nothing here is decided by a model):
  * templates are rendered by a whitelisting engine: only known {placeholders}, no code (onboarding_template);
  * the compensation figures come from CTC arithmetic plus PAYROLL_ENGINE's dated registry, read only; any
    unverified or missing statutory value makes the offer `needs_review`, and approving such an offer needs an
    explicit acknowledgement from the approver;
  * approval chain: the named hiring manager, then a named HR administrator. Nobody approves an offer they drafted,
    nobody approves twice, and a change to an offer starts the chain again;
  * identity is the Caller, never an argument; every record carries the organisation and reads filter on it;
  * nothing is sent by this agent: delivery goes through an injected MessageSender, and without one the result
    is `not_configured` with the drafted message.

LEGAL: recording that a candidate "accepted" is a record, not a signature. A click or a reply email can form a
contract (IT Act s.10A) but is not a secure electronic signature under s.3A. If you need the candidate's own
authenticated assent as evidence, send the PDF through ESIGN. Whether this wording, the stamp duty and the notice
terms are right for Tamil Nadu needs a lawyer.

## Class `OfferLetters`

Offer letters with a two-person approval chain. See the module docstring for the rules and the legal limits.

- `__init__(config)`
- `health_check()`
- `list_templates()` — The built-in template and this organisation's own, with the placeholders they may use.
- `add_template(name, body)` — Store a template after validating every placeholder against the whitelist (HR administrators only).
- `compensation_preview(annual_ctc, join_month, local_body, structure)` — The CTC breakdown with arithmetic, without making an offer. Pay data: HR or payroll administrators.
- `create_offer(candidate_name, candidate_email, role_title, department, location, join_date, annual_ctc, hiring_manager_id, hr_approver_id, manager_name, valid_days, probation_months, application_id, template_id, company_name, local_body, structure)` — Draft an offer (HR administrators). The drafter can approve neither step; the two approvers must differ.
- `revise_offer(offer_id, reason, annual_ctc, join_date, role_title, department, location, valid_days, probation_months, structure)` — Change an unsent offer: a new version, the old one kept in history, and the approval chain starts again.
- `submit_for_approval(offer_id)` — Send the current version to the first approver (HR administrators).
- `approve(offer_id, note, acknowledge_review)` — Approve the offer at your step. Only the named approver for the current step; nobody approves their own work.
- `reject(offer_id, note)` — Reject at your step; the drafter revises and resubmits.
- `get_offer_status(offer_id, org)` — An offer's status for another agent (ONBOARDING_FLOW, EMPLOYEE_RECORDS through hr_wiring); not an HTTP method.
- `send_offer(offer_id, delivered_manually)` — Release an approved offer. Delivery needs an injected sender; without one the message is returned as a draft
- `record_response(offer_id, response, evidence_ref, note)` — Record that the candidate accepted or declined (HR administrators). After expiry it is refused.
- `withdraw_offer(offer_id, reason)` — Withdraw an offer that has not been answered (HR administrators).
- `expire_due()` — Mark every sent offer whose expiry has passed as expired (HR administrators).
- `list_offers(status)` — Offers you drafted or must approve; HR administrators see all of the organisation's.
- `get_offer(offer_id)` — The whole offer including compensation. Named approvers and the drafter may read it; anyone else needs pay access.
- `render_offer(offer_id, fmt)` — The offer as "pdf" (base64 + sha256), "html" or "text". Same access rule as get_offer.
- `dsr_export(org, subject_id, links)`
- `dsr_erase(org, subject_id, on, links)` — Anonymise the subject's offers that never became a contract; hold the live or accepted ones as the registry says.

## Depends on

- `velaris.agentkit`
- `velaris.agentkit.onboarding_common`
- `velaris.agentkit.onboarding_offer_math`
- `velaris.agentkit.onboarding_pdf`
- `velaris.agentkit.results`
- `velaris.core.access`
- `velaris.intel`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `ATS_CORE`, `EMPLOYEE_RECORDS`, `ESIGN`
- **platform modules:** `velaris/agentkit/hr_wiring.py`, `velaris/agentkit/onboarding_adapters.py`, `velaris/agentkit/onboarding_common.py`, `velaris/agentkit/onboarding_dsr.py`, `velaris/api/allowlist.py`
- **tests:** `velaris/tests/test_hr_data_traces.py`, `velaris/tests/test_hr_wiring.py`, `velaris/tests/test_onboarding_offer.py`, `velaris/tests/test_onboarding_records.py`
