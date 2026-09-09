# ================================================================================

from dataclasses import dataclass
from typing import Dict, Any, List
import hashlib
import json

@dataclass
class BorrowerProfile:
    borrower_id: str
    income: float
    liabilities: float
    credit_history_years: int
    delinquency_count: int
    loan_amount: float
    loan_type: str

class CreditRiskEngine:
    SUPPORTED_LOAN_TYPES = {"personal","home","auto","business"}
    MAX_INCOME = 5_00_00_000
    MAX_LIAB = 5_00_00_000
    MAX_LOAN = 10_00_00_000
    MAX_DELINQ = 50
    MAX_HISTORY = 60

    def _h(self, s: str) -> int:
        return int(hashlib.sha256(s.encode()).hexdigest()[:14],16)

    def validate(self, b: BorrowerProfile) -> List[str]:
        e=[]
        if not b.borrower_id or len(b.borrower_id)>64:
            e.append("invalid borrower_id")
        if b.income<0 or b.income>self.MAX_INCOME:
            e.append("income out of range")
        if b.liabilities<0 or b.liabilities>self.MAX_LIAB:
            e.append("liabilities out of range")
        if b.loan_amount<0 or b.loan_amount>self.MAX_LOAN:
            e.append("loan_amount out of range")
        if b.credit_history_years<0 or b.credit_history_years>self.MAX_HISTORY:
            e.append("credit_history_years invalid")
        if b.delinquency_count<0 or b.delinquency_count>self.MAX_DELINQ:
            e.append("delinquency_count invalid")
        if b.loan_type not in self.SUPPORTED_LOAN_TYPES:
            e.append("unsupported loan_type")
        return e

    def compute_risk(self, b: BorrowerProfile) -> Dict[str,Any]:
        err=self.validate(b)
        if err:
            return {"status":"failed","errors":err}

        base = self._h(b.borrower_id) % 500

        dti = (b.liabilities / b.income)*100 if b.income>0 else 1000
        dti_score = min(500, dti*4)

        history_score = max(0, 300 - b.credit_history_years*5)
        delinquency_score = b.delinquency_count * 15
        loan_exposure = min(500, b.loan_amount/100000)

        raw = base + dti_score + history_score + delinquency_score + loan_exposure
        normalized = max(0, min(1000, raw))

        if normalized < 250:
            tier="low"
        elif normalized < 500:
            tier="moderate"
        elif normalized < 750:
            tier="high"
        else:
            tier="critical"

        return {
            "status":"ok",
            "borrower_id":b.borrower_id,
            "risk_score":normalized,
            "risk_tier":tier,
            "details":{
                "dti_score":dti_score,
                "history_score":history_score,
                "delinquency_score":delinquency_score,
                "loan_exposure":loan_exposure,
                "base_entropy":base
            }
        }

if __name__=="__main__":
    sample=BorrowerProfile(
        borrower_id="br-001",
        income=800000,
        liabilities=200000,
        credit_history_years=12,
        delinquency_count=1,
        loan_amount=500000,
        loan_type="personal"
    )
    eng=CreditRiskEngine()
    print(json.dumps(eng.compute_risk(sample),indent=2))

# ================================================================================