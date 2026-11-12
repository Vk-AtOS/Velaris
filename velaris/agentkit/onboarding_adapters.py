"""The seams between the paperwork agents and things that may not exist yet or that need a real-world account.

Each is a small typing.Protocol. An agent takes an implementation in its config dict (`config["ats"]`,
`config["sender"]`, `config["pdf_signer"]`); without one it reports `not_configured` for that step and does not
pretend. Tests pass fakes.

AtsAdapter    the applicant tracking agent (ATS_CORE, built by another worker). Only these two public calls are
              assumed. `get_candidate` returns None for an unknown application or one of another organisation:
                  {"application_id", "name", "email", "phone"?, "role_title"?, "department"?,
                   "consent": {"purpose", "notice_version", "given_at", "retention_until"} | None}
MessageSender delivers one message (offer-letter email, signing link, OTP, reminder) and returns True when the
              transport accepted it. Velaris sends nothing itself: no mail account, no SMS gateway is assumed.
OfferStatus   OFFER_LETTERS (or anything that can answer): `get_offer_status(offer_id, org)` -> "accepted" | other | None.
              ONBOARDING_FLOW refuses to start from an offer that is not accepted when one is configured.
PolicyAckView read-only view of POLICY_ACKS evidence: `ack_evidence(org, employee_id, policy_key)` ->
                  {"current_version": int | None, "acks": [{"employee_id", "policy_key", "version", "evidence_sha256"}]}.
              ONBOARDING_FLOW completes a policy_ack task only on a matching, current acknowledgement; no view = refuse.
EsignView     read-only view of ESIGN: `request_info(request_id, org)` -> {"status", "document_ref"} | None.
              OFFER_LETTERS calls a response "esign_evidence" only when the referenced request is sealed for that offer.
PdfSigner     puts the PLATFORM certificate's signature into a PDF (PAdES). See onboarding_esign.py for how
              pyHanko or an Aadhaar eSign hash-out plugs in.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Protocol


class AtsAdapter(Protocol):
    def get_candidate(self, application_id: str, org: str) -> Optional[Dict[str, Any]]: ...

    def record_offer_outcome(self, application_id: str, org: str, outcome: str, offer_id: str) -> bool: ...


class MessageSender(Protocol):
    def send(self, to: str, subject: str, body: str) -> bool: ...


class PdfSigner(Protocol):
    def sign_pdf(self, pdf: bytes, evidence_digest: str) -> bytes: ...


class OfferStatus(Protocol):
    def get_offer_status(self, offer_id: str, org: str) -> Optional[str]: ...


class PolicyAckView(Protocol):
    def ack_evidence(self, org: str, employee_id: str, policy_key: str) -> Optional[Dict[str, Any]]: ...


class EsignView(Protocol):
    def request_info(self, request_id: str, org: str) -> Optional[Dict[str, Any]]: ...


class PolicyAcksReader:
    """The real PolicyAckView: POLICY_ACKS's public `ack_evidence` (its own store, no second copy)."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        from velaris.agents.POLICY_ACKS.main import PolicyAcks      # late: the agent packages import this module
        self._agent = PolicyAcks(config)

    def ack_evidence(self, org: str, employee_id: str, policy_key: str) -> Optional[Dict[str, Any]]:
        return self._agent.ack_evidence(org, employee_id, policy_key)


class EsignReader:
    """The real EsignView: ESIGN's public `request_info`."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        from velaris.agents.ESIGN.main import Esign                # late: the agent packages import this module
        self._agent = Esign(config)

    def request_info(self, request_id: str, org: str) -> Optional[Dict[str, Any]]:
        return self._agent.request_info(request_id, org)
