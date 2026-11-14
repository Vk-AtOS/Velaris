"""Leave balances fail closed; API keys in URLs never reach the trace or cache."""
import importlib.util
import os

import httpx


def test_leave_needs_balance_and_cannot_be_over_or_self_approved(tmp_path):
    root = os.path.join(os.path.dirname(__file__), "..", "..")
    spec = importlib.util.spec_from_file_location(
        "leave_main", os.path.join(root, "departments", "hr", "LEAVE_MANAGEMENT", "main.py"))
    lm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(lm)
    lm._DB = str(tmp_path / "leaves.db")
    leave = lm.LeaveManagement()
    from velaris.core.access import Caller, acting_as
    hr = Caller("manager", "acme", frozenset({"hr_admin"}))
    emp = Caller("e1", "acme")

    assert leave.approve(1, "manager")["error"] == "unauthenticated"                 # nobody approves anonymously
    with acting_as(emp):
        assert leave.apply("e1", "casual", "2026-11-16", "2026-11-20")["error"] == "no_balance_record"
        assert leave.approve(1, "e1")["error"] == "denied"                           # an employee is not an approver
    with acting_as(hr):
        leave.seed_balances("e1", 2026)
    with acting_as(emp):
        # Two 7-day requests against 12 days: each passes apply(), only one may be approved.
        first, second = (leave.apply("e1", "casual", "2026-11-16", "2026-11-24")["id"] for _ in range(2))
    with acting_as(Caller("e1", "acme", frozenset({"hr_admin"}))):
        assert leave.approve(first, "e1")["error"] == "self_approval_not_allowed"
    with acting_as(hr):
        assert leave.approve(first, "manager")["status"] == "approved"
        assert leave.approve(second, "manager")["error"] == "insufficient_balance"
        assert leave.get_balance("e1", 2026)["balance"]["casual"]["used"] == 7


def test_api_key_in_url_is_not_written_to_disk(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    from velaris.intel import web_fetch

    fetcher = web_fetch.Fetcher(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"ok": 1})),
        resolver=lambda host: ["93.184.216.34"], min_gap_s=0)
    fetcher.fetch("https://api.example.com/SECRETKEY/search/x", use_cache=False, is_api=True)
    written = "".join(
        open(os.path.join(folder, name), errors="ignore").read()
        for folder, _, names in os.walk(tmp_path) for name in names)
    assert "api.example.com" in written and "SECRETKEY" not in written
