"""Inter-rater agreement, written from the published formulas (no libraries).

  weighted_kappa    Cohen's kappa for two raters over ordered categories. Disagreement weights: none (0/1), linear
                    |i-j|/(k-1), quadratic (|i-j|/(k-1))^2. kappa = 1 - D_observed / D_expected, with the expectation taken
                    from the two raters' marginal distributions.
  krippendorff_alpha  alpha = 1 - D_o / D_e from the coincidence matrix (Krippendorff 2011), any number of raters, missing
                    ratings allowed (units with fewer than two ratings are dropped), levels nominal / ordinal / interval.

Both return None when the statistic is undefined (no variation at all, or too little data), never a made-up number.
"""
from __future__ import annotations

from collections import Counter
from itertools import permutations
from typing import Any, Dict, List, Optional, Sequence


def weighted_kappa(a: Sequence[Any], b: Sequence[Any], categories: Sequence[Any], weights: str = "quadratic") -> Optional[float]:
    if len(a) != len(b) or not a:
        raise ValueError("two equal-length, non-empty rating lists are required")
    cats = list(categories)
    idx = {c: i for i, c in enumerate(cats)}
    if any(x not in idx for x in (*a, *b)):
        raise ValueError("a rating is outside the category list")
    k, n = len(cats), len(a)

    def d(i: int, j: int) -> float:
        if weights == "none":
            return 0.0 if i == j else 1.0
        r = abs(i - j) / (k - 1) if k > 1 else 0.0
        return r if weights == "linear" else r * r if weights == "quadratic" else (_ for _ in ()).throw(ValueError("weights: none, linear or quadratic"))
    d_obs = sum(d(idx[x], idx[y]) for x, y in zip(a, b)) / n
    pa, pb = Counter(idx[x] for x in a), Counter(idx[y] for y in b)
    d_exp = sum(pa[i] * pb[j] * d(i, j) for i in pa for j in pb) / (n * n)
    return None if d_exp == 0 else 1 - d_obs / d_exp


def krippendorff_alpha(units: Sequence[Sequence[Any]], level: str = "ordinal") -> Optional[float]:
    """units: one list of ratings per rated item (None entries are missing). level: nominal, ordinal or interval."""
    if level not in ("nominal", "ordinal", "interval"):
        raise ValueError("level must be nominal, ordinal or interval")
    o: Dict[Any, Dict[Any, float]] = {}
    for u in units:
        vals = [v for v in u if v is not None]
        m = len(vals)
        if m < 2:
            continue
        for i, j in permutations(range(m), 2):
            o.setdefault(vals[i], {}).setdefault(vals[j], 0.0)
            o[vals[i]][vals[j]] += 1.0 / (m - 1)
    cats = sorted({c for c in o} | {k for row in o.values() for k in row})
    n_c = {c: sum(o.get(c, {}).values()) for c in cats}
    n = sum(n_c.values())
    if n < 2:
        return None
    if level == "ordinal":
        cum, run = {}, 0.0
        for c in cats:
            cum[c] = run + n_c[c]
            run = cum[c]

        def delta(c: Any, k: Any) -> float:
            lo, hi = (c, k) if cats.index(c) <= cats.index(k) else (k, c)
            between = cum[hi] - cum[lo] + n_c[lo]
            return (between - (n_c[lo] + n_c[hi]) / 2) ** 2
    elif level == "interval":
        def delta(c: Any, k: Any) -> float:
            return float(c - k) ** 2
    else:
        def delta(c: Any, k: Any) -> float:
            return 0.0 if c == k else 1.0
    d_o = sum(o[c][k] * delta(c, k) for c in o for k in o[c] if c != k) / n
    d_e = sum(n_c[c] * n_c[k] * delta(c, k) for c in cats for k in cats if c != k) / (n * (n - 1))
    return None if d_e == 0 else 1 - d_o / d_e


def leniency(ratings: Dict[str, Dict[Any, float]]) -> Dict[str, Optional[float]]:
    """ratings: rater -> {unit: score}. Each rater's mean difference from the mean of the other raters on the same units."""
    out: Dict[str, Optional[float]] = {}
    for r, mine in ratings.items():
        diffs: List[float] = []
        for unit, score in mine.items():
            others = [x[unit] for q, x in ratings.items() if q != r and unit in x]
            if others:
                diffs.append(score - sum(others) / len(others))
        out[r] = round(sum(diffs) / len(diffs), 3) if diffs else None
    return out
