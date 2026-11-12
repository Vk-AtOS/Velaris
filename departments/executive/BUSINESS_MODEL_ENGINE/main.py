"""BUSINESS_MODEL_ENGINE: revenue-model analysis of the revenue streams the caller supplies.

For streams [{"name", "kind": recurring | project | one_off, "revenue", "direct_cost",
"customer"?}] the engine computes, in decimal:

  share of revenue and gross margin per stream, and overall
  recurring share            = recurring revenue / total revenue
  customer concentration     = Herfindahl-Hirschman index, sum of (customer share %)^2,
                               0-10000 (10000 = one customer), and the largest customer's share

It describes the model as the numbers stand. It does not judge it or forecast.
"""
import logging
from decimal import Decimal
from typing import Any, Dict, List

from velaris.agentkit import biz_common as kit

logger = logging.getLogger("BUSINESS_MODEL_ENGINE")
KINDS = ("recurring", "project", "one_off")
MAX_STREAMS = 5000


def _share(part: Decimal, whole: Decimal) -> float:
    return round(float(part / whole), 4)


class BUSINESS_MODEL_ENGINEAgent:
    def __init__(self, name="BUSINESS_MODEL_ENGINE"):
        self.name = name

    def health_check(self):
        return kit.health(self.name)

    def analyze(self, streams: Any) -> Dict[str, Any]:
        if not isinstance(streams, (list, tuple)) or len(streams) > MAX_STREAMS:
            return kit.failed([f"streams must be a list of at most {MAX_STREAMS} records"])
        if not streams:
            return kit.needs_data("no revenue streams supplied")
        errors: List[str] = []
        rows = []
        for i, s in enumerate(streams):
            if not isinstance(s, dict):
                errors.append(f"streams[{i}] must be an object")
                continue
            name, revenue = kit.ident(s.get("name")), kit.money(s.get("revenue"))
            cost = kit.money(s.get("direct_cost", 0))
            customer = s.get("customer")
            if name is None:
                errors.append(f"streams[{i}].name must be a non-empty string")
            if s.get("kind") not in KINDS:
                errors.append(f"streams[{i}].kind must be one of {KINDS}")
            if revenue is None or revenue < 0:
                errors.append(f"streams[{i}].revenue must be a non-negative amount")
            if cost is None or cost < 0:
                errors.append(f"streams[{i}].direct_cost must be a non-negative amount")
            if customer is not None and kit.ident(customer) is None:
                errors.append(f"streams[{i}].customer must be a non-empty string when given")
            rows.append((name, s.get("kind"), revenue, cost, customer))
        if errors:
            return kit.failed(errors)
        total = sum((r[2] for r in rows), Decimal(0))
        if total == 0:
            return kit.needs_data("total revenue is zero: shares and margins are undefined")
        total_cost = sum((r[3] for r in rows), Decimal(0))
        by_kind = {k: sum((r[2] for r in rows if r[1] == k), Decimal(0)) for k in KINDS}
        by_customer: Dict[str, Decimal] = {}
        for _, _, revenue, _, customer in rows:
            if customer is not None:
                by_customer[customer.strip()] = by_customer.get(customer.strip(), Decimal(0)) + revenue
        attributed = sum(by_customer.values(), Decimal(0))
        concentration = None
        if attributed > 0:
            shares = {c: v / attributed for c, v in by_customer.items()}
            top = max(sorted(shares), key=lambda c: shares[c])
            concentration = {
                "hhi": round(float(sum((s * 100) ** 2 for s in shares.values())), 1),
                "top_customer": top, "top_customer_share": round(float(shares[top]), 4),
                "customers": len(shares), "revenue_attributed_share": _share(attributed, total),
            }
        return {
            "status": "ok", "total_revenue": kit.inr(total), "gross_profit": kit.inr(total - total_cost),
            "gross_margin": _share(total - total_cost, total),
            "recurring_share": _share(by_kind["recurring"], total),
            "revenue_by_kind": {k: kit.inr(v) for k, v in by_kind.items()},
            "streams": [{"name": n, "kind": k, "revenue": kit.inr(r), "share": _share(r, total),
                         "gross_margin": _share(r - c, r) if r else None} for n, k, r, c, _ in rows],
            "customer_concentration": concentration,
            "method": "shares of supplied revenue; HHI = sum of squared customer shares in percent (0-10000)",
        }
