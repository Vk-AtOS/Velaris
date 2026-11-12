"""
Tax on salary for one employee and one tax year, and the monthly deduction under s.392(1).

The computation follows the Income-tax Act, 2025 (from 1 April 2026) and the Finance Act, 2026:
gross salary -> exemptions (old regime only) -> standard deduction -> profession tax (old only)
-> other heads -> Chapter VIII deductions (old only) -> total income, rounded (s.516) -> slab tax
-> rebate s.156 (with marginal relief) -> surcharge (with marginal relief) -> 4% cess -> rounded
-> less tax already deducted, spread over the remaining salary payments (s.392(1), 392(5)(c)).

Every figure comes from statutory.py. Every step is a line in the result. If any figure is
missing or unverified the result is needs_review and carries no amounts.

Out of scope (the engine refuses rather than guesses): perquisite valuation (a taxable value
may be passed in as other_salary), arrears relief s.157, house-property income or loss,
employer pension contribution s.124(1)/(2), deductions other than s.123 and s.124(3),
capital gains and other special-rate income, non-resident specifics.
"""
from datetime import date
from decimal import ROUND_FLOOR, Decimal
from typing import Any, Dict, List, Optional, Tuple

from velaris.agents.PAYROLL_ENGINE.registry import Run, inr, money, paise
from velaris.agents.TDS_ENGINE import statutory

REGIMES = ("new", "old")
AGE_BANDS = ("below_60", "60_to_79", "80_plus")
PROOF_MODES = ("proven_only", "declared")
DECLARATIONS = ("rent_paid", "section_123", "section_124_3", "professional_tax")
HUNDRED = Decimal(100)


def round_to(amount: Decimal, multiple: int) -> Decimal:
    """s.516: drop paise, then to the nearest multiple; a last figure of 5 or more rounds up."""
    rupees = amount.to_integral_value(rounding=ROUND_FLOOR)
    m = Decimal(multiple)
    low = (rupees / m).to_integral_value(rounding=ROUND_FLOOR) * m
    return low + m if rupees - low >= m / 2 else low


def slab_tax(income: Decimal, slabs) -> Tuple[Decimal, List[Dict[str, str]]]:
    """Tax on `income` through a slab table, with one line per band that has income in it."""
    tax, lower, lines = Decimal(0), Decimal(0), []
    for upper, rate in slabs:
        top = income if upper is None else min(income, Decimal(upper))
        if top > lower:
            part = top - lower
            band_tax = part * Decimal(rate) / HUNDRED
            tax += band_tax
            label = f"{inr(lower)} - {inr(Decimal(upper)) if upper is not None else 'above'}"
            lines.append({"band": label, "rate_percent": str(rate), "income_in_band": inr(part),
                          "tax": inr(band_tax)})
        if upper is None or income <= upper:
            break
        lower = Decimal(upper)
    return tax, lines


def surcharge(income: Decimal, tax: Decimal, bands, slabs) -> Tuple[Decimal, Decimal, int]:
    """(surcharge after marginal relief, the relief, rate %). Relief: tax + surcharge may not exceed
    tax + surcharge at the threshold plus the income above the threshold."""
    rate, threshold = 0, None
    for t, r in bands:
        if income > t:
            rate, threshold = r, Decimal(t)
    if not rate:
        return Decimal(0), Decimal(0), 0
    full = tax * Decimal(rate) / HUNDRED
    tax_at, _ = slab_tax(threshold, slabs)
    sc_at, _, _ = surcharge(threshold, tax_at, bands, slabs)
    limit = tax_at + sc_at + (income - threshold)
    relief = max(Decimal(0), tax + full - limit)
    return full - relief, relief, rate


def _declared(decl: Dict[str, Any], name: str) -> Optional[Dict[str, Any]]:
    item = decl.get(name)
    if item is None:
        return None
    if not isinstance(item, dict) or "amount" not in item:
        raise ValueError(f"declaration {name} must be {{'amount': ..., 'proof': bool}}")
    return item


class _Lines:
    def __init__(self) -> None:
        self.rows: List[Dict[str, Any]] = []

    def add(self, step: str, amount: Optional[Decimal], basis: str, **extra: Any) -> None:
        self.rows.append({"step": step, "amount": inr(amount) if isinstance(amount, Decimal) else amount,
                          "basis": basis, **extra})


def compute_salary_tax(*, tax_year: str, regime: str, salary: Dict[str, Any], declarations: Dict[str, Any],
                       age_band: Optional[str], resident: bool, city: Optional[str], proof_mode: str,
                       tds_deducted_so_far: Any, remaining_payments: int) -> Dict[str, Any]:
    if regime not in REGIMES:
        raise ValueError(f"regime must be one of {REGIMES}, got {regime!r}")
    if proof_mode not in PROOF_MODES:
        raise ValueError(f"proof_mode must be one of {PROOF_MODES}, got {proof_mode!r}")
    if not isinstance(remaining_payments, int) or isinstance(remaining_payments, bool) or not 1 <= remaining_payments <= 12:
        raise ValueError("remaining_payments must be an integer from 1 to 12 (salary payments left this "
                         "tax year, including the one being paid)")
    start, _end = statutory.tax_year_bounds(tax_year)
    run = Run(statutory.PARAMS, start)
    unknown = sorted(set(declarations) - set(DECLARATIONS))
    for name in unknown:
        run.review(f"declaration {name!r} is not handled by this engine; it is not guessed at")
    if regime == "old" and age_band not in AGE_BANDS:
        run.review(f"old regime: age_band is required, one of {AGE_BANDS}")
    if not resident:
        run.review("non-resident employee: rebate and age bands differ and non-resident salary is out of "
                   "scope of this engine")

    basic = money(salary.get("basic", 0))
    hra = money(salary.get("hra", 0))
    other = money(salary.get("other_salary", 0))
    other_employer = money(salary.get("other_employer_salary", 0))
    other_income = money(salary.get("other_income", 0))
    paid_so_far = money(tds_deducted_so_far)

    # Every figure first: a missing or unverified one stops the computation before any amount.
    slabs = run.param("new_regime_slabs" if regime == "new" else f"old_regime_slabs:{age_band}") \
        if regime == "new" or age_band in AGE_BANDS else None
    sc_bands = run.param(f"surcharge:{regime}")
    cess_pct = run.param("health_education_cess_percent")
    std = run.param(f"standard_deduction:{regime}")
    rebate = run.param(f"rebate:{regime}")
    multiple = run.param("rounding_to_multiple")
    pt_rule = run.param("professional_tax_deduction")
    cap_123 = run.param("deduction_cap:s123") if regime == "old" and "section_123" in declarations else None
    cap_124 = run.param("deduction_cap:s124_3") if regime == "old" and "section_124_3" in declarations else None
    hra_rule = pan_limit = None
    if regime == "old" and "rent_paid" in declarations:
        hra_rule = run.param("hra_exemption")
        pan_limit = run.param("hra_landlord_pan_rent_threshold")

    lines, decl_rows = _Lines(), []
    base = {"tax_year": tax_year, "regime": regime, "parameters_used": run.parameters()}
    if run.reasons:
        return {**base, "status": "needs_review", "review_reasons": run.reasons, "computation": [],
                "declarations": [], "annual_tax": None, "monthly_tds": None, "form_130_data": None}

    def use(name: str) -> Optional[Decimal]:
        """A declared amount if it may be used under this regime and proof mode, else None (with a row)."""
        item = _declared(declarations, name)
        if item is None:
            return None
        amount, proof = money(item["amount"]), bool(item.get("proof"))
        row = {"name": name, "declared": inr(amount), "proof": proof}
        if regime == "new":
            decl_rows.append({**row, "used": False, "why": "not allowed under s.202 (new regime)"})
            return None
        if name == "rent_paid" and amount > pan_limit and not item.get("landlord_pan"):
            proof = False
            row["why_no_proof"] = f"rent above {inr(Decimal(pan_limit))}: landlord PAN required (rule 205, Form No. 124)"
        if proof_mode == "proven_only" and not proof:
            decl_rows.append({**row, "used": False, "why": "no evidence furnished (s.392(5)(b), rule 205)"})
            return None
        decl_rows.append({**row, "used": True, "why": "evidence furnished" if proof else
                          "declared, evidence still to be furnished (proof_mode='declared')"})
        return amount

    gross = basic + hra + other + other_employer
    lines.add("Gross salary", gross, "basic (incl. DA) + HRA + other salary + salary from other employers "
              "(s.392(4)(a)(i))", components={"basic": inr(basic), "hra": inr(hra), "other_salary": inr(other),
                                              "other_employer_salary": inr(other_employer)})
    exempt_hra = Decimal(0)
    rent = use("rent_paid")
    if rent is not None:
        on_city = (city or "").strip().upper().replace("BANGALORE", "BENGALURU")
        pct = hra_rule["metro_percent"] if on_city in hra_rule["metro_cities"] else hra_rule["other_percent"]
        limb_b = max(Decimal(0), rent - basic * Decimal(hra_rule["rent_excess_over_salary_fraction"]))
        limb_c = basic * Decimal(pct) / HUNDRED
        exempt_hra = min(hra, limb_b, limb_c)
        lines.add("Less: HRA exemption", exempt_hra, "rule 279: least of HRA received, rent - 10% of salary, "
                  f"{pct}% of salary ({'listed city' if pct == hra_rule['metro_percent'] else 'other place'})",
                  limbs={"hra_received": inr(hra), "rent_minus_10pct_salary": inr(limb_b),
                         f"{pct}pct_of_salary": inr(limb_c)})
    elif regime == "new" and hra:
        lines.add("HRA exemption", Decimal(0), "not allowed under s.202 (Schedule III Sl. No. 11 excluded)")
    after_exempt = gross - exempt_hra
    std_amount = min(Decimal(std), after_exempt)
    lines.add("Less: standard deduction", std_amount, f"s.19(1) Table Sl. No. 2: Rs {std} or the salary, "
              "whichever is less")
    pt = use("professional_tax")
    pt_amount = pt if pt is not None else Decimal(0)
    if pt is not None:
        lines.add("Less: profession tax", pt_amount, f"s.19(1) Table Sl. No. 1 ({pt_rule['old']})")
    salary_income = max(Decimal(0), after_exempt - std_amount - pt_amount)
    lines.add("Income under the head Salaries", salary_income, "")
    if other_income:
        lines.add("Add: income under other heads", other_income, "declared by the employee (s.392(4)(a)(iv))")
    gti = salary_income + other_income
    lines.add("Gross total income", gti, "")
    chapter8 = Decimal(0)
    s123 = use("section_123")
    if s123 is not None:
        allowed = min(s123, Decimal(cap_123))
        chapter8 += allowed
        lines.add("Less: s.123 (Schedule XV)", allowed, f"cap Rs {cap_123}")
    s124 = use("section_124_3")
    if s124 is not None:
        allowed = min(s124, Decimal(cap_124))
        chapter8 += allowed
        lines.add("Less: s.124(3) pension contribution", allowed, f"cap Rs {cap_124}")
    total_income = round_to(max(Decimal(0), gti - chapter8), multiple)
    lines.add("Total income (rounded)", total_income, f"s.516: nearest Rs {multiple}")

    tax, bands = slab_tax(total_income, slabs)
    lines.add("Tax on total income", tax, "s.202(1)" if regime == "new" else "Finance Act, 2026 Part III "
              "Paragraph A", bands=bands)
    rebate_amt = Decimal(0)
    limit = Decimal(rebate["income_limit"])
    if total_income <= limit:
        rebate_amt = min(tax, Decimal(rebate["max_rebate"]))
        basis = f"s.156({'2)(a' if regime == 'new' else '1'}): income not above {inr(limit)}"
    elif regime == "new" and tax > total_income - limit:
        rebate_amt = tax - (total_income - limit)
        basis = (f"s.156(2)(b) marginal relief: tax {inr(tax)} exceeds income above {inr(limit)} "
                 f"({inr(total_income - limit)}) by this amount")
    else:
        basis = f"no rebate: income above {inr(limit)}"
    lines.add("Less: rebate", rebate_amt, basis)
    after_rebate = tax - rebate_amt
    sc, relief, sc_rate = surcharge(total_income, after_rebate, sc_bands, slabs)
    lines.add("Add: surcharge", sc, f"{sc_rate}% of tax" + (f", less marginal relief {inr(relief)}" if relief else "")
              if sc_rate else "income not above Rs 50,00,000")
    cess = (after_rebate + sc) * Decimal(cess_pct) / HUNDRED
    lines.add("Add: health and education cess", cess, f"{cess_pct}% of tax and surcharge")
    annual = round_to(after_rebate + sc + cess, multiple)
    lines.add("Tax payable for the year (rounded)", annual, f"s.516: nearest Rs {multiple}")
    balance = max(Decimal(0), annual - paid_so_far)
    monthly = paise(balance / remaining_payments)
    lines.add("Less: tax already deducted this year", paid_so_far, "s.392(4)(a)(v), 392(5)(c)")
    lines.add("Deduct from this payment", monthly, f"balance {inr(balance)} over {remaining_payments} remaining "
              "payments (s.392(1) average rate; s.392(5)(c) adjustment). Shown to the paisa: no rounding rule "
              "for the monthly deduction was found in the texts read.")
    return {
        **base, "status": "ok", "review_reasons": [], "computation": lines.rows, "declarations": decl_rows,
        "annual_tax": inr(annual), "monthly_tds": inr(monthly), "total_income": inr(total_income),
        "form_130_data": {
            "note": "Data a Form No. 130 (salary TDS certificate, tax year 2026-27 onward) would need. The form "
                    "itself, its Part A (deductor, TAN, challans) and the quarterly statement in Form No. 138 "
                    "are not generated here.",
            "tax_year": tax_year, "regime": "s.202 (new)" if regime == "new" else "s.202(4) option (old)",
            "gross_salary": inr(gross), "exemptions": {"hra_schedule_iii_sl_11": inr(exempt_hra)},
            "standard_deduction": inr(std_amount), "profession_tax": inr(pt_amount),
            "income_chargeable_salaries": inr(salary_income), "other_income": inr(other_income),
            "gross_total_income": inr(gti), "chapter_viii_deductions": inr(chapter8),
            "total_income": inr(total_income), "tax_on_total_income": inr(tax), "rebate_s156": inr(rebate_amt),
            "surcharge": inr(sc), "cess": inr(cess), "tax_payable": inr(annual),
            "tds_deducted_so_far": inr(paid_so_far),
        },
    }


def tax_year_of(on: date) -> str:
    start = on.year if on.month >= 4 else on.year - 1
    return f"{start}-{str(start + 1)[-2:]}"
