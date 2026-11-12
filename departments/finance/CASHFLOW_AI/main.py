"""CASHFLOW_AI: cash-flow projection from dated receivables and payables.

Method (no model, no forecasting of unknown items): start from the opening
balance, place every supplied receivable and payable on its due date, walk the
dates in order and report the running balance per 7-day bucket, the lowest
balance, and the runway: the days until the balance first goes below zero.
Every assumption the projection rests on is listed in the result.
"""
import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Tuple

from velaris.agentkit import biz_common as kit

logger = logging.getLogger("CASHFLOW_AI")
MAX_ITEMS = 10_000
MAX_HORIZON_DAYS = 730


def _items(raw: Any, kind: str, errors: List[str]) -> List[Tuple[date, Decimal, Decimal]]:
    """[(due, amount, probability)] from a list of {due, amount, probability?}."""
    out = []
    if not isinstance(raw, (list, tuple)) or len(raw) > MAX_ITEMS:
        errors.append(f"{kind} must be a list of at most {MAX_ITEMS} items")
        return out
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            errors.append(f"{kind}[{i}] must be an object")
            continue
        due, amount = kit.as_date(item.get("due")), kit.money(item.get("amount"))
        prob = kit.number(item.get("probability", 1), 0, 1)
        if due is None:
            errors.append(f"{kind}[{i}].due must be a date (YYYY-MM-DD)")
        if amount is None or amount < 0:
            errors.append(f"{kind}[{i}].amount must be a non-negative amount")
        if prob is None or (kind == "payables" and "probability" in item):
            errors.append(f"{kind}[{i}].probability must be between 0 and 1 (receivables only)")
        if due is not None and amount is not None and amount >= 0 and prob is not None:
            out.append((due, amount, Decimal(str(prob))))
    return out


class CashflowAiAgent:
    def __init__(self, config: Dict[str, Any] = None):
        self.version = (config or {}).get("version", kit.VERSION)

    def health_check(self) -> Dict[str, Any]:
        return {"agent": "CASHFLOW_AI", "status": "ok", "version": self.version}

    def project(self, opening_balance: Any, receivables: Any = (), payables: Any = (),
                as_of: Any = None, horizon_days: int = 90) -> Dict[str, Any]:
        errors: List[str] = []
        opening = kit.money(opening_balance)
        if opening is None:
            errors.append("opening_balance must be an amount")
        start = date.today() if as_of is None else kit.as_date(as_of)
        if start is None:
            errors.append("as_of must be a date (YYYY-MM-DD)")
        if isinstance(horizon_days, bool) or not isinstance(horizon_days, int) \
                or not 1 <= horizon_days <= MAX_HORIZON_DAYS:
            errors.append(f"horizon_days must be a whole number from 1 to {MAX_HORIZON_DAYS}")
        ins, outs = _items(receivables, "receivables", errors), _items(payables, "payables", errors)
        if errors:
            return kit.failed(errors)
        end = start + timedelta(days=horizon_days)
        # (date, order, signed amount): payables sort before receipts on the same day
        events, overdue_in, overdue_out, beyond = [], Decimal(0), Decimal(0), 0
        for sign, order, rows in ((1, 1, ins), (-1, 0, outs)):
            for due, amount, prob in rows:
                if due > end:
                    beyond += 1
                    continue
                if due < start:
                    if sign > 0:
                        overdue_in += amount * prob
                    else:
                        overdue_out += amount
                    due = start
                events.append((due, order, sign * amount * prob))
        events.sort(key=lambda e: (e[0], e[1]))
        balance, low, low_on, shortfall_on = opening, opening, start, None
        buckets = [{"start": start + timedelta(days=7 * i), "inflow": Decimal(0), "outflow": Decimal(0)}
                   for i in range((horizon_days + 6) // 7)]
        for due, _, signed in events:
            balance += signed
            bucket = buckets[min((due - start).days // 7, len(buckets) - 1)]
            bucket["inflow" if signed > 0 else "outflow"] += abs(signed)
            if balance < low:
                low, low_on = balance, due
            if balance < 0 and shortfall_on is None:
                shortfall_on = due
        running, weeks = opening, []
        for b in buckets:
            running += b["inflow"] - b["outflow"]
            weeks.append({"week_start": b["start"].isoformat(), "inflow": kit.inr(b["inflow"]),
                          "outflow": kit.inr(b["outflow"]), "closing_balance": kit.inr(running)})
        return {
            "status": "ok", "as_of": start.isoformat(), "horizon_end": end.isoformat(),
            "opening_balance": kit.inr(opening), "closing_balance": kit.inr(balance),
            "lowest_balance": kit.inr(low), "lowest_balance_on": low_on.isoformat(),
            "shortfall_on": shortfall_on.isoformat() if shortfall_on else None,
            "runway_days": (shortfall_on - start).days if shortfall_on else None,
            "runway": (f"balance goes below zero on {shortfall_on.isoformat()}" if shortfall_on
                       else f"no shortfall within {horizon_days} days on the items supplied"),
            "weeks": weeks,
            "overdue_receivables": kit.inr(overdue_in), "overdue_payables": kit.inr(overdue_out),
            "items_beyond_horizon": beyond,
            "assumptions": [
                "Only the receivables and payables supplied are counted; no unlisted income or cost is forecast.",
                "Each item moves cash on its due date, in full.",
                "A receivable with a probability counts at amount x probability; payables count in full.",
                "Items already overdue are placed on the as-of date.",
                "On a shared date, payments leave before receipts arrive.",
                "Runway is the first day the balance is below zero; None means it never is within the horizon.",
            ],
        }

    def run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(payload, dict) or "opening_balance" not in payload:
            return kit.failed(["payload must be an object with opening_balance, receivables, payables"])
        return self.project(payload["opening_balance"], payload.get("receivables", ()),
                            payload.get("payables", ()), payload.get("as_of"), payload.get("horizon_days", 90))
