# ================================================================================

"""HUMAN_APPROVAL_WORKFLOW: an in-memory approval request book.

Who asks and who approves is the current caller (velaris.core.access), never the
argument: the stored requester and approver are the caller's id. request_approval()
returns "" and approve()/reject() return False when there is no caller, when the
requester/approver argument is missing, empty or names someone other than the caller,
or when the caller would decide their own request.
"""
import copy
import logging
import uuid
from typing import Dict, Optional

from velaris.agentkit.checks import ident
from velaris.core.access import check_caller
from velaris.intel import approvals

NAME = "HUMAN_APPROVAL_WORKFLOW"
logger = logging.getLogger(NAME)


class HumanApproval:
    def __init__(self):
        self.requests: Dict[str, Dict] = {}

    def request_approval(self, requester: str, action: str, meta: dict) -> str:
        if ident(requester) is None:
            return ""
        caller, refused = check_caller(NAME, "request", {"action": str(action)[:128]}, claimed=requester)
        if refused:
            return ""
        req_id = str(uuid.uuid4())
        if not self._audit("requested", req_id, caller.id, "needs_approval", {"action": action, "requester": caller.id}):
            return ""
        self.requests[req_id] = {
            "requester": caller.id,
            "action": action,
            "meta": meta,
            "status": "PENDING"
        }
        return req_id

    @staticmethod
    def _audit(event: str, req_id: str, by: str, decision: str, subject, note: str = "") -> bool:
        """The shared approval trail (velaris.intel.approvals); False when it cannot be written (fail closed)."""
        try:
            approvals.audit("HUMAN_APPROVAL_WORKFLOW", event, request_id=req_id, subject=subject, by=by, decision=decision, note=note)
            return True
        except (OSError, ValueError, TypeError) as e:
            logger.warning("HUMAN_APPROVAL_WORKFLOW: %s of %s not recorded: %s", event, req_id, e)
            return False

    def _decider(self, req_id: str, approver: str) -> Optional[str]:
        """The caller's id if they may decide this pending request, else None."""
        req = self.requests.get(req_id) if isinstance(req_id, str) else None
        if req is None or ident(approver) is None:
            return None
        caller, refused = check_caller(NAME, "decide", {"id": req_id[:64]}, claimed=approver)
        if refused or caller.id == req["requester"] or req["status"] != "PENDING":
            return None
        return caller.id

    def approve(self, req_id: str, approver: str) -> bool:
        who = self._decider(req_id, approver)
        if who is None:
            return False
        if not self._audit("decided", req_id, who, "approve", self.requests[req_id]["action"]):
            return False             # an approval that cannot be recorded does not happen
        self.requests[req_id].update(status="APPROVED", approver=who)
        return True

    def reject(self, req_id: str, approver: str, reason: str) -> bool:
        who = self._decider(req_id, approver)
        if who is None:
            return False
        if not self._audit("decided", req_id, who, "reject", self.requests[req_id]["action"], str(reason)):
            return False
        self.requests[req_id].update(status="REJECTED", approver=who, reason=reason)
        return True

    def status(self, req_id: str) -> Optional[Dict]:
        """A copy of the request: editing it cannot change the stored status."""
        return copy.deepcopy(self.requests.get(req_id))

# ================================================================================