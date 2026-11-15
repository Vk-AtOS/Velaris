"""PAYROLL_ENGINE: India statutory payroll computation (Tamil Nadu scope), Decimal arithmetic, every figure dated and sourced.

Deliberately NOT implemented (KAN-198; each needs the accountant/lawyer verification of KAN-79 and is listed here so nobody assumes
it works; a result carries status "provisional" or "needs_review" while any of it matters):
  * ESI wage ceiling of Rs 25,000 for persons with disability (the engine applies Rs 21,000 to everyone).
  * ESI exemption for employees earning up to Rs 176 a day.
  * The ESI contribution-period rule (Apr-Sep / Oct-Mar: coverage held to the end of the period); the engine tests the ceiling monthly.
  * EDLI and EPF administration charges (explicit null fields, listed under not_implemented).
  * Statutory rounding rules of EPFO/ESIC (the engine rounds to paise, ROUND_HALF_UP).
See statutory.py for each parameter's source, date and verified flag.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))

import calendar
import logging
from datetime import date
from decimal import Decimal
from typing import Dict, Any, List, Optional, Tuple, Union
from velaris.agents.ZOHO_PAYROLL.main import ZohoPayrollConnector
from velaris.agents.PAYROLL_ENGINE import statutory
from velaris.agents.PAYROLL_ENGINE.registry import money, paise
from velaris.core.access import Caller

logger = logging.getLogger("PAYROLL_ENGINE")

PayPeriod = Union[date, str, Tuple[int, int], None]
EPF_BASES = (None, "ceiling", "full_wages")


def _month_bounds(pay_period: PayPeriod) -> Tuple[date, date]:
    """First and last day of the pay month. Accepts a date, 'YYYY-MM', (year, month); None = this month."""
    if pay_period is None:
        pay_period = date.today()
    if isinstance(pay_period, date):
        year, month = pay_period.year, pay_period.month
    elif isinstance(pay_period, str):
        year, month = (int(p) for p in pay_period.split("-")[:2])
    else:
        year, month = pay_period
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


class _Run:
    """One employee-month: looks parameters up by date and records what was used and what is unresolved."""

    def __init__(self, start: date, end: date):
        self.start, self.end = start, end
        self.used: Dict[str, Dict[str, Any]] = {}
        self.reasons: List[str] = []

    def param(self, name: str, on: Optional[date] = None) -> Any:
        entry = statutory.lookup(name, on or self.end)
        if entry is None:
            self.reasons.append(f"{name}: no registry value in force on {(on or self.end).isoformat()}")
            return None
        self.used[f"{name}@{entry.effective_from}"] = statutory.describe(name, entry)
        return entry.value

    def warnings(self) -> List[str]:
        return [f"UNVERIFIED statutory parameter {u['name']}={u['value']!r}: {u['note']}"
                for u in self.used.values() if not u["verified"]]


def _d(value: Any) -> Decimal:
    """A registry number (int, float or Decimal) as an exact Decimal through its decimal text."""
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _epf_wages(run: _Run, basic: Decimal, epf_basis: Optional[str]) -> Optional[Decimal]:
    """Wages on which EPF is contributed for the month, or None when it needs review."""
    if epf_basis not in EPF_BASES:
        raise ValueError(f"epf_basis must be one of {EPF_BASES}, got {epf_basis!r}")
    run.param("epf_wage_base")
    old_cap = run.param("epf_wage_ceiling", run.start)
    new_cap = run.param("epf_wage_ceiling", run.end)
    if old_cap is None or new_cap is None:
        return None
    old_cap, new_cap = _d(old_cap), _d(new_cap)
    if epf_basis == "full_wages":
        return basic
    if old_cap == new_cap:
        return min(basic, new_cap)
    if basic <= min(old_cap, new_cap):
        return basic  # every treatment of the change gives the same answer
    rule = statutory.EPF_CEILING_TRANSITIONS.get((run.start.year, run.start.month))
    if rule is None:
        run.reasons.append(
            f"epf: wage ceiling changed from {old_cap} to {new_cap} during {run.start:%Y-%m} and the "
            "registry holds no primary-source rule for treating that month")
        return None
    if epf_basis is None:
        run.reasons.append(
            f"epf: wage ceiling changed from {old_cap} to {new_cap} during {run.start:%Y-%m}; the "
            "contribution depends on the employee's status before the change. Pass "
            "epf_basis='ceiling' (existing member contributing on the old ceiling) or 'full_wages' "
            "(already contributing on actual wages). An employee who was excluded before the change "
            "is not computed by this engine.")
        return None
    run.used[f"epf_ceiling_transition@{rule.effective_from}"] = statutory.describe("epf_ceiling_transition", rule)
    v = rule.value
    return (min(basic, old_cap) * v["days_before"] + min(basic, new_cap) * v["days_after"]) / Decimal(v["day_basis"])


def _compute_pt(run: _Run, local_body: Optional[str], half_year_gross: Optional[Decimal]) -> Optional[Decimal]:
    """Tamil Nadu profession tax deducted in this pay month, or None when it needs review."""
    body = statutory.normalise_local_body(local_body)
    slabs_name = f"pt_half_yearly_slabs:{body}"
    if body is None or slabs_name not in statutory.PARAMS:
        run.reasons.append(
            f"professional_tax: no verified schedule for local body {local_body!r}; Tamil Nadu "
            "profession tax is set per local body and is not guessed")
        return None
    months = run.param(f"pt_deduction_months:{body}")
    if months is None:
        return None
    which = months.get(run.start.month)
    if which is None:
        return Decimal(0)  # half-yearly tax: nothing is deducted in this pay month
    if half_year_gross is None:
        run.reasons.append(
            f"professional_tax: {run.start:%B} is a deduction month for {body}; half_year_gross "
            "(the employee's gross income for the half-year) is required")
        return None
    half_start, _label = statutory.half_year_of(run.start, which)
    slabs = run.param(slabs_name, half_start)
    if slabs is None:
        return None
    for upper, tax in slabs:
        if upper is None or half_year_gross <= upper:
            return Decimal(tax)
    return None


def _sum(*amounts: Optional[Decimal]) -> Optional[Decimal]:
    return None if any(a is None for a in amounts) else paise(sum(amounts, Decimal(0)))


def _mul(base: Optional[Decimal], rate: Any) -> Optional[Decimal]:
    return None if base is None or rate is None else paise(base * _d(rate))


# Employer charges the engine does NOT compute. Named in every result so the omission is visible, never silent.
NOT_IMPLEMENTED = ("edli_employer", "epf_admin_charges")


def _compute_statutory(run: _Run, basic: Decimal, gross: Decimal, local_body: Optional[str],
                       half_year_gross: Optional[Decimal], epf_basis: Optional[str]) -> Dict[str, Any]:
    run.param("contribution_rounding")
    epf_wages = _epf_wages(run, basic, epf_basis)
    epf_emp = _mul(epf_wages, run.param("epf_employee_rate"))
    epf_er = _mul(epf_wages, run.param("epf_employer_rate"))

    run.param("esi_wage_base")
    esi_ceiling = run.param("esi_wage_ceiling")
    esi_emp_rate, esi_er_rate = run.param("esi_employee_rate"), run.param("esi_employer_rate")
    if esi_ceiling is None:
        esi_emp = esi_er = None
    elif gross <= _d(esi_ceiling):
        esi_emp, esi_er = _mul(gross, esi_emp_rate), _mul(gross, esi_er_rate)
    else:
        esi_emp = esi_er = Decimal("0.00")

    pt = _compute_pt(run, local_body, half_year_gross)
    return {
        "epf_wages": None if epf_wages is None else paise(epf_wages),
        "epf_employee": epf_emp,
        "epf_employer": epf_er,
        "esi_employee": esi_emp,
        "esi_employer": esi_er,
        "professional_tax": None if pt is None else paise(pt),
        "edli_employer": None,                 # not implemented: see NOT_IMPLEMENTED
        "epf_admin_charges": None,             # not implemented
        "total_employee_deductions": _sum(epf_emp, esi_emp, pt),
        "total_employer_contributions": _sum(epf_er, esi_er),
    }


class PayrollEngine:
    """
    India statutory payroll computation engine (Tamil Nadu scope).
    Wraps Zoho Payroll for live data; also does local computation
    from raw salary components when Zoho credentials are unavailable.

    Every statutory number comes from statutory.py by the pay period's date.
    A result whose "status" is "needs_review" has None for each amount that
    could not be established (and for every total that depends on it) and
    says why in "review_reasons". Never pay from such a result.
    """

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self._zoho: Optional[ZohoPayrollConnector] = None
        if config and config.get("zoho_enabled"):
            self._zoho = ZohoPayrollConnector(config)

    def health_check(self) -> Dict[str, Any]:
        return {"agent": "PAYROLL_ENGINE", "status": "ok", "zoho_enabled": self._zoho is not None}

    # ── Local computation (no Zoho creds needed) ──────────────────────────
    def compute(self, employee_id: str, basic: Any, hra: Any,
                special_allowance: Any, tds: Any = 0, *,
                pay_period: PayPeriod = None, local_body: Optional[str] = None,
                half_year_gross: Any = None,
                epf_basis: Optional[str] = None) -> Dict[str, Any]:
        """
        Compute one month's take-home from salary components.
        basic, hra, special_allowance, tds — all monthly INR values.

        pay_period      date, "YYYY-MM" or (year, month); default: the current month.
        local_body      where the employee works, e.g. "GREATER_CHENNAI_CORPORATION" (alias "GCC").
                        Without a local body that has a verified schedule, profession tax needs review.
        half_year_gross gross income for the half-year; required in a profession-tax deduction month.
        epf_basis       None/"ceiling": contribute up to the statutory ceiling; "full_wages": on actual basic.
                        In a month where the ceiling changes it must be given explicitly.
        """
        try:
            basic, hra, special_allowance, tds = money(basic), money(hra), money(special_allowance), money(tds)
            half_year_gross = None if half_year_gross is None else money(half_year_gross)
            start, end = _month_bounds(pay_period)
        except (ValueError, TypeError) as e:
            return {"employee_id": employee_id, "status": "invalid_input", "reason": str(e)[:200]}
        run = _Run(start, end)
        gross = paise(basic + hra + special_allowance)
        s = _compute_statutory(run, basic, gross, local_body, half_year_gross, epf_basis)
        total_deductions = _sum(s["total_employee_deductions"], tds)
        net_pay = None if total_deductions is None else paise(gross - total_deductions)
        ctc = _sum(gross, s["total_employer_contributions"])
        warnings = run.warnings() + [f"NOT IMPLEMENTED: {n} is not computed; monthly CTC and employer cost exclude it" for n in NOT_IMPLEMENTED]
        # ok: every figure rests on a verified parameter. provisional: figures are computed but rest on an unverified
        # parameter or leave out a charge (see warnings): do not pay or file from them. needs_review: a figure is missing.
        status = "needs_review" if run.reasons else ("provisional" if warnings else "ok")
        if run.reasons:
            logger.warning("Payroll for %s %s needs review: %s", employee_id, f"{start:%Y-%m}", "; ".join(run.reasons))

        logger.debug("Payroll computed for %s %s: gross=%s net=%s", employee_id, f"{start:%Y-%m}", gross, net_pay)
        return {
            "employee_id": employee_id,
            "pay_period": f"{start:%Y-%m}",
            "status": status,
            "review_reasons": run.reasons,
            "gross": gross,
            "components": {"basic": paise(basic), "hra": paise(hra), "special_allowance": paise(special_allowance)},
            "statutory": s,
            "tds": paise(tds),
            "total_deductions": total_deductions,
            "net_pay": net_pay,
            "ctc_monthly": ctc,
            "ctc_annual": None if ctc is None else paise(ctc * 12),
            "parameters_used": list(run.used.values()),
            "warnings": warnings,
            "not_implemented": list(NOT_IMPLEMENTED),
        }

    def compute_bulk(self, employees: List[Dict[str, Any]], pay_period: PayPeriod = None) -> List[Dict[str, Any]]:
        """
        employees: [{"employee_id": ..., "basic": ..., "hra": ..., "special_allowance": ..., "tds": ...,
                     optional "pay_period", "local_body", "half_year_gross", "epf_basis"}]
        pay_period applies to every employee that does not carry its own.
        """
        return [self.compute(**{"pay_period": pay_period, **e}) for e in employees]

    def org_statutory_summary(self, employees: List[Dict[str, Any]], pay_period: PayPeriod = None) -> Dict[str, Any]:
        """
        Aggregates EPF/ESI/PT obligations across the org for one month.
        Amounts under review are left out of the sums; when any exist, "status" is
        "needs_review", the employees are listed, and the two grand totals are None.
        """
        results = self.compute_bulk(employees, pay_period)
        sources = {
            "total_epf_employee": lambda r: r["statutory"]["epf_employee"],
            "total_epf_employer": lambda r: r["statutory"]["epf_employer"],
            "total_esi_employee": lambda r: r["statutory"]["esi_employee"],
            "total_esi_employer": lambda r: r["statutory"]["esi_employer"],
            "total_pt": lambda r: r["statutory"]["professional_tax"],
            "total_tds": lambda r: r.get("tds", 0),
            "total_gross": lambda r: r["gross"],
            "total_net_pay": lambda r: r["net_pay"],
        }
        valid = [r for r in results if r["status"] != "invalid_input"]
        totals: Dict[str, Any] = {
            k: paise(sum((get(r) or Decimal(0) for r in valid), Decimal(0))) for k, get in sources.items()
        }
        totals["headcount"] = len(results)
        totals["total_compliance_liability"] = paise(
            totals["total_epf_employee"] + totals["total_epf_employer"] +
            totals["total_esi_employee"] + totals["total_esi_employer"] +
            totals["total_pt"]
        )
        totals["not_implemented"] = list(NOT_IMPLEMENTED)
        review = [r["employee_id"] for r in results if r["status"] in ("needs_review", "invalid_input")]
        totals["status"] = "needs_review" if review else ("provisional" if any(r["status"] == "provisional" for r in results) else "ok")
        totals["needs_review_employees"] = review
        if review:
            totals["total_net_pay"] = None
            totals["total_compliance_liability"] = None
        totals["warnings"] = sorted({w for r in valid for w in r["warnings"]})
        return totals

    # ── Zoho-backed methods (requires zoho_enabled=True) ──────────────────
    # Each of these reads a stored payslip; ZohoPayrollConnector checks the caller (and raises
    # AccessDenied) before anything is fetched. compute() above only works on figures its caller
    # already supplied, so it reveals nothing new and is not gated.
    def get_payslip(self, employee_id: str, year: int, month: int, *, caller: Optional[Caller] = None) -> Dict:
        if not self._zoho:
            return {"error": "zoho_not_configured"}
        return self._zoho.get_payslip(employee_id, year, month, caller=caller)

    def get_statutory_deductions(self, employee_id: str, year: int, month: int, *,
                                 caller: Optional[Caller] = None) -> Dict:
        if not self._zoho:
            return {"error": "zoho_not_configured"}
        return self._zoho.get_statutory_deductions(employee_id, year, month, caller=caller)

    def get_ytd_summary(self, employee_id: str, financial_year: int, *, caller: Optional[Caller] = None) -> Dict:
        if not self._zoho:
            return {"error": "zoho_not_configured"}
        return self._zoho.get_ytd_summary(employee_id, financial_year, caller=caller)


if __name__ == "__main__":
    eng = PayrollEngine()
    result = eng.compute("EMP001", basic=40000, hra=16000, special_allowance=14000, tds=3500,
                         pay_period="2026-10", local_body="GCC")
    print("Status:", result["status"], result["review_reasons"])
    print("Net pay:", result["net_pay"])
    print("CTC annual:", result["ctc_annual"])
    print("Statutory:", result["statutory"])
    for w in result["warnings"]:
        print("WARNING:", w)
    org = eng.org_statutory_summary([
        {"employee_id": "E1", "basic": 40000, "hra": 16000, "special_allowance": 14000, "local_body": "GCC"},
        {"employee_id": "E2", "basic": 25000, "hra": 10000, "special_allowance": 5000},
    ], pay_period="2026-10")
    print("Org EPF liability:", org["total_epf_employer"], "| needs review:", org["needs_review_employees"])
