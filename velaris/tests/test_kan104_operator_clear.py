"""KAN-104: an action id left 'in_progress' by a crash can be cleared by an operator, and only by one."""
from importlib import import_module

from velaris.core.access import SECURITY_ADMIN, Caller, acting_as
from velaris.intel import trace


def _aae():
    mod = lambda p, n: getattr(import_module(f"departments.{p}.main"), n)
    policy = mod("_ai_core.AAE_POLICY", "AAE_POLICYAgent")([{"id": "ok", "effect": "allow", "if": [{"field": "type", "value": "noop"}]}])
    return mod("_ai_core.AAE_RUNTIME", "AAE_RUNTIMEAgent")(policy)


def _as(*roles):
    return acting_as(Caller("u1", "kf", frozenset(roles)))


def test_clear_stuck_needs_admin_and_reruns_once_cleared():
    a = _aae()
    calls = []

    def dies(p):
        calls.append(1)
        if len(calls) == 1:
            raise SystemExit                       # the process dies mid-handler: nothing is recorded
        return "ok"
    a.register("noop", dies)
    act = {"id": "z1", "type": "noop", "params": {}}
    with _as():
        try:
            a.run(act)
        except SystemExit:
            pass
        assert a.run(act)["status"] == "in_progress"
        assert a.clear_stuck("z1")["status"] == "denied"
    with _as(SECURITY_ADMIN):
        assert a.clear_stuck("z1")["status"] == "ok"
        assert a.clear_stuck("z1")["status"] == "not_stuck"
        assert a.run(act)["status"] == "ok"
        assert a.clear_stuck("z1")["status"] == "not_stuck"          # a finished record is never cleared
    assert len(calls) == 2
    assert any(e["action"] == "action.cleared" for e in trace.entries())
