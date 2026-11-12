# ================================================================================

"""HUMAN_APPROVAL_WORKFLOW: an in-memory approval request book.

Who asks and who approves is the current caller (velaris.core.access), never the
argument: request_approval() returns "" and approve()/reject() return False when there
is no caller, when the named requester/approver is not the caller, or when the caller
would approve their own request.
"""
import uuid
from typing import Dict, Optional

from velaris.core.access import check_caller

NAME = "HUMAN_APPROVAL_WORKFLOW"

class HumanApproval:
    def __init__(self):
        self.requests: Dict[str, Dict] = {}

    def request_approval(self, requester: str, action: str, meta: dict) -> str:
        _, refused = check_caller(NAME, "request", {"action": str(action)[:128]}, claimed=requester)
        if refused:
            return ""
        req_id = str(uuid.uuid4())
        self.requests[req_id] = {
            "requester": requester,
            "action": action,
            "meta": meta,
            "status": "PENDING"
        }
        return req_id

    def _may_decide(self, req_id: str, approver: str) -> bool:
        req = self.requests.get(req_id)
        if req is None:
            return False
        caller, refused = check_caller(NAME, "decide", {"id": str(req_id)[:64]}, claimed=approver)
        return refused is None and caller.id != req["requester"]

    def approve(self, req_id: str, approver: str) -> bool:
        if not self._may_decide(req_id, approver):
            return False
        if self.requests[req_id]["status"] != "PENDING":
            return False
        self.requests[req_id]["status"] = "APPROVED"
        self.requests[req_id]["approver"] = approver
        return True

    def reject(self, req_id: str, approver: str, reason: str) -> bool:
        if not self._may_decide(req_id, approver):
            return False
        if self.requests[req_id]["status"] != "PENDING":
            return False
        self.requests[req_id]["status"] = "REJECTED"
        self.requests[req_id]["approver"] = approver
        self.requests[req_id]["reason"] = reason
        return True

    def status(self, req_id: str) -> Optional[Dict]:
        return self.requests.get(req_id)

# ================================================================================