"""Sensitive reads need a caller: own record, or a role that may read others'. Every decision is traced."""
import threading

import pytest

from velaris.core import access
from velaris.core.access import AccessDenied, Caller, acting_as, authorize_read, current_caller
from velaris.intel import trace

ASHA = Caller(id="u-asha", org="kf", roles=frozenset(), employee_id="E1")
HR = Caller(id="u-hr", org="kf", roles=frozenset({"hr_admin"}))
PAYROLL = Caller(id="u-pay", org="kf", roles=frozenset({"payroll_admin"}))
OTHER_ORG_HR = Caller(id="u-x", org="other", roles=frozenset({"hr_admin"}))
PAYSLIP = {"gross_pay": 90000, "net_pay": 70000, "deductions": [{"name": "EPF", "amount": 1800}]}


@pytest.fixture(autouse=True)
def _data(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))


def decisions():
    return [(e["action"].split(".")[1], e["payload"]["caller"], e["payload"]["subject"], e["payload"]["reason"])
            for e in trace.entries() if e["actor"] == "access"]


@pytest.mark.parametrize("caller, category, subject, org, allowed", [
    (None, "pay", "E1", None, False),                    # nobody
    (ASHA, "pay", "E1", None, True),                     # own record
    (ASHA, "pay", "E2", None, False),                    # someone else's
    (ASHA, "pay", None, None, False),                    # everyone's
    (HR, "pay", "E2", None, True),
    (HR, "bank", "E2", None, False),                     # HR may not read bank details
    (PAYROLL, "bank", "E2", None, True),
    (PAYROLL, "health", "E2", None, False),
    (HR, "pay", "E2", "kf", True),
    (OTHER_ORG_HR, "pay", "E2", "kf", False),            # role in another organisation
    (ASHA, "E1", "E1", None, False),                     # unknown category, even for own record
    (HR, "salary", "E2", None, False),
])
def test_decide_is_deny_by_default(caller, category, subject, org, allowed):
    assert access.decide(caller, category, subject, org)[0] is allowed


def test_every_decision_is_traced_and_denials_raise():
    assert authorize_read("pay", "E1", agent="T", caller=ASHA) is ASHA
    with pytest.raises(AccessDenied, match="no caller identity"):
        authorize_read("pay", "E1", agent="T")
    with pytest.raises(AccessDenied):
        authorize_read("pay", "E2", agent="T", caller=ASHA)
    assert decisions() == [("granted", "u-asha", "E1", "own record"),
                           ("denied", None, "E1", "no caller identity"),
                           ("denied", "u-asha", "E2",
                            "not the caller's own record and no role that may read other people's")]
    assert trace.verify()["ok"]


def test_caller_travels_in_context_and_never_leaks_between_threads():
    with acting_as(HR):
        assert current_caller() is HR
        authorize_read("pay", "E2", agent="T")
        with acting_as(None):                            # an inner block can drop the identity
            with pytest.raises(AccessDenied):
                authorize_read("pay", "E2", agent="T")
        seen = []
        t = threading.Thread(target=lambda: seen.append(current_caller()))
        t.start()
        t.join()
        assert seen == [None]                            # a new thread does not inherit it
    assert current_caller() is None


def test_replacement_policy_is_one_function_and_cannot_fail_open(monkeypatch):
    monkeypatch.setattr(access, "decide", lambda c, cat, s, o: (True, "external says yes"))
    authorize_read("bank", "E9", agent="T", caller=ASHA)
    for wrong in ((None, "unsure"), ("yes", "truthy is not True"), (1, "one")):
        monkeypatch.setattr(access, "decide", lambda c, cat, s, o, w=wrong: w)
        with pytest.raises(AccessDenied):
            authorize_read("bank", "E9", agent="T", caller=ASHA)


def test_bad_caller_is_rejected():
    for kw in ({"id": "", "org": "kf"}, {"id": "a", "org": " "}, {"id": "a", "org": "kf", "roles": "hr_admin"}):
        with pytest.raises(ValueError):
            Caller(**kw)


# ── the agents ───────────────────────────────────────────────────────────────
class FakeZoho:
    def __init__(self):
        self.calls = []

    def get(self, url, params=None):
        self.calls.append(url)
        if "payslips" in url:
            return {"payslip": PAYSLIP}
        if "ytd" in url:
            return {"ytd_summary": {"net": 1}}
        if "getRecords" in url and "employee" in url:
            return {"response": {"result": [{"EmployeeID": "E1", "PAN": "ABCDE1234F"}]}}
        return {"response": {"result": []}}


def metrics_engine():
    from velaris.agents.EMPLOYEE_METRICS_ENGINE.main import EmployeeMetricsEngine
    engine = EmployeeMetricsEngine()                     # no config: used to crash in the connectors
    zoho = FakeZoho()
    engine.people.zoho = engine.payroll.zoho = engine.projects.zoho = zoho
    return engine, zoho


def test_profile_pay_needs_own_record_or_a_role():
    engine, zoho = metrics_engine()
    anonymous = engine.get_employee_profile("E1", 3, 2026)
    assert anonymous["payroll"] == {"withheld": "no caller identity"}
    assert not any("payslips" in u for u in zoho.calls)  # refused before anything was fetched
    other = engine.get_employee_profile("E2", 3, 2026, caller=ASHA)
    assert "withheld" in other["payroll"] and "gross" not in other["payroll"]
    own = engine.get_employee_profile("E1", 3, 2026, caller=ASHA)
    assert own["payroll"]["gross"] == 90000 and own["payroll"]["statutory"] == {"EPF": 1800}
    with acting_as(HR):
        assert engine.get_employee_profile("E2", 3, 2026)["payroll"]["net"] == 70000
    assert [d[0] for d in decisions()] == ["denied", "denied", "granted", "granted", "granted", "granted"]


def test_scorecard_reads_no_pay_and_needs_no_pay_permission():
    engine, zoho = metrics_engine()
    assert [s["employee_id"] for s in engine.get_team_scorecard(["E1", "E2"], 3, 2026)] == ["E1", "E2"]
    assert not any("payslips" in u for u in zoho.calls) and decisions() == []


def test_payroll_connector_engine_and_people_list_are_gated():
    from velaris.agents.PAYROLL_ENGINE.main import PayrollEngine
    from velaris.agents.ZOHO_PEOPLE.main import ZohoPeopleConnector
    engine = PayrollEngine({"zoho_enabled": True})
    engine._zoho.zoho = FakeZoho()
    for call in (lambda c: engine.get_payslip("E2", 2026, 3, caller=c),
                 lambda c: engine.get_ytd_summary("E2", 2026, caller=c),
                 lambda c: engine.get_statutory_deductions("E2", 2026, 3, caller=c),
                 lambda c: engine._zoho.get_cost_to_company("E2", 2026, 3, caller=c)):
        with pytest.raises(AccessDenied):
            call(None)
        with pytest.raises(AccessDenied):
            call(ASHA)
        call(PAYROLL)
    people = ZohoPeopleConnector()
    people.zoho = FakeZoho()
    with pytest.raises(AccessDenied):
        people.get_employees(caller=PAYROLL)             # identity records are HR's, not payroll's
    assert people.get_employees(caller=HR)[0]["PAN"] == "ABCDE1234F"


def test_leave_history_is_health_data(tmp_path):
    from velaris.agents.LEAVE_MANAGEMENT import main as lm
    lm._DB = str(tmp_path / "leaves.db")
    leave = lm.LeaveManagement()
    with pytest.raises(AccessDenied):
        leave.seed_balances("E1", 2026)                  # no caller
    with acting_as(HR):
        leave.seed_balances("E1", 2026)
        leave.apply("E1", "sick", "2026-11-16", "2026-11-17", reason="flu")
    with pytest.raises(AccessDenied):
        leave.employee_history("E1")
    with pytest.raises(AccessDenied):
        leave.employee_history("E1", caller=Caller(id="u-b", org="kf", employee_id="E2"))
    assert leave.employee_history("E1", caller=ASHA)[0]["reason"] == "flu"
    with pytest.raises(AccessDenied):
        leave.pending_approvals(caller=ASHA)
    assert len(leave.pending_approvals(caller=HR)) == 1


def test_backend_dispatch_carries_the_caller_to_the_agent(monkeypatch):
    from velaris.agents.ZOHO_PAYROLL.main import ZohoPayrollConnector
    from velaris.backend.engine import backend
    monkeypatch.setattr(ZohoPayrollConnector, "_payslip", lambda self, e, y, m: PAYSLIP)
    params = {"employee_id": "E1", "year": 2026, "month": 3}
    assert backend.run("ZOHO_PAYROLL", "get_payslip", params, caller=ASHA) == PAYSLIP
    with pytest.raises(AccessDenied):
        backend.run("ZOHO_PAYROLL", "get_payslip", params)
    with acting_as(HR):                                  # dispatch replaces, never inherits, the caller
        with pytest.raises(AccessDenied):
            backend.run("ZOHO_PAYROLL", "get_payslip", params, caller=None)
    for bad in ("_payslip", "__init__", "not a name"):
        with pytest.raises(PermissionError):
            backend.run("ZOHO_PAYROLL", bad, params, caller=HR)


def test_backend_runs_async_methods_as_the_caller(monkeypatch):
    import types
    from velaris.backend.engine import backend

    class AsyncAgent:
        async def read(self, employee_id):
            return authorize_read("pay", employee_id, agent="ASYNC").id

    module = types.ModuleType("fake_async_agent")
    AsyncAgent.__module__ = module.__name__
    module.AsyncAgent = AsyncAgent
    monkeypatch.setattr(backend.router, "get_agent", lambda name: module)
    assert backend.run("ASYNC", "read", {"employee_id": "E1"}, caller=ASHA) == "u-asha"
    with pytest.raises(AccessDenied):
        backend.run("ASYNC", "read", {"employee_id": "E2"}, caller=ASHA)
