"""VEL-12: the production identity resolver (signed session of the current request) makes delegations usable, and only then."""
import secrets

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from velaris.api import session_identity
from velaris.api.app import Settings, create_app
from velaris.api.auth import make_assertion, sign
from velaris.core.access import Caller, acting_as
from velaris.intel import tools
from velaris.intel.llm import FakeLLM
from velaris.orchestration import absence, autonomy, identity
from velaris.orchestration.base import DepartmentOrchestrator
from velaris.tests.orch_helpers import FINAL, DemoAgent, call, install

DAY = 86400.0
NOW = 1_000_000.0
CFO = Caller("cfo", "acme", frozenset({"payroll_admin"}))
CLERK = Caller("clerk", "acme", frozenset({"employee"}))
OWNER = Caller("owner", "acme", frozenset({"governance_admin"}))
SECRET, KEY = b"s" * 32, Ed25519PrivateKey.generate()


@pytest.fixture
def engine(monkeypatch):
    e = install(monkeypatch, "finance")
    monkeypatch.setattr(identity, "_resolver", None)         # no test directory: only the production resolver
    session_identity.install()
    with acting_as(OWNER):
        autonomy.set_money_limit(1000)
    absence.grant(CFO, classes=["money_under_limit"], departments=["finance"], start=NOW - 10, end=NOW + 7 * DAY,
                  max_amount=500, clock=lambda: NOW)
    yield e
    session_identity.bind(None)
    tools.clear()


def run_as_clerk(engine, tmp_path):
    it = iter([call("DEMO.make_payment", amount=300, vendor="Acme"), FINAL])
    llm = FakeLLM(lambda p, m: next(it))
    return DepartmentOrchestrator("finance", scope="Finance.", llm=llm, engine=engine, models=["fk:m"],
                                  flow_path=str(tmp_path / "f.db"), wall=lambda: NOW).run("pay Acme", CLERK)


def test_with_the_principals_signed_session_the_delegation_is_honoured(engine, tmp_path):
    session_identity.bind(CFO)
    assert run_as_clerk(engine, tmp_path).status == "done" and DemoAgent.calls == [("make_payment", 300, "Acme")]


def test_without_a_signed_session_or_with_somebody_elses_the_delegation_is_refused_and_kept(engine, tmp_path):
    assert run_as_clerk(engine, tmp_path).status == "waiting_approval"           # nobody verified
    session_identity.bind(CLERK)
    assert run_as_clerk(engine, tmp_path).status == "waiting_approval" and DemoAgent.calls == []
    assert absence.briefing(CFO)["delegations"][0]["revoked_at"] is None        # unverifiable is not "gone": not auto-revoked


def test_another_organisations_user_cannot_use_it(engine, tmp_path):
    session_identity.bind(Caller("cfo", "other", frozenset({"payroll_admin"})))      # same user id, other org
    assert run_as_clerk(engine, tmp_path).status == "waiting_approval" and DemoAgent.calls == []
    with pytest.raises(identity.IdentityUnavailable):
        identity.current("acme", "cfo")


def test_the_app_installs_the_resolver_and_binds_each_verified_request(monkeypatch):
    monkeypatch.setenv("VELARIS_ORG", "acme")
    monkeypatch.setattr(identity, "_resolver", None)
    seen = []
    real = session_identity.bind
    monkeypatch.setattr(session_identity, "bind", lambda c: (seen.append(c), real(c)))
    client = TestClient(create_app(Settings(secret=SECRET, identity_key=KEY.public_key(), org="acme"),
                                   engine=type("E", (), {"router": type("R", (), {"departments": {}, "failed": {}})()})()))
    assert identity.has_resolver()
    client.get("/autonomy")                                                        # unsigned: nobody is bound
    assert seen == []
    nonce = secrets.token_urlsafe(16)
    token = make_assertion(KEY, sub="cfo", org="acme", roles=["governance_admin"], nonce=nonce)
    assert client.get("/autonomy", headers=sign(SECRET, "GET", "/autonomy", b"", token, nonce=nonce)).status_code == 200
    assert [(c.id, c.org) for c in seen] == [("cfo", "acme")]
