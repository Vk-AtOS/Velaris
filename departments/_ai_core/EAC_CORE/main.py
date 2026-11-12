"""EAC_CORE: one compliance assessment, end to end.

assess(subject, record) runs EAC_COMPLIANCE's controls over the record and
writes the outcome to the audit trail through EAC_AUDIT. If the outcome cannot
be recorded the assessment is reported as failed: there is no compliant result
without its audit entry. history(subject) reads past assessments back.
"""
from typing import Any, Dict, List, Optional

from velaris.agentkit.checks import ident
from velaris.agentkit.results import fail, health, invalid
from velaris.agents.EAC_AUDIT.main import EAC_AUDITAgent
from velaris.agents.EAC_COMPLIANCE.main import EAC_COMPLIANCEAgent

NAME = "EAC_CORE"


class EAC_COREAgent:
    def __init__(self):
        self.compliance = EAC_COMPLIANCEAgent()
        self.audit = EAC_AUDITAgent()

    def health_check(self):
        return health(NAME)

    def assess(self, subject: str, record: Any, controls: Optional[List[Dict[str, Any]]] = None,
               framework: Optional[str] = None) -> Dict[str, Any]:
        """Evaluate, record, return. `subject` names what was assessed (an invoice id, a vendor, ...)."""
        if ident(subject) is None:
            return invalid("subject must be a non-empty string", compliant=False)
        result = self.compliance.evaluate(record, controls, framework)
        logged = self.audit.record("assessment", {
            "subject": subject.strip(), "outcome": result["status"], "compliant": result["compliant"],
            "checked": result.get("checked", 0), "violations": [v["id"] for v in result.get("violations", [])],
        }, actor=NAME)
        if logged["status"] != "ok":
            return {**result, **fail("audit_failed", "the assessment could not be recorded, so it does not count"),
                    "compliant": False}
        return {**result, "subject": subject.strip(), "audit_hash": logged["hash"]}

    def history(self, subject: str, limit: int = 50) -> Dict[str, Any]:
        """Past assessments of one subject, oldest first."""
        found = self.audit.find(event="assessment", actor=NAME, limit=10_000)
        if found["status"] != "ok" or not isinstance(limit, int) or limit < 1:
            return invalid("limit must be a positive integer", assessments=[])
        mine = [{"ts": e["ts"], **e["payload"]} for e in found["events"] if e["payload"].get("subject") == subject]
        return {"status": "ok", "assessments": mine[-limit:]}
