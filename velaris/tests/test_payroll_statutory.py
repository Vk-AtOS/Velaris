"""Statutory registry and date-driven payroll computation (India, Tamil Nadu). No network."""
from datetime import date
from decimal import Decimal

import pytest

from velaris.agents.PAYROLL_ENGINE import statutory
from velaris.agents.PAYROLL_ENGINE.main import PayrollEngine

GCC = "GREATER_CHENNAI_CORPORATION"
ENG = PayrollEngine()


def pay(basic, period, hra=0.0, special=0.0, **kw):
    kw.setdefault("local_body", GCC)
    return ENG.compute("E1", basic=basic, hra=hra, special_allowance=special, pay_period=period, **kw)


# ── registry lookup on both sides of each effective date ──────────────────
@pytest.mark.parametrize("name,on,expected", [
    ("epf_wage_ceiling", date(2014, 8, 31), None),
    ("epf_wage_ceiling", date(2014, 9, 1), 15000),
    ("epf_wage_ceiling", date(2026, 9, 16), 15000),
    ("epf_wage_ceiling", date(2026, 9, 17), 25000),
    ("esi_employee_rate", date(2019, 6, 30), None),
    ("esi_employee_rate", date(2019, 7, 1), 0.0075),
    ("esi_employer_rate", date(2019, 6, 30), None),
    ("esi_employer_rate", date(2019, 7, 1), 0.0325),
    ("esi_wage_ceiling", date(2016, 12, 31), None),
    ("esi_wage_ceiling", date(2017, 1, 1), 21000),
    ("epf_employee_rate", date(2026, 11, 1), 0.12),
    ("epf_employer_rate", date(2026, 11, 1), 0.12),
    ("no_such_parameter", date(2026, 11, 1), None),
])
def test_lookup_by_date(name, on, expected):
    entry = statutory.lookup(name, on)
    assert (entry.value if entry else None) == expected


def test_pt_schedule_lookup_both_sides():
    name = f"pt_half_yearly_slabs:{GCC}"
    assert statutory.lookup(name, date(2018, 3, 31)) is None
    assert dict(statutory.lookup(name, date(2024, 9, 30)).value)[30000] == 135
    assert dict(statutory.lookup(name, date(2024, 10, 1)).value)[30000] == 180


def test_every_verified_entry_has_source_and_fetch_date():
    entries = [e for es in statutory.PARAMS.values() for e in es] + list(statutory.EPF_CEILING_TRANSITIONS.values())
    for e in entries:
        if e.verified:
            assert e.source_url and e.source_url.startswith("https://") and e.fetched_on
        else:
            assert e.note


# ── EPF ceiling ───────────────────────────────────────────────────────────
def test_ceiling_applied_before_and_after_change():
    before, after = pay(40000, "2026-08", half_year_gross=240000), pay(40000, "2026-10")
    assert before["statutory"]["epf_employee"] == before["statutory"]["epf_employer"] == 1800.0
    assert after["statutory"]["epf_employee"] == after["statutory"]["epf_employer"] == 3000.0
    assert after["status"] == "provisional" and after["net_pay"] == 37000.0


def test_wages_under_ceiling_and_full_wages_basis():
    assert pay(10000, "2026-10")["statutory"]["epf_employee"] == 1200.0
    assert pay(40000, "2026-10", epf_basis="full_wages")["statutory"]["epf_employee"] == 4800.0
    with pytest.raises(ValueError):
        pay(40000, "2026-10", epf_basis="guess")


# ── September 2026 transition ─────────────────────────────────────────────
def test_transition_month_needs_review_without_member_status():
    r = pay(20000, "2026-09")
    assert r["status"] == "needs_review"
    assert r["statutory"]["epf_employee"] is None and r["statutory"]["epf_employer"] is None
    assert r["net_pay"] is None and r["ctc_monthly"] is None
    assert any("ceiling changed from 15000 to 25000" in reason for reason in r["review_reasons"])


def test_transition_month_split_matches_epfo_illustration():
    # EPFO FAQ Q7 Scenario C: wages 20,000 -> EPF wages 17,333.33, employee share 2,080.00
    r = pay(20000, "2026-09", epf_basis="ceiling")
    assert r["status"] == "provisional"
    assert r["statutory"]["epf_wages"] == Decimal("17333.33")
    assert r["statutory"]["epf_employee"] == r["statutory"]["epf_employer"] == 2080.0
    assert pay(40000, "2026-09", epf_basis="ceiling")["statutory"]["epf_wages"] == Decimal("19666.67")
    assert any(p["name"] == "epf_ceiling_transition" for p in r["parameters_used"])


def test_transition_month_unambiguous_cases():
    assert pay(12000, "2026-09")["statutory"]["epf_employee"] == 1440.0       # under both ceilings
    assert pay(20000, "2026-09", epf_basis="full_wages")["statutory"]["epf_employee"] == 2400.0


def test_mid_month_change_without_a_primary_source_rule_needs_review(monkeypatch):
    monkeypatch.setitem(statutory.PARAMS, "epf_wage_ceiling", statutory.PARAMS["epf_wage_ceiling"] + [
        statutory.Entry(30000, date(2027, 6, 10), None, None, False, "test")])
    r = pay(28000, "2027-06", epf_basis="ceiling")
    assert r["status"] == "needs_review" and r["statutory"]["epf_employee"] is None
    assert pay(28000, "2027-07")["statutory"]["epf_employee"] == 3360.0


# ── ESI ───────────────────────────────────────────────────────────────────
def test_esi_at_and_above_ceiling():
    at = pay(12000, "2026-10", hra=5000, special=4000)["statutory"]
    assert (at["esi_employee"], at["esi_employer"]) == (157.5, 682.5)
    above = pay(12000, "2026-10", hra=5000, special=4001)["statutory"]
    assert (above["esi_employee"], above["esi_employer"]) == (0.0, 0.0)


def test_period_before_registry_needs_review():
    r = pay(12000, "2019-06")
    assert r["status"] == "needs_review" and r["statutory"]["esi_employee"] is None


# ── Tamil Nadu profession tax, half-yearly ────────────────────────────────
@pytest.mark.parametrize("half_year_gross,tax", [
    (21000, 0.0), (21001, 180.0), (30000, 180.0), (30001, 425.0), (45001, 930.0),
    (60001, 1025.0), (75000, 1025.0), (75001, 1250.0), (420000, 1250.0),
])
def test_pt_slabs_in_deduction_months(half_year_gross, tax):
    for period in ("2026-08", "2027-01"):
        r = pay(10000, period, half_year_gross=half_year_gross)
        assert r["status"] == "provisional" and r["statutory"]["professional_tax"] == tax


def test_pt_not_deducted_outside_august_and_january():
    for period in ("2026-07", "2026-09", "2026-10", "2026-12", "2027-02"):
        assert pay(10000, period, epf_basis="ceiling")["statutory"]["professional_tax"] == 0.0


def test_pt_half_year_selects_schedule():
    # January 2025 pays for II/2024-25 (new schedule); the half-year is April-September / October-March
    assert pay(10000, "2025-01", half_year_gross=25000)["statutory"]["professional_tax"] == 180.0
    assert statutory.half_year_of(date(2026, 8, 1), "H1") == (date(2026, 4, 1), "2026-27 H1")
    assert statutory.half_year_of(date(2027, 1, 1), "H2") == (date(2026, 10, 1), "2026-27 H2")


def test_pt_deduction_month_without_half_year_income_needs_review():
    r = pay(10000, "2026-08")
    assert r["status"] == "needs_review" and r["statutory"]["professional_tax"] is None
    assert r["statutory"]["epf_employee"] == 1200.0   # other components still computed


@pytest.mark.parametrize("body", [None, "COIMBATORE_CORPORATION", "Some Panchayat"])
def test_unknown_local_body_needs_review(body):
    r = pay(10000, "2026-10", local_body=body, half_year_gross=60000)
    assert r["status"] == "needs_review"
    assert r["statutory"]["professional_tax"] is None and r["net_pay"] is None
    assert any("professional_tax" in reason for reason in r["review_reasons"])


def test_local_body_aliases():
    for body in ("GCC", "chennai", "Greater Chennai Corporation"):
        assert pay(10000, "2026-10", local_body=body)["status"] == "provisional"


# ── result contract ───────────────────────────────────────────────────────
def test_result_lists_parameters_and_unverified_warnings():
    r = pay(40000, "2026-10")
    used = {p["name"]: p for p in r["parameters_used"]}
    ceiling = used["epf_wage_ceiling"]
    assert (ceiling["value"], ceiling["effective_from"], ceiling["verified"]) == (25000, "2026-09-17", True)
    assert ceiling["source_url"].startswith("https://www.labour.gov.in/") and ceiling["fetched_on"] == "2026-11-11"
    unverified = sorted(p["name"] for p in r["parameters_used"] if not p["verified"])
    assert unverified == ["contribution_rounding", "epf_wage_base", "esi_wage_base"]
    assert [w for w in r["warnings"] if w.startswith("UNVERIFIED")] and len(r["warnings"]) == 3 + 2
    assert r["not_implemented"] == ["edli_employer", "epf_admin_charges"] and sum(w.startswith("NOT IMPLEMENTED") for w in r["warnings"]) == 2


def test_unverified_value_is_flagged_when_used(monkeypatch):
    monkeypatch.setitem(statutory.PARAMS, "esi_wage_ceiling", [
        statutory.Entry(21000, date(2017, 1, 1), None, None, False, "kept from the old engine")])
    r = pay(10000, "2026-10")
    assert r["statutory"]["esi_employee"] == 75.0
    assert any("esi_wage_ceiling" in w for w in r["warnings"])


def test_legacy_call_shape_and_default_period():
    r = ENG.compute("EMP001", basic=40000, hra=16000, special_allowance=14000, tds=3500)
    for key in ("employee_id", "gross", "components", "statutory", "tds", "total_deductions",
                "net_pay", "ctc_monthly", "ctc_annual"):
        assert key in r
    assert r["pay_period"] == f"{date.today():%Y-%m}" and r["gross"] == 70000
    assert r["status"] == "needs_review"   # no local body given -> profession tax is not guessed


def test_org_summary_flags_review_and_keeps_resolved_sums():
    people = [
        {"employee_id": "A", "basic": 40000, "hra": 16000, "special_allowance": 14000, "local_body": "GCC"},
        {"employee_id": "B", "basic": 25000, "hra": 10000, "special_allowance": 5000},
    ]
    org = ENG.org_statutory_summary(people, pay_period=(2026, 10))
    assert org["headcount"] == 2 and org["total_epf_employer"] == 6000.0
    assert org["status"] == "needs_review" and org["needs_review_employees"] == ["B"]
    assert org["total_net_pay"] is None and org["total_compliance_liability"] is None
    ok = ENG.org_statutory_summary(people[:1], pay_period=date(2026, 10, 31))
    assert ok["status"] == "provisional" and ok["total_compliance_liability"] == 6000.0 and ok["warnings"]


# ── KAN-107: Decimal money, half-up to paise, input validation, honest status ──
def test_money_is_decimal_rounded_half_up_to_paise_and_not_float():
    r = ENG.compute("E1", "33333.335", "0", "0", pay_period="2026-10", local_body=GCC)
    assert isinstance(r["gross"], Decimal) and r["gross"] == Decimal("33333.34")                   # a float would give .33 (binary 33333.3349...)
    assert all(isinstance(r["statutory"][k], Decimal) for k in ("epf_employee", "esi_employee", "professional_tax"))
    assert r["statutory"]["epf_employee"] == Decimal("3000.00")
    assert str(ENG.compute("E", "10000", "0", "0", pay_period="2026-10", local_body=GCC)["statutory"]["esi_employee"]) == "75.00"   # 0.75% exactly


def test_unusable_amounts_are_refused_not_computed():
    for bad in (-1, "abc", None, float("nan"), True):
        r = ENG.compute("E1", bad, 0, 0, pay_period="2026-10", local_body=GCC)
        assert r["status"] == "invalid_input" and "net_pay" not in r
    assert ENG.compute("E1", 100, 0, 0, tds=-5, pay_period="2026-10")["status"] == "invalid_input"


def test_status_is_never_ok_while_parameters_are_unverified_or_charges_missing():
    r = pay(40000, "2026-10", 16000, 14000)
    assert r["status"] == "provisional" and r["review_reasons"] == []
    assert "edli_employer" in r["statutory"] and r["statutory"]["edli_employer"] is None and r["statutory"]["epf_admin_charges"] is None
