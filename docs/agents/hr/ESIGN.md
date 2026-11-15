# ESIGN

- **Department:** `hr`
- **Status (static inventory):** `real`
- **Source:** `departments/hr/ESIGN/main.py` (544 lines)

## Purpose

ESIGN: signing requests with a ceremony, evidence per signer, a hash-chain seal and a verifier.

Read velaris/agentkit/onboarding_esign.py first: it says what the "signature" is (evidence of click-accept, NOT an
IT Act s.3A signature, needs a lawyer) and how a real PDF signature (pyHanko, Aadhaar eSign) would plug in.

The rule that matters most: NOTHING IS SIGNED WITHOUT THE SIGNER'S OWN TOKEN. At send time each signer gets a random
token by e-mail (through the injected MessageSender, or into an owner-only outbox file when none is configured). The
token is never returned by any method, never stored (only its SHA-256), and an administrator who creates, sends,
voids or seals a request has no way to read it. The signing methods take the token and the signer's e-mail and
ignore the current Caller entirely, so being an administrator gives no power to sign for anyone.

Ceremony per signer: sent -> viewed -> consented -> signed (or declined). Optional one-time code between viewed and
consented. A request is sealed when every signer has signed. Requests expire; reminders rotate the token (the old
link dies). All times come from an injectable clock.

## Class `Esign`

Signing requests: create, send, ceremony (token-authenticated), seal, verify. See the module docstring.

- `__init__(config)`
- `health_check()`
- `create_request(title, document_base64, signers, valid_days, document_ref)` — Register a document for signing (HR administrators). signers: [{"name","email","role"?,"otp_required"?,"phone"?}].
- `send_request(request_id)` — Issue each signer's personal token and deliver it. Tokens are not returned to you; they go to the signers.
- `send_reminders()` — Re-send to signers who have not finished (HR administrators). Each reminder issues a NEW token; the old link dies.
- `process_due()` — Expire requests whose time has passed (HR administrators). Their tokens stop working.
- `void_request(request_id, reason)` — Cancel a request that is not yet sealed (its drafter or an HR administrator). Sealed documents are never voided.
- `open_signing(token, email, ip, user_agent)` — The signer opens the request: records "viewed" and shows the document hash and the consent text.
- `request_otp(token, email, ip, user_agent)` — Draft a one-time code to the signer's phone (or e-mail). Delivery is through the injected sender or the outbox.
- `verify_otp(token, email, code, ip, user_agent)` — Check the one-time code. Five wrong tries lock the code.
- `give_consent(token, email, ip, user_agent, consent_text_version)` — The signer accepts the consent text (by its version). Needs the one-time code first when the signer uses one.
- `sign_document(token, email, typed_name, ip, user_agent)` — The signer states their intent by typing their name. Builds the evidence record; the last signer triggers the seal.
- `decline_signing(token, email, reason, ip, user_agent)` — The signer declines; the whole request is closed as declined and no other token works.
- `seal_request(request_id)` — Retry sealing a request that completed but could not be sealed (HR administrators).
- `verify(request_id)` — Recompute the document hash, every evidence hash, the seal chain, the sealed PDF and the trace anchor.
- `request_info(request_id, org)` — Status, document_ref, the document's SHA-256 and a SHA-256 of each signer's e-mail, for another agent (OFFER_LETTERS) that
- `dsr_export(org, subject_id, links)`
- `dsr_erase(org, subject_id, on, links)` — Anonymise the subject's signer data on requests that were never sealed; sealed evidence is held as the registry says.
- `get_request(request_id)` — Status of a request (its drafter and HR administrators). No tokens are ever included.
- `list_requests(status)`
- `get_sealed_document(request_id)` — The sealed PDF (base64) of a sealed request, and the platform-signed one when a signer was configured.

## Depends on

- `velaris.agentkit`
- `velaris.agentkit.onboarding_common`
- `velaris.agentkit.results`
- `velaris.agentkit.state`
- `velaris.core.access`
- `velaris.intel`
- `velaris.intel.paths`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** `EMPLOYEE_RECORDS`, `OFFER_LETTERS`
- **platform modules:** `velaris/agentkit/hr_wiring.py`, `velaris/agentkit/onboarding_adapters.py`, `velaris/agentkit/onboarding_common.py`, `velaris/agentkit/onboarding_dsr.py`, `velaris/api/allowlist.py`, `velaris/api/public.py`
- **tests:** `velaris/tests/test_api_public.py`, `velaris/tests/test_hr_data_traces.py`, `velaris/tests/test_hr_wiring.py`, `velaris/tests/test_onboarding_esign.py`, `velaris/tests/test_onboarding_records.py`
