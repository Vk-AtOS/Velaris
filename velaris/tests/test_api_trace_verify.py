"""KAN-136: GET /trace/verify is administrators only, bounded and checkpointed."""
import json

from velaris.api import trace_check
from velaris.intel import trace
from velaris.tests.test_api_service import app_client, send


def test_only_admins_verify_and_checkpoint_matches_the_real_chain(tmp_path):
    c = app_client(tmp_path)
    denied = send(c, "GET", "/trace/verify", roles=["hr_admin"])
    assert denied.status_code == 403 and denied.json()["error"]["code"] == "admin_only"
    ok = send(c, "GET", "/trace/verify", roles=["governance_admin"]).json()
    assert ok["ok"] is True and ok["complete"] is True and ok["entries"] > 0


def test_bounded_walks_resume_from_the_checkpoint_and_detect_tampering():
    for i in range(30):
        trace.append("t", "a", {"i": i})
    first = trace_check.verify_incremental(max_entries=10)
    assert first["ok"] and first["entries"] == 10 and first["complete"] is False
    assert trace_check.verify_incremental(max_entries=100)["entries"] == 30
    trace.append("t", "a", {"i": 99})
    assert trace_check.verify_incremental()["entries"] == 31                  # only the new entry was read
    path = trace._path()
    lines = path.read_text().splitlines()
    forged = json.loads(lines[-1])
    forged["payload"] = {"i": 0}
    path.write_text("\n".join(lines[:-1] + [json.dumps(forged, sort_keys=True)]) + "\n")
    from velaris.agentkit.state import JsonState
    JsonState("API", "trace_checkpoint.json").save({"offset": 0, "prev": trace_check.GENESIS, "entries": 0})   # fresh walk
    bad = trace_check.verify_incremental()
    assert bad["ok"] is False and bad["broken_at"] == 31
    assert trace.verify()["ok"] is False


def test_waiting_runs_are_filtered_by_caller_before_the_cap_and_flow_connections_are_reused():
    from velaris.intel.flow import Flow
    from velaris.intel.llm import FakeLLM
    f = Flow([], llm=FakeLLM({}))

    def waiting_run(run_id, user, org="acme"):
        ev = []
        f._append(run_id, ev, "start", {"meta": {"caller": {"id": user, "org": org, "roles": [], "employee_id": None}}})
        f._append(run_id, ev, "gate", {})

    waiting_run("mine", "alice")
    for i in range(250):                                    # 250 newer runs of other people
        waiting_run(f"o{i}", "bob")
    waiting_run("other_org", "alice", "globex")
    assert f.waiting(limit=200)[0] != "mine"                # the old behaviour: crowded out
    assert f.waiting(org="acme", owner="alice", limit=200) == ["mine"]
    assert len(f.waiting(org="acme", limit=200)) == 200
    assert Flow([], llm=FakeLLM({}))._db is f._db           # same thread, same file: one connection
