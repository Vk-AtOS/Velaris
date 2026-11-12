"""How long each class of HR record must be kept, as a dated registry. READ THIS BEFORE TRUSTING A NUMBER.

Same machinery as PAYROLL_ENGINE and TDS_ENGINE (departments/hr/PAYROLL_ENGINE/registry.py: Entry rows with
value, effective date, source, fetch date, verified flag; to change the law, append an Entry, never edit one).

Two kinds of row, told apart by value["kind"]:

  "statutory"  a period some law requires. Used ONLY when verified=True (read at a primary source, URL beside
               it). Every statutory row below is verified=False: no primary source was read in the session that
               wrote this file, so the periods shown are PLANNING FIGURES in years, labelled as such, and the
               answer for such a class is always `needs_review` with action `hold`: the data is kept and a
               person (a CA or lawyer) must confirm the period before anything is erased.
  "policy"     the company's own choice (how long to keep an unsuccessful candidate's CV, for example). Not law,
               needs no primary source, always used, but flagged for the data-protection owner to confirm.

Which statutes are likely to matter (to be confirmed by a lawyer / CA, not asserted here): wage and payroll
registers under the labour codes and the Tamil Nadu Shops and Establishments rules; income-tax record keeping
and TDS certificates; EPF and ESI scheme records; limitation periods for employment contract disputes.
The DPDP Act 2023 s.8(7) says erase when the purpose ends or consent is withdrawn UNLESS another law requires
retention; that exception is exactly what the "statutory" rows stand for.
"""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional

from velaris.agents.PAYROLL_ENGINE import registry
from velaris.agents.PAYROLL_ENGINE.registry import Entry

AS_OF = date(2026, 11, 13)
_NOTE_ST = ("PLANNING FIGURE, not law. No primary source read; confirm with a CA/lawyer which statute applies "
            "and for how long before erasing anything in this class.")
FLOOR = date(2000, 1, 1)


def _st(years: int, what: str) -> List[Entry]:
    return [Entry({"kind": "statutory", "years": years, "from": "end of the financial year of the record"},
                  FLOOR, None, None, False, f"{what}. {_NOTE_ST}")]


def _pol(years: Any, anchor: str, what: str) -> List[Entry]:
    return [Entry({"kind": "policy", "years": years, "from": anchor}, FLOOR, None, None, True,
                  f"Company policy default, set by the data-protection owner: {what}")]


PARAMS: Dict[str, List[Entry]] = {
    "retention:payroll_records": _st(8, "Payslips, wage registers, salary computation"),
    "retention:tax_records": _st(8, "TDS certificates, tax declarations, Form 16 data"),
    "retention:pf_esi_records": _st(8, "EPF/ESI nominations, UAN and contribution records"),
    "retention:attendance_leave_records": _st(8, "Attendance and leave registers"),
    "retention:employment_contract": _st(8, "Signed offer, appointment letter and e-sign evidence"),
    "retention:employee_master_core": _st(8, "Name and employee id needed to read the statutory records above"),
    "retention:candidate_unsuccessful": _pol(0.5, "application outcome", "CV and screening data of people not hired"),
    "retention:onboarding_documents": _pol(1, "start of employment", "scans collected during onboarding"),
    "retention:onboarding_identifiers": _pol(1, "end of employment", "masked/sealed PAN, bank and Aadhaar digest"),
    "retention:policy_acknowledgements": _pol(3, "end of employment", "policy acknowledgement evidence"),
}

STATUTORY = sorted(k.split(":", 1)[1] for k, v in PARAMS.items() if v[0].value["kind"] == "statutory")


def table(on: date) -> List[Dict[str, Any]]:
    """Every class with its row in force on `on`, for display."""
    out = []
    for name in sorted(PARAMS):
        e = registry.lookup(PARAMS, name, on)
        row = registry.describe(name, e) if e else {"name": name, "value": None}
        row["class"] = name.split(":", 1)[1]
        row["needs_review"] = e is None or (e.value["kind"] == "statutory" and not e.verified)
        out.append(row)
    return out


def decide(record_class: str, anchor: Optional[date], on: date) -> Dict[str, Any]:
    """May records of this class be erased on `on`? {"action": "erase"|"hold", "status": "ok"|"needs_review", ...}

    anchor is the date the retention clock starts (None when it is not known: statutory classes then hold).
    A statutory class is never "erase" unless its row is verified AND the period has passed.
    """
    entry = registry.lookup(PARAMS, f"retention:{record_class}", on)
    if entry is None:
        return {"class": record_class, "action": "hold", "status": "needs_review", "retain_until": None,
                "reason": "no retention row for this class: kept until one is added"}
    kind, years = entry.value["kind"], entry.value["years"]
    if kind == "policy":
        return {"class": record_class, "action": "erase", "status": "ok", "retain_until": None,
                "reason": "company policy, not a legal retention duty; an erasure request is honoured now"}
    if not entry.verified:
        return {"class": record_class, "action": "hold", "status": "needs_review", "retain_until": None,
                "planning_years": years, "reason": "statutory period not verified at a primary source: kept until "
                "a person confirms it"}
    if anchor is None:
        return {"class": record_class, "action": "hold", "status": "needs_review", "retain_until": None,
                "reason": "the date the retention period starts is unknown"}
    until = date(anchor.year + int(years), anchor.month, min(anchor.day, 28))
    return {"class": record_class, "action": "hold" if on <= until else "erase", "status": "ok",
            "retain_until": until.isoformat(), "reason": "statutory retention period"}


def planned_delete_after(record_class: str, anchor: date, on: date) -> Optional[str]:
    """The date a POLICY class is due for deletion (anchor + its years), or None for a statutory or unknown class."""
    entry = registry.lookup(PARAMS, f"retention:{record_class}", on)
    if entry is None or entry.value["kind"] != "policy":
        return None
    days = int(float(entry.value["years"]) * 365)
    return date.fromordinal(anchor.toordinal() + days).isoformat()
