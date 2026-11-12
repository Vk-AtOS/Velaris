"""CUSTOMER_BEHAVIOR_ENGINE: descriptive metrics and a rule-based segment for one customer account.

  annual value          = purchases per year x average order value x (1 - return rate %)   (decimal)
  complaints per order  = complaints / purchases per year

The segment is decided by the first rule in SEGMENT_RULES that applies, and the
result names that rule and the reading behind it:

  S1 inactive     no purchases in the year
  S2 at_risk      churn_risk flag set, or complaints per order >= 0.2, or engagement below 20
  S3 high_value   annual value >= high_value_threshold (only when the caller supplies one)
  S4 regular      none of the above

The thresholds are this engine's defaults and can be overridden. Behaviour flags
are reported as declared; they carry no weights. The segment describes an
account for marketing follow-up. It is not a score and not a decision about a person.
"""
import logging
from dataclasses import dataclass
from typing import Any, Dict, List

from velaris.agentkit import biz_common as kit

logger = logging.getLogger("CUSTOMER_BEHAVIOR_ENGINE")

SEGMENT_RULES = {
    "S1": "inactive: no purchases in the year",
    "S2": "at_risk: churn_risk flag, complaints per order at or above the limit, or engagement below the floor",
    "S3": "high_value: annual value at or above the supplied threshold",
    "S4": "regular: no other rule applies",
}
COMPLAINTS_PER_ORDER_LIMIT = 0.2
ENGAGEMENT_FLOOR = 20


@dataclass
class CustomerBehaviorInput:
    customer_id: str
    purchase_freq: float          # purchases per year
    avg_order_value: float
    return_rate: float            # % of order value returned
    complaints: int               # in the same year
    engagement_score: float       # 0-100, as measured by the caller
    behavior_flags: Dict[str, bool]


class CustomerBehaviorEngine:
    MAX_FREQ = 1000
    MAX_ORDER = 100000
    MAX_RETURN = 100
    MAX_COMPLAINTS = 10000
    MAX_ENG = 100
    FLAG_WEIGHT = {"discount_seeker": 0, "loyal": 0, "churn_risk": 0, "premium_affinity": 0,
                   "inconsistent_activity": 0}       # recognised flags (weights no longer used)

    def health_check(self) -> Dict[str, Any]:
        return kit.health("CUSTOMER_BEHAVIOR_ENGINE")

    def validate(self, c: CustomerBehaviorInput) -> List[str]:
        e = kit.dataclass_errors(c, ["purchase_freq", "avg_order_value", "return_rate", "complaints",
                                     "engagement_score"], ["behavior_flags"])
        if kit.ident(getattr(c, "customer_id", None), 64) is None:
            e.append("customer_id invalid")
        if e:
            return e
        if c.purchase_freq < 0 or c.purchase_freq > self.MAX_FREQ:
            e.append("purchase_freq invalid")
        if c.avg_order_value < 0 or c.avg_order_value > self.MAX_ORDER:
            e.append("avg_order_value invalid")
        if c.return_rate < 0 or c.return_rate > self.MAX_RETURN:
            e.append("return_rate invalid")
        if c.complaints < 0 or c.complaints > self.MAX_COMPLAINTS:
            e.append("complaints invalid")
        if c.engagement_score < 0 or c.engagement_score > self.MAX_ENG:
            e.append("engagement_score invalid")
        e += [f"unsupported flag {k}" for k in c.behavior_flags if k not in self.FLAG_WEIGHT]
        return e

    def analyze(self, c: CustomerBehaviorInput, high_value_threshold: Any = None) -> Dict[str, Any]:
        err = self.validate(c)
        threshold = None if high_value_threshold is None else kit.money(high_value_threshold)
        if high_value_threshold is not None and (threshold is None or threshold <= 0):
            err.append("high_value_threshold must be a positive amount")
        if err:
            return kit.failed(err)
        value = kit.paise(kit.money(c.purchase_freq) * kit.money(c.avg_order_value)
                          * (100 - kit.money(c.return_rate)) / 100)
        per_order = c.complaints / c.purchase_freq if c.purchase_freq else None
        if c.purchase_freq == 0:
            rule, why = "S1", "purchase_freq is 0"
        elif c.behavior_flags.get("churn_risk"):
            rule, why = "S2", "churn_risk flag is set"
        elif per_order >= COMPLAINTS_PER_ORDER_LIMIT:
            rule, why = "S2", f"{per_order:.2f} complaints per order (limit {COMPLAINTS_PER_ORDER_LIMIT})"
        elif c.engagement_score < ENGAGEMENT_FLOOR:
            rule, why = "S2", f"engagement {c.engagement_score} below {ENGAGEMENT_FLOOR}"
        elif threshold is not None and value >= threshold:
            rule, why = "S3", f"annual value {kit.inr(value)} >= {kit.inr(threshold)}"
        else:
            rule, why = "S4", "no other rule applies"
        return {
            "status": "ok", "customer_id": c.customer_id, "segment": SEGMENT_RULES[rule].split(":")[0],
            "deciding_rule": rule, "deciding_reason": why, "annual_value": kit.inr(value),
            "complaints_per_order": round(per_order, 4) if per_order is not None else None,
            "flags_declared": sorted(k for k, on in c.behavior_flags.items() if on),
            "rules": SEGMENT_RULES, "high_value_rule_evaluated": threshold is not None,
            "thresholds": {"complaints_per_order": COMPLAINTS_PER_ORDER_LIMIT, "engagement_floor": ENGAGEMENT_FLOOR,
                           "high_value": kit.inr(threshold) if threshold is not None else None},
            "note": "A description of the account for follow-up, not a score or a decision about a person.",
        }
