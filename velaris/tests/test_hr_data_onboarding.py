"""KAN-107: ONBOARDING_FLOW stores nothing while blocked or after the case is closed, and erasure follows retention."""
import base64
import os
from pathlib import Path

from velaris.agents.ONBOARDING_FLOW import main as flow_mod
from velaris.core.access import acting_as
from velaris.tests.onboarding_helpers import ORG
from velaris.tests.test_onboarding_flow import EMP, HR1, PAN, make, start, unblock

DOC = base64.b64encode(b"scan").decode()


def _docs():
    return list((Path(os.environ["VELARIS_DATA"]) / "agents" / "ONBOARDING_FLOW" / "docs").glob("*"))


def test_document_refused_and_no_file_written_while_blocked():
    o, _ = make()
    cid = start(o)
    with acting_as(EMP):
        assert o.collect_document(cid, "identity_proof", "id.pdf", DOC)["status"] == "blocked"
    assert _docs() == []
    unblock(o, cid)
    with acting_as(EMP):
        assert o.collect_document(cid, "identity_proof", "id.pdf", DOC)["status"] == "ok"
    assert len(_docs()) == 1


def test_closed_case_accepts_no_identifier_form_or_document():
    o, _ = make()
    cid = start(o)
    unblock(o, cid)
    with acting_as(HR1):
        assert o.cancel_case(cid, "withdrew")["status"] == "ok"
    with acting_as(EMP):
        assert o.submit_identifier(cid, "pan", PAN)["status"] == "conflict"
        assert o.submit_form(cid, "emergency_contact", {"name": "R", "relation": "father", "phone": "9"})["status"] == "conflict"
        assert o.collect_document(cid, "identity_proof", "id.pdf", DOC)["status"] == "conflict"
    assert _docs() == []


def test_dsr_erase_keeps_documents_when_retention_says_hold(monkeypatch):
    o, _ = make()
    cid = start(o)
    unblock(o, cid)
    with acting_as(EMP):
        o.collect_document(cid, "identity_proof", "id.pdf", DOC)
    real = flow_mod.retention.decide
    monkeypatch.setattr(flow_mod.retention, "decide", lambda cls, a, on: (
        {"class": cls, "action": "hold", "status": "needs_review", "reason": "x", "retain_until": None} if cls == "onboarding_documents" else real(cls, a, on)))
    with acting_as(HR1):
        res = o.dsr_erase(ORG, "E7")
    assert any("documents" in h["what"] for h in res["held"]) and not any("documents" in e for e in res["erased"])
    assert len(_docs()) == 1
