"""KAN-107 / KAN-96: EMPLOYEE_RECORDS conversion needs a verified accepted offer; export masks contact details; erasure is complete and reported."""
from velaris.agents.EMPLOYEE_RECORDS.main import EmployeeRecords
from velaris.core.access import acting_as
from velaris.tests.onboarding_helpers import FakeOffers, HR1, Clock


def test_conversion_refused_without_offer_id_or_without_an_offer_view():
    er = EmployeeRecords({"clock": Clock(), "offers": FakeOffers("accepted")})
    with acting_as(HR1):
        assert er.propose_conversion("A1", "d", "x", "m", "2026-12-01", name="N", email="n@x.in")["status"] == "conflict"
    er = EmployeeRecords({"clock": Clock()})
    with acting_as(HR1):
        assert er.propose_conversion("A1", "d", "x", "m", "2026-12-01", offer_id="o1", name="N", email="n@x.in")["status"] == "not_configured"
        assert er.propose_conversion("A1", "d", "x", "m", "2026-12-01", name="N", email="n@x.in")["status"] == "conflict"


# ---- erasure reaches every store of the subject, and says what it did -----------------------------------------------------
def _offer(oid, status, email="asha@example.in", app="APP-1"):
    return {"id": oid, "org": "acme", "status": status, "candidate": {"name": "Asha Raman", "email": email, "application_id": app, "consent": None},
            "terms": {"role_title": "Engineer", "join_date": "2026-12-01", "manager_name": "Boss"}, "sent_at": None, "response": None}


def _request(rid, status, email="asha@example.in"):
    return {"id": rid, "org": "acme", "title": "Offer", "status": status, "document_sha256": "0" * 64, "document_ref": None,
            "signers": [{"id": "s1", "name": "Asha Raman", "email": email, "state": "signed", "phone": "9000000000", "evidence": {"x": 1},
                         "token_sha256": None}]}


def test_erase_subject_reaches_offers_and_esign_and_reports_what_was_erased_and_held():
    from velaris.tests.test_onboarding_records import exited_employee, make
    er, pol, flow, clock, _ = make()
    emp, _cid = exited_employee(er, flow, pol, clock)
    offers = [p for p in er.participants if type(p).__name__ == "OfferLetters"][0]
    esign = [p for p in er.participants if type(p).__name__ == "Esign"][0]
    offers.store.put("offers", _offer("ofr-declined", "declined"))
    offers.store.put("offers", _offer("ofr-accepted", "accepted"))
    offers.store.put("offers", _offer("ofr-other", "declined", email="someone@else.in", app="APP-9"))
    esign.store.put("requests", _request("sig-voided", "voided"))
    esign.store.put("requests", _request("sig-sealed", "sealed"))
    with acting_as(HR1):
        res = er.erase_subject(emp, "DSR-1")
    assert res["status"] == "ok" and res["complete"] is True and {"OfferLetters", "Esign"} <= set(res["stores_covered"])
    assert any("ofr-declined" in x for x in res["erased"]) and any("sig-voided" in x for x in res["erased"])
    held = {h["what"] for h in res["held"]}
    assert {"offer:ofr-accepted", "esign:sig-sealed"} <= held
    from velaris.core.access import Caller
    stored = offers.store.state.load()["records"]["offers"]
    assert stored["acme:ofr-declined"]["candidate"]["email"] == "erased" and stored["acme:ofr-accepted"]["candidate"]["email"] == "asha@example.in"
    assert stored["acme:ofr-other"]["candidate"]["email"] == "someone@else.in"            # someone else's offer is untouched
    reqs = esign.store.state.load()["records"]["requests"]
    assert reqs["acme:sig-voided"]["signers"][0]["email"] == "erased" and reqs["acme:sig-sealed"]["signers"][0]["email"] == "asha@example.in"


def test_a_failing_store_is_reported_not_hidden():
    from velaris.tests.test_onboarding_records import exited_employee, make
    er, pol, flow, clock, _ = make()
    emp, _cid = exited_employee(er, flow, pol, clock)

    class Broken:
        def dsr_erase(self, *a, **k):
            raise RuntimeError("disk")
    er.participants.append(Broken())
    with acting_as(HR1):
        res = er.erase_subject(emp, "DSR-2")
    assert res["status"] == "ok" and res["complete"] is False and res["failed_stores"] == ["Broken"]


def test_export_masks_contact_details():
    from velaris.tests.test_onboarding_records import hire, make
    er, *_ = make()
    emp = hire(er)
    from velaris.tests.onboarding_helpers import person
    with acting_as(HR1):
        out = er.export_subject(emp)["export"]["employee"]
    assert out["email"] == "a***@example.in" and out["phone"].endswith("0000") and "asha@example.in" not in str(out)
