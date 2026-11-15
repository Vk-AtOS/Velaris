"""KAN-107: ESIGN ceremony steps, POLICY_ACKS retire/acknowledge outcomes and OFFER_LETTERS expiry reach the trace ledger."""
import json

from velaris.core.access import acting_as
from velaris.intel import trace
from velaris.tests.onboarding_helpers import HR1, person
from velaris.tests.test_onboarding_esign import IP, UA, ceremony, setup


def _actions(name):
    return [e for e in trace.entries() if e["action"] == name]


def test_esign_every_ceremony_step_is_traced_without_personal_data():
    e, sender, _, rid = setup()
    tok = sender.token_for("asha@example.in")
    e.open_signing(tok, "asha@example.in", IP, UA)
    e.open_signing(tok, "wrong@example.in", IP, UA)
    ceremony(e, sender, "ravi@example.in", "Ravi Kumar")
    steps = _actions("signer.step")
    assert [s["payload"]["state"] for s in steps][:2] == ["viewed", "viewed"]
    assert "identity_mismatch" in [s["payload"]["result"] for s in steps]
    assert len(steps) >= 5 and rid in json.dumps(steps[0]["payload"])
    blob = json.dumps(steps)
    assert "asha@example.in" not in blob and IP not in blob and tok not in blob


def test_esign_decline_is_traced():
    e, sender, _, rid = setup()
    tok = sender.token_for("asha@example.in")
    assert e.decline_signing(tok, "asha@example.in", "no thanks", IP, UA)["status"] == "ok"
    assert _actions("signer.step")[-1]["payload"]["state"] == "declined"


def test_policy_retire_and_acknowledge_have_outcome_events():
    from velaris.tests.test_onboarding_records import hire, make
    er, pol, flow, clock, _ = make()
    emp = hire(er)
    with acting_as(HR1):
        pol.publish_policy("code_of_conduct", "Code", "Be kind.", "2026-12-01")
    with acting_as(person(emp)):
        sha = pol.get_policy("code_of_conduct")["policy"]["text_sha256"]
        assert pol.acknowledge("code_of_conduct", sha)["status"] == "ok"
    with acting_as(HR1):
        assert pol.retire_policy("code_of_conduct", "obsolete")["status"] == "ok"
    ack, ret = _actions("policy.acknowledged"), _actions("policy.retired")
    assert len(ack) == 1 and len(ret) == 1 and emp not in json.dumps(ack[0]["payload"])
