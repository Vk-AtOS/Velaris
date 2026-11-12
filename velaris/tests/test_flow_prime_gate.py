"""Flow steps approved in AetherOS Prime (velaris.core.prime), against a fake Prime. No network."""
import json
import secrets

import httpx
import pytest

from velaris.core import access, prime
from velaris.core.access import AccessDenied, Caller
from velaris.core.prime import PrimeGate, PrimeReadAuthoriser
from velaris.intel import trace
from velaris.intel.flow import Flow, FlowError, Tool
from velaris.intel.llm import FakeLLM

OWNER = {"caller": {"id": "u1", "org": "acme", "roles": [], "employee_id": "E1"}}


@pytest.fixture(autouse=True)
def _data(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))


class FakePrime:
    """Just enough of AetherOS Prime: POST /prime/requests, GET /prime/service/requests/{id}."""

    def __init__(self):
        self.requests, self.down, self.outcome = {}, False, "NEEDS_APPROVAL"

    def view(self, r):
        return {k: r[k] for k in ("id", "state", "request_hash", "action", "executor", "decided_by",
                                  "decision_reason", "execution")}

    def handler(self, request):
        if self.down:
            raise httpx.ConnectError("prime is down")
        assert request.headers["authorization"] == "Bearer aesk_test"
        if request.method == "POST" and request.url.path == "/prime/requests":
            body = json.loads(request.content)
            if self.outcome == "REFUSE":
                return httpx.Response(201, json={"outcome": "REFUSE", "reason": "no delegation from u1",
                                                 "request": None})
            rid = secrets.token_hex(8)
            self.requests[rid] = {
                "id": rid, "state": "pending", "request_hash": secrets.token_hex(32), "executor": body["executor"],
                "action": {"type": body["type"], "on_behalf_of": body["on_behalf_of"], "params": body["params"]},
                "decided_by": None, "decision_reason": None, "execution": None}
            if self.outcome == "EXECUTE":    # within a delegation at autonomy 4: Prime approves and runs its check
                self.requests[rid].update(state="approved", decided_by="prime", execution={"status": "succeeded"})
            return httpx.Response(201, json={"outcome": self.outcome, "reason": "within delegation",
                                             "request": self.view(self.requests[rid])})
        if request.method == "GET" and request.url.path.startswith("/prime/service/requests/"):
            r = self.requests.get(request.url.path.rsplit("/", 1)[1])
            return httpx.Response(200, json=self.view(r)) if r else httpx.Response(404, json={})
        return httpx.Response(404, json={})

    def only(self):
        assert len(self.requests) == 1
        return next(iter(self.requests.values()))

    def decide(self, quoted_hash, approve, by="deputy@acme", reason="", exec_status="succeeded"):
        """What Prime does when someone decides in its inbox: the quoted hash must match."""
        r = self.only()
        if quoted_hash != r["request_hash"]:
            return 409
        r.update(state="approved" if approve else "rejected", decided_by=by, decision_reason=reason,
                 execution={"status": exec_status, "result": {"error": "role changed"}} if approve else None)
        return 200


@pytest.fixture
def fake():
    return FakePrime()


def gate(fake):
    return PrimeGate("http://aetheros.test", "aesk_test", transport=httpx.MockTransport(fake.handler))


def make(fake, paid, *replies):
    it = iter(replies)
    tools = [Tool("pay", lambda vendor, amount: paid.append((vendor, amount)) or "paid",
                  "Pay a vendor", {"vendor": "", "amount": ""})]
    return Flow(tools, llm=FakeLLM(lambda prompt, model: next(it)), gate=gate(fake))


PAY = json.dumps({"tool": "pay", "args": {"vendor": "Acme", "amount": 10}})
FINAL = json.dumps({"final": "done"})


def test_approved_in_prime_with_the_right_hash_resumes_once(fake):
    paid = []
    r = make(fake, paid, PAY).start("pay acme", meta=OWNER)
    assert r.status == "waiting_approval" and paid == []
    req = fake.only()
    assert req["action"]["type"] == prime.ACTION_TYPE and req["executor"] == prime.EXECUTOR
    assert req["action"]["on_behalf_of"] == "u1"
    assert req["action"]["params"]["call_hash"] == r.pending["call_hash"]
    assert r.pending["approver"]["prime_request_id"] == req["id"]
    with pytest.raises(FlowError):          # with a gate nobody decides around Prime
        make(fake, paid).decide(r.run_id, r.pending["call_hash"], approve=True, by="u2")
    assert make(fake, paid).resume(r.run_id).status == "waiting_approval"      # still pending in Prime
    assert fake.decide(req["request_hash"], approve=True) == 200
    flow = make(fake, paid, FINAL)
    assert flow.resume(r.run_id).status == "done" and paid == [("Acme", 10)]
    assert make(fake, paid).resume(r.run_id).status == "done" and paid == [("Acme", 10)]
    decision = next(e for e in flow.history(r.run_id) if e["kind"] == "decision")
    assert decision["by"] == "deputy@acme" and decision["call_hash"] == r.pending["call_hash"]
    assert flow.verify(r.run_id)["ok"] and trace.verify()["ok"]


def test_wrong_hash_rejection_and_failed_final_check_never_run(fake):
    paid = []
    r = make(fake, paid, PAY).start("pay", meta=OWNER)
    assert fake.decide("0" * 64, approve=True) == 409                # Prime refuses a decision on another hash
    assert make(fake, paid).resume(r.run_id).status == "waiting_approval" and paid == []
    fake.decide(fake.only()["request_hash"], approve=False, reason="wrong vendor")
    llm_flow = make(fake, paid, FINAL)
    assert llm_flow.resume(r.run_id).status == "done" and paid == []
    assert "NOT DONE: rejected by deputy@acme: wrong vendor" in llm_flow.llm.calls[-1]["prompt"]

    fake2 = FakePrime()
    r = make(fake2, paid, PAY).start("pay", meta=OWNER)
    fake2.decide(fake2.only()["request_hash"], approve=True, exec_status="failed")
    assert make(fake2, paid, FINAL).resume(r.run_id).status == "done" and paid == []


def test_a_tampered_answer_from_prime_is_not_an_approval(fake):
    paid = []
    r = make(fake, paid, PAY).start("pay", meta=OWNER)
    req = fake.only()
    fake.decide(req["request_hash"], approve=True)
    req["action"]["params"]["call_hash"] = "f" * 64                    # approval now names another call
    assert make(fake, paid).resume(r.run_id).status == "waiting_approval"
    req["action"]["params"]["call_hash"] = r.pending["call_hash"]
    req["request_hash"] = "e" * 64                                     # not the request that was submitted
    assert make(fake, paid).resume(r.run_id).status == "waiting_approval" and paid == []
    assert any(e["action"] == "gate.error" for e in trace.entries())


def test_prime_down_means_the_step_waits_and_is_asked_later(fake):
    paid = []
    fake.down = True
    r = make(fake, paid, PAY).start("pay", meta=OWNER)
    assert r.status == "waiting_approval" and r.pending["approver"] is None and paid == []
    assert make(fake, paid).resume(r.run_id).status == "waiting_approval" and fake.requests == {}
    fake.down = False
    assert make(fake, paid).resume(r.run_id).status == "waiting_approval" and len(fake.requests) == 1
    fake.down = True
    fake.decide(fake.only()["request_hash"], approve=True)
    assert make(fake, paid).resume(r.run_id).status == "waiting_approval" and paid == []
    fake.down = False
    assert make(fake, paid, FINAL).resume(r.run_id).status == "done" and paid == [("Acme", 10)]


def test_prime_refusal_and_auto_execute(fake):
    paid = []
    fake.outcome = "REFUSE"
    llm_flow = make(fake, paid, PAY, FINAL)
    assert llm_flow.start("pay", meta=OWNER).status == "done" and paid == []
    assert "rejected by prime: Prime: REFUSE: no delegation from u1" in llm_flow.llm.calls[-1]["prompt"]

    auto = FakePrime()
    auto.outcome = "EXECUTE"
    assert make(auto, paid, PAY, FINAL).start("pay", meta=OWNER).status == "done" and paid == [("Acme", 10)]
    paid.clear()

    # A run that names no person cannot be put to Prime: it waits, and nothing runs.
    nobody = FakePrime()
    assert make(nobody, paid, PAY).start("pay").status == "waiting_approval"
    assert nobody.requests == {} and paid == []


def test_direct_call_without_gate_waits_then_finishes_with_the_tool_output():
    paid = []
    flow = Flow([Tool("pay", lambda vendor, amount: paid.append(vendor) or {"receipt": 7}, "Pay",
                      {"vendor": "", "amount": ""})], llm=FakeLLM(lambda p, m: pytest.fail("no model")))
    with pytest.raises(FlowError):
        flow.call("pay", {"vendor": "Acme", "extra": 1})
    r = flow.call("pay", {"vendor": "Acme", "amount": 5}, meta=OWNER)
    assert r.status == "waiting_approval" and flow.waiting() == [r.run_id]
    r = flow.decide(r.run_id, r.pending["call_hash"], approve=True, by="u2")
    assert r.status == "done" and json.loads(r.output) == {"receipt": 7} and paid == ["Acme"]
    assert flow.waiting() == [] and flow.history(r.run_id)[0]["meta"] == OWNER


def test_read_authoriser_asks_prime_and_fails_closed(monkeypatch):
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        if seen[-1]["category"] == "pay":
            return httpx.Response(200, json={"allowed": True, "reason": "role payroll_admin"})
        if seen[-1]["category"] == "bank":
            return httpx.Response(500, json={"allowed": True})
        return httpx.Response(200, json={"allowed": "yes"})
    auth = PrimeReadAuthoriser("http://aetheros.test", "aesk_test", transport=httpx.MockTransport(handler))
    who = Caller("u1", "acme", frozenset({"payroll_admin"}))
    assert auth(who, "pay", "E2", "acme") == (True, "role payroll_admin")
    assert auth(who, "bank", "E2")[0] is False                      # error status, whatever the body says
    assert auth(who, "health", "E2")[0] is False                    # anything but true is no
    assert auth(None, "pay", "E2")[0] is False and len(seen) == 3    # no caller: Prime is not even asked
    assert seen[0]["caller"] == {"id": "u1", "org": "acme", "roles": ["payroll_admin"], "employee_id": None}

    def down(request):
        raise httpx.ConnectError("down")
    monkeypatch.setattr(access, "decide", PrimeReadAuthoriser("http://x", "k", transport=httpx.MockTransport(down)))
    with pytest.raises(AccessDenied):
        access.authorize_read("pay", "E1", agent="T", caller=Caller("u1", "acme", employee_id="E1"))


def test_read_authoriser_is_local_unless_configured(monkeypatch):
    local = access.decide
    monkeypatch.setattr(access, "decide", local)
    assert prime.install_read_authoriser({}) == "local" and access.decide is local
    with pytest.raises(ValueError):
        prime.install_read_authoriser({"VELARIS_READ_AUTHORISER": "maybe"})
    assert prime.install_read_authoriser({"VELARIS_READ_AUTHORISER": "prime", "VELARIS_PRIME_URL": "http://a",
                                          "VELARIS_PRIME_API_KEY": "k"}) == "prime"
    assert isinstance(access.decide, PrimeReadAuthoriser)
    assert prime.gate_from_env({}) is None
    with pytest.raises(ValueError):
        prime.gate_from_env({"VELARIS_PRIME_URL": "http://a"})
