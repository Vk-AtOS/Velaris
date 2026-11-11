# ================================================================================

import uuid
from typing import Dict, Optional

class HumanApproval:
    def __init__(self):
        self.requests: Dict[str, Dict] = {}

    def request_approval(self, requester: str, action: str, meta: dict) -> str:
        req_id = str(uuid.uuid4())
        self.requests[req_id] = {
            "requester": requester,
            "action": action,
            "meta": meta,
            "status": "PENDING"
        }
        return req_id

    def approve(self, req_id: str, approver: str) -> bool:
        if req_id not in self.requests:
            return False
        if self.requests[req_id]["status"] != "PENDING":
            return False
        self.requests[req_id]["status"] = "APPROVED"
        self.requests[req_id]["approver"] = approver
        return True

    def reject(self, req_id: str, approver: str, reason: str) -> bool:
        if req_id not in self.requests:
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