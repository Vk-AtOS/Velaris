"""PRIME authorisation and the VCAS autopilot that depends on it. Temp data dir; fixed clock."""
import pytest

from velaris.agents.PRIME.main import VelarisPrime
from velaris.agents.VCAS_AUTOPILOT.main import VCASAutopilotAgent
from velaris.agents.VCAS_CORE.main import VCASCoreAgent
from velaris.agents.VCAS_ROUTER.main import VCASRouterAgent
from velaris.agents.VCAS_SUPERVISOR.main import VCASSupervisorAgent
from velaris.intel import trace

T0 = 1_800_000_000.0
DAY = 86400


@pytest.fixture(autouse=True)
def _data(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    return tmp_path


def _grant(prime, **kw):
    args = dict(grantor="meena", principal="ap-bot", actions=["invoice.approve"], approver="kumar",
                autonomy="act", max_amount=50_000, currency="INR", now=T0)
    args.update(kw)
    return prime.grant(**args)


# ---- PRIME -------------------------------------------------------------------

def test_prime_allows_within_grant_and_routes_the_rest_to_the_approver():
    prime = VelarisPrime()
    assert _grant(prime)["status"] == "ok"
    ok = prime.authorize("ap-bot", "invoice.approve", "inv/1", {"amount": 20_000, "currency": "INR"}, now=T0 + 60)
    assert ok["decision"] == "allow" and ok["grant_id"] and len(ok["trace_hash"]) == 64
    over = prime.authorize("ap-bot", "invoice.approve", "inv/2", {"amount": 80_000, "currency": "INR"}, now=T0 + 60)
    assert over["decision"] == "needs_approval" and over["approver"] == "kumar" and "exceeds" in over["reason"]
    usd = prime.authorize("ap-bot", "invoice.approve", None, {"amount": 10, "currency": "USD"}, now=T0 + 60)
    assert usd["decision"] == "needs_approval"
    other = prime.authorize("ap-bot", "leave.approve", None, {}, now=T0 + 60)
    assert other["decision"] == "needs_approval" and "outside" in other["reason"]
    actions = [e["action"] for e in trace.entries()]
    assert actions.count("prime.request") == 4 and actions.count("prime.decision") == 4 and "prime.grant" in actions


def test_prime_never_list_ceiling_expiry_revocation_and_autonomy():
    prime = VelarisPrime()
    g = _grant(prime, valid_for_seconds=DAY)["grant_id"]
    ctx = {"amount": 100, "currency": "INR"}
    assert prime.authorize("ap-bot", "person.terminate", None, {}, now=T0)["decision"] == "deny"
    assert prime.authorize("ap-bot", "invoice.approve", None, {"amount": 600_000, "currency": "INR"},
                           now=T0)["decision"] == "deny"
    assert prime.authorize("ap-bot", "invoice.approve", None, ctx, now=T0 + DAY)["reason"].endswith("has expired")
    assert prime.authorize("someone-else", "invoice.approve", None, ctx, now=T0)["decision"] == "deny"
    assert prime.authorize("ap-bot", "invoice.approve", None, {"currency": "INR"}, now=T0)["decision"] == "deny"
    assert prime.revoke(g, by="ap-bot")["status"] == "denied"                  # the principal cannot revoke
    assert prime.revoke(g, by="meena", now=T0 + 10)["status"] == "ok"
    assert "revoked" in VelarisPrime().authorize("ap-bot", "invoice.approve", None, ctx, now=T0 + 20)["reason"]
    assert prime.revoke(g, by="meena")["status"] == "already_revoked"
    _grant(prime, autonomy="with_approval")
    assert prime.authorize("ap-bot", "invoice.approve", None, ctx, now=T0 + 30)["decision"] == "needs_approval"
    _grant(prime, principal="viewer", autonomy="observe")
    assert prime.authorize("viewer", "invoice.approve", None, ctx, now=T0 + 30)["decision"] == "deny"


def test_prime_resources_and_notify():
    prime = VelarisPrime()
    _grant(prime, actions=["report.*"], resources=["finance/*"], autonomy="act_and_notify", max_amount=None)
    r = prime.authorize("ap-bot", "report.generate", "finance/q3", {}, now=T0 + 1)
    assert r["decision"] == "allow" and r["notify"] == "meena"
    assert prime.authorize("ap-bot", "report.generate", "hr/salaries", {}, now=T0 + 1)["decision"] == "needs_approval"


@pytest.mark.parametrize("override, fragment", [
    ({"approver": "meena"}, "approver"),
    ({"actions": []}, "actions"),
    ({"actions": ["person.*"]}, "NEVER"),
    ({"autonomy": "godmode"}, "autonomy"),
    ({"max_amount": 900_000}, "max_amount"),
    ({"currency": "USD"}, "currency"),
    ({"valid_for_seconds": 40 * DAY}, "at most"),
    ({"valid_for_seconds": -5}, "after"),
    ({"principal": ""}, "principal"),
])
def test_prime_rejects_bad_grants(override, fragment):
    prime = VelarisPrime()
    r = _grant(prime, **override)
    assert r["status"] == "invalid_input" and fragment in r["reason"] and prime.grants() == []


def test_prime_bad_requests_and_gated_execute():
    prime = VelarisPrime()
    assert prime.authorize(None, "invoice.approve")["decision"] == "deny"
    assert prime.authorize("a", "invoice.approve", 5)["decision"] == "deny"
    assert prime.authorize("a", "invoice.approve", None, "ctx")["decision"] == "deny"
    assert prime.authorize("a", "made.up")["reason"].startswith("unknown action")
    refused = prime.execute("VIGILIS", "health_check")
    assert refused["status"] == "not_authorised" and refused["executed"] is False
    prime.grant("meena", "ops-bot", ["agent.execute"], "kumar", resources=["VIGILIS.health_check"], autonomy="act")
    assert prime.execute("VIGILIS", "health_check", principal="ops-bot")["status"] == "ok"
    assert prime.execute("VIGILIS", "generate_test_keypair", principal="ops-bot")["executed"] is False


# ---- VCAS --------------------------------------------------------------------

def _task(n=1, amount=10_000, **kw):
    return {"id": f"t{n}", "action": "invoice.approve", "principal": "ap-bot", "resource": f"inv/{n}",
            "context": {"amount": amount, "currency": "INR"}, "params": {"invoice": n}, **kw}


def test_router_and_supervisor():
    assert VCASRouterAgent().route(_task())["autopilot_route"] == "manual"
    assert VCASRouterAgent().route(_task(), ["invoice.approve"])["handler"] == "invoice.approve"
    assert VCASRouterAgent().route("TASK")["status"] == "invalid_input"
    sup = VCASSupervisorAgent()
    assert sup.approve(_task())["approved"] is False                       # no grant yet
    _grant(sup.prime, now=None)
    assert sup.approve(_task())["approved"] is True
    assert sup.approve("TASK")["approved"] is False


def test_autopilot_runs_once_and_only_with_a_recorded_approval():
    prime = VelarisPrime()
    _grant(prime, now=None)
    pilot = VCASAutopilotAgent()
    calls = []
    pilot.register("invoice.approve", lambda p: calls.append(p) or {"approved_invoice": p["invoice"]})
    task = _task()
    assert pilot.execute(task, {"decision": "allow"})["status"] == "not_approved"        # forged approval
    assert pilot.execute(task, {"trace_hash": "f" * 64})["status"] == "not_approved"
    allow = VCASSupervisorAgent(prime).approve(task)
    other = _task(2)
    assert pilot.execute(other, allow)["status"] == "not_approved"                      # approval is per task
    r = pilot.execute(task, allow)
    assert r["executed"] is True and r["run"]["result"] == {"approved_invoice": 1}
    again = VCASAutopilotAgent()
    again.register("invoice.approve", lambda p: calls.append(p))
    assert again.execute(task, allow)["status"] == "already_run" and len(calls) == 1      # survives restart


def test_autopilot_records_handler_failures():
    prime = VelarisPrime()
    _grant(prime, now=None)
    pilot = VCASAutopilotAgent()
    pilot.register("invoice.approve", lambda p: 1 / 0)
    r = pilot.execute(_task(), VCASSupervisorAgent(prime).approve(_task()))
    assert r["executed"] is False and r["status"] == "failed" and "ZeroDivisionError" in r["run"]["error"]
    assert pilot.register("x", "not callable")["status"] == "invalid_input"
    assert pilot.execute("TASK")["executed"] is False


def test_core_full_flow_with_a_person_in_the_loop():
    prime = VelarisPrime()
    _grant(prime, now=None)
    pilot = VCASAutopilotAgent()
    done = []
    pilot.register("invoice.approve", lambda p: done.append(p["invoice"]) or "ok")
    core = VCASCoreAgent(autopilot=pilot, supervisor=VCASSupervisorAgent(prime))
    assert core.submit(_task(1))["outcome"] == "done" and done == [1]
    big = core.submit(_task(2, amount=90_000))
    assert big["outcome"] == "pending" and big["approver"] == "kumar" and done == [1]
    restarted = VCASCoreAgent(autopilot=pilot, supervisor=VCASSupervisorAgent(prime))
    assert "t2" in restarted.pending()
    assert restarted.decide("t2", True, by="ap-bot")["status"] == "denied"              # not the approver
    assert restarted.decide("t2", True, by="kumar")["outcome"] == "done" and done == [1, 2]
    assert restarted.decide("t2", True, by="kumar")["status"] == "not_found"
    core.submit(_task(3, amount=90_000))
    assert core.decide("t3", False, by="kumar")["outcome"] == "rejected" and done == [1, 2]


def test_core_manual_denied_and_bad_input():
    core = VCASCoreAgent()
    assert core.submit(_task())["outcome"] == "manual"                                  # nothing registered
    core.autopilot.register("invoice.approve", lambda p: "ok")
    assert core.submit(_task())["outcome"] == "denied"                                  # no grant
    assert core.submit({"id": "x"})["status"] == "invalid_input"
    assert core.decide("nope", True, by="kumar")["status"] == "not_found"


def test_an_approval_covers_one_task_one_amount_once():
    prime = VelarisPrime()
    _grant(prime, now=None)
    pilot = VCASAutopilotAgent()
    ran = []
    pilot.register("invoice.approve", lambda p: ran.append(p["invoice"]) or "ok")
    sup = VCASSupervisorAgent(prime)
    a = _task(1, amount=10_000)
    allow_a = sup.approve(a)
    assert allow_a["approved"] is True
    bigger = {**a, "context": {"amount": 49_000, "currency": "INR"}}         # same id, larger amount
    assert pilot.execute(bigger, allow_a)["status"] == "not_approved"
    other = {**a, "id": "t-other"}                                           # same everything, other task
    assert pilot.execute(other, allow_a)["status"] == "not_approved"
    assert pilot.execute(a, allow_a)["executed"] is True and ran == [1]
    # replay: the same recorded approval cannot run a second task, even if the task id is re-used fresh
    fresh = VCASAutopilotAgent()
    fresh.register("invoice.approve", lambda p: ran.append(p["invoice"]) or "ok")
    fresh._runs.update(lambda s: s["runs"].pop("t1"))                        # pretend the run record was lost
    assert fresh.execute(a, allow_a)["status"] == "not_approved" and ran == [1]
    # a human approval recorded by VCAS_CORE for one task does not cover another
    core = VCASCoreAgent(autopilot=pilot, supervisor=sup)
    core.submit(_task(5, amount=90_000))
    decided = core.decide("t5", True, by="kumar")
    assert decided["outcome"] == "done"
    human_hash = next(e["hash"] for e in trace.entries() if e["actor"] == "VCAS_CORE")
    assert pilot.execute(_task(6, amount=90_000), {"trace_hash": human_hash})["status"] == "not_approved"
