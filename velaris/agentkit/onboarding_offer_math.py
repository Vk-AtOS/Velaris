"""CTC to monthly components, with the arithmetic shown, and statutory amounts read from PAYROLL_ENGINE.

No statutory figure is written here. Employer and employee contributions, the wage ceilings and the profession-tax
slabs are all obtained by calling PayrollEngine.compute() (public, read-only, date-driven from its dated
registry) for the month the person joins. When that registry has no value for the date, or a value it flags
as not verified, the result is `needs_review` and says which: nothing is silently assumed.

What IS a company choice (not law) and is therefore an input: `basic_pct` (basic as a percentage of monthly CTC) and
`hra_pct_of_basic`. Defaults are supplied for a first customer and reported under `assumptions`.

When `ctc_includes_employer_contributions` is true (the usual Indian practice), employer EPF/ESI are part of the CTC,
so gross = monthly CTC - employer contributions. ESI depends on gross and gross depends on ESI, so the figure is found
by iterating (at most 4 passes); if it has not settled, the result is needs_review.

Not computed: income-tax withholding (depends on the employee's declaration and regime), gratuity, bonus, insurance.
The take-home shown is therefore "before income tax".
"""
from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional

from velaris.agents.PAYROLL_ENGINE.main import PayrollEngine
from velaris.agents.PAYROLL_ENGINE.registry import money, paise

DEFAULT_STRUCTURE = {"basic_pct": "40", "hra_pct_of_basic": "50", "ctc_includes_employer_contributions": True}
LOCAL_BODIES = ("GREATER_CHENNAI_CORPORATION",)


def _d(x: Any) -> Optional[Decimal]:
    return None if x is None else Decimal(str(x))


def _s(x: Optional[Decimal]) -> Optional[str]:
    return None if x is None else str(paise(x))


def breakdown(annual_ctc: Any, structure: Optional[Dict[str, Any]], join_month: str, local_body: Optional[str],
              engine: Optional[PayrollEngine] = None) -> Dict[str, Any]:
    """The compensation breakdown. Raises ValueError for unusable input (zero CTC, percentages out of range)."""
    engine = engine or PayrollEngine()
    ctc = money(annual_ctc)
    if ctc <= 0:
        raise ValueError("annual_ctc must be above zero")
    assumptions: List[str] = []
    st = dict(DEFAULT_STRUCTURE)
    if structure:
        unknown = set(structure) - set(st)
        if unknown:
            raise ValueError(f"unknown structure keys {sorted(unknown)}")
        st.update(structure)
    else:
        assumptions.append("structure is the platform default (a company choice, not law): "
                           f"basic {st['basic_pct']}% of CTC, HRA {st['hra_pct_of_basic']}% of basic")
    basic_pct, hra_pct = money(st["basic_pct"]), money(st["hra_pct_of_basic"])
    if not (Decimal(0) < basic_pct <= Decimal(100)) or hra_pct > Decimal(100):
        raise ValueError("basic_pct must be above 0 and at most 100; hra_pct_of_basic at most 100")
    inclusive = bool(st["ctc_includes_employer_contributions"])
    monthly = paise(ctc / 12)
    basic = paise(monthly * basic_pct / 100)
    hra = paise(basic * hra_pct / 100)
    lines: List[Dict[str, Any]] = [
        {"item": "Monthly CTC", "formula": f"{_s(ctc)} / 12", "amount": _s(monthly)},
        {"item": "Basic", "formula": f"{_s(monthly)} x {basic_pct}%", "amount": _s(basic)},
        {"item": "HRA", "formula": f"{_s(basic)} x {hra_pct}%", "amount": _s(hra)}]
    reasons: List[str] = []
    gross = monthly
    result: Dict[str, Any] = {}
    settled = False
    for _ in range(4):
        special = paise(gross - basic - hra)
        if special < 0:
            raise ValueError("basic plus HRA exceed the gross: lower basic_pct or hra_pct_of_basic")
        result = engine.compute("offer", float(basic), float(hra), float(special), pay_period=join_month,
                                local_body=local_body, half_year_gross=float(gross * 6))
        er = result["statutory"]
        if not inclusive:
            settled = True
            break
        if er["epf_employer"] is None or er["esi_employer"] is None:
            break
        new_gross = paise(monthly - _d(er["epf_employer"]) - _d(er["esi_employer"]))
        if new_gross == gross:
            settled = True
            break
        gross = new_gross
    reasons += [f"payroll registry: {r}" for r in result.get("review_reasons", [])]
    reasons += list(result.get("warnings", []))
    sta = result["statutory"]
    if inclusive and not settled:
        reasons.append("employer contributions and gross did not settle in 4 passes: set the structure by hand")
    special_out: Optional[Decimal] = paise(gross - basic - hra) if (settled or not inclusive) else None
    if inclusive:
        lines += [{"item": "Employer EPF", "formula": "from PAYROLL_ENGINE registry", "amount": _s(_d(sta["epf_employer"]))},
                  {"item": "Employer ESI", "formula": "from PAYROLL_ENGINE registry", "amount": _s(_d(sta["esi_employer"]))},
                  {"item": "Gross (monthly CTC less employer contributions)", "formula": "", "amount": _s(gross if settled else None)}]
    lines.append({"item": "Special allowance", "formula": "gross - basic - HRA", "amount": _s(special_out)})
    ded = [{"item": "Employee EPF", "amount": sta["epf_employee"]}, {"item": "Employee ESI", "amount": sta["esi_employee"]},
           {"item": "Professional tax (for the joining month)", "amount": sta["professional_tax"]}]
    take_home = None
    if special_out is not None and sta["total_employee_deductions"] is not None:
        take_home = paise(gross - _d(sta["total_employee_deductions"]))
    assumptions.append("income tax withholding, gratuity, bonus and insurance are not computed; take-home is before income tax")
    return {
        "status": "needs_review" if reasons else "ok", "review_reasons": reasons, "assumptions": assumptions,
        "annual_ctc": _s(ctc), "monthly_ctc": _s(monthly), "join_month": join_month, "structure": st,
        "components": {"basic": _s(basic), "hra": _s(hra), "special_allowance": _s(special_out), "gross": _s(gross if settled or not inclusive else None)},
        "employer_contributions": {"epf": _s(_d(sta["epf_employer"])), "esi": _s(_d(sta["esi_employer"]))},
        "employee_deductions": [{"item": d["item"], "amount": _s(_d(d["amount"]))} for d in ded],
        "take_home_before_income_tax": _s(take_home), "lines": lines,
        "parameters_used": result.get("parameters_used", []),
    }
