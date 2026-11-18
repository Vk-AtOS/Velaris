"""KAN-73: finalising an exit revokes the leaver's Atlassian tokens; a revocation failure keeps the exit open."""
from velaris.core import atlassian_oauth
from velaris.core.atlassian_oauth import OAuth
from velaris.tests.test_onboarding_records import HR1, ORG, acting_as, hire, make


def _token(emp, org=ORG):
    OAuth()._store.update(lambda d: d["tokens"].__setitem__(OAuth._key(org, emp), {"site": "s", "scope": "x"}))


def _finish(er, xid):
    for _ in range(3):
        for t in er.exit_status(xid)["tasks"]:
            if t["required"] and t["state"] in ("ready", "overdue"):
                er.complete_exit_task(xid, t["key"])


def test_finalise_exit_revokes_atlassian_tokens():
    er, *_ = make()
    e1, e2 = hire(er), "E9"
    _token(e1)
    _token(e2)
    with acting_as(HR1):
        xid = er.start_exit(e1, "2027-03-31", "resignation")["exit_id"]
        _finish(er, xid)
        assert er.finalise_exit(xid)["tokens_revoked"] == {"atlassian": True}
    tokens = OAuth()._store.load()["tokens"]
    assert OAuth._key(ORG, e1) not in tokens and OAuth._key(ORG, e2) in tokens          # only the leaver's


def test_revocation_failure_keeps_the_exit_open(monkeypatch):
    er, *_ = make()
    e1 = hire(er)
    _token(e1)
    with acting_as(HR1):
        xid = er.start_exit(e1, "2027-03-31", "resignation")["exit_id"]
        _finish(er, xid)
        with monkeypatch.context() as m:
            m.setattr(atlassian_oauth.OAuth, "revoke_user", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("store down")))
            assert er.finalise_exit(xid)["status"] == "revocation_failed"
        assert er.get_employee(e1)["employee"]["status"] == "notice"
    with acting_as(HR1):
        assert er.finalise_exit(xid)["status"] == "ok"
