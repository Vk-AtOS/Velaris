"""
TDS on payments by a company to resident contractors and professionals (Income-tax Act, 2025).

  contract_work          s.393(1) Table Sl. No. 6(i)   (old s.194C)
  professional_fees      s.393(1) Table Sl. No. 6(iii) (old s.194J), 10%
  technical_fees         s.393(1) Table Sl. No. 6(iii), 2% (technical, not professional, services)
  call_centre            s.393(1) Table Sl. No. 6(iii), 2% (payee engaged only in running a call centre)
  director_remuneration  s.393(1) Table Sl. No. 6(iii)(c), 10%, no threshold (not salary under s.392)

The payer is taken to be a company (a "designated person" s.402(11)(d) and a "specified person"
s.402(37)(a)). The amount passed is the sum credited or paid excluding GST shown separately on
the invoice; whether GST is excluded under the 2025 Act was not established from a primary text
(the old-Act circular was not read), so the caller decides what base to pass and the result says so.
Lower-deduction certificates, non-resident payees and s.393(4) exceptions are not handled.
"""
from decimal import Decimal
from typing import Any, Dict

from velaris.agents.PAYROLL_ENGINE.registry import Run, inr, money
from velaris.agents.TDS_ENGINE import statutory

NATURES = ("contract_work", "professional_fees", "technical_fees", "call_centre", "director_remuneration")
PAYEE_TYPES = ("individual", "huf", "company", "firm", "llp", "other")
HUNDRED = Decimal(100)


def compute_vendor_tds(*, tax_year: str, nature: str, payee_type: str, amount: Any, paid_before: Any = 0,
                       tds_before: Any = 0, pan_available: bool = True, payee_resident: bool = True) -> Dict[str, Any]:
    """TDS on one credit or payment to a payee.

    paid_before   sums of the same nature already credited or paid to this payee in the tax year
    tds_before    tax already deducted on those sums
    Where the aggregate threshold is first crossed by this payment, s.393(1)(a) says tax is deducted
    on "the entire amount", so tax due on the earlier sums is caught up here.
    """
    if nature not in NATURES:
        raise ValueError(f"nature must be one of {NATURES}, got {nature!r}")
    if payee_type not in PAYEE_TYPES:
        raise ValueError(f"payee_type must be one of {PAYEE_TYPES}, got {payee_type!r}")
    start, _ = statutory.tax_year_bounds(tax_year)
    run = Run(statutory.PARAMS, start)
    amount, before, deducted = money(amount), money(paid_before), money(tds_before)
    if not payee_resident:
        run.review("payee is not resident: s.393(2) applies, which this engine does not compute")
    rule = run.param("tds_393_1_sl6i_contract" if nature == "contract_work" else "tds_393_1_sl6iii_professional")
    no_pan_rate = run.param("tds_no_pan_rate")
    base = {"tax_year": tax_year, "nature": nature, "payee_type": payee_type, "amount": inr(amount),
            "base_note": "amount is the sum credited/paid as passed by the caller (GST shown separately should "
                         "be left out by the caller; not established from a primary text)",
            "parameters_used": run.parameters()}
    if run.reasons:
        return {**base, "status": "needs_review", "review_reasons": run.reasons, "tds": None, "lines": []}

    aggregate = before + amount
    lines = []
    if nature == "contract_work":
        rate = rule["rate_individual_huf"] if payee_type in ("individual", "huf") else rule["rate_other"]
        section = "s.393(1) Table Sl. No. 6(i)"
        over_single = amount > rule["single_sum_threshold"]
        over_aggregate = aggregate > rule["aggregate_threshold"]
        due = over_single or over_aggregate
        lines.append(f"thresholds: this sum {inr(amount)} vs Rs {rule['single_sum_threshold']} "
                     f"({'exceeded' if over_single else 'not exceeded'}); aggregate {inr(aggregate)} vs "
                     f"Rs {rule['aggregate_threshold']} ({'exceeded' if over_aggregate else 'not exceeded'})")
        taxable = aggregate if over_aggregate else (amount if over_single else Decimal(0))
    else:
        section = "s.393(1) Table Sl. No. 6(iii)"
        rate = rule["rate_professional"] if nature in ("professional_fees", "director_remuneration") else rule["rate_technical"]
        threshold = rule["director_threshold"] if nature == "director_remuneration" else rule["threshold"]
        due = aggregate > threshold
        lines.append(f"threshold: aggregate {inr(aggregate)} vs Rs {threshold} ({'exceeded' if due else 'not exceeded'})")
        taxable = aggregate if due else Decimal(0)
    if due and not pan_available:
        lines.append(f"no valid PAN: rate is the higher of {rate}% and {no_pan_rate}% (s.397(2)(b)(i))")
        rate = max(rate, no_pan_rate)
    gross_tds = taxable * Decimal(rate) / HUNDRED
    tds = max(Decimal(0), gross_tds - deducted)
    if due:
        lines.append(f"{rate}% of {inr(taxable)} = {inr(gross_tds)}; less already deducted {inr(deducted)} = {inr(tds)}")
    else:
        lines.append("no deduction: threshold not exceeded")
    return {**base, "status": "ok", "review_reasons": [], "section": section, "rate_percent": rate if due else 0,
            "taxable_base": inr(taxable), "tds": inr(tds), "lines": lines,
            "return_form": "quarterly non-salary statement Form No. 140, certificate Form No. 131 (CBDT transition "
                           "FAQ Q6.10, Q6.15); not generated here"}
