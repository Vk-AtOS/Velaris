"""Composition root for the HR paperwork agents: builds the real collaborators the agents take through their config.

The agents (ONBOARDING_FLOW, OFFER_LETTERS, EMPLOYEE_RECORDS, ESIGN) refuse, fail closed, when a collaborator is absent:
no `policy_acks` means a policy task cannot complete, no `esign` means an offer response cannot cite evidence, no `ats`
means a conversion takes unverified name and e-mail. Nothing used to construct them. This module does:

    from velaris.agentkit.hr_wiring import hr_config
    cfg = hr_config("OFFER_LETTERS")          # {"ats": AtsReader, "esign": EsignReader, "sender": MailDraftSender?}

BackendEngine.run() calls hr_config(agent) when the caller passes no config of its own (an explicit config is used as given,
nothing is merged: tests and special deployments keep full control). Agents not listed here get {} as before.

What each adapter is, and what it never does
  PolicyAcksReader   POLICY_ACKS.ack_evidence      (velaris.agentkit.onboarding_adapters)
  EsignReader        ESIGN.request_info            (same)
  OffersReader       OFFER_LETTERS.get_offer_status
  AtsReader          ATS_CORE.candidate_summary / record_offer_outcome, called as the current Caller: ATS_CORE's own role
                     checks and access category "candidate" decide, so a caller who may not read a candidate gets None
  MailDraftSender    a MessageSender that only DRAFTS through velaris.mail.drafts into one mailbox the current Caller may send
                     from (VELARIS_HR_MAILBOX_ID). It never sends; a person sends the draft. Absent mailbox: no sender.
Every adapter answers only for the organisation of the current Caller (identity and organisation flow through unchanged
from acting_as(); no caller or another organisation: None / False). Adapters never cache and never hold credentials.

Deliberately not wired
  pdf_signer   needs a real certificate; left unset, ESIGN reports platform_signature "not_configured".
  ESIGN sender signing links and one-time codes must not sit in a mailbox draft and be reported "sent": ESIGN keeps using its
               owner-only outbox until a real transport exists (config["sender"] given explicitly).
  participants EMPLOYEE_RECORDS builds its own (ONBOARDING_FLOW, POLICY_ACKS) from the config it is given, which now carries
               the views above.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Callable, Dict, Mapping, Optional

from velaris.agentkit.onboarding_adapters import EsignReader, PolicyAcksReader, own_org
from velaris.agents.ATS_CORE.main import AtsCore
from velaris.agents.OFFER_LETTERS.main import OfferLetters
from velaris.core.access import current_caller
from velaris.mail.common import MailError
from velaris.mail.drafts import create_assistant_draft
from velaris.mail.store import MailStore

logger = logging.getLogger("velaris.hr_wiring")
MAILBOX_ENV = "VELARIS_HR_MAILBOX_ID"


class AtsReader:
    """AtsAdapter over ATS_CORE. Runs ATS_CORE's own gated methods as the current Caller."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self._ats = AtsCore(config)

    def get_candidate(self, application_id: str, org: str) -> Optional[Dict[str, Any]]:
        if not own_org(org):
            return None
        out = self._ats.candidate_summary(application_id=str(application_id))
        if out.get("status") != "ok":
            return None                          # unknown, erased, consent gone, or the caller may not read candidates
        return {k: out[k] for k in ("application_id", "name", "email", "phone", "role_title", "department", "consent")}

    def record_offer_outcome(self, application_id: str, org: str, outcome: str, offer_id: str) -> bool:
        if not own_org(org):
            return False
        out = self._ats.record_offer_outcome(application_id=str(application_id), outcome=outcome, offer_id=str(offer_id))
        return out.get("status") == "ok"


class OffersReader:
    """OfferStatus over OFFER_LETTERS."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self._offers = OfferLetters(config)

    def get_offer_status(self, offer_id: str, org: str) -> Optional[str]:
        return self._offers.get_offer_status(offer_id, org) if own_org(org) else None


class MailDraftSender:
    """MessageSender that drafts. `send` returns True when a draft was created in the mailbox, which is NOT delivery:
    `drafts_only` tells OFFER_LETTERS to record the offer as released by draft and to say so."""

    drafts_only = True

    def __init__(self, store: MailStore, mailbox_id: str) -> None:
        self._store, self._mailbox = store, mailbox_id

    def send(self, to: str, subject: str, body: str) -> bool:
        who = current_caller()
        if who is None:
            return False
        try:
            create_assistant_draft(self._store, who, self._mailbox, to=[to], subject=subject, text=body)
        except MailError as e:                   # not allowed to send from that mailbox, no such mailbox, audit down ...
            logger.warning("mail draft refused: %s", e.code)
            return False
        return True


def _mail_sender(environ: Mapping[str, str], store: Optional[MailStore]) -> Optional[MailDraftSender]:
    mailbox = environ.get(MAILBOX_ENV, "").strip()
    if not mailbox:
        return None
    return MailDraftSender(store if store is not None else MailStore(), mailbox)


# agent -> collaborator name -> how to build it. A builder gets the base config.
_WIRING: Dict[str, Dict[str, Callable[[Dict[str, Any]], Any]]] = {
    "ONBOARDING_FLOW": {"policy_acks": PolicyAcksReader, "offers": OffersReader},
    "EMPLOYEE_RECORDS": {"ats": AtsReader, "offers": OffersReader, "policy_acks": PolicyAcksReader},
    "OFFER_LETTERS": {"ats": AtsReader, "esign": EsignReader},
}


def hr_config(agent: str, base: Optional[Dict[str, Any]] = None, *, environ: Optional[Mapping[str, str]] = None,
              mail_store: Optional[MailStore] = None) -> Dict[str, Any]:
    """`base` plus the collaborators `agent` takes. Entries already in `base` are kept as given (a test's fake wins)."""
    cfg = dict(base or {})
    for name, build in _WIRING.get(agent, {}).items():
        if cfg.get(name) is None:
            cfg[name] = build(cfg)
    if agent == "OFFER_LETTERS" and cfg.get("sender") is None:
        sender = _mail_sender(os.environ if environ is None else environ, mail_store)
        if sender is not None:
            cfg["sender"] = sender
    return cfg

