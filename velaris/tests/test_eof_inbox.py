"""Defect 13: the EOF queues have a reader, and an unread queue cannot grow without bound."""
import pytest

from velaris.agents.EOF_GATEWAY import main as gw
from velaris.agents.EOF_GATEWAY.main import EOF_GATEWAYAgent
from velaris.core.access import Caller, acting_as
from velaris.orchestration import inbox

ASHA = Caller("asha", "acme")


@pytest.fixture(autouse=True)
def _data(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))


class Consumer:
    def on_message(self, message):
        return message


class Silent:
    pass


class FakeEngine:
    def __init__(self, cls, fail=False):
        self.cls, self.ran, self.fail = cls, [], fail

    def agent_class(self, name):
        if name == "NOPE":
            raise LookupError(name)
        return self.cls

    def run(self, agent, method, params, caller=None):
        self.ran.append((agent, method, params["message"]["payload"], caller.id))
        if self.fail:
            raise RuntimeError("boom")


def send(n):
    with acting_as(ASHA):
        return EOF_GATEWAYAgent().route("ORCHESTRIX", {"n": n})


def test_messages_reach_an_agent_that_defines_on_message_as_that_agent():
    assert [send(n)["routed"] for n in (1, 2)] == [True, True]
    eng = FakeEngine(Consumer)
    out = inbox.deliver("ORCHESTRIX", engine=eng, org="acme")
    assert out["delivered"] == 2 and out["consumer"] is True
    assert eng.ran == [("ORCHESTRIX", "on_message", {"n": 1}, "ORCHESTRIX"), ("ORCHESTRIX", "on_message", {"n": 2}, "ORCHESTRIX")]
    assert inbox.deliver("ORCHESTRIX", engine=eng, org="acme")["delivered"] == 0          # taken once


def test_an_agent_without_on_message_leaves_its_messages_queued_and_says_so():
    send(1)
    out = inbox.deliver("ORCHESTRIX", engine=FakeEngine(Silent), org="acme")
    assert out["consumer"] is False and "stay queued" in out["reason"]
    assert inbox.deliver("NOPE", engine=FakeEngine(Silent))["consumer"] is False
    assert inbox.deliver("ORCHESTRIX", engine=FakeEngine(Consumer), org="acme")["delivered"] == 1     # still there


def test_a_failing_handler_is_counted_and_the_rest_still_go():
    send(1), send(2)
    out = inbox.deliver("ORCHESTRIX", engine=FakeEngine(Consumer, fail=True), org="acme")
    assert out["failed"] == 2 and out["delivered"] == 0


def test_an_inbox_nobody_reads_stops_accepting_at_the_backlog_limit(monkeypatch):
    monkeypatch.setattr(gw, "MAX_BACKLOG", 2)
    assert send(1)["routed"] and send(2)["routed"]
    full = send(3)
    assert full["routed"] is False and full["status"] == "queue_full"
    inbox.deliver("ORCHESTRIX", engine=FakeEngine(Consumer), org="acme")          # reading frees the room
    assert send(4)["routed"] is True
