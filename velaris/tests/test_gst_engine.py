"""GST_ENGINE: outward supplies of IT services by a Tamil Nadu company. Hand-computed figures; no network.

Sources for every rate and rule: departments/finance/GST_ENGINE/statutory.py. The State (SGST) rate for
Tamil Nadu is unverified in the registry, so intra-State supplies are needs_review unless a test supplies
a verified entry.
"""
from dataclasses import replace
from datetime import date

import pytest

from velaris.agents.GST_ENGINE import statutory
from velaris.agents.GST_ENGINE.gstin import check_char, validate_gstin
from velaris.agents.GST_ENGINE.main import GstEngine

ENG = GstEngine()


def gstin(prefix14):
    return prefix14 + check_char(prefix14)


TN = gstin("33AABCK1234F1Z")        # Tamil Nadu supplier (State code 33)
TN2 = gstin("33AAACV5678G1Z")       # another Tamil Nadu business
MH = "27AAPFU0939F1ZV"              # Maharashtra; a GSTIN published as valid (checks the algorithm independently)
KA = gstin("29AABCT4321H1Z")        # Karnataka
D = date(2026, 10, 15)


def price(**kw):
    args = dict(supplier_gstin=TN, sac="998314", taxable_value=100000, invoice_date=D)
    args.update(kw)
    return ENG.price_outward_supply(**args)


@pytest.fixture
def sgst_verified(monkeypatch):
    entry = statutory.PARAMS["sgst_rate:TAMIL_NADU"][0]
    monkeypatch.setitem(statutory.PARAMS, "sgst_rate:TAMIL_NADU", [replace(entry, verified=True, source_url="https://example.test", fetched_on=D)])


# ── registry ──────────────────────────────────────────────────────────────
def test_registry_rows_are_sourced_and_unverified_ones_explain_themselves():
    for name, entries in statutory.PARAMS.items():
        for e in entries:
            if e.verified:
                assert e.source_url.startswith("https://") and e.fetched_on, name
            else:
                assert e.note, name
    unverified = sorted(n for n, es in statutory.PARAMS.items() if not es[0].verified)
    assert unverified == ["rcm_services_candidates", "sgst_rate:TAMIL_NADU"]


# ── GSTIN ─────────────────────────────────────────────────────────────────
def test_gstin_valid_and_checksum():
    assert validate_gstin(MH) == {"valid": True, "reason": "", "state_code": "27", "pan": "AAPFU0939F"}
    assert validate_gstin(TN)["valid"] and validate_gstin(TN.lower())["valid"]        # case-insensitive
    # hand check of the last character for 27AAPFU0939F1Z: values 2,7,10,10,25,15,30,0,9,3,9,15,1,35;
    # weights 1,2,1,2,...: 2, 14, 10, 20, 25, 30, 30, 0, 9, 6, 9, 30, 1, 70; each p//36 + p%36:
    # 2, 14, 10, 20, 25, 30, 30, 0, 9, 6, 9, 30, 1, (1+34=35) = 221; 221 % 36 = 5; (36-5) = 31 = 'V'.
    assert check_char("27AAPFU0939F1Z") == "V"


@pytest.mark.parametrize("bad,why", [
    (MH[:-1] + "W", "check character"),          # one character off
    (MH[:-1], "format"),                          # 14 characters
    (MH + "1", "format"),                         # 16 characters
    ("27aapfu0939f1zv ", None),                   # lower case and a space are tolerated -> valid
    ("AAAAAAAAAAAAAAA", "format"),
    ("00AAPFU0939F1ZV", "State code"),             # well-formed, but there is no State 00
    ("27AAPFU0939F0ZV", "format"),                # entity number 0 is not allowed
    ("27AAPFU0939F1XV", "format"),                # 14th character must be Z
    (None, "format"), (12345, "format"), ("", "format"),
])
def test_gstin_invalid(bad, why):
    r = validate_gstin(bad)
    if why is None:
        assert r["valid"]
    else:
        assert not r["valid"] and why in r["reason"]


# ── place of supply and rates ─────────────────────────────────────────────
def test_inter_state_b2b_is_igst_at_18_percent():
    # Recipient in Maharashtra (State code from its GSTIN): IGST 18% x 1,00,000 = 18,000; total 1,18,000.
    r = price(recipient_gstin=MH)
    assert r["status"] == "ok" and r["supply_type"] == "inter-State" and r["place_of_supply_state_code"] == "27"
    assert r["tax"] == {"cgst": "0.00", "sgst": "0.00", "igst": "18000.00"} and r["invoice_total"] == "118000.00"


def test_intra_state_is_cgst_plus_sgst(sgst_verified):
    # Tamil Nadu to Tamil Nadu: CGST 9% + SGST 9% of 1,00,000 = 9,000 + 9,000; total 1,18,000.
    r = price(recipient_gstin=TN2)
    assert r["status"] == "ok" and r["supply_type"] == "intra-State"
    assert r["tax"] == {"cgst": "9000.00", "sgst": "9000.00", "igst": "0.00"} and r["invoice_total"] == "118000.00"


def test_intra_state_needs_review_while_the_state_rate_is_unverified():
    r = price(recipient_gstin=TN2)
    assert r["status"] == "needs_review" and r["tax"] is None and "invoice_total" not in r
    assert any("sgst_rate:TAMIL_NADU" in x and "not verified" in x for x in r["review_reasons"])


def test_unregistered_recipient_uses_address_on_record_else_suppliers_state(sgst_verified):
    on_record = price(recipient_state_code="29")                      # State on the invoice = address on record
    assert on_record["supply_type"] == "inter-State" and on_record["tax"]["igst"] == "18000.00"
    assert "Circular 242/36/2024" in on_record["place_of_supply_basis"]
    none = price()                                                    # no address on record -> supplier's location
    assert none["supply_type"] == "intra-State" and none["tax"]["cgst"] == "9000.00"
    same = price(recipient_state_code="33")
    assert same["supply_type"] == "intra-State"


def test_supplier_in_another_state_has_no_state_rate_in_the_registry():
    r = price(supplier_gstin=MH, recipient_gstin=MH)                  # Maharashtra to Maharashtra
    assert r["status"] == "needs_review" and any("State code 27" in x for x in r["review_reasons"])


def test_rounding_to_the_paisa():
    # 333.33 x 18% = 59.9994 -> 60.00 ; total 393.33
    r = price(recipient_gstin=MH, taxable_value="333.33")
    assert r["tax"]["igst"] == "60.00" and r["invoice_total"] == "393.33"


def test_sac_9984_and_unknown_sac():
    assert price(recipient_gstin=MH, sac="998439")["tax"]["igst"] == "18000.00"
    assert price(recipient_gstin=MH, sac="9971")["status"] == "needs_review"             # not 9983/9984
    assert price(recipient_gstin=MH, sac="998431")["status"] == "needs_review"           # may be an e-book
    assert price(recipient_gstin=MH, sac="IT-svc")["status"] == "needs_review"


def test_invalid_gstins_are_invalid_not_priced():
    assert price(supplier_gstin=TN[:-1] + "A" if TN[-1] != "A" else TN[:-1] + "B", recipient_gstin=MH)["status"] == "invalid"
    r = price(recipient_gstin=MH[:-1] + "W")
    assert r["status"] == "invalid" and r["tax"] is None and "recipient GSTIN" in r["review_reasons"][0]


def test_date_before_the_registry_needs_review():
    assert price(recipient_gstin=MH, invoice_date=date(2017, 6, 30))["status"] == "needs_review"


# ── export of services ────────────────────────────────────────────────────
def test_export_under_lut_is_zero_rated():
    r = price(recipient_outside_india=True, payment_in_convertible_forex=True, lut=True, taxable_value=250000)
    assert r["status"] == "ok" and r["zero_rated"] and r["supply_type"] == "export of services"
    assert r["tax"] == {"cgst": "0.00", "sgst": "0.00", "igst": "0.00"} and r["invoice_total"] == "250000.00"
    assert "Letter of Undertaking" in r["lines"][0] and len(r["conditions_s2_6"]) == 5


def test_export_without_lut_pays_igst_and_claims_refund():
    r = price(recipient_outside_india=True, payment_in_convertible_forex=True, lut=False)
    assert r["zero_rated"] and r["tax"]["igst"] == "18000.00" and "refund" in r["lines"][0]   # 18% x 1,00,000


@pytest.mark.parametrize("kw", [{"payment_in_convertible_forex": None}, {"payment_in_convertible_forex": False},
                                {"payment_in_convertible_forex": True, "distinct_person": True}])
def test_export_conditions_not_met_needs_review(kw):
    r = price(recipient_outside_india=True, lut=True, **kw)
    assert r["status"] == "needs_review" and r["tax"] is None


def test_sez_supply_is_not_guessed():
    assert price(recipient_gstin=MH, sez=True)["status"] == "needs_review"


# ── invoice validation ────────────────────────────────────────────────────
def invoice(**kw):
    base = dict(supplier_name="Acme IT", supplier_address="Chennai", supplier_gstin=TN, invoice_number="INV/2026/001",
                invoice_date="2026-10-15", description="Software development", sac="998314", total_value="118000",
                taxable_value="100000", tax_rate="18", tax_amount="18000", reverse_charge_flag="N",
                recipient_gstin=MH, recipient_name="Buyer Ltd", recipient_address="Pune", place_of_supply="Maharashtra")
    base.update(kw)
    return base


def test_complete_invoice_is_ok():
    r = ENG.validate_invoice(invoice(), aggregate_turnover=1000000)
    assert r["status"] == "ok" and r["errors"] == [] and r["e_invoice"]["required"] is False


def test_missing_fields_and_bad_serial():
    r = ENG.validate_invoice(invoice(description="", invoice_number="INV/2026/0000000001"), aggregate_turnover=1)
    assert r["status"] == "invalid"
    assert "missing description" in r["errors"] and any("at most 16 characters" in e for e in r["errors"])
    assert any("at most 16" in e for e in ENG.validate_invoice(invoice(invoice_number="A B"), aggregate_turnover=1)["errors"])


def test_inter_state_needs_place_of_supply_with_state():
    r = ENG.validate_invoice(invoice(place_of_supply=None), aggregate_turnover=1)
    assert any("rule 46(n)" in e for e in r["errors"])


def test_unregistered_recipient_details_from_fifty_thousand():
    base = dict(recipient_gstin=None, recipient_name=None, recipient_address=None, taxable_value="49999.99")
    assert ENG.validate_invoice(invoice(**base), aggregate_turnover=1)["status"] == "ok"
    r = ENG.validate_invoice(invoice(**{**base, "taxable_value": "50000"}), aggregate_turnover=1)
    assert r["status"] == "invalid" and "missing recipient_state_code" in " ".join(r["errors"])


def test_export_invoice_needs_endorsement_and_country():
    r = ENG.validate_invoice(invoice(recipient_gstin=None, export=True, place_of_supply="Outside India"), aggregate_turnover=1)
    assert any("country_of_destination" in e for e in r["errors"]) and any("export_endorsement" in e for e in r["errors"])


def test_einvoice_threshold_is_above_five_crore():
    # Aggregate turnover must be MORE than Rs 5 crore (10/2023-CT, from 1 Aug 2023).
    at = ENG.validate_invoice(invoice(), aggregate_turnover=50000000)
    assert at["e_invoice"]["required"] is False and at["status"] == "ok"
    over = ENG.validate_invoice(invoice(), aggregate_turnover=50000001)
    assert over["e_invoice"]["required"] is True and any("IRN and QR" in e for e in over["errors"])
    ok = ENG.validate_invoice(invoice(irn="a" * 64, qr_code="qr"), aggregate_turnover="60000000")
    assert ok["status"] == "ok"


def test_einvoice_needs_review_without_turnover_or_before_the_threshold_date():
    assert ENG.validate_invoice(invoice())["status"] == "needs_review"
    before = ENG.validate_invoice(invoice(invoice_date="2023-07-31"), aggregate_turnover=1)
    assert before["status"] == "needs_review" and before["e_invoice"]["required"] is None


# ── monthly summary ───────────────────────────────────────────────────────
def supply(number, **kw):
    base = dict(supplier_gstin=TN, sac="998314", taxable_value=100000, invoice_date="2026-10-15", invoice_number=number)
    base.update(kw)
    return base


def test_monthly_summary_tables_and_totals():
    supplies = [
        supply("1", recipient_gstin=MH),                                                       # B2B inter: IGST 18,000
        supply("2", recipient_outside_india=True, payment_in_convertible_forex=True, lut=True, taxable_value=200000),
        supply("3", recipient_state_code="29", taxable_value=50000),                           # B2C inter: IGST 9,000
    ]
    s = ENG.monthly_summary(supplies, "2026-10")
    assert s["status"] == "ok"
    assert [r["invoice"] for r in s["gstr1"]["b2b_4A"]] == ["1"] and [r["invoice"] for r in s["gstr1"]["exports_6A"]] == ["2"]
    assert s["gstr1"]["exports_6A"][0]["with_payment_of_igst"] is False
    outward = s["gstr3b"]["3.1(a)_outward_taxable_supplies"]
    # taxable 1,00,000 + 50,000 = 1,50,000 ; IGST 18,000 + 9,000 = 27,000
    assert outward == {"taxable_value": "150000.00", "cgst": "0.00", "sgst": "0.00", "igst": "27000.00"}
    assert s["gstr3b"]["3.1(b)_zero_rated"] == {"taxable_value": "200000.00"}
    assert s["gstr3b"]["3.2_inter_state_to_unregistered_by_place_of_supply"] == {"29": "50000.00"}


def test_monthly_summary_leaves_out_what_needs_review_and_wrong_months(sgst_verified):
    supplies = [supply("1", recipient_gstin=TN2), supply("2", sac="9971", recipient_gstin=MH),
                supply("3", recipient_gstin=MH, invoice_date="2026-09-30")]
    s = ENG.monthly_summary(supplies, "2026-10")
    assert [x["invoice"] for x in s["needs_review"]] == ["2"] and [x["invoice"] for x in s["invalid"]] == ["3"]
    assert s["status"] == "needs_review"
    # only invoice 1 (intra-State, sgst_verified): CGST 9,000 + SGST 9,000
    t = s["gstr3b"]["3.1(a)_outward_taxable_supplies"]
    assert (t["taxable_value"], t["cgst"], t["sgst"], t["igst"]) == ("100000.00", "9000.00", "9000.00", "0.00")


def test_reverse_charge_candidates_are_never_confirmed_or_totalled():
    s = ENG.monthly_summary([], "2026-10", purchases=[{"kind": "director_services", "taxable_value": 100000}])
    rcm = s["gstr3b"]["3.1(d)_inward_reverse_charge"]
    assert s["status"] == "needs_review" and rcm["totals"] is None and rcm["candidates"][0]["confirmed"] is False
    assert "13/2017-CT(R) serial 6" in rcm["candidates"][0]["candidate"]
    assert ENG.rcm_check("office_rent")["candidate"] is None
