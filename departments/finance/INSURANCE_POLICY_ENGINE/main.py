"""INSURANCE_POLICY_ENGINE: underwriting clauses and premium from a supplied rate table.

Premium rates belong to an insurer's filed product, so the engine holds none.
The caller supplies the rate table:

    {"per_thousand": [{"max_age": 35, "rate": "1.80"}, {"max_age": 45, "rate": "3.10"}],
     "loadings_pct": {"smoker": 25},          # optional, % added to the base premium
     "max_income_multiple": 20}               # optional, sum assured <= multiple x income

  base premium  = sum assured / 1000 x annual rate of the first band with max_age >= age
  premium       = base x (1 + sum of loadings % / 100), in decimal, half-up to the paisa

Without a rate table the result is `needs_data`. Each underwriting clause is
reported; a declared health condition with no loading in the table refers the
case to an underwriter. The engine never declines anyone. GST on the premium is
not computed (`needs_review`): no verified rate is held in a dated registry.
"""
import json
import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, List, Optional

from velaris.agentkit import biz_common as kit

logger = logging.getLogger("INSURANCE_POLICY_ENGINE")

CLAUSES = {
    "U1": "Sum assured is within the product's multiple of annual income.",
    "U2": "Every declared health condition has a loading in the rate table.",
    "U3": "The rate table has a band for the applicant's age.",
}


@dataclass
class PolicyApplication:
    policy_id: str
    applicant_age: int
    applicant_income: float
    sum_assured: float
    policy_type: str
    tenure_years: int
    health_flags: Dict[str, bool]


def _rate_table_errors(t: Any) -> List[str]:
    if not isinstance(t, dict) or not isinstance(t.get("per_thousand"), (list, tuple)) or not t["per_thousand"]:
        return ["rate_table needs a non-empty 'per_thousand' list"]
    e = []
    for i, band in enumerate(t["per_thousand"]):
        rate = kit.money(band.get("rate")) if isinstance(band, dict) else None
        if rate is None or rate < 0 or kit.number(band.get("max_age"), 0, 150) is None:
            e.append(f"per_thousand[{i}] needs max_age and a non-negative rate")
    loadings = t.get("loadings_pct", {})
    if not isinstance(loadings, dict) or any(kit.number(v, 0, 1000) is None for v in loadings.values()):
        e.append("loadings_pct must map a condition to a percentage")
    if "max_income_multiple" in t and kit.number(t["max_income_multiple"], 0) is None:
        e.append("max_income_multiple must be a non-negative number")
    return e


class InsurancePolicyEngine:
    SUPPORTED_TYPES = {"term", "whole-life", "ulip", "health"}
    MIN_AGE = 18
    MAX_AGE = 75
    MIN_SUM = 100000
    MAX_SUM = 100000000
    MAX_TENURE = 40
    # kept as the list of recognised conditions; the numbers are no longer used
    HEALTH_WEIGHT = {"smoker": 70, "diabetic": 60, "cardiac": 90, "hypertension": 40}

    def health_check(self) -> Dict[str, Any]:
        return kit.health("INSURANCE_POLICY_ENGINE")

    def validate(self, p: PolicyApplication) -> List[str]:
        e = kit.dataclass_errors(p, ["applicant_age", "applicant_income", "sum_assured", "tenure_years"],
                                 ["health_flags"], texts=["policy_type"])
        if kit.text(getattr(p, "policy_id", None), 64) is None:
            e.append("policy_id invalid")
        if e:
            return e
        if p.policy_type not in self.SUPPORTED_TYPES:
            e.append("unsupported policy_type")
        if not self.MIN_AGE <= p.applicant_age <= self.MAX_AGE:
            e.append("age out of range")
        if p.applicant_income < 0:
            e.append("applicant_income invalid")
        if p.sum_assured < self.MIN_SUM or p.sum_assured > self.MAX_SUM:
            e.append("sum_assured out of range")
        if p.tenure_years <= 0 or p.tenure_years > self.MAX_TENURE:
            e.append("tenure_years invalid")
        e += [f"unsupported health flag {k}" for k in p.health_flags if k not in self.HEALTH_WEIGHT]
        return e

    def compute_premium(self, p: PolicyApplication, rate_table: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        err = self.validate(p)
        if rate_table is not None:
            err += _rate_table_errors(rate_table)
        if err:
            return kit.failed(err)
        if rate_table is None:
            return kit.needs_data("no rate_table supplied: premium rates are the insurer's, the engine holds none",
                                  policy_id=p.policy_id, premium=None)
        declared = sorted(k for k, v in p.health_flags.items() if v)
        loadings = {k: Decimal(str(rate_table.get("loadings_pct", {})[k])) for k in declared
                    if k in rate_table.get("loadings_pct", {})}
        unloaded = [k for k in declared if k not in loadings]
        band = next((b for b in sorted(rate_table["per_thousand"], key=lambda b: b["max_age"])
                     if b["max_age"] >= p.applicant_age), None)
        multiple = rate_table.get("max_income_multiple")
        sum_assured = kit.money(p.sum_assured)
        checks = {
            "U1": (None, "no max_income_multiple in the rate table") if multiple is None else
                  (sum_assured <= kit.money(p.applicant_income) * Decimal(str(multiple)),
                   f"sum assured {kit.inr(sum_assured)} vs {multiple} x income"),
            "U2": (not unloaded, f"no loading for: {', '.join(unloaded)}" if unloaded else "all declared conditions loaded"),
            "U3": (band is not None, f"band max_age {band['max_age']}" if band else f"no band covers age {p.applicant_age}"),
        }
        deciding = next((cid for cid in CLAUSES if checks[cid][0] is False), None)
        base = premium = None
        if band is not None:
            base = kit.paise(sum_assured / 1000 * kit.money(band["rate"]))
            premium = kit.paise(base * (100 + sum(loadings.values(), Decimal(0))) / 100)
        return {
            "status": "ok", "policy_id": p.policy_id,
            "outcome": "refer_to_underwriter" if deciding else "standard_terms",
            "deciding_clause": deciding, "deciding_reason": checks[deciding][1] if deciding else "all clauses passed",
            "clauses": [{"id": cid, "text": CLAUSES[cid], "passed": checks[cid][0], "detail": checks[cid][1]}
                        for cid in CLAUSES],
            "base_premium": kit.inr(base) if base is not None else None,
            "loadings_pct": {k: str(v) for k, v in loadings.items()},
            "annual_premium": kit.inr(premium) if premium is not None else None,
            "premium_is_indicative": deciding is not None,
            "rate_used": {"max_age": band["max_age"], "per_thousand": str(band["rate"])} if band else None,
            "gst": "needs_review", "gst_reason": "no verified GST rate for insurance premiums is held in a dated registry",
            "human_decision_required": deciding is not None,
        }


if __name__ == "__main__":
    sample = PolicyApplication("pol-001", 35, 800000, 5000000, "term", 20, {"smoker": False})
    table = {"per_thousand": [{"max_age": 35, "rate": "1.80"}, {"max_age": 75, "rate": "6.00"}]}
    print(json.dumps(InsurancePolicyEngine().compute_premium(sample, table), indent=2))
