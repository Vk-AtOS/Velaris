"""Validation and masking of the identifiers and forms the onboarding flow collects. Data capture only.

No legal figure lives here. The checks are format checks (a PAN has ten characters of a fixed shape, an Aadhaar
number has twelve digits and a valid Verhoeff check digit), not a statement that the number belongs to the person:
nothing here calls UIDAI, NSDL or a bank. Format-valid is not verified; the records say so.
"""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List

PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
IFSC_RE = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")

# Verhoeff tables (the check-digit scheme used for Aadhaar numbers).
_D = ((0, 1, 2, 3, 4, 5, 6, 7, 8, 9), (1, 2, 3, 4, 0, 6, 7, 8, 9, 5), (2, 3, 4, 0, 1, 7, 8, 9, 5, 6),
      (3, 4, 0, 1, 2, 8, 9, 5, 6, 7), (4, 0, 1, 2, 3, 9, 5, 6, 7, 8), (5, 9, 8, 7, 6, 0, 4, 3, 2, 1),
      (6, 5, 9, 8, 7, 1, 0, 4, 3, 2), (7, 6, 5, 9, 8, 2, 1, 0, 4, 3), (8, 7, 6, 5, 9, 3, 2, 1, 0, 4),
      (9, 8, 7, 6, 5, 4, 3, 2, 1, 0))
_P = ((0, 1, 2, 3, 4, 5, 6, 7, 8, 9), (1, 5, 7, 6, 2, 8, 3, 0, 9, 4), (5, 8, 0, 3, 7, 9, 6, 1, 4, 2),
      (8, 9, 1, 6, 0, 4, 3, 5, 2, 7), (9, 4, 5, 3, 1, 2, 6, 8, 7, 0), (4, 2, 8, 6, 5, 7, 3, 9, 0, 1),
      (2, 7, 9, 3, 8, 0, 6, 4, 1, 5), (7, 0, 4, 6, 9, 1, 3, 2, 5, 8))


def verhoeff_ok(digits: str) -> bool:
    c = 0
    for i, ch in enumerate(reversed(digits)):
        c = _D[c][_P[i % 8][int(ch)]]
    return c == 0


def normalise_identifier(kind: str, value: Any) -> str:
    """The canonical form of a PAN / Aadhaar / bank account / IFSC / UAN. Raises ValueError naming the problem."""
    if not isinstance(value, str):
        raise ValueError(f"{kind} must be text")
    v = "".join(value.split()).upper() if kind in ("pan", "ifsc") else "".join(value.replace("-", " ").split())
    if kind == "pan":
        if not PAN_RE.match(v):
            raise ValueError("PAN must be 5 letters, 4 digits, 1 letter")
    elif kind == "ifsc":
        if not IFSC_RE.match(v):
            raise ValueError("IFSC must be 4 letters, a zero, then 6 letters or digits")
    elif kind == "aadhaar":
        if not (v.isdigit() and len(v) == 12) or v[0] in "01" or not verhoeff_ok(v):
            raise ValueError("Aadhaar must be 12 digits, not starting 0 or 1, with a valid check digit")
    elif kind == "bank_account":
        if not (v.isdigit() and 9 <= len(v) <= 18):
            raise ValueError("bank account number must be 9 to 18 digits")
    elif kind == "uan":
        if not (v.isdigit() and len(v) == 12):
            raise ValueError("UAN must be 12 digits")
    else:
        raise ValueError(f"unknown identifier kind '{kind}'")
    return v


def mask(kind: str, value: str) -> str:
    """The masked form shown everywhere except through authorize_read: only the last four characters survive."""
    if kind == "aadhaar":
        return "XXXX XXXX " + value[-4:]
    return "*" * max(0, len(value) - 4) + value[-4:]


# ---- forms (data capture, no figures of law) ----------------------------------------------------------

TAX_REGIMES = ("old", "new")
FORMS: Dict[str, Dict[str, Any]] = {
    "tax_declaration": {"fields": ("regime", "previous_employer_income_declared", "notes"), "required": ("regime",)},
    "pf_nomination": {"fields": ("nominees",), "required": ("nominees",)},
    "esi_nomination": {"fields": ("nominees",), "required": ("nominees",)},
    "emergency_contact": {"fields": ("name", "relation", "phone"), "required": ("name", "relation", "phone")},
}
_NOMINEE_KEYS = ("name", "relation", "date_of_birth", "share_percent")


def validate_form(form: str, fields: Any) -> List[str]:
    """Problems with a submitted form (empty = acceptable). Only whitelisted fields are accepted."""
    spec = FORMS.get(form)
    if spec is None:
        return [f"unknown form '{form}'; known: {sorted(FORMS)}"]
    if not isinstance(fields, dict):
        return ["fields must be an object"]
    problems = [f"unknown field '{k}'" for k in fields if k not in spec["fields"]]
    problems += [f"missing field '{k}'" for k in spec["required"] if fields.get(k) in (None, "", [])]
    if problems:
        return problems
    for k, v in fields.items():
        if k != "nominees" and (not isinstance(v, (str, bool)) or (isinstance(v, str) and len(v) > 500)):
            problems.append(f"{k} must be short text")
    if form == "tax_declaration" and fields.get("regime") not in TAX_REGIMES:
        problems.append(f"regime must be one of {TAX_REGIMES}")
    if form in ("pf_nomination", "esi_nomination"):
        nominees = fields.get("nominees")
        if not isinstance(nominees, list) or not 1 <= len(nominees) <= 10:
            return ["nominees must be a list of 1 to 10 people"]
        total = Decimal(0)
        for n in nominees:
            if not isinstance(n, dict) or set(n) - set(_NOMINEE_KEYS) or not n.get("name") or not n.get("relation"):
                return ["each nominee needs a name and relation, and only name/relation/date_of_birth/share_percent"]
            try:
                share = Decimal(str(n.get("share_percent")))
            except InvalidOperation:
                return ["each nominee needs a numeric share_percent"]
            if not Decimal(0) < share <= Decimal(100):
                return ["share_percent must be above 0 and at most 100"]
            total += share
        if total != Decimal(100):
            problems.append(f"nominee shares add up to {total}, they must add up to 100")
    return problems
