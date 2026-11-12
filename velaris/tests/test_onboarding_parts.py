"""The building blocks: PDF writer/parser, safe templates, crypto and masking, field checks, checklists, retention."""
import os
import stat
from datetime import date
from pathlib import Path

import pytest

from velaris.agentkit import onboarding_checklists as cl
from velaris.agentkit import onboarding_crypto as crypto
from velaris.agentkit import onboarding_esign as es
from velaris.agentkit import onboarding_fields as fields
from velaris.agentkit import onboarding_retention as retention
from velaris.agentkit import onboarding_template as tpl
from velaris.agentkit.onboarding_pdf import PdfError, append_page, build_pdf, parse_pdf, wrap, text_width


# ---- PDF -----------------------------------------------------------------------------------------------------
def test_pdf_reparse_structure_and_text():
    pdf = build_pdf([("h1", "Offer ₹"), ("p", "Hello (world) \\ done"), ("row", ["Basic", "1,000.00", "12,000.00"])], title="T (1)")
    info = parse_pdf(pdf)
    assert pdf.startswith(b"%PDF-1.4") and pdf.rstrip().endswith(b"%%EOF")
    assert info["pages"] == 1 and info["title"] == "T (1)"
    assert "Offer Rs." in info["text"][0] and "Hello (world) \\ done" in info["text"][0]
    assert "12,000.00" in info["text"][0]


def test_pdf_is_deterministic_and_paginates():
    lines = [("p", f"line {i}") for i in range(200)]
    a, b = build_pdf(lines), build_pdf(lines)
    assert a == b and parse_pdf(a)["pages"] >= 3


def test_pdf_wraps_inside_margins():
    for piece in wrap("word " * 200 + "x" * 300, 10.5, 595 - 112):
        assert text_width(piece, 10.5) <= 595 - 112 + 1


def test_pdf_parser_rejects_damage():
    pdf = build_pdf([("p", "x")])
    with pytest.raises(PdfError):
        parse_pdf(b"not a pdf")
    with pytest.raises(PdfError):
        parse_pdf(pdf.replace(b"/Count 1", b"/Count 2"))
    with pytest.raises(PdfError):
        parse_pdf(pdf.replace(b"1 0 obj", b"9 0 obj", 1))         # xref entry no longer points at its object
    with pytest.raises(PdfError):
        parse_pdf(pdf.replace(b"%%EOF", b""))


def test_pdf_append_page_is_incremental_and_chainable():
    pdf = build_pdf([("p", "original")])
    two = append_page(pdf, [("h1", "Evidence"), ("p", "x" * 3000)])
    assert two.startswith(pdf)                                  # original bytes are an exact prefix
    info = parse_pdf(two)
    assert info["pages"] >= 2 and "Evidence" in info["text"][-1] or any("Evidence" in t for t in info["text"])
    three = append_page(two, [("p", "again")])
    assert three.startswith(two) and parse_pdf(three)["pages"] == info["pages"] + 1


def test_pdf_append_refuses_foreign_pdf():
    with pytest.raises(PdfError):
        append_page(b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\nstartxref\n0\n%%EOF\n", [("p", "x")])


# ---- templates ---------------------------------------------------------------------------------------------------
ALLOWED = ("name", "ctc")


def test_template_renders_whitelisted_values():
    assert tpl.render("Hi {name}, {ctc} {{literal}}", {"name": "A", "ctc": 5}, ALLOWED) == "Hi A, 5 {literal}"
    assert tpl.render("<{name}>", {"name": "<b>&"}, ALLOWED, html=True) == "<&lt;b&gt;&amp;>"


@pytest.mark.parametrize("bad", ["{name.__class__}", "{name[0]}", "{name!r}", "{name:>10}", "{0}", "{}", "{unknown}", "{name", "}"])
def test_template_rejects_everything_that_is_not_a_plain_whitelisted_name(bad):
    assert tpl.validate(bad, ALLOWED)
    with pytest.raises(tpl.TemplateError):
        tpl.render(bad, {"name": "x", "ctc": 1}, ALLOWED)


def test_template_missing_and_bad_values():
    with pytest.raises(tpl.TemplateError):
        tpl.render("{name}", {}, ALLOWED)
    for v in (None, True, 1.5, ["x"], object()):
        with pytest.raises(tpl.TemplateError):
            tpl.render("{name}", {"name": v}, ALLOWED)
    with pytest.raises(tpl.TemplateError):
        tpl.render("{name}", {"name": "x" * 5000}, ALLOWED)
    with pytest.raises(tpl.TemplateError):
        tpl.render("", {}, ALLOWED)


def test_template_never_executes_values():
    class Boom:
        def __str__(self):
            raise AssertionError("must not be called")
    with pytest.raises(tpl.TemplateError):
        tpl.render("{name}", {"name": Boom()}, ALLOWED)


# ---- crypto and masking --------------------------------------------------------------------------------------------
def test_seal_roundtrip_and_binding():
    token = crypto.seal(b"ABCDE1234F", "case1:pan")
    assert "ABCDE1234F" not in token
    assert crypto.open_sealed(token, "case1:pan") == b"ABCDE1234F"
    assert crypto.seal(b"ABCDE1234F", "case1:pan") != token          # fresh nonce each time
    with pytest.raises(crypto.SealError):
        crypto.open_sealed(token, "case2:pan")                     # moved to another record
    head, nonce, body = token.split(".")
    flipped = body[:-2] + ("AA" if body[-2:] != "AA" else "BB")
    with pytest.raises(crypto.SealError):
        crypto.open_sealed(f"{head}.{nonce}.{flipped}", "case1:pan")
    for junk in ("", "v1", "v2.a.b", "v1.!!.!!"):
        with pytest.raises(crypto.SealError):
            crypto.open_sealed(junk, "case1:pan")


def test_key_file_is_owner_only():
    crypto.seal(b"x", "a")
    key = Path(os.environ["VELARIS_DATA"]) / "onboarding_field.key"
    assert stat.S_IMODE(key.stat().st_mode) == 0o600 and key.stat().st_size == 32


def test_aadhaar_digest_keeps_last_four_and_a_keyed_hash_only():
    d = crypto.aadhaar_digest("2341 2341 2346")
    assert d["last4"] == "2346" and "234123412346" not in str(d) and len(d["digest"]) == 64
    assert crypto.aadhaar_matches("234123412346", d) and not crypto.aadhaar_matches("234123412347", d)


@pytest.mark.parametrize("kind,good", [("pan", "abcde1234f"), ("ifsc", "hdfc0001234"), ("bank_account", "1234567890"),
                                       ("aadhaar", "2341 2341 2346"), ("uan", "123456789012")])
def test_identifier_normalisation(kind, good):
    assert fields.normalise_identifier(kind, good)


@pytest.mark.parametrize("kind,bad", [("pan", "ABCDE12345"), ("pan", "ABCD1234FF"), ("ifsc", "HDFC1001234"), ("bank_account", "12345"),
                                      ("bank_account", "12345abcde"), ("aadhaar", "234123412345"), ("aadhaar", "123412341234"),
                                      ("aadhaar", "2341"), ("uan", "1"), ("passport", "x")])
def test_identifier_rejection(kind, bad):
    with pytest.raises(ValueError):
        fields.normalise_identifier(kind, bad)
    with pytest.raises(ValueError):
        fields.normalise_identifier("pan", 12345)


def test_masking_keeps_only_the_last_four():
    assert fields.mask("pan", "ABCDE1234F") == "******234F"
    assert fields.mask("aadhaar", "234123412346") == "XXXX XXXX 2346"
    assert fields.mask("bank_account", "123456789012") == "********9012"


def test_forms_validation():
    ok_nom = {"nominees": [{"name": "A", "relation": "spouse", "share_percent": "60"}, {"name": "B", "relation": "child", "share_percent": 40}]}
    assert fields.validate_form("pf_nomination", ok_nom) == []
    assert fields.validate_form("pf_nomination", {"nominees": [{"name": "A", "relation": "x", "share_percent": 50}]})      # not 100
    assert fields.validate_form("pf_nomination", {"nominees": [{"name": "A", "relation": "x", "share_percent": 100, "pan": "x"}]})
    assert fields.validate_form("tax_declaration", {"regime": "weird"})
    assert fields.validate_form("tax_declaration", {"regime": "new", "extra": 1})
    assert fields.validate_form("nope", {})
    assert fields.validate_form("tax_declaration", {"regime": "new"}) == []


# ---- checklists ----------------------------------------------------------------------------------------------------------
def test_every_template_combination_is_consistent():
    for role in [*cl.ROLE_ADDONS, "other"]:
        for loc in [*cl.LOCATION_ADDONS, "other"]:
            assert cl.template_problems(cl.onboarding_items(role, loc)) == []
    assert cl.template_problems(cl.EXIT_BASE) == []
    assert cl.template_problems([cl._i("a", "A", "hr", 0, ("b",)), cl._i("b", "B", "hr", 0, ("a",))]) == ["dependency cycle"]
    assert cl.template_problems([cl._i("a", "A", "hr", 0, ("zz",))])


def test_due_dates_are_relative_to_the_join_date_and_blocking_is_reported():
    tasks = cl.build_tasks(date(2026, 12, 1), cl.onboarding_items("engineering", "chennai"), {"it": "it1"})
    by = {t["key"]: t for t in tasks}
    assert by["confirm_offer_accepted"]["due_date"] == "2026-11-24" and by["orientation"]["due_date"] == "2026-12-01"
    assert by["provision_accounts"]["assignee"] == "it1"
    prog = cl.progress(tasks, date(2026, 11, 20))
    assert prog["completion_percent"] == 0.0 and not prog["complete"]
    blocked = {b["task"]: b for b in prog["blocked"]}
    assert blocked["collect_pan"]["waiting_for"] == ["confirm_offer_accepted"]
    by["confirm_offer_accepted"]["state"] = "done"
    after = cl.progress(tasks, date(2026, 11, 30))
    assert "collect_pan" not in {b["task"] for b in after["blocked"]} and after["completion_percent"] > 0
    assert "confirm_offer_accepted" not in after["overdue"] and "provision_accounts" in after["overdue"]


def test_reminders_are_drafts_for_due_soon_or_overdue_only():
    tasks = cl.build_tasks(date(2026, 12, 1), cl.onboarding_items("other", "other"))
    for t in tasks:
        if t["key"] == "confirm_offer_accepted":
            t["state"] = "done"
    r = cl.reminders(tasks, date(2026, 11, 27), within_days=2)
    keys = {x["task"] for x in r}
    assert "collect_pan" in keys and "tax_declaration" not in keys          # due 2026-11-26 (overdue) vs 2026-12-08
    assert all(x["state"] in ("ready", "overdue") for x in r)


# ---- retention -----------------------------------------------------------------------------------------------------------
def test_statutory_classes_are_held_and_flagged_because_nothing_is_verified():
    on = date(2026, 11, 13)
    assert retention.STATUTORY and all(not retention.PARAMS[f"retention:{c}"][0].verified for c in retention.STATUTORY)
    for c in retention.STATUTORY:
        d = retention.decide(c, date(1990, 1, 1), on)            # even an ancient record is not erased on an unverified period
        assert d["action"] == "hold" and d["status"] == "needs_review" and d["retain_until"] is None
    assert retention.decide("no_such_class", None, on)["action"] == "hold"


def test_policy_classes_erase_and_a_verified_row_would_be_used(monkeypatch):
    on = date(2026, 11, 13)
    assert retention.decide("candidate_unsuccessful", None, on)["action"] == "erase"
    from velaris.agents.PAYROLL_ENGINE.registry import Entry
    monkeypatch.setitem(retention.PARAMS, "retention:payroll_records", [Entry(
        {"kind": "statutory", "years": 8, "from": "x"}, date(2000, 1, 1), "https://example.gov.in/rule", date(2026, 11, 13), True, "test row")])
    assert retention.decide("payroll_records", date(2015, 3, 31), on) ["action"] == "erase"
    held = retention.decide("payroll_records", date(2022, 3, 31), on)
    assert held["action"] == "hold" and held["status"] == "ok" and held["retain_until"] == "2030-03-28"
    assert retention.decide("payroll_records", None, on)["status"] == "needs_review"


def test_retention_table_marks_statutory_rows_needs_review():
    rows = {r["class"]: r for r in retention.table(date(2026, 11, 13))}
    assert rows["payroll_records"]["needs_review"] and not rows["candidate_unsuccessful"]["needs_review"]


def test_seal_chain_changes_when_anything_changes():
    ev = [{"a": 1}, {"a": 2}]
    h = [es.evidence_hash(e) for e in ev]
    base = es.chain("d" * 64, h)
    assert len(base) == 3 and base != es.chain("e" * 64, h) and base != es.chain("d" * 64, h[::-1])
    assert base != es.chain("d" * 64, [es.evidence_hash({"a": 1}), es.evidence_hash({"a": 3})])
