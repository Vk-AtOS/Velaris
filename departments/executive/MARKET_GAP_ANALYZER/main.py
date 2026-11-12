"""MARKET_GAP_ANALYZER: coverage analysis of customer needs against offerings.

All inputs come from the caller (surveys, lost-deal reasons, competitor pages):

  needs                 [{"need", "demand", "source"?}]   demand = how often it was asked for
  own_offerings         [{"name", "covers": [need, ...]}]
  competitor_offerings  [{"competitor", "covers": [need, ...]}]   optional

Each need is classed by set membership, nothing more:
  open_gap         nobody covers it          competitor_only   competitors do, we do not
  contested        we and competitors do     unique_strength   only we do
Gaps (open_gap and competitor_only) are listed by demand, highest first. The
agent has no market data of its own: no needs supplied -> `needs_data`.
"""
import logging
from typing import Any, Dict, List

from velaris.agentkit import biz_common as kit

logger = logging.getLogger("MARKET_GAP_ANALYZER")
MAX_ROWS = 5000


def _coverage(rows: Any, label: str, who_key: str, errors: List[str]) -> Dict[str, List[str]]:
    """{need (lower-cased): [who covers it]}."""
    out: Dict[str, List[str]] = {}
    if not isinstance(rows, (list, tuple)) or len(rows) > MAX_ROWS:
        errors.append(f"{label} must be a list of at most {MAX_ROWS} records")
        return out
    for i, r in enumerate(rows):
        who = kit.ident(r.get(who_key)) if isinstance(r, dict) else None
        covers = r.get("covers") if isinstance(r, dict) else None
        if who is None or not isinstance(covers, (list, tuple)) or any(kit.ident(c) is None for c in covers):
            errors.append(f"{label}[{i}] needs '{who_key}' and a 'covers' list of need names")
            continue
        for need in covers:
            names = out.setdefault(need.strip().lower(), [])
            if who not in names:
                names.append(who)
    return out


class MARKET_GAP_ANALYZERAgent:
    def __init__(self, name="MARKET_GAP_ANALYZER"):
        self.name = name

    def health_check(self):
        return kit.health(self.name)

    def analyze(self, needs: Any, own_offerings: Any = (), competitor_offerings: Any = ()) -> Dict[str, Any]:
        errors: List[str] = []
        if not isinstance(needs, (list, tuple)) or len(needs) > MAX_ROWS:
            return kit.failed([f"needs must be a list of at most {MAX_ROWS} records"])
        demand: Dict[str, Dict[str, Any]] = {}
        for i, n in enumerate(needs):
            name = kit.ident(n.get("need")) if isinstance(n, dict) else None
            amount = kit.number(n.get("demand"), 0) if isinstance(n, dict) else None
            if name is None or amount is None:
                errors.append(f"needs[{i}] needs a 'need' name and a non-negative 'demand'")
            elif name.lower() in demand:
                errors.append(f"needs[{i}] repeats '{name.lower()}'")
            else:
                demand[name.lower()] = {"demand": amount, "source": str(n.get("source", ""))[:500]}
        ours = _coverage(own_offerings, "own_offerings", "name", errors)
        theirs = _coverage(competitor_offerings, "competitor_offerings", "competitor", errors)
        if errors:
            return kit.failed(errors)
        if not demand:
            return kit.needs_data("no customer needs supplied; the analyzer holds no market data", gaps=[])
        rows = []
        for need, info in demand.items():
            us, them = ours.get(need, []), theirs.get(need, [])
            kind = ("contested" if them else "unique_strength") if us else ("competitor_only" if them else "open_gap")
            rows.append({"need": need, "demand": info["demand"], "source": info["source"], "class": kind,
                         "covered_by_us": us, "covered_by_competitors": them})
        rows.sort(key=lambda r: (-r["demand"], r["need"]))
        total = sum(r["demand"] for r in rows)
        served = sum(r["demand"] for r in rows if r["covered_by_us"])
        return {
            "status": "ok", "needs": rows,
            "gaps": [r for r in rows if r["class"] in ("open_gap", "competitor_only")],
            "demand_covered_share": round(served / total, 4) if total else None,
            "unknown_needs_referenced": sorted((set(ours) | set(theirs)) - set(demand)),
            "method": "set membership of each need in own and competitor coverage; gaps ordered by supplied demand",
        }
