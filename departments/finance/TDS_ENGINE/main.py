"""
TDS_ENGINE: tax deducted at source under the Income-tax Act, 2025 (tax year 2026-27 onward).

  salary_tds(...)   annual tax projection and this month's deduction for one employee (s.392),
                    new regime (s.202) by default, old regime when the employee has opted. Returns
                    a person's tax figures, so the caller is checked first (velaris.core.access,
                    category "pay": the employee themself, or payroll/HR admin).
  vendor_tds(...)   deduction on a payment to a resident contractor or professional (s.393(1)
                    Table Sl. No. 6(i) and 6(iii)).

Why finance and one agent for both: deducting and depositing TDS is the employer's tax
obligation, and both computations read the same Act, Finance Act and Rules, so they share one
dated registry (statutory.py). PAYROLL_ENGINE takes the monthly figure as its `tds` input.

Every figure is in statutory.py with its source. A result with status "needs_review" carries
no tax amount and says why. These figures need an accountant's check before use.
"""
from datetime import date
from typing import Any, Dict, Optional

from velaris.agents.TDS_ENGINE import salary as salary_calc, vendor
from velaris.core.access import Caller, authorize_read


class TdsEngine:
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = config or {}
        self.org = self.config.get("org")      # Velaris organisation the employees belong to; None = single org

    def health_check(self) -> Dict[str, Any]:
        return {"agent": "TDS_ENGINE", "status": "ok"}

    def salary_tds(self, employee_id: str, *, salary: Dict[str, Any], regime: str = "new",
                   declarations: Optional[Dict[str, Any]] = None, age_band: Optional[str] = None,
                   resident: bool = True, city: Optional[str] = None, proof_mode: str = "proven_only",
                   tds_deducted_so_far: Any = 0, remaining_payments: int = 12,
                   tax_year: Optional[str] = None, caller: Optional[Caller] = None) -> Dict[str, Any]:
        """
        salary         annual projected figures for the tax year (INR): basic (incl. DA), hra, other_salary
                       (special allowance, bonus, taxable value of perquisites), other_employer_salary,
                       other_income (other heads, declared by the employee).
        regime         "new" (s.202, default) or "old" (employee exercised the s.202(4) option).
        declarations   old regime only: {"rent_paid"|"section_123"|"section_124_3"|"professional_tax":
                       {"amount": ..., "proof": bool, "landlord_pan": bool (rent only)}}.
        proof_mode     "proven_only" (default: unproven claims are left out) or "declared".
        """
        authorize_read("pay", employee_id, agent="TDS_ENGINE", caller=caller, org=self.org)
        result = salary_calc.compute_salary_tax(
            tax_year=tax_year or salary_tax_year(date.today()), regime=regime, salary=salary,
            declarations=declarations or {}, age_band=age_band, resident=resident, city=city,
            proof_mode=proof_mode, tds_deducted_so_far=tds_deducted_so_far, remaining_payments=remaining_payments)
        return {"employee_id": employee_id, **result,
                "disclaimer": "Computed from the registry; needs an accountant's check before use."}

    def vendor_tds(self, *, nature: str, payee_type: str, amount: Any, paid_before: Any = 0, tds_before: Any = 0,
                   pan_available: bool = True, payee_resident: bool = True,
                   tax_year: Optional[str] = None) -> Dict[str, Any]:
        result = vendor.compute_vendor_tds(
            tax_year=tax_year or salary_tax_year(date.today()), nature=nature, payee_type=payee_type,
            amount=amount, paid_before=paid_before, tds_before=tds_before, pan_available=pan_available,
            payee_resident=payee_resident)
        return {**result, "disclaimer": "Computed from the registry; needs an accountant's check before use."}


def salary_tax_year(on: date) -> str:
    return salary_calc.tax_year_of(on)
