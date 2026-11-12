"""TDS_ENGINE: salary tax under the Income-tax Act, 2025 (tax year 2026-27) and vendor TDS.

Every expected number is worked out by hand in the test; sources are in
departments/finance/TDS_ENGINE/statutory.py. No network.
"""
from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from velaris.agents.PAYROLL_ENGINE import registry
from velaris.agents.TDS_ENGINE import salary as sal, statutory, vendor
from velaris.agents.TDS_ENGINE.main import TdsEngine
from velaris.core.access import AccessDenied, Caller


@pytest.fixture(autouse=True)
def _data(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))


def tax(gross=0, regime="new", **kw):
    args = dict(tax_year="2026-27", regime=regime, salary={"basic": gross}, declarations={}, age_band=None,
                resident=True, city="Chennai", proof_mode="proven_only", tds_deducted_so_far=0, remaining_payments=12)
    args.update(kw)
    return sal.compute_salary_tax(**args)


# ── registry ──────────────────────────────────────────────────────────────
def test_every_verified_entry_has_https_source_and_fetch_date():
    for name, entries in statutory.PARAMS.items():
        for e in entries:
            if e.verified:
                assert e.source_url.startswith("https://www.incometaxindia.gov.in/") and e.fetched_on, name
            else:
                assert e.note, name


def test_finance_act_rates_stop_at_end_of_tax_year():
    assert registry.lookup(statutory.PARAMS, "health_education_cess_percent", date(2027, 3, 31)).value == 4
    assert registry.lookup(statutory.PARAMS, "health_education_cess_percent", date(2027, 4, 1)) is None
    assert registry.lookup(statutory.PARAMS, "new_regime_slabs", date(2026, 3, 31)) is None


def test_tax_year_bounds():
    assert statutory.tax_year_bounds("2026-27") == (date(2026, 4, 1), date(2027, 3, 31))
    for bad in ("2026", "2026-28", "26-27", "2026/27"):
        with pytest.raises(ValueError):
            statutory.tax_year_bounds(bad)


# ── s.516 rounding and slab arithmetic ────────────────────────────────────
@pytest.mark.parametrize("amount,expected", [
    ("1234.99", 1230),    # paise ignored, last figure 4 -> down
    ("1235", 1240),       # last figure 5 -> up
    ("1239.50", 1240),    # 1239: last figure 9 -> up
    ("1230", 1230),
])
def test_rounding_to_ten(amount, expected):
    assert sal.round_to(Decimal(amount), 10) == expected


def test_slab_boundaries_new_regime():
    slabs = statutory.PARAMS["new_regime_slabs"][0].value
    assert sal.slab_tax(Decimal(400000), slabs)[0] == 0
    assert sal.slab_tax(Decimal(400001), slabs)[0] == Decimal("0.05")           # 1 x 5%
    assert sal.slab_tax(Decimal(800000), slabs)[0] == 20000                       # 4,00,000 x 5%
    assert sal.slab_tax(Decimal(800001), slabs)[0] == Decimal("20000.10")         # + 1 x 10%
    # 4L@5% 20,000 + 4L@10% 40,000 + 4L@15% 60,000 + 4L@20% 80,000 + 4L@25% 1,00,000 = 3,00,000 at Rs 24 lakh
    assert sal.slab_tax(Decimal(2400000), slabs)[0] == 300000
    assert sal.slab_tax(Decimal(2400010), slabs)[0] == 300003                     # 10 x 30%


# ── new regime: rebate cliff and marginal relief ──────────────────────────
def test_new_regime_income_exactly_at_rebate_limit():
    # gross 12,75,000 - standard deduction 75,000 = total income 12,00,000.
    # Tax = 4L x 5% 20,000 + 4L x 10% 40,000 = 60,000; rebate min(100% x 60,000, 60,000) = 60,000 -> nil.
    r = tax(1275000)
    assert r["status"] == "ok" and r["total_income"] == "1200000.00" and r["annual_tax"] == "0.00"
    assert r["monthly_tds"] == "0.00"


def test_new_regime_marginal_relief_just_above_limit():
    # gross 12,85,000 -> total income 12,10,000. Tax 60,000 + 10,000 x 15% = 61,500.
    # s.156(2)(b): rebate = tax - (income - 12,00,000) = 61,500 - 10,000 = 51,500 -> tax 10,000.
    # Cess 4% = 400 -> 10,400. Monthly over 12 = 866.666... -> 866.67.
    r = tax(1285000)
    rebate = next(x for x in r["computation"] if x["step"] == "Less: rebate")
    assert rebate["amount"] == "51500.00" and "marginal relief" in rebate["basis"]
    assert r["annual_tax"] == "10400.00" and r["monthly_tds"] == "866.67"


def test_new_regime_marginal_relief_ends_where_tax_equals_excess_income():
    # total income 12,70,590: tax 60,000 + 70,590 x 15% = 70,588.50 > excess 70,590? No: 70,588.50 < 70,590,
    # so no rebate is needed - tax is lower than the income above 12 lakh. Tax 70,588.50, cess 2,823.54,
    # total 73,412.04 -> rounded 73,410.
    r = tax(1345590)          # 12,70,590 + 75,000
    assert r["total_income"] == "1270590.00"
    assert next(x for x in r["computation"] if x["step"] == "Less: rebate")["amount"] == "0.00"
    assert r["annual_tax"] == "73410.00"


def test_new_regime_surcharge_with_marginal_relief_above_fifty_lakh():
    # gross 51,00,000 -> total income 50,25,000. Tax to 24L = 3,00,000; 26,25,000 x 30% = 7,87,500 -> 10,87,500.
    # Surcharge 10% = 1,08,750 -> 11,96,250. Tax at exactly 50L = 3,00,000 + 26,00,000 x 30% = 10,80,000, so tax+surcharge
    # may not exceed 10,80,000 + 25,000 = 11,05,000: relief 91,250, surcharge 17,500. Cess 4% x 11,05,000 = 44,200.
    # Total 11,49,200.
    r = tax(5100000)
    sc = next(x for x in r["computation"] if x["step"] == "Add: surcharge")
    assert sc["amount"] == "17500.00" and "marginal relief 91250.00" in sc["basis"]
    assert r["annual_tax"] == "1149200.00"


def test_surcharge_not_charged_at_exactly_fifty_lakh():
    # gross 50,75,000 -> total income exactly 50,00,000: tax 10,80,000, no surcharge, cess 43,200 -> 11,23,200.
    r = tax(5075000)
    assert next(x for x in r["computation"] if x["step"] == "Add: surcharge")["amount"] == "0.00"
    assert r["annual_tax"] == "1123200.00"


def test_standard_deduction_cannot_exceed_salary():
    r = tax(60000)
    assert next(x for x in r["computation"] if "standard deduction" in x["step"])["amount"] == "60000.00"
    assert r["annual_tax"] == "0.00"


# ── old regime ────────────────────────────────────────────────────────────
def test_old_regime_rebate_cliff_at_five_lakh():
    # Standard deduction 50,000. Basic 5,50,000 -> income 5,00,000: tax 12,500 = rebate -> nil.
    assert tax(550000, "old", age_band="below_60")["annual_tax"] == "0.00"
    # Basic 5,50,010 -> income 5,00,010: tax 12,500 + 10 x 20% = 12,502, no rebate (s.156(1) needs <= 5L, and the
    # old regime has no marginal relief). Cess 500.08 -> 13,002.08 -> rounded 13,000.
    r = tax(550010, "old", age_band="below_60")
    assert r["annual_tax"] == "13000.00"


def test_old_regime_full_computation_with_declarations_line_by_line():
    # Basic 6,00,000 + HRA 2,40,000 + special 3,60,000 = gross 12,00,000. Rent paid 3,00,000, Chennai (50%).
    # HRA exemption = least of HRA 2,40,000; rent - 10% x basic = 3,00,000 - 60,000 = 2,40,000; 50% x basic = 3,00,000
    # -> 2,40,000. Less std 50,000, profession tax 2,500 -> salary income 9,07,500. s.123 claimed 2,00,000, cap
    # 1,50,000 -> 7,57,500 (already a multiple of 10).
    # Tax = 12,500 (2.5L-5L at 5%) + 2,57,500 x 20% 51,500 = 64,000; no rebate; cess 2,560; 66,560.
    # Monthly 66,560 / 12 = 5,546.666... -> 5,546.67.
    decl = {"rent_paid": {"amount": 300000, "proof": True, "landlord_pan": True},
            "section_123": {"amount": 200000, "proof": True},
            "professional_tax": {"amount": 2500, "proof": True}}
    r = tax(regime="old", age_band="below_60", city="chennai",
            salary={"basic": 600000, "hra": 240000, "other_salary": 360000}, declarations=decl)
    steps = {x["step"]: x["amount"] for x in r["computation"]}
    assert steps["Less: HRA exemption"] == "240000.00" and steps["Income under the head Salaries"] == "907500.00"
    assert steps["Less: s.123 (Schedule XV)"] == "150000.00" and steps["Total income (rounded)"] == "757500.00"
    assert steps["Tax on total income"] == "64000.00" and steps["Add: health and education cess"] == "2560.00"
    assert r["annual_tax"] == "66560.00" and r["monthly_tds"] == "5546.67"
    assert r["form_130_data"]["tax_payable"] == "66560.00" and "not generated" in r["form_130_data"]["note"]


def test_hra_other_city_uses_forty_percent_and_rent_limb():
    # basic 4,00,000, HRA 2,00,000, rent 1,00,000 in Coimbatore (40%): limbs HRA 2,00,000; rent - 40,000 = 60,000;
    # 40% x 4,00,000 = 1,60,000 -> exemption 60,000.
    r = tax(regime="old", age_band="below_60", city="Coimbatore", salary={"basic": 400000, "hra": 200000},
            declarations={"rent_paid": {"amount": 100000, "proof": True}})
    assert next(x for x in r["computation"] if "HRA" in x["step"])["amount"] == "60000.00"


def test_age_bands_use_their_own_slabs():
    # Income 5,00,000 after 50,000 std: age 60-79 nil up to 3L, 5% to 5L = 10,000 -> rebate (<= 5L) 10,000 -> 0.
    # At income 5,50,000: 60-79: 10,000 + 20% x 50,000 = 20,000; below 60: 12,500 + 10,000 = 22,500.
    assert sal.slab_tax(Decimal(550000), statutory.PARAMS["old_regime_slabs:60_to_79"][0].value)[0] == 20000
    assert sal.slab_tax(Decimal(550000), statutory.PARAMS["old_regime_slabs:below_60"][0].value)[0] == 22500
    assert sal.slab_tax(Decimal(550000), statutory.PARAMS["old_regime_slabs:80_plus"][0].value)[0] == 10000


# ── declarations and proof flags ──────────────────────────────────────────
def test_new_regime_ignores_old_regime_declarations_and_says_so():
    r = tax(1285000, declarations={"section_123": {"amount": 150000, "proof": True}})
    row = r["declarations"][0]
    assert row["used"] is False and "not allowed under s.202" in row["why"]
    assert r["annual_tax"] == "10400.00"     # identical to the no-declaration figure above


def test_unproven_declaration_is_left_out_unless_declared_mode():
    decl = {"section_123": {"amount": 100000, "proof": False}}
    base = dict(regime="old", age_band="below_60", salary={"basic": 1000000}, declarations=decl)
    out = tax(**base)
    # income 10,00,000 - 50,000 = 9,50,000: tax 12,500 + 4,50,000 x 20% = 1,02,500 (+4% = 1,06,600)
    assert out["declarations"][0]["used"] is False and out["annual_tax"] == "106600.00"
    inc = tax(proof_mode="declared", **base)
    # income 8,50,000: 12,500 + 3,50,000 x 20% = 82,500 (+4% = 85,800)
    assert inc["declarations"][0]["used"] is True and inc["annual_tax"] == "85800.00"


def test_rent_over_one_lakh_without_landlord_pan_is_not_proven():
    decl = {"rent_paid": {"amount": 120000, "proof": True}}
    r = tax(regime="old", age_band="below_60", salary={"basic": 600000, "hra": 100000}, declarations=decl)
    assert r["declarations"][0]["used"] is False and "landlord PAN" in r["declarations"][0]["why_no_proof"]


def test_monthly_tds_adjusts_for_tax_already_deducted():
    # annual 10,400; 4,000 already deducted; 6,400 over 6 remaining payments = 1,066.666... -> 1,066.67
    r = tax(1285000, tds_deducted_so_far=4000, remaining_payments=6)
    assert r["monthly_tds"] == "1066.67"
    assert tax(1285000, tds_deducted_so_far=20000, remaining_payments=6)["monthly_tds"] == "0.00"


# ── needs_review: nothing is guessed ──────────────────────────────────────
@pytest.mark.parametrize("kw,fragment", [
    ({"tax_year": "2027-28"}, "no registry value"),
    ({"tax_year": "2025-26"}, "no registry value"),
    ({"regime": "old"}, "age_band is required"),
    ({"declarations": {"section_80d": {"amount": 1, "proof": True}}}, "not handled"),
    ({"resident": False}, "non-resident"),
])
def test_needs_review_carries_no_amounts(kw, fragment):
    r = tax(1285000, **kw)
    assert r["status"] == "needs_review" and r["annual_tax"] is None and r["monthly_tds"] is None
    assert r["computation"] == [] and any(fragment in reason for reason in r["review_reasons"])


def test_unverified_figure_is_never_used(monkeypatch):
    entry = statutory.PARAMS["standard_deduction:new"][0]
    monkeypatch.setitem(statutory.PARAMS, "standard_deduction:new", [replace(entry, verified=False, note="test")])
    r = tax(1285000)
    assert r["status"] == "needs_review" and r["annual_tax"] is None
    assert any("not verified" in x for x in r["review_reasons"])


def test_bad_arguments_raise():
    with pytest.raises(ValueError):
        tax(1285000, regime="third")
    with pytest.raises(ValueError):
        tax(1285000, remaining_payments=0)
    with pytest.raises(ValueError):
        tax(-5)


# ── access: a person's tax figures are pay data ───────────────────────────
def test_salary_tds_requires_access_to_pay():
    eng = TdsEngine()
    kw = dict(salary={"basic": 1285000}, tax_year="2026-27")
    with pytest.raises(AccessDenied):
        eng.salary_tds("E1", **kw)
    with pytest.raises(AccessDenied):
        eng.salary_tds("E1", caller=Caller("u2", "acme", frozenset(), employee_id="E2"), **kw)
    own = eng.salary_tds("E1", caller=Caller("u1", "acme", frozenset(), employee_id="E1"), **kw)
    admin = eng.salary_tds("E1", caller=Caller("u3", "acme", frozenset({"payroll_admin"})), **kw)
    assert own["annual_tax"] == admin["annual_tax"] == "10400.00" and "accountant" in own["disclaimer"]


# ── vendor TDS: s.393(1) Sl. No. 6 ────────────────────────────────────────
def vtds(nature, payee, amount, **kw):
    return vendor.compute_vendor_tds(tax_year="2026-27", nature=nature, payee_type=payee, amount=amount, **kw)


def test_contract_rates_and_thresholds():
    assert vtds("contract_work", "company", 100000)["tds"] == "2000.00"       # 2% x 1,00,000
    assert vtds("contract_work", "individual", 100000)["tds"] == "1000.00"    # 1% x 1,00,000
    assert vtds("contract_work", "individual", 30000)["tds"] == "0.00"        # 30,000 is not above 30,000
    assert vtds("contract_work", "individual", 30001)["tds"] == "300.01"      # 1% x 30,001
    # five payments of 20,000 each are under the single-sum limit; the fifth takes the aggregate to 1,00,000 (not
    # above), the sixth to 1,20,000 -> tax on the entire 1,20,000 at 2%.
    assert vtds("contract_work", "company", 20000, paid_before=100000)["tds"] == "2400.00"
    assert vtds("contract_work", "company", 20000, paid_before=80000)["tds"] == "0.00"


def test_aggregate_threshold_catches_up_and_credits_earlier_deductions():
    # earlier 80,000 with nothing deducted, now 25,000: aggregate 1,05,000 > 1,00,000 -> 2% x 1,05,000 = 2,100.
    assert vtds("contract_work", "company", 25000, paid_before=80000)["tds"] == "2100.00"
    # same, but 500 was already deducted earlier -> 1,600.
    assert vtds("contract_work", "company", 25000, paid_before=80000, tds_before=500)["tds"] == "1600.00"


def test_professional_and_technical_fees():
    assert vtds("professional_fees", "individual", 60000)["tds"] == "6000.00"     # 10% x 60,000
    assert vtds("professional_fees", "company", 50000)["tds"] == "0.00"           # not above 50,000
    assert vtds("professional_fees", "company", 50001)["tds"] == "5000.10"        # 10% x 50,001
    assert vtds("technical_fees", "company", 100000)["tds"] == "2000.00"          # 2% x 1,00,000
    assert vtds("director_remuneration", "individual", 10000)["tds"] == "1000.00"  # nil threshold, 10%


def test_no_pan_uses_twenty_percent():
    r = vtds("contract_work", "company", 100000, pan_available=False)
    assert r["tds"] == "20000.00" and r["rate_percent"] == 20
    assert vtds("contract_work", "company", 10000, pan_available=False)["tds"] == "0.00"   # below threshold


def test_vendor_needs_review_cases():
    assert vtds("contract_work", "company", 100000, payee_resident=False)["status"] == "needs_review"
    r = vendor.compute_vendor_tds(tax_year="2027-28", nature="contract_work", payee_type="company", amount=1)
    assert r["status"] == "ok"    # s.393 rates are in the Act, not a Finance Act schedule: no valid_until
    with pytest.raises(ValueError):
        vtds("rent", "company", 1)
    with pytest.raises(ValueError):
        vtds("contract_work", "trust", 1)
