"""CLAIMS_ASSESSMENT_ENGINE: explicit rule evaluation of an insurance claim.

Each clause in CLAUSES is evaluated in order and reported with its result; the
result names the clause that decided the routing. The engine computes the
payable amount (sum-insured cap, deductible, co-pay) in decimal and routes the
claim. It never rejects a claim: anything that is not straightforward goes to a
person (assessor or investigator) with the reason.

The clause table and REQUIRED_DOCS are this engine's defaults, not any insurer's
policy wording; pass the policy's own required documents and limits to assess().
"""
import json
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional

from velaris.agentkit import biz_common as kit

logger = logging.getLogger("CLAIMS_ASSESSMENT_ENGINE")

CLAUSES = {
    "C1": "Every document required for the policy type is on file.",
    "C2": "The claimant has no recorded past fraud.",
    "C3": "The policy's sum insured is known, so the payable amount can be computed.",
    "C4": "Severity is below the referral threshold and the payable amount is within the auto-settlement limit.",
}
REQUIRED_DOCS = {
    "health": ("medical_report", "bills", "id_proof"),
    "term": ("id_proof", "medical_report"),
    "whole-life": ("id_proof", "medical_report"),
    "ulip": ("id_proof", "medical_report"),
}
REFERRAL_SEVERITY = 8


@dataclass
class ClaimCase:
    claim_id: str
    policy_type: str
    claim_amount: float
    incident_severity: int
    documentation_flags: Dict[str, bool]
    claimant_history_flags: Dict[str, bool]


class ClaimsAssessmentEngine:
    SUPPORTED_TYPES = {"term", "whole-life", "ulip", "health"}
    MAX_CLAIM = 100000000
    MAX_SEVERITY = 10
    # kept as the lists of recognised flags; the numbers are no longer used as weights
    DOC_WEIGHTS = {"police_report": 50, "medical_report": 80, "id_proof": 30, "bills": 40}
    HISTORY_WEIGHTS = {"past_fraud": 200, "past_delay": 60, "multiple_small_claims": 80}

    def health_check(self) -> Dict[str, Any]:
        return kit.health("CLAIMS_ASSESSMENT_ENGINE")

    def validate(self, c: ClaimCase) -> List[str]:
        e = kit.dataclass_errors(c, ["claim_amount", "incident_severity"],
                                 ["documentation_flags", "claimant_history_flags"], texts=["policy_type"])
        if kit.ident(getattr(c, "claim_id", None), 64) is None:
            e.append("claim_id invalid")
        if e:
            return e
        if c.policy_type not in self.SUPPORTED_TYPES:
            e.append("unsupported policy_type")
        if c.claim_amount < 0 or c.claim_amount > self.MAX_CLAIM:
            e.append("claim_amount invalid")
        if c.incident_severity < 1 or c.incident_severity > self.MAX_SEVERITY:
            e.append("incident_severity invalid")
        e += [f"unsupported documentation flag {k}" for k in c.documentation_flags if k not in self.DOC_WEIGHTS]
        e += [f"unsupported history flag {k}" for k in c.claimant_history_flags if k not in self.HISTORY_WEIGHTS]
        return e

    def assess(self, c: ClaimCase, sum_insured: Any = None, deductible: Any = 0, copay_pct: Any = 0,
               auto_settle_limit: Any = None, required_docs: Optional[List[str]] = None) -> Dict[str, Any]:
        err = self.validate(c)
        cap = None if sum_insured is None else kit.money(sum_insured)
        ded, copay = kit.money(deductible), kit.number(copay_pct, 0, 100)
        limit = None if auto_settle_limit is None else kit.money(auto_settle_limit)
        if sum_insured is not None and (cap is None or cap < 0):
            err.append("sum_insured must be a non-negative amount")
        if ded is None or ded < 0:
            err.append("deductible must be a non-negative amount")
        if copay is None:
            err.append("copay_pct must be between 0 and 100")
        if auto_settle_limit is not None and (limit is None or limit < 0):
            err.append("auto_settle_limit must be a non-negative amount")
        if required_docs is not None and not (isinstance(required_docs, (list, tuple))
                                              and all(isinstance(d, str) and d in self.DOC_WEIGHTS for d in required_docs)):
            err.append("required_docs must be a list of recognised documents")
        if err:
            return kit.failed(err)

        needed = tuple(required_docs) if required_docs is not None else REQUIRED_DOCS[c.policy_type]
        missing = [d for d in needed if not c.documentation_flags.get(d)]
        claimed = kit.money(c.claim_amount)
        payable = None
        if cap is not None:
            payable = kit.paise(max(Decimal(0), min(claimed, cap) - ded) * (100 - Decimal(str(copay))) / 100)
        checks = {
            "C1": (not missing, f"missing: {', '.join(missing)}" if missing else "all on file"),
            "C2": (not c.claimant_history_flags.get("past_fraud"), "past_fraud flag is set"
                   if c.claimant_history_flags.get("past_fraud") else "no fraud flag"),
            "C3": (cap is not None, "sum insured supplied" if cap is not None else "sum_insured not supplied"),
        }
        if payable is None or limit is None:
            checks["C4"] = (False, "no auto-settlement limit supplied: every claim goes to an assessor"
                            if payable is not None else "payable amount unknown")
        elif c.incident_severity >= REFERRAL_SEVERITY:
            checks["C4"] = (False, f"severity {c.incident_severity} >= {REFERRAL_SEVERITY}")
        else:
            checks["C4"] = (payable <= limit, f"payable {kit.inr(payable)} vs limit {kit.inr(limit)}")
        routes = {"C1": "pend_for_documents", "C2": "refer_to_investigator",
                  "C3": "refer_to_assessor", "C4": "refer_to_assessor"}
        deciding = next((cid for cid in CLAUSES if not checks[cid][0]), None)
        return {
            "status": "ok", "claim_id": c.claim_id,
            "outcome": routes[deciding] if deciding else "eligible_for_settlement",
            "deciding_clause": deciding, "deciding_reason": checks[deciding][1] if deciding else "all clauses passed",
            "clauses": [{"id": cid, "text": CLAUSES[cid], "passed": checks[cid][0], "detail": checks[cid][1]}
                        for cid in CLAUSES],
            "claimed": kit.inr(claimed), "payable": kit.inr(payable) if payable is not None else None,
            "payable_method": "min(claimed, sum insured) - deductible, less co-pay %, never below zero",
            "missing_documents": missing, "human_decision_required": deciding is not None,
            "note": "The engine never rejects a claim; a person decides anything it does not clear.",
        }


if __name__ == "__main__":
    sample = ClaimCase("clm-001", "health", 300000, 5, {"medical_report": True, "bills": True}, {})
    print(json.dumps(ClaimsAssessmentEngine().assess(sample, sum_insured=250000), indent=2))
