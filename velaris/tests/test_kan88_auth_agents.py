"""KAN-88: recovery, PIN, owner and identity agents are random, hashed, single-use, throttled and role-gated."""
import json
import time
from importlib import import_module

import pytest

from velaris.agentkit import secure
from velaris.intel.paths import agent_dir
from velaris.core.access import SECURITY_ADMIN, Caller, acting_as

ADMIN = Caller("sec", "kf", frozenset({SECURITY_ADMIN}))
MEMBER = Caller("bob", "kf", frozenset())


def mod(name):
    return import_module(f"velaris.agents.{name}.main")


def test_secure_primitives():
    h = secure.hash_secret("1234")
    assert h != secure.hash_secret("1234") and secure.verify_secret("1234", h)
    assert not secure.verify_secret("1235", h)
    for junk in (None, "", "x$y", "scrypt$!!$!!"):
        assert secure.verify_secret("1234", junk) is False
    assert secure.verify_secret(b"1234", h) is False and secure.verify_secret("é", None) is False
    with pytest.raises(ValueError):
        secure.safe_join("/tmp", "../x")
    with pytest.raises(ValueError):
        secure.safe_join("/tmp", "a/b")
    assert secure.safe_join("/tmp", "ok", ".json").name == "ok.json"


def test_throttle_survives_new_instances_and_expires():
    t = secure.Throttle("T", max_attempts=2, lock_seconds=0.2)
    t.fail("u"), t.fail("u")
    assert secure.Throttle("T").locked("u")
    time.sleep(0.25)
    assert not t.locked("u")


# ---- MFA_RECOVERY_WORKFLOW ----------------------------------------------------
def test_recovery_needs_admin_and_a_verified_code():
    m = mod("MFA_RECOVERY_WORKFLOW").MFARecoveryWorkflow()
    with acting_as(MEMBER):
        assert m.issue_recovery_code("bob") is None            # a member cannot mint codes
    assert m.issue_recovery_code("bob") is None                # nor can nobody
    with acting_as(ADMIN):
        code = m.issue_recovery_code("bob")
    assert len(code) == 8 and code.isdigit()
    assert m.issue_reset_token("bob") is None                  # no verified code yet: no token
    assert m.verify_recovery_code("bob", code) is True
    assert m.verify_recovery_code("bob", code) is False        # consumed
    tok = m.issue_reset_token("bob")
    assert tok and m.issue_reset_token("bob") is None          # the verification buys one token
    assert not m.reset_credentials("bob", "wrong", "h")
    assert not m.reset_credentials("bob", tok, "")             # new_hash is required
    assert m.reset_credentials("bob", tok, "newhash") and m.credential_hash("bob") == "newhash"
    assert not m.reset_credentials("bob", tok, "again")        # single use
    assert not m.reset_credentials("eve", tok, "x")            # tied to the user


def test_recovery_expiry_and_lockout(monkeypatch):
    M = mod("MFA_RECOVERY_WORKFLOW")
    m = M.MFARecoveryWorkflow()
    with acting_as(ADMIN):
        code = m.issue_recovery_code("bob")
    real = time.time()
    monkeypatch.setattr(M, "_now", lambda: real + M.CODE_TTL + 1)
    assert m.verify_recovery_code("bob", code) is False        # expired
    monkeypatch.undo()
    with acting_as(ADMIN):
        code = m.issue_recovery_code("al")
    for _ in range(5):
        assert not m.verify_recovery_code("al", "00000000" if code != "00000000" else "11111111")
    assert m.verify_recovery_code("al", code) is False         # locked even for the right code


# ---- PIN_UNLOCK_LAYER ---------------------------------------------------------
def test_pin_is_salted_persisted_and_locks_out():
    P = mod("PIN_UNLOCK_LAYER").PINUnlockLayer
    p = P()
    assert p.register_pin("a", "1234") and not p.register_pin("a", "9999") and not p.register_pin("b", "12")
    raw = (agent_dir("PIN_UNLOCK_LAYER") / "pins.json").read_text()
    assert "1234" not in raw and "sha256" not in raw and json.loads(raw)["pins"]["a"].startswith("scrypt$")
    assert P().is_locked("a")                                  # a second worker sees the same state
    for _ in range(5):
        assert not p.unlock("a", "0000")
    assert not P().unlock("a", "1234") and P().is_locked("a")  # locked out, right PIN refused
    q = P()
    q.register_pin("c", "4321")
    assert q.unlock("c", "4321") and not q.is_locked("c")
    q.lock("c")
    assert q.is_locked("c") and not q.unlock("nobody", "4321")


# ---- OWNER_VERIFICATION -------------------------------------------------------
def test_owner_enrol_replace_and_partial():
    O = mod("OWNER_VERIFICATION").OwnerVerification
    o = O()
    assert o.enroll("f", "a", "v") is False                    # no caller
    with acting_as(MEMBER):
        assert o.enroll("f", "a", "v") is False
    with acting_as(ADMIN):
        assert o.enroll("f", "a", "v") is True
    with acting_as(MEMBER):
        assert o.enroll("x", "y", "z") is False                # cannot replace the owner
    assert O().verify("f", "a", "v") and not O().verify("f", "a", "x")
    assert O().partial_verify(finger="f", face="a")
    assert not O().partial_verify(finger="f")                  # one factor is never enough
    assert not O().partial_verify(finger="f", face="WRONG")
    assert not O().partial_verify(finger="f", pet="a")
    assert all(v.startswith("scrypt$") for v in O().owner_templates.values())


def test_owner_lockout():
    O = mod("OWNER_VERIFICATION").OwnerVerification
    o = O()
    with acting_as(ADMIN):
        o.enroll("f", "a", "v")
    for _ in range(5):
        assert not o.verify("f", "a", "bad")
    assert not o.verify("f", "a", "v")


# ---- IDENTITY_FRAMEWORK -------------------------------------------------------
def test_identity_lockout_and_unknown_user_costs_the_same(monkeypatch):
    I = mod("IDENTITY_FRAMEWORK")
    idf = I.IdentityFramework()
    assert idf.create_identity("al", "pw-good", {})
    calls = []
    real = I.hashlib.pbkdf2_hmac
    monkeypatch.setattr(I.hashlib, "pbkdf2_hmac", lambda *a, **k: calls.append(1) or real(*a, **k))
    assert not idf.validate_identity("ghost", "x")
    assert calls, "an unknown username must still be hashed"
    for _ in range(5):
        assert not idf.validate_identity("al", "wrong")
    assert not idf.validate_identity("al", "pw-good")          # locked
    assert not idf.validate_identity(None, "x")
