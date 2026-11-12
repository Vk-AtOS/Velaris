"""EAC family: compliance controls, the audit view of the trace, and the assessment that joins them."""
import json

import pytest

from velaris.agents.EAC_AUDIT.main import EAC_AUDITAgent
from velaris.agents.EAC_COMPLIANCE.main import EAC_COMPLIANCEAgent
from velaris.agents.EAC_CORE.main import EAC_COREAgent

PO = {"id": "PO-01", "framework": "procurement", "severity": "high",
      "when": [{"field": "amount", "op": ">", "value": 50000}],
      "require": [{"field": "purchase_order", "op": "exists"}]}
GST = {"id": "GST-01", "framework": "tax", "field": "gstin", "op": "matches", "value": r"^\d{2}[A-Z]{5}\d{4}"}


@pytest.fixture(autouse=True)
def _data(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    return tmp_path


def test_compliance_controls_persist_and_decide():
    c = EAC_COMPLIANCEAgent()
    assert c.add_control(PO)["status"] == "ok" and c.add_control(GST)["status"] == "ok"
    c = EAC_COMPLIANCEAgent()                                  # restart
    assert [x["id"] for x in c.list_controls()] == ["GST-01", "PO-01"]
    good = c.evaluate({"amount": 80000, "purchase_order": "PO-9", "gstin": "33ABCDE1234F1Z5"})
    assert good["compliant"] is True and good["checked"] == 2 and good["pass_rate"] == 1.0
    bad = c.evaluate({"amount": 80000, "gstin": "33ABCDE1234F1Z5"})
    assert bad["compliant"] is False and [v["id"] for v in bad["violations"]] == ["PO-01"]
    assert bad["violations"][0]["severity"] == "high" and bad["pass_rate"] == 0.5


def test_compliance_framework_filter_and_conditional_skip():
    c = EAC_COMPLIANCEAgent()
    c.add_control(PO)
    c.add_control(GST)
    small = c.evaluate({"amount": 100}, framework="procurement")     # the control does not apply
    assert small["compliant"] is True and small["checked"] == 0 and small["skipped"] == ["PO-01"]
    assert c.remove_control("PO-01")["status"] == "ok" and c.remove_control("PO-01")["status"] == "not_found"


def test_compliance_fails_closed():
    c = EAC_COMPLIANCEAgent()
    assert c.evaluate({"amount": 1})["status"] == "no_controls"
    assert c.evaluate({"amount": 1})["compliant"] is False
    assert c.evaluate("an invoice", [PO])["status"] == "invalid_input"
    assert c.add_control({"id": "x", "field": "a", "op": "between", "value": 1})["status"] == "invalid_input"
    assert c.add_control({"field": "a", "op": "exists"})["status"] == "invalid_input"
    broken = c.evaluate({"a": 1}, [{"id": "x", "field": "a", "op": "matches", "value": "("}])
    assert broken["status"] == "invalid_controls" and broken["compliant"] is False
    missing = c.evaluate({}, [{"id": "x", "field": "a", "op": "!=", "value": 1}])
    assert missing["compliant"] is False                       # an absent field satisfies nothing


def test_audit_records_finds_and_masks_identifiers():
    a = EAC_AUDITAgent()
    first = a.record("exception_granted", {"subject": "INV-7", "by": "ravi@example.com"}, actor="finance")
    assert first["status"] == "ok" and len(first["hash"]) == 64
    a.record("assessment", {"subject": "INV-8"})
    found = a.find(event="exception_granted")
    assert found["total"] == 1 and found["events"][0]["payload"]["by"] == "[EMAIL]"
    assert a.find(actor="finance")["total"] == 1 and a.find(since=first["ts"] + 3600)["total"] == 0
    assert a.summary()["counts"] == {"exception_granted": 1, "assessment": 1}
    assert a.verify()["intact"] is True


def test_audit_detects_tampering(_data):
    a = EAC_AUDITAgent()
    a.record("assessment", {"subject": "INV-1", "compliant": False})
    a.record("assessment", {"subject": "INV-2", "compliant": True})
    path = _data / "trace.jsonl"
    lines = path.read_text().splitlines()
    doctored = json.loads(lines[0])
    doctored["payload"]["compliant"] = True
    path.write_text("\n".join([json.dumps(doctored, sort_keys=True)] + lines[1:]) + "\n")
    v = a.verify()
    assert v["intact"] is False and v["status"] == "tampered" and v["broken_at"] == 1


def test_audit_bad_input():
    a = EAC_AUDITAgent()
    assert a.record("", {})["status"] == "invalid_input"
    assert a.record("x", {"f": object()})["status"] == "invalid_input"
    assert a.record("x", "details")["status"] == "invalid_input"
    assert a.find(limit=0)["status"] == "invalid_input"
    assert a.find(since="yesterday")["status"] == "invalid_input"
    assert a.find()["events"] == []                             # an empty trail is not an error


def test_core_assessment_is_evaluated_and_audited():
    core = EAC_COREAgent()
    core.compliance.add_control(PO)
    r = core.assess("INV-42", {"amount": 90000})
    assert r["compliant"] is False and r["subject"] == "INV-42" and len(r["audit_hash"]) == 64
    core.assess("INV-42", {"amount": 90000, "purchase_order": "PO-3"})
    core.assess("INV-43", {"amount": 5})
    history = EAC_COREAgent().history("INV-42")["assessments"]
    assert [h["compliant"] for h in history] == [False, True]
    assert history[0]["violations"] == ["PO-01"]


def test_core_without_controls_and_bad_subject():
    core = EAC_COREAgent()
    r = core.assess("INV-1", {"amount": 1})
    assert r["status"] == "no_controls" and r["compliant"] is False and "audit_hash" in r
    assert core.assess("", {"amount": 1})["status"] == "invalid_input"
    assert core.history("nobody")["assessments"] == []


def test_core_unrecorded_assessment_does_not_count(monkeypatch):
    core = EAC_COREAgent()
    monkeypatch.setattr(core.audit, "record", lambda *a, **k: {"status": "storage_error", "reason": "disk"})
    r = core.assess("INV-1", {"amount": 1}, controls=[{"id": "c", "field": "amount", "op": "exists"}])
    assert r["status"] == "audit_failed" and r["compliant"] is False
