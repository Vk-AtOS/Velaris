"""One Velaris deployment = one organisation (VELARIS_ORG); leave self-approval by employee id."""
import importlib.util
import os
import sys

import pytest

from velaris.core import access
from velaris.core.access import Caller, acting_as

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
ACME = Caller(id="u1", org="acme", roles=frozenset({"hr_admin"}), employee_id="E1")
GLOBEX = Caller(id="u9", org="globex", roles=frozenset({"hr_admin"}), employee_id="E9")


def _load(name, *parts):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, *parts, "main.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod                      # dataclasses look the module up by name
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(autouse=True)
def _env(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    monkeypatch.setenv("VELARIS_ORG", "acme")


def test_access_denies_another_organisation_only_when_configured(monkeypatch):
    assert access.decide(GLOBEX, "identity", None)[0] is False
    assert access.decide(ACME, "identity", None)[0] is True
    with acting_as(GLOBEX):
        _who, refusal = access.check_caller("X", "change")
    assert refusal and refusal["status"] == "denied"
    with pytest.raises(access.AccessDenied):
        access.authorize_read("identity", None, agent="X", caller=GLOBEX)
    monkeypatch.setattr(access, "decide", lambda *a: (True, "replacement says yes"))   # e.g. Prime
    with pytest.raises(access.AccessDenied):
        access.authorize_read("identity", None, agent="X", caller=GLOBEX)
    monkeypatch.delenv("VELARIS_ORG")
    assert access.org_denied(GLOBEX) is None                                          # dev/offline unchanged


def test_itsm_tickets_are_stamped_and_hidden_from_other_organisations():
    itsm = _load("itsm_main", "departments", "it_infrastructure", "ITSM_ENGINE")
    t = itsm.Ticket("T1", "network", "high", "major", "high", "router", {})
    with acting_as(ACME):
        assert itsm.ITSMEngine().open_ticket(t)["ticket"]["org"] == "acme"
    e = itsm.ITSMEngine()
    with acting_as(GLOBEX):
        assert e.get_ticket("T1")["status"] == "unknown_ticket"
        assert e.sla_status("T1")["status"] == "unknown_ticket"
        assert e.list_tickets() == []
        assert e.transition("T1", "assigned")["status"] == "denied"
    with acting_as(None):
        assert e.list_tickets() == []                                                  # fail closed
    with acting_as(ACME):
        assert [x["ticket_id"] for x in e.list_tickets()] == ["T1"]
        assert e.transition("T1", "assigned")["status"] == "denied"                    # moving tickets needs infra_admin
    with acting_as(Caller("u-ops", "acme", frozenset({"infra_admin"}))):
        assert e.transition("T1", "assigned")["status"] == "ok"


def test_leave_org_and_self_approval_by_employee_id(tmp_path, monkeypatch):
    lm = _load("leave_main2", "departments", "hr", "LEAVE_MANAGEMENT")
    monkeypatch.setattr(lm, "_DB", str(tmp_path / "leaves.db"))
    leave = lm.LeaveManagement()
    manager = Caller(id="u1", org="acme", roles=frozenset({"hr_admin"}), employee_id="E1")
    other = Caller(id="u2", org="acme", roles=frozenset({"hr_admin"}), employee_id="E2")
    with acting_as(manager):
        leave.seed_balances("E1", 2026)
        a = leave.apply("E1", "casual", "2026-11-16", "2026-11-17")["id"]
        b = leave.apply("E1", "casual", "2026-11-18", "2026-11-19")["id"]
        # the request names E1 (employee id), the reviewer is u1 (user id): still the same person
        assert leave.approve(a, "u1")["error"] == "self_approval_not_allowed"
        assert leave.reject(a, "u1")["error"] == "self_approval_not_allowed"
        assert leave.approve(a, "someone-else")["error"] == "reviewer_must_be_caller"
    with acting_as(GLOBEX):                                                            # another organisation
        assert leave.approve(a, "u9")["error"] == "access_denied"
    with acting_as(other):
        done = leave.approve(a, "u2")
        assert done["status"] == "approved" and done["reviewed_by_employee"] == "E2"
        assert [r["id"] for r in leave.pending_approvals()] == [b]
    # a request stamped with another organisation is invisible to approval even for a matching caller
    conn = lm._db()
    conn.execute("UPDATE leave_requests SET org='globex' WHERE id=?", (b,))
    conn.commit()
    conn.close()
    with acting_as(other):
        assert leave.approve(b, "u2")["error"] == "not_found"
        assert leave.pending_approvals() == []
