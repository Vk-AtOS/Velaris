"""
Dated statutory registry: the shared machinery behind every legal figure Velaris uses.

A parameter is a list of Entry rows. Each row carries its value, the first date it applies,
the primary-source URL it was read from, the date it was read, and whether it was verified
there. `valid_until` closes a row whose law is time-boxed (a Finance Act's rate schedule is
enacted for one tax year): after that date the row no longer answers, so a missing new law
shows up as "no value" instead of last year's figure carried forward.

Used by PAYROLL_ENGINE (statutory.py) and by the finance tax engines (TDS_ENGINE, GST_ENGINE).
To change the law: append an Entry. Never edit a past one.
"""
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

PAISE = Decimal("0.01")


@dataclass(frozen=True)
class Entry:
    value: Any
    effective_from: date
    source_url: Optional[str]
    fetched_on: Optional[date]
    verified: bool
    note: str = ""
    valid_until: Optional[date] = None       # last day this row applies; None = until replaced


Params = Dict[str, List[Entry]]


def lookup(params: Params, name: str, on: date) -> Optional[Entry]:
    """The entry of `name` in force on date `on`, or None if the registry has none."""
    current = None
    for entry in params.get(name, []):
        if entry.effective_from <= on and (current is None or entry.effective_from > current.effective_from):
            current = entry
    if current is not None and current.valid_until is not None and on > current.valid_until:
        return None
    return current


def describe(name: str, entry: Entry) -> Dict[str, Any]:
    """Plain-dict form of an entry for results."""
    return {
        "name": name,
        "value": entry.value if not isinstance(entry.value, Decimal) else str(entry.value),
        "effective_from": entry.effective_from.isoformat(),
        "valid_until": entry.valid_until.isoformat() if entry.valid_until else None,
        "source_url": entry.source_url,
        "fetched_on": entry.fetched_on.isoformat() if entry.fetched_on else None,
        "verified": entry.verified,
        "note": entry.note,
    }


class Run:
    """One computation: looks parameters up by date, records what was used and what is unresolved.

    strict=True (the tax engines): an entry that is not verified at a primary source is not
    used. param() returns None and the reason is recorded, so the result is needs_review and
    nothing is computed from an unverified figure.
    """

    def __init__(self, params: Params, on: date, *, strict: bool = True) -> None:
        self.params, self.on, self.strict = params, on, strict
        self.used: Dict[str, Dict[str, Any]] = {}
        self.reasons: List[str] = []

    def param(self, name: str, on: Optional[date] = None) -> Any:
        when = on or self.on
        entry = lookup(self.params, name, when)
        if entry is None:
            self.reasons.append(f"{name}: no registry value in force on {when.isoformat()}")
            return None
        self.used[f"{name}@{entry.effective_from}"] = describe(name, entry)
        if self.strict and not entry.verified:
            self.reasons.append(f"{name}: value {entry.value!r} is not verified at a primary source - {entry.note}")
            return None
        return entry.value

    def review(self, reason: str) -> None:
        self.reasons.append(reason)

    @property
    def status(self) -> str:
        return "needs_review" if self.reasons else "ok"

    def parameters(self) -> List[Dict[str, Any]]:
        return list(self.used.values())


def money(value: Any) -> Decimal:
    """An amount as an exact Decimal. Floats go through their decimal text. Raises ValueError."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        raise ValueError(f"not an amount: {value!r}")
    try:
        d = Decimal(str(value).strip())
    except InvalidOperation as e:
        raise ValueError(f"not an amount: {value!r}") from e
    if not d.is_finite() or d < 0:
        raise ValueError(f"amount must be finite and not negative: {value!r}")
    return d


def paise(d: Decimal) -> Decimal:
    return d.quantize(PAISE, rounding=ROUND_HALF_UP)


def inr(d: Optional[Decimal]) -> Optional[str]:
    """Money as it leaves an engine: a two-decimal string, or None when it could not be established."""
    return None if d is None else str(paise(d))
