"""CREDIT_RISK_ENGINE: a points scorecard over a borrower's declared figures.

Method: four characteristics are computed from the profile, each falls into one
bin of SCORECARD and earns that bin's points; the points add up to a 0-100 score
and a band. The whole table is returned with the result, so every point can be
traced. Two borrowers with the same figures always get the same score.

The scorecard is this engine's own, laid out like a published application
scorecard. It has NOT been fitted to default data and is not a bureau score. The
result is evidence for a credit officer: the engine makes no lending decision.
"""
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from velaris.agentkit import biz_common as kit

logger = logging.getLogger("CREDIT_RISK_ENGINE")

# characteristic -> (direction, [(bound, points)], points when beyond every bound)
# "max": first bin whose bound >= value.  "min": first bin whose bound <= value.
SCORECARD = {
    "debt_to_income": ("max", [(1.0, 40), (2.0, 30), (3.5, 20), (5.0, 10)], 0),
    "delinquency_count": ("max", [(0, 30), (1, 20), (2, 10)], 0),
    "credit_history_years": ("min", [(10, 20), (5, 15), (2, 8)], 0),
    "loan_to_income": ("max", [(0.5, 10), (1.0, 7), (3.0, 4)], 0),
}
BANDS = [(75, "low"), (50, "medium"), (0, "high")]   # score >= threshold -> risk band


def _points(name: str, value: Optional[float]) -> int:
    direction, bins, beyond = SCORECARD[name]
    if value is None:
        return beyond
    for bound, pts in bins:
        if (direction == "max" and value <= bound) or (direction == "min" and value >= bound):
            return pts
    return beyond


@dataclass
class BorrowerProfile:
    borrower_id: str
    income: float                 # annual
    liabilities: float            # outstanding debt before this loan
    credit_history_years: int
    delinquency_count: int
    loan_amount: float
    loan_type: str


class CreditRiskEngine:
    SUPPORTED_LOAN_TYPES = {"personal", "home", "auto", "business"}
    MAX_INCOME = 5_00_00_000
    MAX_LIAB = 5_00_00_000
    MAX_LOAN = 10_00_00_000
    MAX_DELINQ = 50
    MAX_HISTORY = 60

    def health_check(self) -> Dict[str, Any]:
        return kit.health("CREDIT_RISK_ENGINE")

    def validate(self, b: BorrowerProfile) -> List[str]:
        e = kit.dataclass_errors(b, ["income", "liabilities", "credit_history_years",
                                     "delinquency_count", "loan_amount"], texts=["loan_type"])
        if kit.text(getattr(b, "borrower_id", None), 64) is None:
            e.append("invalid borrower_id")
        if e:
            return e
        if b.income < 0 or b.income > self.MAX_INCOME:
            e.append("income out of range")
        if b.liabilities < 0 or b.liabilities > self.MAX_LIAB:
            e.append("liabilities out of range")
        if b.loan_amount < 0 or b.loan_amount > self.MAX_LOAN:
            e.append("loan_amount out of range")
        if b.credit_history_years < 0 or b.credit_history_years > self.MAX_HISTORY:
            e.append("credit_history_years invalid")
        if b.delinquency_count < 0 or b.delinquency_count > self.MAX_DELINQ:
            e.append("delinquency_count invalid")
        if b.loan_type not in self.SUPPORTED_LOAN_TYPES:
            e.append("unsupported loan_type")
        return e

    def compute_risk(self, b: BorrowerProfile) -> Dict[str, Any]:
        err = self.validate(b)
        if err:
            return kit.failed(err)
        notes = []
        if b.income > 0:
            dti = (b.liabilities + b.loan_amount) / b.income
            lti = b.loan_amount / b.income
        else:
            dti = lti = None
            notes.append("income is zero: income ratios are undefined and earn no points")
        values = {"debt_to_income": dti, "delinquency_count": b.delinquency_count,
                  "credit_history_years": b.credit_history_years, "loan_to_income": lti}
        breakdown = [{"characteristic": k, "value": None if v is None else round(v, 4),
                      "points": _points(k, v), "max_points": SCORECARD[k][1][0][1]} for k, v in values.items()]
        score = sum(row["points"] for row in breakdown)
        return {
            "status": "ok", "borrower_id": b.borrower_id, "score": score, "max_score": 100,
            "band": next(band for threshold, band in BANDS if score >= threshold),
            "breakdown": breakdown, "notes": notes,
            "scorecard": {k: {"direction": d, "bins": bins, "beyond": beyond}
                          for k, (d, bins, beyond) in SCORECARD.items()},
            "bands": BANDS,
            "method": "debt_to_income = (liabilities + loan) / annual income; loan_to_income = loan / annual "
                      "income; each characteristic earns the points of its bin; score is the sum",
            "decision": None, "human_decision_required": True,
            "caveat": "Illustrative scorecard, not fitted to default data and not a bureau score.",
        }


if __name__ == "__main__":
    sample = BorrowerProfile("br-001", 800000, 200000, 12, 1, 500000, "personal")
    print(json.dumps(CreditRiskEngine().compute_risk(sample), indent=2))
