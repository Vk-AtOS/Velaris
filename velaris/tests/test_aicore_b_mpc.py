"""MPC family: record cleaning, multi-source fusion, and the two together."""
from velaris.agents.MPC_CORE.main import MPC_COREAgent
from velaris.agents.MPC_FUSION.main import MPC_FUSIONAgent
from velaris.agents.MPC_PREPROC.main import MPC_PREPROCAgent


def test_preproc_normalises_keys_numbers_dates_and_whitespace():
    r = MPC_PREPROCAgent().preprocess(
        {"Total Amount": " 1,20,000.50 ", "invoiceDate": "5/11/2026", "Vendor  Name": "  Acme​   Ltd ",
         "Notes": "", "phone": "9876543210", "pin": "600042", "PIN code": "060004", "qty": "12"})
    assert r["status"] == "ok"
    assert r["record"] == {"total_amount": 120000.5, "invoice_date": "2026-11-05", "vendor_name": "Acme Ltd",
                           "phone": "9876543210", "pin": "600042", "pin_code": "060004", "qty": 12.0}
    assert r["stats"]["empty_dropped"] == 1 and r["stats"]["dates_normalised"] == 1


def test_preproc_dedupes_lists_and_redacts_on_request():
    pre = MPC_PREPROCAgent()
    r = pre.preprocess([{"Name": "Asha "}, {"name": "Asha"}, {"name": "Ravi", "tags": ["", "x"]}])
    assert r["records"] == [{"name": "Asha"}, {"name": "Ravi", "tags": ["x"]}]
    assert r["stats"]["duplicates_removed"] == 1
    masked = pre.preprocess({"contact": "mail ravi@example.com", "nested": {"pan": "ABCDE1234F"}}, redact=True)
    assert masked["record"] == {"contact": "mail [EMAIL]", "nested": {"pan": "[PAN]"}}
    assert masked["stats"]["values_redacted"] == 2
    assert pre.preprocess({"contact": "ravi@example.com"})["record"]["contact"] == "ravi@example.com"


def test_preproc_bad_input():
    pre = MPC_PREPROCAgent()
    for bad in (None, "a record", [], [{"a": 1}, "b"], 7):
        r = pre.preprocess(bad)
        assert r["status"] == "invalid_input" and r["records"] == []


def test_fusion_prefers_trust_then_recency_and_reports_conflicts():
    r = MPC_FUSIONAgent().fuse([
        {"source": "crm", "record": {"name": "Acme Ltd", "city": "Chennai", "phone": "111"}, "trust": 0.6, "ts": 10},
        {"source": "erp", "record": {"name": "Acme Ltd", "city": "Coimbatore", "gstin": "33A"}, "trust": 0.9, "ts": 5},
        {"source": "web", "record": {"city": "Chennai", "phone": "222"}, "trust": 0.6, "ts": 20},
    ])
    assert r["record"] == {"name": "Acme Ltd", "city": "Coimbatore", "gstin": "33A", "phone": "222"}
    assert r["provenance"]["city"] == "erp" and r["provenance"]["phone"] == "web"     # trust; then recency
    assert [c["field"] for c in r["conflicts"]] == ["city", "phone"]
    assert len(r["conflicts"][0]["candidates"]) == 3 and r["agreement"] == 0.5


def test_fusion_majority_breaks_a_full_tie_and_agreeing_sources_have_no_conflict():
    f = MPC_FUSIONAgent()
    tie = f.fuse([{"source": "a", "record": {"x": 1}}, {"source": "b", "record": {"x": 2}},
                  {"source": "c", "record": {"x": 2}}])
    assert tie["record"]["x"] == 2 and tie["provenance"]["x"] == "b"
    same = f.fuse([{"source": "a", "record": {"x": 1, "y": None}}, {"source": "b", "record": {"x": 1}}])
    assert same["conflicts"] == [] and same["agreement"] == 1.0 and "y" not in same["record"]


def test_fusion_bad_input():
    f = MPC_FUSIONAgent()
    assert f.fuse([])["status"] == "invalid_input"
    assert f.fuse("sources")["status"] == "invalid_input"
    assert f.fuse([{"source": "a"}])["status"] == "invalid_input"
    assert f.fuse([{"source": "a", "record": {}, "trust": 2}])["status"] == "invalid_input"
    assert f.fuse([{"source": "a", "record": {}}, {"source": "a", "record": {}}])["status"] == "invalid_input"
    assert f.fuse([{"source": "a", "record": {}}])["agreement"] is None


def test_core_cleaning_removes_false_conflicts():
    raw = [{"source": "crm", "record": {"Total Amount": "1,200", "Vendor": "Acme  Ltd"}, "trust": 0.5},
           {"source": "erp", "record": {"total_amount": 1200.0, "vendor": "Acme Ltd"}, "trust": 0.8}]
    assert len(MPC_FUSIONAgent().fuse(raw)["conflicts"]) == 0 and len(MPC_FUSIONAgent().fuse(raw)["record"]) == 4
    r = MPC_COREAgent().run(raw)
    assert r["status"] == "ok" and r["record"] == {"total_amount": 1200.0, "vendor": "Acme Ltd"}
    assert r["conflicts"] == [] and r["cleaning"]["numbers_parsed"] == 1 and r["cleaning"]["keys_renamed"] == 2


def test_core_real_conflict_survives_cleaning_and_bad_input():
    core = MPC_COREAgent()
    r = core.run([{"source": "a", "record": {"Amount": "100"}, "trust": 0.2},
                  {"source": "b", "record": {"amount": "150"}, "trust": 0.9}])
    assert r["record"] == {"amount": 150.0} and r["conflicts"][0]["field"] == "amount"
    assert core.run([])["status"] == "invalid_input"
    assert core.run([{"source": "a", "record": "text"}])["status"] == "invalid_input"
    assert core.run(None)["record"] is None


def test_identifier_named_fields_stay_text():
    """KAN-106: a PIN/ZIP/phone is an identifier, not a quantity, with or without redact."""
    from velaris.agents.MPC_PREPROC.main import MPC_PREPROCAgent
    r = MPC_PREPROCAgent().preprocess({"PIN": "600042", "zip_code": "94105", "Phone": "12345", "qty": "600042"})["record"]
    assert r == {"pin": "600042", "zip_code": "94105", "phone": "12345", "qty": 600042.0}


def test_optima_normalize_refuses_non_finite_metrics():
    import pytest
    from velaris.agents.OPTIMA.main import OptimaAgent as Optima
    with pytest.raises(ValueError):
        Optima().metric_normalize({"a": float("nan"), "b": 2.0})
    with pytest.raises(ValueError):
        Optima().metric_normalize({"a": float("inf"), "b": 2.0})
