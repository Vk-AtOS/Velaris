"""DOMAIN_MASTERY: how the company actually performs in each sales vertical.

"Mastery" is measured, not claimed: from the deal records supplied, per vertical,
  win rate = won / (won + lost), won revenue and its share, average won deal,
  median days from open to close of won deals.
A vertical counts as `established` only with at least `min_closed` closed deals;
below that its rates are shown but marked as too small a sample to rely on.
"""
import logging
from typing import Any, Dict

from velaris.agentkit import biz_common as kit
from velaris.agentkit import biz_sales

logger = logging.getLogger("DOMAIN_MASTERY")


class DOMAIN_MASTERYAgent:
    def __init__(self):
        self.name = "DOMAIN_MASTERY"

    def health_check(self):
        return kit.health("DOMAIN_MASTERY")

    def assess(self, deals: Any, min_closed: int = 5) -> Dict[str, Any]:
        if isinstance(min_closed, bool) or not isinstance(min_closed, int) or min_closed < 1:
            return kit.failed(["min_closed must be a whole number of at least 1"])
        parsed, errors = biz_sales.parse_deals(deals)
        if errors:
            return kit.failed(errors)
        if not parsed:
            return kit.needs_data("no deal records supplied", verticals=[])
        rows = biz_sales.public(biz_sales.vertical_stats(parsed))
        for r in rows:
            r["closed"] = r["won"] + r["lost"]
            r["established"] = r["closed"] >= min_closed
            r["sample_too_small"] = not r["established"]
        return {"status": "ok", "verticals": rows, "min_closed": min_closed,
                "established": [r["vertical"] for r in rows if r["established"]],
                "method": "win rate = won / (won + lost); verticals ordered by won revenue"}
