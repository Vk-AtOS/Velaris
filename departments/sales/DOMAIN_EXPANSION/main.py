"""DOMAIN_EXPANSION: how much of each vertical's market the company has, and what is left.

Needs two things from the caller: deal records, and a market size per vertical
WITH the source it came from ({"healthcare": {"size": 50000000, "source": "..."}}).
The agent holds no market sizes and does not estimate one: without them the
result is `needs_data`.

  penetration = won revenue in the vertical / market size
  whitespace  = market size - won revenue

Verticals are listed by whitespace, largest first. Revenue and market size must
cover the same period and currency; the agent cannot check that and says so.
"""
import logging
from decimal import Decimal
from typing import Any, Dict, List

from velaris.agentkit import biz_common as kit
from velaris.agentkit import biz_sales

logger = logging.getLogger("DOMAIN_EXPANSION")


class DOMAIN_EXPANSIONAgent:
    def __init__(self):
        self.name = "DOMAIN_EXPANSION"

    def health_check(self):
        return kit.health("DOMAIN_EXPANSION")

    def assess(self, deals: Any, market_sizes: Any = None) -> Dict[str, Any]:
        parsed, errors = biz_sales.parse_deals(deals)
        sizes: Dict[str, Dict[str, Any]] = {}
        if market_sizes is not None and not isinstance(market_sizes, dict):
            errors.append("market_sizes must map a vertical to {'size', 'source'}")
        for name, entry in (market_sizes if isinstance(market_sizes, dict) else {}).items():
            size = kit.money(entry.get("size")) if isinstance(entry, dict) else None
            source = kit.text(entry.get("source"), 500) if isinstance(entry, dict) else None
            if kit.text(name, 100) is None or size is None or size <= 0:
                errors.append(f"market_sizes[{name!r}] needs a positive 'size'")
            elif source is None:
                errors.append(f"market_sizes[{name!r}] needs the 'source' the size came from")
            else:
                sizes[name.strip().lower()] = {"size": size, "source": source}
        if errors:
            return kit.failed(errors)
        if not sizes:
            return kit.needs_data("no market sizes supplied; the agent does not estimate market size",
                                  verticals=[])
        revenue = {r["vertical"]: r["_revenue"] for r in biz_sales.vertical_stats(parsed)}
        rows: List[Dict[str, Any]] = []
        for name, entry in sizes.items():
            won = revenue.get(name, Decimal(0))
            rows.append({"vertical": name, "market_size": kit.inr(entry["size"]), "source": entry["source"],
                         "won_revenue": kit.inr(won), "penetration": round(float(won / entry["size"]), 6),
                         "whitespace": kit.inr(entry["size"] - won), "_white": entry["size"] - won,
                         "entered": name in revenue and won > 0})
        rows.sort(key=lambda r: (-r["_white"], r["vertical"]))
        return {"status": "ok", "verticals": biz_sales.public(rows),
                "verticals_without_market_size": sorted(set(revenue) - set(sizes)),
                "method": "penetration = won revenue / supplied market size; ordered by whitespace",
                "caveat": "Revenue and market size must cover the same period and currency; not checked here."}
