"""
Effective-dated statutory parameters for the India payroll engine (Tamil Nadu scope).

Rules of this file:
  * Every statutory number lives here, never in main.py.
  * verified=True ONLY if the value was read at a primary government source on
    `fetched_on`; the URL sits next to the value.
  * verified=False means "the engine's long-standing value, NOT confirmed as
    current law". The engine surfaces every such parameter as a warning.
  * `effective_from` is the earliest date this registry vouches for. A lookup
    before the first entry returns None and the engine asks for review.

To change the law: append an Entry. Never edit a past one.
"""
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from velaris.agents.PAYROLL_ENGINE import registry
from velaris.agents.PAYROLL_ENGINE.registry import Entry

FETCHED = date(2026, 11, 11)

# Primary sources read on FETCHED.
SRC_GAZETTE_SO_5109 = "https://www.labour.gov.in/static/uploads/2026/09/2b0f1dbbd3769fc388416186ec145328.pdf"
SRC_GAZETTE_SO_2702 = "https://www.labour.gov.in/static/uploads/2026/06/1dbfa6f5ef9510c30fa6c32008d1f816.pdf"
SRC_PIB_CEILING = "https://www.pib.gov.in/PressReleasePage.aspx?PRID=2310811"
SRC_EPFO_FAQ = "https://pmvbry-cdn.epfindia.gov.in/wp-content/uploads/2026/09/EPFO_Wage_Ceiling_FAQs.pdf"
SRC_ESIC_CONTRIBUTION = "https://www.esic.gov.in/contribution"
SRC_ESIC_COVERAGE = "https://www.esic.gov.in/coverage"
SRC_GCC_REVENUE = "https://chennaicorporation.gov.in/gcc/department/revenue"
SRC_GCC_PT_PRESS = "https://chennaicorporation.gov.in/gcc/pdf/PT_Press_Release.pdf"


PARAMS: Dict[str, List[Entry]] = {
    # ── EPF ───────────────────────────────────────────────────────────────
    "epf_wage_ceiling": [
        Entry(15000, date(2014, 9, 1), SRC_PIB_CEILING, FETCHED, True,
              "PIB release 16 Sep 2026: ceiling 'enhanced to Rs.15,000 in September 2014' and in "
              "force until the 2026 revision; re-notified under the Code on Social Security by "
              f"S.O. 2702(E) of 29 May 2026 ({SRC_GAZETTE_SO_2702}, read). The exact day in "
              "September 2014 was not read; 1 Sep 2014 is this registry's floor."),
        Entry(25000, date(2026, 9, 17), SRC_GAZETTE_SO_5109, FETCHED, True,
              "Gazette of India Extraordinary No. 4918, S.O. 5109(E) dated 17 Sep 2026: Rs 25,000 "
              "per month for Chapter III of the Code on Social Security, 2020, with effect from "
              "the date of publication. Gazette text read."),
    ],
    "epf_employee_rate": [
        Entry(0.12, date(2014, 9, 1), SRC_EPFO_FAQ, FETCHED, True,
              "EPFO Wage Ceiling FAQs (Sept 2026) Q12/Q13: employee 12% of EPF wages. The date the "
              "rate began was not researched; 1 Sep 2014 is this registry's floor."),
    ],
    "epf_employer_rate": [
        Entry(0.12, date(2014, 9, 1), SRC_EPFO_FAQ, FETCHED, True,
              "EPFO Wage Ceiling FAQs Q12/Q13/Q39: employer 12% (8.33% EPS + 3.67% EPF). The engine "
              "computes the combined 12% only; EDLI 0.5% and admin charges 0.5% are NOT computed."),
    ],
    "epf_wage_base": [
        Entry("basic", date(2014, 9, 1), None, None, False,
              "Engine applies EPF to the `basic` component only. EPFO FAQ Q25/Q26 says the base is "
              "wages under section 2(88) of the Code on Social Security (Basic + DA + retaining "
              "allowance); whether allowances must be added back was not established."),
    ],
    # ── ESI ───────────────────────────────────────────────────────────────
    "esi_employee_rate": [
        Entry(0.0075, date(2019, 7, 1), SRC_ESIC_CONTRIBUTION, FETCHED, True,
              "ESIC contribution page: 0.75% w.e.f. 01.07.2019 (page last reviewed 2025-04-04)."),
    ],
    "esi_employer_rate": [
        Entry(0.0325, date(2019, 7, 1), SRC_ESIC_CONTRIBUTION, FETCHED, True,
              "ESIC contribution page: 3.25% w.e.f. 01.07.2019 (page last reviewed 2025-04-04)."),
    ],
    "esi_wage_ceiling": [
        Entry(21000, date(2017, 1, 1), SRC_ESIC_COVERAGE, FETCHED, True,
              "ESIC coverage page: Rs 21,000 per month effective 01.01.2017 (Rs 25,000 for persons "
              "with disability, NOT implemented). Page last reviewed 2025-04-04, i.e. before the "
              "Code on Social Security commenced."),
    ],
    "esi_wage_base": [
        Entry("gross, tested every month", date(2019, 7, 1), None, None, False,
              "Engine applies ESI to basic+hra+special_allowance and tests the ceiling month by "
              "month. The statutory wage definition and the contribution-period rule (Apr-Sep / "
              "Oct-Mar, coverage held to period end) were not established; the Rs 176 daily-wage "
              "employee exemption is not implemented."),
    ],
    # ── Rounding ──────────────────────────────────────────────────────────
    "contribution_rounding": [
        Entry(2, date(2014, 9, 1), None, None, False,
              "Engine rounds every amount to 2 decimals. EPFO/ESIC rounding rules (nearest rupee / "
              "next higher rupee) were not established from a primary source."),
    ],
    # ── Tamil Nadu profession tax: Greater Chennai Corporation ────────────
    # value = ((upper bound of half-yearly gross income, half-yearly tax), ...); None = no upper bound
    "pt_half_yearly_slabs:GREATER_CHENNAI_CORPORATION": [
        Entry(((21000, 0), (30000, 135), (45000, 315), (60000, 690), (75000, 1025), (None, 1250)),
              date(2018, 4, 1), SRC_GCC_REVENUE, FETCHED, True,
              "GCC Revenue Department table, column 'w.e.f. 01.04.2018'."),
        Entry(((21000, 0), (30000, 180), (45000, 425), (60000, 930), (75000, 1025), (None, 1250)),
              date(2024, 10, 1), SRC_GCC_REVENUE, FETCHED, True,
              "GCC Revenue Department table, column 'w.e.f. II/2024-2025' (second half-year of "
              f"2024-25, read as starting 1 Oct 2024); same table in the 2026 press release {SRC_GCC_PT_PRESS}."),
    ],
    # value = {pay month: which half-year it pays for}
    "pt_deduction_months:GREATER_CHENNAI_CORPORATION": [
        Entry({8: "H1", 1: "H2"}, date(2024, 10, 1), SRC_GCC_PT_PRESS, FETCHED, True,
              "GCC press release (2026): Rule 277(2), Tamil Nadu Urban Local Bodies Rules 2023 - "
              "deducted through the pay bills for August and January; the Tamil text ties August "
              "2026 to the first half-year of 2026-27. January = second half-year is inferred."),
    ],
}

# Months in which the EPF ceiling changes part-way and a primary source says how to treat them.
# A mid-month change with no entry here makes the engine return needs_review.
EPF_CEILING_TRANSITIONS: Dict[Tuple[int, int], Entry] = {
    (2026, 9): Entry(
        {"days_before": 16, "days_after": 14, "day_basis": 30},
        date(2026, 9, 17), SRC_EPFO_FAQ, FETCHED, True,
        "EPFO Wage Ceiling FAQs Q7 (Scenario C) and Q9: wages for 1-16 Sep capped at the old "
        "ceiling x 16/30, wages for 17-30 Sep capped at the new ceiling x 14/30, one ECR."),
}

LOCAL_BODY_ALIASES = {
    "GCC": "GREATER_CHENNAI_CORPORATION",
    "CHENNAI": "GREATER_CHENNAI_CORPORATION",
    "GREATER CHENNAI CORPORATION": "GREATER_CHENNAI_CORPORATION",
}


def lookup(name: str, on: date) -> Optional[Entry]:
    """The entry of `name` in force on date `on`, or None if the registry has none."""
    return registry.lookup(PARAMS, name, on)


def normalise_local_body(local_body: Optional[str]) -> Optional[str]:
    if not local_body:
        return None
    key = " ".join(str(local_body).upper().replace("_", " ").split())
    return LOCAL_BODY_ALIASES.get(key, key.replace(" ", "_"))


def half_year_of(pay_month_start: date, which: str) -> Tuple[date, str]:
    """Start date and label of the half-year ('H1' Apr-Sep, 'H2' Oct-Mar) a deduction month pays for."""
    fy = pay_month_start.year if pay_month_start.month >= 4 else pay_month_start.year - 1
    start = date(fy, 4, 1) if which == "H1" else date(fy, 10, 1)
    return start, f"{fy}-{str(fy + 1)[-2:]} {which}"


def describe(name: str, entry: Entry) -> Dict[str, Any]:
    """Plain-dict form of an entry for payroll results."""
    return registry.describe(name, entry)
