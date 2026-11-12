"""PRICING_OPTIMIZER_ENGINE: profit-maximising price, by two stated methods.

  optimize_from_demand   observed (price, quantity) points -> least-squares line q = a + b.p,
                         then the price that maximises (p - cost)(a + b.p):
                             p* = cost/2 - a/(2b), clipped to [min_price, max_price].
                         Refuses with fewer than 3 distinct prices, or when demand does not
                         fall as price rises (b >= 0): there is nothing to optimise.
  optimize               a PricingInput with a constant price elasticity e (> 1): the inverse-
                         elasticity (Lerner) rule p* = cost . e / (e - 1). With e <= 1 profit
                         rises with price without limit, so a max_price is required.

Fitting and arithmetic are in code; no model is involved. demand_index,
competition_index, season_factor and the constraint flags of PricingInput have
no defined unit and are NOT used; the result lists them as ignored. Bounds are
passed as min_price / max_price. PRICING_OPTIMIZER delegates here.
"""
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from velaris.agentkit import biz_common as kit

logger = logging.getLogger("PRICING_OPTIMIZER_ENGINE")
MIN_DISTINCT_PRICES = 3
MAX_POINTS = 10_000


@dataclass
class PricingInput:
    product_id: str
    base_cost: float
    demand_index: float
    competition_index: float
    season_factor: float
    elasticity: float
    constraints: Dict[str, bool]


def _bounds(min_price: Any, max_price: Any, errors: List[str]) -> Tuple[Optional[float], Optional[float]]:
    lo = None if min_price is None else kit.number(min_price, 0)
    hi = None if max_price is None else kit.number(max_price, 0)
    if (min_price is not None and lo is None) or (max_price is not None and hi is None):
        errors.append("min_price and max_price must be non-negative numbers")
    elif lo is not None and hi is not None and lo > hi:
        errors.append("min_price is above max_price")
    return lo, hi


def _clip(price: float, lo: Optional[float], hi: Optional[float]) -> Tuple[float, Optional[str]]:
    if lo is not None and price < lo:
        return lo, "min_price"
    if hi is not None and price > hi:
        return hi, "max_price"
    return price, None


class PricingOptimizerEngine:
    MAX_COST = 1000000
    MAX_INDEX = 100
    MAX_SEASON = 10
    MAX_ELASTICITY = 5.0
    # kept as the list of recognised flags; the numbers are no longer used
    CONSTRAINT_WEIGHTS = {"regulatory_cap": 500, "inventory_clearance": -300,
                          "premium_positioning": 700, "low_margin_mode": -200}

    def health_check(self) -> Dict[str, Any]:
        return kit.health("PRICING_OPTIMIZER_ENGINE")

    def validate(self, p: PricingInput) -> List[str]:
        e = kit.dataclass_errors(p, ["base_cost", "demand_index", "competition_index", "season_factor",
                                     "elasticity"], ["constraints"])
        if kit.ident(getattr(p, "product_id", None), 64) is None:
            e.append("product_id invalid")
        if e:
            return e
        if p.base_cost <= 0 or p.base_cost > self.MAX_COST:
            e.append("base_cost invalid")
        if not 0 <= p.demand_index <= self.MAX_INDEX:
            e.append("demand_index invalid")
        if not 0 <= p.competition_index <= self.MAX_INDEX:
            e.append("competition_index invalid")
        if not 0 <= p.season_factor <= self.MAX_SEASON:
            e.append("season_factor invalid")
        if not 0 < p.elasticity <= self.MAX_ELASTICITY:
            e.append("elasticity invalid")
        e += [f"unsupported constraint {k}" for k in p.constraints if k not in self.CONSTRAINT_WEIGHTS]
        return e

    def optimize(self, p: PricingInput, min_price: Any = None, max_price: Any = None) -> Dict[str, Any]:
        err = self.validate(p)
        lo, hi = _bounds(min_price, max_price, err)
        if err:
            return kit.failed(err)
        ignored = ["demand_index", "competition_index", "season_factor"] + sorted(p.constraints)
        if p.elasticity > 1:
            price, bound = _clip(p.base_cost * p.elasticity / (p.elasticity - 1), lo, hi)
        elif hi is not None:
            price, bound = hi, "max_price"
        else:
            return kit.needs_data(
                f"elasticity {p.elasticity} <= 1: profit rises with price without limit, so a max_price is needed",
                product_id=p.product_id, optimal_price=None)
        return {"status": "ok", "product_id": p.product_id, "optimal_price": round(price, 2),
                "unit_margin": round(price - p.base_cost, 2), "markup_on_cost": round(price / p.base_cost - 1, 4),
                "bound_applied": bound, "ignored_inputs": ignored,
                "method": "constant-elasticity demand, inverse-elasticity rule p* = cost x e / (e - 1)"}

    def optimize_from_demand(self, product_id: Any, unit_cost: Any, points: Any,
                             min_price: Any = None, max_price: Any = None) -> Dict[str, Any]:
        err: List[str] = []
        if kit.ident(product_id, 64) is None:
            err.append("product_id invalid")
        cost = kit.number(unit_cost, 0, self.MAX_COST)
        if cost is None:
            err.append("unit_cost must be a non-negative number")
        lo, hi = _bounds(min_price, max_price, err)
        pts: List[Tuple[float, float]] = []
        if not isinstance(points, (list, tuple)) or len(points) > MAX_POINTS:
            err.append(f"points must be a list of at most {MAX_POINTS} (price, quantity) pairs")
        else:
            for i, pt in enumerate(points):
                ok = isinstance(pt, (list, tuple)) and len(pt) == 2
                price, qty = (kit.number(pt[0], 0), kit.number(pt[1], 0)) if ok else (None, None)
                if price is None or qty is None or price == 0:
                    err.append(f"points[{i}] must be (positive price, non-negative quantity)")
                else:
                    pts.append((price, qty))
        if err:
            return kit.failed(err)
        distinct = len({p for p, _ in pts})
        if distinct < MIN_DISTINCT_PRICES:
            return kit.needs_data(f"{distinct} distinct price(s) observed; at least {MIN_DISTINCT_PRICES} are "
                                  "needed to fit a demand line", product_id=product_id, optimal_price=None)
        n = len(pts)
        mean_p, mean_q = sum(p for p, _ in pts) / n, sum(q for _, q in pts) / n
        sxx = sum((p - mean_p) ** 2 for p, _ in pts)
        slope = sum((p - mean_p) * (q - mean_q) for p, q in pts) / sxx
        intercept = mean_q - slope * mean_p
        ss_tot = sum((q - mean_q) ** 2 for _, q in pts)
        ss_res = sum((q - (intercept + slope * p)) ** 2 for p, q in pts)
        fit = {"intercept": round(intercept, 6), "slope": round(slope, 6), "points": n,
               "r_squared": round(1 - ss_res / ss_tot, 4) if ss_tot else None}
        if slope >= 0:
            return kit.needs_data("the observed quantities do not fall as price rises, so no profit-maximising "
                                  "price exists on this data", product_id=product_id, optimal_price=None, fit=fit)
        price, bound = _clip(cost / 2 - intercept / (2 * slope), lo, hi)
        qty = max(0.0, intercept + slope * price)
        seen = [p for p, _ in pts]
        return {"status": "ok", "product_id": product_id, "optimal_price": round(price, 2),
                "expected_quantity": round(qty, 2), "expected_profit": round((price - cost) * qty, 2),
                "unit_margin": round(price - cost, 2), "bound_applied": bound, "fit": fit,
                "extrapolated": not min(seen) <= price <= max(seen),
                "method": "least-squares line q = a + b.p; p* = cost/2 - a/(2b), clipped to the bounds",
                "caveat": "Expected figures hold only as far as the fitted line does; check r_squared and "
                          "whether the price lies outside the observed range (extrapolated)."}
