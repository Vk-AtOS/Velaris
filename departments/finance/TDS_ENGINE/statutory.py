"""
Dated registry of Income-tax figures for TDS (Income-tax Act, 2025; tax year 2026-27 onward).

Rules of this file (same as PAYROLL_ENGINE/statutory.py):
  * Every statutory number lives here, never in the computation modules.
  * verified=True ONLY if the value was read in the primary government text on `fetched_on`;
    the URL sits next to the value and the note says exactly where in that text.
  * verified=False: the engines do not use the value (registry.Run strict mode) and the
    result is needs_review.
  * Rates that a Finance Act enacts for one tax year carry valid_until = the last day of that
    year. From 1 April 2027 they answer nothing until the Finance Act, 2027 is read and added.

Primary texts read on FETCHED (all published by the Income Tax Department, incometaxindia.gov.in):
  SRC_ACT    Income-tax Act, 2025 (30 of 2025) as amended by the Finance Act, 2026 (686 pages).
             s.1(3): in force from 1 April 2026.
  SRC_FA     The Finance Act, 2026 (No. 4 of 2026), Gazette of India Extraordinary, 30 March 2026.
  SRC_RULES  Income-tax Rules, 2026, G.S.R. 198(E), in force from 1 April 2026.
  SRC_FAQ    CBDT "FAQs on Interplay and Transition to the Income-tax Act, 2025".
"""
from datetime import date
from typing import Dict, List

from velaris.agents.PAYROLL_ENGINE.registry import Entry

FETCHED = date(2026, 11, 12)
TY_2026_27_START, TY_2026_27_END = date(2026, 4, 1), date(2027, 3, 31)

SRC_ACT = "https://www.incometaxindia.gov.in/documents/d/guest/income_tax_act_2025_as_amended_by_fa_act_2026-pdf"
SRC_FA = "https://www.incometaxindia.gov.in/documents/d/guest/finance-act-2026-pdf-1"
SRC_RULES = "https://www.incometaxindia.gov.in/documents/d/guest/en-notified-it-rules-2026-20-03-2026-pdf"
SRC_FAQ = "https://www.incometaxindia.gov.in/documents/81799/11848482/FAQs-on-Interplay-and-Transition.pdf"

ACT_START = date(2026, 4, 1)

# Slab tables: ((upper bound of the band or None, rate %), ...), bands contiguous from 0.
PARAMS: Dict[str, List[Entry]] = {
    # ── salary: rates ─────────────────────────────────────────────────────
    "new_regime_slabs": [
        Entry(((400000, 0), (800000, 5), (1200000, 10), (1600000, 15), (2000000, 20), (2400000, 25), (None, 30)),
              ACT_START, SRC_ACT, FETCHED, True,
              "Income-tax Act, 2025 s.202(1) Table (default regime for individuals unless the option in "
              "s.202(4) is exercised). The Finance Act, 2026 memorandum states the s.202 rates for tax year "
              "2026-27 are as already enacted."),
    ],
    "old_regime_slabs:below_60": [
        Entry(((250000, 0), (500000, 5), (1000000, 20), (None, 30)), TY_2026_27_START, SRC_FA, FETCHED, True,
              "Finance Act, 2026, First Schedule Part III Paragraph A(I) - rates for deducting tax from "
              "'Salaries' under s.392 for tax year 2026-27.", TY_2026_27_END),
    ],
    "old_regime_slabs:60_to_79": [
        Entry(((300000, 0), (500000, 5), (1000000, 20), (None, 30)), TY_2026_27_START, SRC_FA, FETCHED, True,
              "Finance Act, 2026, First Schedule Part III Paragraph A(II): resident individual aged 60 or "
              "more but less than 80 at any time during the tax year.", TY_2026_27_END),
    ],
    "old_regime_slabs:80_plus": [
        Entry(((500000, 0), (1000000, 20), (None, 30)), TY_2026_27_START, SRC_FA, FETCHED, True,
              "Finance Act, 2026, First Schedule Part III Paragraph A(III): resident individual aged 80 "
              "or more at any time during the tax year.", TY_2026_27_END),
    ],
    # (income above which the rate applies, surcharge %), ascending. Marginal relief at each threshold.
    "surcharge:new": [
        Entry(((5000000, 10), (10000000, 15), (20000000, 25)), TY_2026_27_START, SRC_FA, FETCHED, True,
              "Finance Act, 2026 s.2(12)(b) Table Sl. No. 10 (income chargeable under s.202 of the 2025 Act; "
              "s.2(12) applies for the purposes of s.2(10), which covers tax deducted from 'Salaries' under "
              "s.392): 10% above Rs 50 lakh, 15% above Rs 1 crore, 25% above Rs 2 crore. Marginal relief: "
              "s.2(13) Table Sl. No. 6 (Rs 50 lakh, 1 crore, 2 crore). Dividend/capital-gain caps not "
              "implemented (salary only).", TY_2026_27_END),
    ],
    "surcharge:old": [
        Entry(((5000000, 10), (10000000, 15), (20000000, 25), (50000000, 37)), TY_2026_27_START, SRC_FA, FETCHED,
              True,
              "Finance Act, 2026 First Schedule Part III Paragraph F, Table 1 Sl. No. 1 (individuals): 10% "
              "above Rs 50 lakh, 15% above Rs 1 crore, 25% above Rs 2 crore, 37% above Rs 5 crore; marginal "
              "relief Table 2 Sl. No. 1 (Rs 50 lakh, 1 crore, 2 crore, 5 crore).", TY_2026_27_END),
    ],
    "health_education_cess_percent": [
        Entry(4, TY_2026_27_START, SRC_FA, FETCHED, True,
              "Finance Act, 2026 s.2(16): 'Health and Education Cess on income-tax' at 4% of income-tax and "
              "surcharge for the cases in s.2(6) to (14), which include s.2(10) (salary TDS).", TY_2026_27_END),
    ],
    # ── salary: deductions and rebate ─────────────────────────────────────
    "standard_deduction:new": [
        Entry(75000, ACT_START, SRC_ACT, FETCHED, True,
              "s.19(1) Table Sl. No. 2(a): Rs 75,000 or the salary, whichever is less, where income-tax is "
              "computed under s.202(1)."),
    ],
    "standard_deduction:old": [
        Entry(50000, ACT_START, SRC_ACT, FETCHED, True,
              "s.19(1) Table Sl. No. 2(b): Rs 50,000 or the salary, whichever is less, in any other case."),
    ],
    "rebate:new": [
        Entry({"max_rebate": 60000, "income_limit": 1200000}, ACT_START, SRC_ACT, FETCHED, True,
              "s.156(2)(a): resident individual taxed under s.202(1), total income not above twelve lakh: "
              "100% of tax or Rs 60,000, whichever is less. s.156(2)(b): above twelve lakh, the excess of tax "
              "over (total income - twelve lakh) is rebated (marginal relief). s.156(3): capped at tax at "
              "s.202(1) rates."),
    ],
    "rebate:old": [
        Entry({"max_rebate": 12500, "income_limit": 500000}, ACT_START, SRC_ACT, FETCHED, True,
              "s.156(1): resident individual, total income not above Rs 5,00,000: 100% of tax or Rs 12,500, "
              "whichever is less."),
    ],
    "deduction_cap:s123": [
        Entry(150000, ACT_START, SRC_ACT, FETCHED, True,
              "s.123 (old s.80C): aggregate of the sums in Schedule XV, not exceeding Rs 1,50,000. Not "
              "allowed under s.202 (s.202(2)(a)(xii): Chapter VIII other than s.124(1)/(2), 125(2), 146)."),
    ],
    "deduction_cap:s124_3": [
        Entry(50000, ACT_START, SRC_ACT, FETCHED, True,
              "s.124(3) (old s.80CCD(1B)): own contribution to the notified pension scheme, not exceeding "
              "Rs 50,000; s.124(5): not for an amount already deducted under s.123."),
    ],
    "professional_tax_deduction": [
        Entry({"old": "entire amount", "new": "not allowed"}, ACT_START, SRC_ACT, FETCHED, True,
              "s.19(1) Table Sl. No. 1: tax on employment under article 276(2), entire amount; excluded "
              "under s.202 by s.202(2)(a)(iv)."),
    ],
    "hra_exemption": [
        Entry({"rent_excess_over_salary_fraction": "0.10", "metro_percent": 50, "other_percent": 40,
               "metro_cities": ("MUMBAI", "KOLKATA", "DELHI", "CHENNAI", "HYDERABAD", "PUNE", "AHMEDABAD",
                                "BENGALURU")},
              ACT_START, SRC_RULES, FETCHED, True,
              "Income-tax Rules, 2026 rule 279 (Schedule III Table Sl. No. 11 of the Act): least of (a) HRA "
              "received, (b) rent paid minus one-tenth of salary, (c) 50% of salary for Mumbai, Kolkata, "
              "Delhi, Chennai, Hyderabad, Pune, Ahmedabad and Bengaluru, 40% elsewhere; 'salary' = basic + "
              "DA if part of the terms of employment, no other allowance. Not allowed under s.202 "
              "(s.202(2)(a)(i), Schedule III Sl. No. 11)."),
    ],
    "hra_landlord_pan_rent_threshold": [
        Entry(100000, ACT_START, SRC_RULES, FETCHED, True,
              "Rules, 2026 rule 205(2) Table Sl. No. 1 (Form No. 124): name, address and PAN of the landlord "
              "where the aggregate rent paid during the tax year exceeds Rs 1,00,000."),
    ],
    "rounding_to_multiple": [
        Entry(10, ACT_START, SRC_ACT, FETCHED, True,
              "s.516: total income and any amount payable rounded to the nearest multiple of Rs 10 (paise "
              "ignored; last figure 5 or more rounds up)."),
    ],
    # ── payments to resident contractors and professionals ────────────────
    "tds_393_1_sl6i_contract": [
        Entry({"rate_individual_huf": 1, "rate_other": 2, "single_sum_threshold": 30000,
               "aggregate_threshold": 100000}, ACT_START, SRC_ACT, FETCHED, True,
              "s.393(1) Table Sl. No. 6(i) (old s.194C): sum for carrying out any work (including supply of "
              "labour) under a contract with a designated person (s.402(11) includes any company and any "
              "firm): 1% if the contractor is an individual or HUF, 2% otherwise; threshold Rs 30,000 for "
              "any such sum and Rs 1,00,000 aggregate. s.393(1)(a): deduct on the entire amount where the "
              "amount or aggregate exceeds the threshold."),
    ],
    "tds_393_1_sl6iii_professional": [
        Entry({"rate_professional": 10, "rate_technical": 2, "threshold": 50000, "director_threshold": 0},
              ACT_START, SRC_ACT, FETCHED, True,
              "s.393(1) Table Sl. No. 6(iii) (old s.194J), payer a specified person (s.402(37)(a): any person "
              "other than an individual/HUF): 2% for fees for technical services (not professional "
              "services), cinema-film royalty, or a payee only operating a call centre; 10% otherwise. "
              "Threshold Rs 50,000 for professional fees, technical fees, royalty, s.26(2)(h) sums; Nil for "
              "director's remuneration not taxed under s.392. 'Professional services' defined in s.402(28)."),
    ],
    "tds_no_pan_rate": [
        Entry(20, ACT_START, SRC_ACT, FETCHED, True,
              "s.397(2)(b)(i): payee without a valid PAN - the higher of the specified rate, the rate in "
              "force, or 20% (5% only for Sl. No. 8(ii)/8(v), not used here)."),
    ],
}


def tax_year_bounds(tax_year: str) -> tuple:
    """'2026-27' -> (date(2026, 4, 1), date(2027, 3, 31)). Raises ValueError for anything else."""
    parts = str(tax_year).split("-")
    if len(parts) != 2 or not (parts[0].isdigit() and parts[1].isdigit()) or len(parts[0]) != 4:
        raise ValueError(f"tax_year must look like '2026-27', got {tax_year!r}")
    start = int(parts[0])
    if (start + 1) % 100 != int(parts[1]):
        raise ValueError(f"tax_year must be two consecutive years, got {tax_year!r}")
    return date(start, 4, 1), date(start + 1, 3, 31)
