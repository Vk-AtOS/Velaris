"""Deal records grouped by vertical (industry served), for the sales DOMAIN_* agents.

A deal is {"vertical": str, "status": "won" | "lost" | "open", "amount": money,
"opened": date?, "closed": date?}. Revenue is exact decimal; rates are plain floats.
"""
from __future__ import annotations

import statistics
from decimal import Decimal
from typing import Any, Dict, List, Tuple

from velaris.agentkit import biz_common as kit

STATUSES = ("won", "lost", "open")
MAX_DEALS = 50_000


def parse_deals(raw: Any) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Validated deals and the problems found. Any problem means the caller should refuse."""
    if not isinstance(raw, (list, tuple)) or len(raw) > MAX_DEALS:
        return [], [f"deals must be a list of at most {MAX_DEALS} records"]
    deals, errors = [], []
    for i, d in enumerate(raw):
        if not isinstance(d, dict):
            errors.append(f"deals[{i}] must be an object")
            continue
        vertical, amount = kit.text(d.get("vertical"), 100), kit.money(d.get("amount"))
        opened, closed = kit.as_date(d.get("opened")), kit.as_date(d.get("closed"))
        if vertical is None:
            errors.append(f"deals[{i}].vertical must be a non-empty string")
        if d.get("status") not in STATUSES:
            errors.append(f"deals[{i}].status must be one of {STATUSES}")
        if amount is None or amount < 0:
            errors.append(f"deals[{i}].amount must be a non-negative amount")
        if (d.get("opened") is not None and opened is None) or (d.get("closed") is not None and closed is None):
            errors.append(f"deals[{i}] has an unreadable date")
        elif opened and closed and closed < opened:
            errors.append(f"deals[{i}] closes before it opens")
        deals.append({"vertical": vertical, "status": d.get("status"), "amount": amount,
                      "opened": opened, "closed": closed})
    return ([] if errors else deals), errors


def vertical_stats(deals: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Per vertical: counts, win rate = won / (won + lost), won revenue and share, average
    won deal, median days from open to close of won deals. Sorted by won revenue, then name."""
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for d in deals:
        groups.setdefault(d["vertical"].strip().lower(), []).append(d)
    total_won = sum((d["amount"] for d in deals if d["status"] == "won"), Decimal(0))
    rows = []
    for name, ds in groups.items():
        won = [d for d in ds if d["status"] == "won"]
        lost = sum(d["status"] == "lost" for d in ds)
        revenue = sum((d["amount"] for d in won), Decimal(0))
        cycles = [(d["closed"] - d["opened"]).days for d in won if d["opened"] and d["closed"]]
        rows.append({
            "vertical": name, "deals": len(ds), "won": len(won), "lost": lost,
            "open": len(ds) - len(won) - lost,
            "win_rate": round(len(won) / (len(won) + lost), 4) if won or lost else None,
            "won_revenue": kit.inr(revenue), "_revenue": revenue,
            "revenue_share": round(float(revenue / total_won), 4) if total_won else None,
            "avg_won_deal": kit.inr(revenue / len(won)) if won else None,
            "median_cycle_days": statistics.median(cycles) if cycles else None,
        })
    rows.sort(key=lambda r: (-r["_revenue"], r["vertical"]))
    return rows


def public(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Rows without the internal Decimal column."""
    return [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]
