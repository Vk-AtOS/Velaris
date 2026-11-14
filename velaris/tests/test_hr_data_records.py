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
