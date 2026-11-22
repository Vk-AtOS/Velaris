"""Behaviour of twelve previously untested agents (MCD ... LEGAL_INTELLIGENCE_ENGINE).

No network, no model: collaborators that would reach Zoho or the web are replaced by
in-memory fakes; the agent under test is always the real one.
"""
from importlib import import_module

import pytest

from velaris.core.access import GOVERNANCE_ADMIN, AccessDenied, Caller, acting_as


@pytest.fixture(autouse=True)
def _data(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))


def cls(agent, name):
    return getattr(import_module(f"velaris.agents.{agent}.main"), name)


HR = Caller(id="u-hr", org="kf", roles=frozenset({"hr_admin"}))
ASHA = Caller(id="u-asha", org="kf", employee_id="E1")
GOV = Caller(id="u-gov", org="kf", roles=frozenset({GOVERNANCE_ADMIN}))


# ── MCD ──────────────────────────────────────────────────────────────────────
def test_MCD_renders_content_and_resolves_known_routes_only():
    m = cls("MCD", "MasterControlDashboard")()
    assert m.render("hi") == "<html><body>hi</body></html>"
    assert m.get_route_target("/status") == "system_status"
    assert m.route_exists("/agents") is True
    assert m.route_exists("/nope") is False and m.get_route_target("/nope") is None


# ── AUTONOMOUS_RESEARCH_ENGINE ───────────────────────────────────────────────
def test_AUTONOMOUS_RESEARCH_ENGINE_ranks_by_matching_fields_and_summarises():
    e = cls("AUTONOMOUS_RESEARCH_ENGINE", "AutonomousResearchEngine")()
    assert e.register_source("Papers") is True and e.register_source("PAPERS") is False
    assert e.add_document("papers", {"t": "Solar cells", "s": "solar"}) is True
    e.add_document("papers", {"t": "Wind", "s": "turbines"})
    e.add_document("PAPERS", {"t": "Solar farms", "s": "x"})
    assert e.add_document("missing", {"t": "solar"}) is False        # unregistered source
    hits = e.query("SOLAR")
    assert [(h["document"]["t"], h["score"]) for h in hits] == [("Solar cells", 2), ("Solar farms", 1)]
    s = e.summarize(hits)
    assert s == {"summary": "t: Solar cells; s: solar | t: Solar farms; s: x", "count": 2}


def test_AUTONOMOUS_RESEARCH_ENGINE_empty_state_gives_no_results():
    e = cls("AUTONOMOUS_RESEARCH_ENGINE", "AutonomousResearchEngine")()
    assert e.query("anything") == []
    assert e.summarize([]) == {"summary": "No results", "count": 0}


# ── AGENT_EVOLUTION ──────────────────────────────────────────────────────────
def test_AGENT_EVOLUTION_proposes_tuning_only_after_more_than_five_records():
    e = cls("AGENT_EVOLUTION", "EvolutionEngine")({"version": "2.0"})
    assert e.health_check() == {"agent": "AGENT_EVOLUTION", "status": "ok", "version": "2.0"}
    assert e.propose("a") == {"agent": "a", "proposal": "none"}      # unknown agent: no history
    for i in range(5):
        assert e.record("a", {"loss": i}) == {"ok": True}
    assert e.propose("a")["proposal"] == "none"
    e.record("a", {"loss": 9})
    assert e.propose("a") == {"agent": "a", "proposal": "tune-params"}
    assert e.propose("b")["proposal"] == "none"                      # history is per agent


# ── ZOHO_PROJECTS ────────────────────────────────────────────────────────────
class FakeZoho:
    def __init__(self, resp, configured=True):
        self.resp, self.calls, self.configured = resp, [], configured

    def get(self, url, params=None):
        self.calls.append((url, params))
        return self.resp

    def health_check(self):
        return {"configured": self.configured}


def zp(resp, configured=True):
    z = cls("ZOHO_PROJECTS", "ZohoProjectsConnector")({"portal_id": "P1"})
    z.zoho = FakeZoho(resp, configured)
    return z


def test_ZOHO_PROJECTS_task_summary_counts_closed_overdue_and_late_closed():
    past, future = 1_000, 10 ** 15
    tasks = [{"status": {"name": "Closed"}, "end_date_long": past, "completed_time_long": past + 1},   # closed late
             {"status": {"name": "Open"}, "end_date_long": past},      # overdue
             {"status": {"name": "Open"}, "end_date_long": future},
             {"status": {"name": "Closed"}, "end_date_long": future, "completed_time_long": past}]      # closed on time
    z = zp({"tasks": tasks})
    assert z.get_task_summary("PR", "O1") == {
        "closed_unknown": 0, "total_tasks": 4, "completed": 2, "completion_rate": 50.0, "overdue": 1, "late_closed": 1,
        "on_time_rate": 50.0}                                  # on time = closed and not closed late
    url, params = z.zoho.calls[0]
    assert url.endswith("/portal/P1/projects/PR/tasks/") and params == {"owner": "O1"}


def test_ZOHO_PROJECTS_empty_responses_give_zero_rates_and_empty_lists():
    z = zp({})
    assert z.get_projects() == [] and z.get_timelogs("PR", "O1", "01-01-2026", "01-31-2026") == []
    s = z.get_task_summary("PR", "O1")
    assert s["completion_rate"] == 0 and s["on_time_rate"] is None and s["late_closed"] == 0


def test_ZOHO_PROJECTS_health_reports_whether_zoho_credentials_are_configured():
    assert zp({}).health_check() == {"agent": "ZOHO_PROJECTS", "status": "ok", "configured": True}
    assert zp({}, configured=False).health_check() == {
        "agent": "ZOHO_PROJECTS", "status": "unconfigured", "configured": False}


def test_ZOHO_PROJECTS_constructs_without_a_config_argument():
    cls("ZOHO_PROJECTS", "ZohoProjectsConnector")()


# ── THREAT_DETECTION_MESH ────────────────────────────────────────────────────
def test_THREAT_DETECTION_MESH_scores_ten_per_field_of_fully_matching_signatures_only():
    t = cls("THREAT_DETECTION_MESH", "ThreatDetectionMesh")()
    assert t.add_signature("brute", {"action": "login", "ok": False}) is True
    assert t.add_signature("brute", {"x": 1}) is False               # duplicate name refused
    assert t.add_signature("probe", {"action": "scan"}) is True
    assert t.detect({"action": "login", "ok": False})["level"] == "HIGH"
    assert t.detect({"action": "login", "ok": True}) == {"event": {"action": "login", "ok": True},
                                                         "score": 0, "level": "LOW"}   # a partial match is not evidence
    assert t.detect({"action": "scan"}) == {"event": {"action": "scan"}, "score": 10, "level": "MEDIUM"}
    assert t.detect({"action": "read"})["level"] == "LOW"
    t.record_event({"action": "login", "ok": False})
    t.record_event({})
    s = t.summary()
    assert s["count"] == 2 and [r["score"] for r in s["results"]] == [20, 0]


def test_THREAT_DETECTION_MESH_without_signatures_everything_is_low():
    t = cls("THREAT_DETECTION_MESH", "ThreatDetectionMesh")()
    assert t.detect({"a": 1})["level"] == "LOW" and t.summary() == {"count": 0, "results": []}


# ── COMPLIANCE_GUARD ─────────────────────────────────────────────────────────
def test_COMPLIANCE_GUARD_flags_missing_and_forbidden_fields():
    g = cls("COMPLIANCE_GUARD", "ComplianceGuard")()
    kyc = {"requires": ["id", "pan"], "forbidden": ["password"]}
    assert g.add_rule("kyc", kyc) is False and g.list_rules() == []  # no caller: rules are governance-admin only
    with acting_as(ASHA):
        assert g.add_rule("kyc", kyc) is False                       # a caller without the role
    with acting_as(GOV):
        assert g.add_rule("kyc", kyc) is True
        assert g.add_rule("kyc", {"requires": ["x"]}) is False       # duplicate name refused
        assert g.add_rule("empty", {}) is False                      # a rule must name fields
    assert g.list_rules() == ["kyc"]
    bad = g.evaluate({"id": 1, "password": "x"})                     # evaluating needs no role
    assert bad["status"] == "VIOLATION"
    assert bad["violations"] == ["Missing field: pan", "Forbidden field: password"]
    assert g.evaluate({"id": 1, "pan": "A"})["status"] == "OK"
    assert g.evaluate("not a dict")["status"] == "VIOLATION"         # fail closed on a non-dict action


def test_COMPLIANCE_GUARD_removing_rules_and_empty_registry():
    g = cls("COMPLIANCE_GUARD", "ComplianceGuard")()
    with acting_as(GOV):
        assert g.remove_rule("ghost") is False
    assert g.evaluate({}) == {"action": {}, "violations": [], "status": "NO_RULES"}   # no rules approve nothing
    with acting_as(GOV):
        assert g.add_rule("r", {"requires": ["a"]}) is True
    assert g.remove_rule("r") is False and g.list_rules() == ["r"]   # no caller: the rule stays
    with acting_as(GOV):
        assert g.remove_rule("r") is True
    assert g.evaluate({})["status"] == "NO_RULES"


# ── EXECUTION_SANDBOX ────────────────────────────────────────────────────────
def test_EXECUTION_SANDBOX_runs_whitelisted_code_and_returns_underscore():
    s = cls("EXECUTION_SANDBOX", "ExecutionSandbox")()
    e = s.safe_exec("_ = sum(range(5)) + max(1, 2)")
    assert e["status"] == "OK" and e["result"] == 12 and s.get_last_result() == 12
    assert s.get_last_error() is None and len(s.get_log()) == 1


def test_EXECUTION_SANDBOX_blocks_builtins_and_records_errors():
    s = cls("EXECUTION_SANDBOX", "ExecutionSandbox")()
    for code in ("import os", "open('/etc/passwd')", "print(1)", "def ("):
        e = s.safe_exec(code)
        assert e["status"] == "ERROR" and e["error"], code
    # Refused while parsing the tree (nothing is ever handed to exec), so the error is a refusal, not an ImportError.
    assert s.get_log()[0]["error"] == "Refused: Import statements are not allowed"
    assert s.get_log()[1]["error"].startswith("Refused:") and "SyntaxError" in s.get_log()[3]["error"]
    assert s.get_last_result() is None and s.get_last_error() == s.get_log()[3]["error"]
    log = s.get_log()
    log.clear()
    assert len(s.get_log()) == 4                                      # get_log returns a copy


# ── FAILPATH_CONTROL_ENGINE ──────────────────────────────────────────────────
def test_FAILPATH_CONTROL_ENGINE_routes_known_and_unknown_failures_and_keeps_history():
    f = cls("FAILPATH_CONTROL_ENGINE", "FailpathControlEngine")()
    assert f.register_handler("E1", "shutdown") is True
    assert f.register_handler("E1", "other") is False and f.get_handler("E1") == "shutdown"
    assert f.route_failure("E1", {"n": 1}) == {"code": "E1", "handler": "shutdown", "context": {"n": 1}}
    assert f.route_failure("E9", {})["handler"] == "UNHANDLED"
    assert [r["code"] for r in f.list_history()] == ["E1", "E9"]
    f.list_handlers().clear()
    assert f.list_handlers() == {"E1": "shutdown"}                    # copies, not internals


# ── MULTI_TENANT_ENGINE ──────────────────────────────────────────────────────
def test_MULTI_TENANT_ENGINE_isolates_tenant_data():
    m = cls("MULTI_TENANT_ENGINE", "MultiTenantEngine")()
    assert m.create_tenant("a") is True and m.create_tenant("a") is False
    m.create_tenant("b")
    assert m.set_value("a", "k", 1) is True
    assert m.get_value("a", "k") == 1 and m.get_value("b", "k") is None
    snap = m.tenant_snapshot("a")
    snap["k"] = 99
    assert m.get_value("a", "k") == 1                                 # snapshot is a copy
    assert m.list_tenants() == ["a", "b"]


def test_MULTI_TENANT_ENGINE_unknown_tenant_is_refused_not_created():
    m = cls("MULTI_TENANT_ENGINE", "MultiTenantEngine")()
    assert m.set_value("ghost", "k", 1) is False and m.get_value("ghost", "k") is None
    assert m.tenant_snapshot("ghost") is None and m.delete_tenant("ghost") is False
    m.create_tenant("a")
    assert m.delete_tenant("a") is True and m.list_tenants() == []


# ── ATTENDANCE_MONITOR ───────────────────────────────────────────────────────
def attendance(records_by_emp):
    a = cls("ATTENDANCE_MONITOR", "AttendanceMonitorAgent")()

    def get(url, params=None):
        r = records_by_emp[params["empId"]]
        if isinstance(r, Exception):
            raise r
        return {"response": {"result": r}}
    a.people.zoho = type("Z", (), {"get": staticmethod(get)})()
    return a


def test_ATTENDANCE_MONITOR_check_today_sorts_present_late_absent_and_unknown():
    a = attendance({"E1": [{"IsLate": "false"}], "E2": [{"IsLate": "true", "CheckIn": "09:40"}],
                    "E3": [], "E4": TimeoutError("zoho down")})
    r = a.check_today(["E1", "E2", "E3", "E4"], "11-14-2026", caller=HR)
    assert r == {"present": ["E1"], "late": [{"id": "E2", "checkin": "09:40"}], "absent": ["E3"],
                 "unknown": ["E4"], "date": "11-14-2026"}                # failed fetch is unknown, never absent


def test_ATTENDANCE_MONITOR_refuses_unauthorised_callers():
    a = attendance({"E1": [], "E2": []})
    with pytest.raises(AccessDenied):
        a.check_today(["E1"], "11-14-2026")                           # no caller at all
    with pytest.raises(AccessDenied):
        a.check_today(["E1", "E2"], "11-14-2026", caller=ASHA)        # may see own record E1, not E2
    with pytest.raises(AccessDenied):
        a.flag_absence_streaks(["E2"], "11-01-2026", "11-14-2026", caller=ASHA)
    assert a.check_today(["E1"], "11-14-2026", caller=ASHA)["absent"] == ["E1"]


def test_ATTENDANCE_MONITOR_flags_employees_at_or_over_the_absence_threshold():
    a = attendance({"E1": [{"Status": "Absent"}] * 3 + [{"Status": "Present"}],
                    "E2": [{"Status": "Absent"}] * 2, "E3": RuntimeError("boom")})
    got = a.flag_absence_streaks(["E1", "E2", "E3"], "11-01-2026", "11-14-2026", caller=HR)
    assert got == [{"employee_id": "E1", "absent_days": 3, "requires_review": True}]
    assert len(a.flag_absence_streaks(["E2"], "a", "b", threshold=2, caller=HR)) == 1


def test_ATTENDANCE_MONITOR_explained_days_do_not_build_an_absence_streak():
    """VEL-55: leave, holiday, week-off and WFH were counted as absences (anything not 'Present')."""
    explained = [{"Status": s} for s in ("On Leave", "Holiday", "Weekly Off", "WFH", "Work From Home", "Half Day", "Weird")]
    a = attendance({"E1": explained, "E2": explained + [{"Status": "Absent"}] * 2, "E3": explained + [{"Status": "absent "}] * 3,
                    "E4": [{}, {"Status": None}, {"Status": "Absent"}]})
    got = a.flag_absence_streaks(["E1", "E2", "E3", "E4"], "11-01-2026", "11-14-2026", caller=HR)
    assert [g["employee_id"] for g in got] == ["E3", "E4"]          # E1, E2: no unexplained streak of 3
    assert got[0]["absent_days"] == 3 and got[1]["absent_days"] == 3   # explained days neither count nor reduce


def test_ATTENDANCE_MONITOR_has_no_unused_shift_start_setting():
    assert not hasattr(attendance({}), "shift_start")


# ── CREATIVE_HOLODECK ────────────────────────────────────────────────────────
def test_CREATIVE_HOLODECK_composes_scene_and_rejects_each_invalid_part():
    h = cls("CREATIVE_HOLODECK", "CreativeHolodeck")()
    s = h.compose("noir", "dark", "city", "searching")
    assert s["description"] == "A dark noir scene set in a city, where characters are searching."
    assert h.compose("baroque", "dark", "city", "searching") == {"error": "invalid_style"}
    assert h.compose("noir", "", "city", "searching") == {"error": "invalid_mood"}
    assert h.compose("noir", "dark", "moon", "searching") == {"error": "invalid_element"}
    assert h.compose("noir", "dark", "city", "flying") == {"error": "invalid_action"}
    r = h.random_scene()
    assert "error" not in r and r["style"] in h.styles and r["mood"] in h.moods


# ── LEGAL_INTELLIGENCE_ENGINE ────────────────────────────────────────────────
def test_LEGAL_INTELLIGENCE_ENGINE_stores_updates_looks_up_and_searches_rules():
    l = cls("LEGAL_INTELLIGENCE_ENGINE", "LegalIntelligenceEngine")()
    assert l.add_rule("Tax", "GST-Rate", "Standard rate is 18 percent") is True
    assert l.add_rule("tax", "gst-rate", "dup") is False              # case-insensitive duplicate
    assert l.lookup("TAX", "gst-RATE") == "Standard rate is 18 percent"
    assert l.update_rule("tax", "gst-rate", "Revised to 12 percent") is True
    l.add_rule("labour", "notice", "Thirty days notice")
    assert l.search("12 PERCENT") == ["tax:gst-rate"]
    assert l.search("notice") == ["labour:notice"]                    # matches rule name too
    assert l.search("zzz") == []


def test_LEGAL_INTELLIGENCE_ENGINE_missing_entries_report_not_found():
    l = cls("LEGAL_INTELLIGENCE_ENGINE", "LegalIntelligenceEngine")()
    assert l.lookup("tax", "x") == "NOT_FOUND" and l.update_rule("tax", "x", "t") is False
    l.add_rule("tax", "a", "t")
    assert l.lookup("tax", "b") == "NOT_FOUND" and l.update_rule("tax", "b", "t") is False


def test_ZOHO_PROJECTS_closed_task_without_completion_time_is_unknown_not_on_time():
    tasks = [{"status": {"name": "Closed"}, "end_date_long": 1_000},                       # no completed_time_long
             {"status": {"name": "Closed"}, "end_date_long": 10 ** 15, "completed_time_long": 5}]
    s = zp({"tasks": tasks}).get_task_summary("PR", "O1")
    assert s["closed_unknown"] == 1 and s["late_closed"] == 0 and s["on_time_rate"] == 100.0
    assert zp({"tasks": tasks[:1]}).get_task_summary("PR", "O1")["on_time_rate"] is None
