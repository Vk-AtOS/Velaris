"""KAN-88: recovery, PIN, owner and identity agents are random, hashed, single-use, throttled and role-gated."""
import json
import time
from concurrent.futures import ThreadPoolExecutor
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
    assert t.begin("u") and t.begin("u")
    assert not secure.Throttle("T").begin("u")               # locked, also from another instance
    time.sleep(0.25)
    assert t.begin("u")
    t.clear("u")
    assert t.begin("u")


def test_throttle_reservation_is_atomic_under_parallel_guesses():
    t = secure.Throttle("T2", max_attempts=3, lock_seconds=60)
    with ThreadPoolExecutor(12) as ex:
        allowed = list(ex.map(lambda _: t.begin("u"), range(12)))
    assert sum(allowed) == 3                                 # not 12: check and count are one step


# ---- MFA_RECOVERY_WORKFLOW ----------------------------------------------------
BOB = Caller("bob", "kf", frozenset())
EVE = Caller("eve", "kf", frozenset())


def test_recovery_needs_admin_and_the_verifier_gets_the_token():
    m = mod("MFA_RECOVERY_WORKFLOW").MFARecoveryWorkflow()
    with acting_as(MEMBER):
        assert m.issue_recovery_code("bob") is None            # a member cannot mint codes
    assert m.issue_recovery_code("bob") is None                # nor can nobody
    with acting_as(ADMIN):
        code = m.issue_recovery_code("bob")
    assert len(code) == 8 and code.isdigit()
    assert not hasattr(m, "issue_reset_token")                 # no separate step another caller could redeem
    with acting_as(EVE):
        assert m.verify_recovery_code("bob", code) is None     # a stranger cannot consume or probe bob's code
    assert m.verify_recovery_code("bob", code) is None         # unauthenticated either
    with acting_as(BOB):
        tok = m.verify_recovery_code("bob", code)              # bob is the verifier and receives the token
        assert tok and m.verify_recovery_code("bob", code) is None       # consumed
    with acting_as(EVE):
        assert not m.reset_credentials("bob", tok, "evil")     # holding the token is not enough for eve
    with acting_as(BOB):
        assert not m.reset_credentials("bob", "wrong", "h")
        assert not m.reset_credentials("bob", tok, "")         # new_hash is required
        assert m.reset_credentials("bob", tok, "newhash") and m.credential_hash("bob") == "newhash"
        assert not m.reset_credentials("bob", tok, "again")    # single use


def test_recovery_expiry_and_lockout(monkeypatch):
    M = mod("MFA_RECOVERY_WORKFLOW")
    m = M.MFARecoveryWorkflow()
    with acting_as(ADMIN):
        code = m.issue_recovery_code("bob")
    real = time.time()
    monkeypatch.setattr(M, "_now", lambda: real + M.CODE_TTL + 1)
    with acting_as(BOB):
        assert m.verify_recovery_code("bob", code) is None     # expired
    monkeypatch.undo()
    with acting_as(ADMIN):
        code = m.issue_recovery_code("al")
    with acting_as(Caller("al", "kf", frozenset())):
        for _ in range(5):
            assert not m.verify_recovery_code("al", "00000000" if code != "00000000" else "11111111")
        assert m.verify_recovery_code("al", code) is None      # locked even for the right code


# ---- PIN_UNLOCK_LAYER ---------------------------------------------------------
def test_pin_is_salted_persisted_and_locks_out():
    P = mod("PIN_UNLOCK_LAYER").PINUnlockLayer
    p = P()
    assert not p.register_pin("a", "1234")                     # no caller: a user name cannot be claimed anonymously
    with acting_as(MEMBER):
        assert not p.register_pin("a", "1234")                 # bob cannot claim a's name
    with acting_as(Caller("a", "kf", frozenset())):
        assert p.register_pin("a", "1234") and not p.register_pin("a", "9999") and not p.register_pin("b", "12")
    with acting_as(MEMBER):
        p.lock("a")                                            # nor relock it
        assert p.unlock("a", "1234") and not p.is_locked("a")
    p.lock("a")                                                # no caller: refused, stays unlocked
    assert not p.is_locked("a")
    with acting_as(ADMIN):
        p.lock("a")                                            # a security admin may
    assert p.is_locked("a")
    raw = (agent_dir("PIN_UNLOCK_LAYER") / "pins.json").read_text()
    assert "1234" not in raw and "sha256" not in raw and json.loads(raw)["pins"]["a"].startswith("scrypt$")
    assert P().is_locked("a")                                  # a second worker sees the same state
    for _ in range(5):
        assert not p.unlock("a", "0000")
    assert not P().unlock("a", "1234") and P().is_locked("a")  # locked out, right PIN refused
    q = P()
    with acting_as(ADMIN):
        assert q.register_pin("c", "4321")
    assert q.unlock("c", "4321") and not q.is_locked("c")
    with acting_as(ADMIN):
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
    assert len(calls) == 1, "an unknown username must still be hashed"
    for _ in range(5):
        assert not idf.validate_identity("al", "wrong")
    calls.clear()
    assert not idf.validate_identity("al", "pw-good")          # locked
    assert len(calls) == 1, "the locked path must do the same hashing work as every other path"
    for _ in range(8):                                         # unknown names are throttled as one bucket too
        assert not idf.validate_identity("ghost", "x")
    assert not idf.validate_identity(None, "x")
    stored = json.loads((agent_dir("IDENTITY_FRAMEWORK") / "throttle.json").read_text())
    assert sorted(k for k in stored if k != "schema_version") == ["\x00unknown", "al"]   # no per-ghost state
