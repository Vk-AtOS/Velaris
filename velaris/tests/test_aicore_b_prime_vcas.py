"""PRIME authorisation and the VCAS autopilot that depends on it. Temp data dir; fixed clock."""
import pytest

from velaris.agentkit.aicore_b_authz import task_digest
from velaris.agents.PRIME.main import VelarisPrime
from velaris.agents.VCAS_AUTOPILOT.main import VCASAutopilotAgent
from velaris.agents.VCAS_CORE.main import VCASCoreAgent
from velaris.agents.VCAS_ROUTER.main import VCASRouterAgent
from velaris.agents.VCAS_SUPERVISOR.main import VCASSupervisorAgent
from velaris.core.access import GOVERNANCE_ADMIN, Caller, acting_as
from velaris.intel import trace

T0 = 1_800_000_000.0
DAY = 86400
MEENA = Caller("meena", "acme", frozenset({GOVERNANCE_ADMIN}))      # gives grants
BOT = Caller("ap-bot", "acme")                                       # the principal the grants name
KUMAR = Caller("kumar", "acme")                                      # the approver the grants name


@pytest.fixture(autouse=True)
def _data(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))
    return tmp_path


def _grant(prime, as_=MEENA, **kw):
    args = dict(principal="ap-bot", actions=["invoice.approve"], approver="kumar",
                autonomy="act", max_amount=50_000, currency="INR", now=T0)
    args.update(kw)
    with acting_as(as_):
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
    with acting_as(BOT):
        assert prime.revoke(g)["status"] == "denied"                           # the principal cannot revoke
        assert prime.revoke(g, by="meena")["status"] == "denied"               # nor claim to be the grantor
    with acting_as(MEENA):
        assert prime.revoke(g, by="meena", now=T0 + 10)["status"] == "ok"
    assert "revoked" in VelarisPrime().authorize("ap-bot", "invoice.approve", None, ctx, now=T0 + 20)["reason"]
    with acting_as(MEENA):
        assert prime.revoke(g)["status"] == "already_revoked"
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
    assert refused["status"] == "unauthenticated" and refused["executed"] is False
    with acting_as(MEENA):
        prime.grant("meena", "ops-bot", ["agent.execute"], "kumar", resources=["VIGILIS.health_check"], autonomy="act")
    with acting_as(Caller("ops-bot", "acme")):
        assert prime.execute("VIGILIS", "health_check", principal="ops-bot")["status"] == "ok"
        assert prime.execute("VIGILIS", "generate_test_keypair")["executed"] is False


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
    allow = VCASSupervisorAgent(prime).approve(task)
    assert pilot.execute(task, allow)["status"] == "not_approved"                       # nobody is calling
    with acting_as(BOT):
        assert pilot.execute(task, {"decision": "allow"})["status"] == "not_approved"    # forged approval
        assert pilot.execute(task, {"trace_hash": "f" * 64})["status"] == "not_approved"
        other = _task(2)
        assert pilot.execute(other, allow)["status"] == "not_approved"                  # approval is per task
        r = pilot.execute(task, allow)
        assert r["executed"] is True and r["run"]["result"] == {"approved_invoice": 1}
        again = VCASAutopilotAgent()
        again.register("invoice.approve", lambda p: calls.append(p))
        assert again.execute(task, allow)["status"] == "already_run" and len(calls) == 1  # survives restart


def test_autopilot_records_handler_failures():
    prime = VelarisPrime()
    _grant(prime, now=None)
    pilot = VCASAutopilotAgent()
    pilot.register("invoice.approve", lambda p: 1 / 0)
    with acting_as(BOT):
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
    with acting_as(BOT):
        assert core.submit(_task(1))["outcome"] == "done" and done == [1]
        big = core.submit(_task(2, amount=90_000))
    assert big["outcome"] == "pending" and big["approver"] == "kumar" and done == [1]
    restarted = VCASCoreAgent(autopilot=pilot, supervisor=VCASSupervisorAgent(prime))
    assert "t2" in restarted.pending()
    with acting_as(BOT):
        assert restarted.decide("t2", True)["status"] == "denied"                       # not the approver
        assert restarted.decide("t2", True, by="kumar")["status"] == "denied"           # cannot claim to be
    with acting_as(KUMAR):
        assert restarted.decide("t2", True, by="kumar")["outcome"] == "done" and done == [1, 2]
        assert restarted.decide("t2", True)["status"] == "not_found"
    with acting_as(BOT):
        core.submit(_task(3, amount=90_000))
    with acting_as(KUMAR):
        assert core.decide("t3", False)["outcome"] == "rejected" and done == [1, 2]


def test_core_manual_denied_and_bad_input():
    core = VCASCoreAgent()
    with acting_as(BOT):
        assert core.submit(_task())["outcome"] == "manual"                              # nothing registered
        core.autopilot.register("invoice.approve", lambda p: "ok")
        assert core.submit(_task())["outcome"] == "denied"                              # no grant
        assert core.submit({"id": "x"})["status"] == "invalid_input"
    with acting_as(KUMAR):
        assert core.decide("nope", True)["status"] == "not_found"


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
    with acting_as(BOT):
        bigger = {**a, "context": {"amount": 49_000, "currency": "INR"}}     # same id, larger amount
        assert pilot.execute(bigger, allow_a)["status"] == "not_approved"
        other = {**a, "id": "t-other"}                                       # same everything, other task
        assert pilot.execute(other, allow_a)["status"] == "not_approved"
        assert pilot.execute(a, allow_a)["executed"] is True and ran == [1]
        # replay: the same recorded approval cannot run a second task, even if the task id is re-used fresh
        fresh = VCASAutopilotAgent()
        fresh.register("invoice.approve", lambda p: ran.append(p["invoice"]) or "ok")
        fresh._runs.update(lambda s: s["runs"].pop("t1"))                    # pretend the run record was lost
        assert fresh.execute(a, allow_a)["status"] == "not_approved" and ran == [1]
        # a human approval recorded by VCAS_CORE for one task does not cover another
        core = VCASCoreAgent(autopilot=pilot, supervisor=sup)
        core.submit(_task(5, amount=90_000))
    with acting_as(KUMAR):
        decided = core.decide("t5", True)
        assert decided["outcome"] == "done"
        human_hash = next(e["hash"] for e in trace.entries() if e["actor"] == "VCAS_CORE")
        assert pilot.execute(_task(6, amount=90_000), {"trace_hash": human_hash})["status"] == "not_approved"


# ---- identity, delegation, execute allowlist, task digest (security review) ----

def test_grant_takes_the_grantor_from_the_caller():
    prime = VelarisPrime()
    assert prime.grant("meena", "ap-bot", ["invoice.approve"], "kumar")["status"] == "unauthenticated"
    with acting_as(BOT):
        assert prime.grant("meena", "x-bot", ["leave.approve"], "kumar")["status"] == "denied"   # names someone else
        assert prime.grant(principal="x-bot", actions=["leave.approve"], approver="kumar")["status"] == "denied"
        assert prime.grant(principal="ap-bot", actions=["leave.approve"], approver="kumar")["status"] == "invalid_input"
    assert _grant(prime, principal="meena", approver="kumar")["reason"] == "a grantor cannot grant to themselves"
    assert prime.grants() == []
    assert _grant(prime)["status"] == "ok" and prime.grants()[0]["grantor"] == "meena"
    assert any(e["action"] == "change.denied" and e["payload"]["change"] == "grant" for e in trace.entries())


def test_a_non_admin_may_delegate_only_what_they_hold():
    prime = VelarisPrime()
    _grant(prime, actions=["invoice.approve", "leave.approve"], resources=["finance/**"], max_amount=40_000,
           autonomy="act_and_notify", valid_for_seconds=10 * DAY, delegable=True)
    sub = dict(as_=BOT, principal="ap-sub", approver="kumar", actions=["invoice.approve"], resources=["finance/q3"],
               max_amount=20_000, autonomy="with_approval", valid_for_seconds=DAY, now=T0 + 1)
    for wider in ({"actions": ["payment.execute"]}, {"actions": ["invoice.*"]}, {"resources": ["hr/x"]},
                  {"resources": ["**"]}, {"max_amount": 45_000}, {"autonomy": "act"},
                  {"valid_for_seconds": 20 * DAY}, {"max_amount": None}, {"approver": "ravi"}):
        r = _grant(prime, **{**sub, **wider})
        assert r["status"] == "denied", wider
    assert _grant(prime, **sub)["status"] == "ok"
    assert prime.authorize("ap-sub", "invoice.approve", "finance/q3", {"amount": 10, "currency": "INR"},
                           now=T0 + 2)["decision"] == "needs_approval"
    # a grant that is not delegable confers nothing to pass on
    _grant(prime, principal="clerk", actions=["leave.approve"], approver="kumar")
    assert _grant(prime, as_=Caller("clerk", "acme"), principal="x", actions=["leave.approve"],
                  approver="kumar", autonomy="observe", max_amount=None)["status"] == "denied"
    assert any(e["action"] == "prime.grant.refused" for e in trace.entries())


@pytest.mark.parametrize("resources", [None, ["*"], ["VIGILIS.*"], ["**"], ["VIGILIS._sign"], ["VIGILIS"]])
def test_execute_grants_need_an_exact_allowlist(resources):
    prime = VelarisPrime()
    r = _grant(prime, principal="ops-bot", actions=["agent.execute"], max_amount=None, resources=resources)
    assert r["status"] == "invalid_input" and "exact" in r["reason"]


@pytest.mark.parametrize("agent, method", [("VIGILIS", "_sign"), ("PRIME", "health_check"),
                                           ("EACPE_HUMAN_GUARD", "set_approvers"), ("VCAS_CORE", "decide"),
                                           ("NEURAL_POLICY_MESH", "remove_policy"), ("PRIME", "grant"),
                                           ("VIGILIS.x", "health_check")])
def test_execute_refuses_private_and_governance_methods(agent, method):
    prime = VelarisPrime()
    if "." not in agent and method.isidentifier() and not method.startswith("_"):
        _grant(prime, principal="ops-bot", actions=["agent.execute"], max_amount=None,
               resources=[f"{agent}.{method}"])
    with acting_as(Caller("ops-bot", "acme")):
        r = prime.execute(agent, method)
    assert r["executed"] is False and r["status"] == "not_authorised"


def test_execute_runs_only_for_the_caller_the_grant_names():
    prime = VelarisPrime()
    _grant(prime, principal="ops-bot", actions=["agent.execute"], max_amount=None, resources=["VIGILIS.health_check"],
           now=None)
    with acting_as(Caller("intruder", "acme")):
        assert prime.execute("VIGILIS", "health_check", principal="ops-bot")["status"] == "denied"
        assert prime.execute("VIGILIS", "health_check")["executed"] is False
    with acting_as(Caller("ops-bot", "acme")):
        assert prime.execute("VIGILIS", "health_check")["status"] == "ok"


def test_an_approval_covers_the_params_too():
    prime = VelarisPrime()
    _grant(prime, now=None)
    pilot = VCASAutopilotAgent()
    ran = []
    pilot.register("invoice.approve", lambda p: ran.append(p) or "ok")
    task = _task(1)
    allow = VCASSupervisorAgent(prime).approve(task)
    decision = next(e for e in trace.entries() if e["hash"] == allow["trace_hash"])
    assert decision["payload"]["task_digest"] == task_digest(task)
    with acting_as(BOT):
        steered = {**task, "params": {"invoice": 1, "pay_to": "attacker"}}
        assert pilot.execute(steered, allow)["status"] == "not_approved" and ran == []
    with acting_as(Caller("other-bot", "acme")):                                  # someone else's allow
        assert pilot.execute(task, allow)["status"] == "not_approved" and ran == []
    with acting_as(BOT):
        assert pilot.execute(task, allow)["executed"] is True and ran == [{"invoice": 1}]


def test_a_person_approves_the_stored_task_exactly():
    prime = VelarisPrime()
    _grant(prime, now=None)
    pilot = VCASAutopilotAgent()
    ran = []
    pilot.register("invoice.approve", lambda p: ran.append(p) or "ok")
    core = VCASCoreAgent(autopilot=pilot, supervisor=VCASSupervisorAgent(prime))
    with acting_as(Caller("other-bot", "acme")):
        assert core.submit(_task(7, amount=90_000))["status"] == "denied"        # cannot submit as ap-bot
    assert core.pending() == {}
    with acting_as(BOT):
        core.submit(_task(7, amount=90_000))
    with acting_as(KUMAR):
        core.decide("t7", False)
    with acting_as(BOT):
        core.submit(_task(8, amount=90_000))
    with acting_as(KUMAR):
        assert core.decide("t8", True)["outcome"] == "done"
        human = [e for e in trace.entries() if e["actor"] == "VCAS_CORE" and e["action"] == "decision"][-1]
        assert human["payload"]["task_digest"] == task_digest(_task(8, amount=90_000))
        steered = {**_task(9, amount=90_000), "id": "t8b", "params": {"invoice": 666}}
        assert pilot.execute(steered, {"trace_hash": human["hash"]})["status"] == "not_approved"
    with acting_as(BOT):                                                          # only the approver may use it
        assert pilot.execute(_task(8, amount=90_000), {"trace_hash": human["hash"]})["status"] != "ok"
    assert ran == [{"invoice": 8}]


def test_autopilot_run_that_cannot_be_traced_fails_closed_with_a_clear_error(monkeypatch):
    """KAN-95: trace.append raising after the handler ran used to escape execute() as a bare OSError."""
    prime = VelarisPrime()
    _grant(prime, now=None)
    pilot = VCASAutopilotAgent()
    calls = []
    pilot.register("invoice.approve", lambda p: calls.append(p) or "ok")
    allow = VCASSupervisorAgent(prime).approve(_task())

    def broken(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(trace, "append", broken)
    with acting_as(BOT):
        r = pilot.execute(_task(), allow)
        assert r["status"] == "audit_failed" and r["executed"] is True and "audit trace" in str(r)
        assert len(calls) == 1 and pilot.run_of(_task()["id"])["state"] == "done"
        assert pilot.execute(_task(), allow)["status"] == "already_run" and len(calls) == 1      # never run twice
