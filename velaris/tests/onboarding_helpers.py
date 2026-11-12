"""Shared fixtures for the onboarding tests: callers, a movable clock, a fake sender and fakes for the adapters."""
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from velaris.core.access import Caller

ORG = "acme"
HR1 = Caller("hr1", ORG, frozenset({"hr_admin"}))
HR2 = Caller("hr2", ORG, frozenset({"hr_admin"}))
MGR = Caller("mgr1", ORG, frozenset())
PAYROLL = Caller("pay1", ORG, frozenset({"payroll_admin"}))
OTHER_ORG_HR = Caller("hrx", "globex", frozenset({"hr_admin"}))


def person(emp_id: str, user: Optional[str] = None) -> Caller:
    return Caller(user or f"u-{emp_id}", ORG, frozenset(), emp_id)


class Clock:
    def __init__(self, start: str = "2026-11-13T09:00:00") -> None:
        self.now = datetime.fromisoformat(start).replace(tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kw: Any) -> None:
        self.now += timedelta(**kw)


class FakeSender:
    """Stands for the signers' mailboxes: the only place a signing token can be read."""

    def __init__(self, accept: bool = True) -> None:
        self.messages: List[Dict[str, str]] = []
        self.accept = accept

    def send(self, to: str, subject: str, body: str) -> bool:
        self.messages.append({"to": to, "subject": subject, "body": body})
        return self.accept

    def token_for(self, email: str) -> str:
        msg = [m for m in self.messages if m["to"] == email and "signing code" in m["body"]][-1]
        return re.search(r"signing code[^:]*: (\S+)", msg["body"]).group(1)

    def otp_for(self, to: str) -> str:
        msg = [m for m in self.messages if m["to"] == to and "one-time code is" in m["body"]][-1]
        return re.search(r"is (\d{6})", msg["body"]).group(1)


class FakeAts:
    def __init__(self, candidates: Dict[str, Dict[str, Any]]) -> None:
        self.candidates, self.outcomes = candidates, []

    def get_candidate(self, application_id: str, org: str) -> Optional[Dict[str, Any]]:
        c = self.candidates.get(application_id)
        return c if c and c.get("org", org) == org else None

    def record_offer_outcome(self, application_id: str, org: str, outcome: str, offer_id: str) -> bool:
        self.outcomes.append((application_id, outcome, offer_id))
        return True


class FakeOffers:
    def __init__(self, status: Optional[str]) -> None:
        self.status = status

    def get_offer_status(self, offer_id: str, org: str) -> Optional[str]:
        return self.status


CANDIDATE = {"name": "Asha Raman", "email": "asha@example.in", "phone": "9000000000", "org": ORG,
             "consent": {"purpose": "recruitment", "notice_version": "n1", "given_at": "2026-10-01T00:00:00Z", "retention_until": "2027-04-01"}}


class FakePolicyAcks:
    """A PolicyAckView: `acks` is a list of (employee_id, policy_key, version, evidence_sha256); `current` maps key -> version."""

    def __init__(self, current: Dict[str, int], acks: List[tuple]) -> None:
        self.current, self.acks = current, acks

    def ack_evidence(self, org: str, employee_id: str, policy_key: str) -> Optional[Dict[str, Any]]:
        return {"current_version": self.current.get(policy_key),
                "acks": [{"employee_id": e, "policy_key": k, "version": v, "evidence_sha256": h}
                         for e, k, v, h in self.acks if e == employee_id and k == policy_key]}


class FakeEsign:
    """An EsignView: `requests` maps request id -> {"status", "document_ref"}."""

    def __init__(self, requests: Dict[str, Dict[str, Any]]) -> None:
        self.requests = requests

    def request_info(self, request_id: str, org: str) -> Optional[Dict[str, Any]]:
        return self.requests.get(request_id)
