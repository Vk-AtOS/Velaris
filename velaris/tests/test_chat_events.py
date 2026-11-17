"""The delivery protocol: snapshot and queue together, acknowledgement by last event id, long poll, expiry,
removed members, ordering, Server-Sent Events framing."""
import json
import threading
import time

import pytest

from velaris.tests.chat_support import ALICE, BOB, CARA, service
from velaris.chat.errors import ChatError
from velaris.chat.events import Hub, sse_frame, BadQueue
from velaris.chat.policy import Limits


def code(fn, *a, **k):
    with pytest.raises(ChatError) as e:
        fn(*a, **k)
    return e.value.code


def kinds(events):
    return [e["type"] for e in events]


@pytest.fixture
def room():
    s = service()
    cid = s.create_channel(ALICE, "public", "general", ["bob"])["id"]
    return s, cid


def test_register_returns_snapshot_and_queue_together(room):
    s, cid = room
    s.post(ALICE, cid, "before")
    r = s.register(BOB)
    assert r["last_event_id"] == -1 and r["queue_id"]
    snap = r["snapshot"]["channels"][0]
    assert snap["id"] == cid and snap["unread"] == 1 and r["snapshot"]["user"]["id"] == "bob"
    assert s.events(BOB, r["queue_id"], -1, 0) == []                           # what is in the snapshot is not also an event
    s.post(ALICE, cid, "after")
    got = s.events(BOB, r["queue_id"], -1, 0)
    assert kinds(got) == ["message"] and got[0]["message"]["body"] == "after" and got[0]["id"] == 0


def test_a_commit_between_snapshot_and_subscribe_is_delivered_exactly_once(room, monkeypatch):
    """The race the design removes: a send that lands while register() is building the snapshot cannot slip between
    the snapshot and the queue, because commits and register() take the same lock."""
    s, cid = room
    done = threading.Event()
    sender = threading.Thread(target=lambda: (s.post(ALICE, cid, "in flight"), done.set()))
    real = s._joined

    def joined_while_a_send_is_arriving(caller):
        rows = real(caller)
        sender.start()
        assert not done.wait(0.3), "the commit must wait for register() to finish"
        return rows
    monkeypatch.setattr(s, "_joined", joined_while_a_send_is_arriving)
    r = s.register(BOB)
    sender.join(5)
    assert done.is_set()
    assert r["snapshot"]["channels"][0]["last_message_id"] == 0                # not in the snapshot ...
    got = s.events(BOB, r["queue_id"], -1, 0)
    assert [e["message"]["body"] for e in got] == ["in flight"]                 # ... so it is in the queue, once
    assert s.events(BOB, r["queue_id"], got[-1]["id"], 0) == []


def test_snapshot_plus_events_cover_every_message_exactly_once_under_concurrency(room):
    s, cid = room
    stop, sent = threading.Event(), []

    def writer():
        for i in range(150):
            sent.append(s.post(ALICE, cid, f"m{i}")["id"])
        stop.set()
    t = threading.Thread(target=writer)
    t.start()
    regs = []
    while not stop.is_set():
        regs.append(s.register(BOB))
        time.sleep(0.002)
    t.join()
    assert len(regs) > 3
    for r in regs[-5:]:                                                          # a user keeps at most MAX_QUEUES_PER_USER queues
        last = r["snapshot"]["channels"][0]["last_message_id"]
        got = [e["message"]["id"] for e in s.events(BOB, r["queue_id"], -1, 0) if e["type"] == "message"]
        assert got == [i for i in sent if i > last], (last, got[:5])            # none lost, none twice, in order


def test_acknowledgement_by_last_event_id(room):
    s, cid = room
    r = s.register(BOB)
    q = r["queue_id"]
    for i in range(3):
        s.post(ALICE, cid, f"m{i}")
    first = s.events(BOB, q, -1, 0)
    assert [e["id"] for e in first] == [0, 1, 2]
    assert s.events(BOB, q, -1, 0) == first                                     # a lost response: same events again
    assert [e["id"] for e in s.events(BOB, q, 0, 0)] == [1, 2]                  # 0 acknowledged
    assert s.events(BOB, q, 2, 0) == []
    assert [e["id"] for e in s.events(BOB, q, -1, 0)] == []                      # acknowledged events stay dropped
    assert code(s.events, BOB, q, -2, 0) == "bad_request"
    assert code(s.events, BOB, q, "x", 0) == "bad_request"


def test_events_go_only_to_the_explicit_recipients(room):
    s, cid = room
    qa, qb, qc = (s.register(u)["queue_id"] for u in (ALICE, BOB, CARA))
    s.post(ALICE, cid, "hello")
    assert kinds(s.events(ALICE, qa, -1, 0)) == ["message"] and kinds(s.events(BOB, qb, -1, 0)) == ["message"]
    assert s.events(CARA, qc, -1, 0) == []                                     # not a member: nothing, not even a hint
    s.mark_read(BOB, cid)
    assert kinds(s.events(BOB, qb, 0, 0)) == ["read"] and s.events(ALICE, qa, 0, 0) == []    # your cursor is yours
    s.join(CARA, cid)
    s.post(ALICE, cid, "second")
    assert [e["message"]["body"] for e in s.events(CARA, qc, -1, 0) if e["type"] == "message"] == ["second"]   # not earlier ones


def test_a_queue_is_bound_to_its_user(room):
    s, cid = room
    q = s.register(BOB)["queue_id"]
    assert code(s.events, ALICE, q, -1, 0) == "bad_queue"
    assert code(s.events, BOB, "nope", -1, 0) == "bad_queue"
    assert not s.drop_queue(ALICE, q) and s.drop_queue(BOB, q)
    assert code(s.events, BOB, q, -1, 0) == "bad_queue"


def test_removed_member_gets_nothing_afterwards(room):
    s, cid = room
    other = s.create_channel(ALICE, "public", "other", ["bob"])["id"]
    q = s.register(BOB)["queue_id"]
    s.post(ALICE, cid, "queued before removal")
    s.post(ALICE, other, "other channel, unaffected")
    s.remove_member(ALICE, cid, "bob")
    s.post(ALICE, cid, "after removal")
    s.react(ALICE, s.history(ALICE, cid)["messages"][0]["id"], "x")
    s.edit(ALICE, s.history(ALICE, cid)["messages"][0]["id"], "edited after removal")
    got = s.events(BOB, q, -1, 0)
    bodies = [e["message"]["body"] for e in got if e["type"] == "message"]
    assert bodies == ["other channel, unaffected"]                              # nothing from the channel after (or before) removal
    removal = [e for e in got if e["type"] == "member"]
    assert len(removal) == 1 and removal[0]["op"] == "remove" and removal[0]["user_id"] == "bob"
    assert not [e for e in got if e.get("channel_id") == cid and e["type"] != "member"]
    assert code(s.history, BOB, cid, ) == "forbidden"
    s.leave(BOB, other)
    s.post(ALICE, other, "after leaving")
    assert all(e["type"] == "member" for e in s.events(BOB, q, max(e["id"] for e in got), 0))


def test_private_channel_events_stop_at_removal_and_nothing_reveals_it(room):
    s, _ = room
    pid = s.create_channel(ALICE, "private", "secret", ["bob"])["id"]
    q = s.register(BOB)["queue_id"]
    s.post(ALICE, pid, "classified")
    s.remove_member(ALICE, pid, "bob")
    s.post(ALICE, pid, "more classified")
    got = s.events(BOB, q, -1, 0)
    assert kinds(got) == ["member"] and "classified" not in json.dumps(got)


def test_long_poll_waits_then_times_out_empty(room):
    s, cid = room
    q = s.register(BOB)["queue_id"]
    start = time.monotonic()
    assert s.events(BOB, q, -1, 0.3) == []
    assert 0.25 <= time.monotonic() - start < 2.0
    timer = threading.Timer(0.15, lambda: s.post(ALICE, cid, "wake up"))
    timer.start()
    start = time.monotonic()
    got = s.events(BOB, q, -1, 10)
    assert [e["message"]["body"] for e in got] == ["wake up"] and time.monotonic() - start < 3.0
    timer.join()
    assert s.events(BOB, q, -1, -5) == got                                       # a negative timeout is no wait, not an error


def test_queues_expire_when_idle():
    clock = [0.0]
    s = service(hub=Hub(ttl=30, clock=lambda: clock[0]))
    cid = s.create_channel(ALICE, "public", "general", ["bob"])["id"]
    q = s.register(BOB)["queue_id"]
    clock[0] = 20
    assert s.events(BOB, q, -1, 0) == []                                         # polling keeps it alive
    clock[0] = 45
    assert s.events(BOB, q, -1, 0) == []
    clock[0] = 100
    assert code(s.events, BOB, q, -1, 0) == "bad_queue"
    assert s.hub.queues() == 0                                                   # the expired queue is gone
    s.post(ALICE, cid, "x")                                                      # emitting to a dead queue does nothing
    r = s.register(BOB)
    assert r["snapshot"]["channels"][0]["last_message_id"] == 1                  # a fresh register recovers everything
    clock[0] = 200
    s.register(CARA)
    assert s.hub.queues() == 1                                                   # expired queues are swept on register


def test_a_queue_that_falls_too_far_behind_is_dropped():
    s = service(limits=Limits(rate_capacity=10_000, rate_per_second=10_000, queue_max_events=3))
    cid = s.create_channel(ALICE, "public", "general", ["bob"])["id"]
    q = s.register(BOB)["queue_id"]
    for i in range(5):
        s.post(ALICE, cid, f"m{i}")
    assert code(s.events, BOB, q, -1, 0) == "bad_queue"                          # the client re-registers for a fresh snapshot
    assert len(s.register(BOB)["snapshot"]["channels"]) == 1


def test_ordering_within_a_channel_matches_message_ids(room):
    s, cid = room
    q = s.register(BOB)["queue_id"]
    threads = [threading.Thread(target=lambda n=n: [s.post(ALICE, cid, f"{n}-{i}") for i in range(20)]) for n in range(4)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    ids = [e["message"]["id"] for e in s.events(BOB, q, -1, 0) if e["type"] == "message"]
    assert ids == sorted(ids) and len(ids) == 80 == len(set(ids))
    assert [e["id"] for e in s.events(BOB, q, -1, 0)] == list(range(80))
    per_sender = [m["body"] for m in s.history(BOB, cid, limit=100)["messages"] if m["body"].startswith("0-")]
    assert per_sender == [f"0-{i}" for i in range(20)]                            # one sender's messages keep their order


def test_idempotent_resend_emits_one_event(room):
    s, cid = room
    q = s.register(BOB)["queue_id"]
    s.post(ALICE, cid, "once", local_id="abc")
    s.post(ALICE, cid, "once", local_id="abc")
    assert kinds(s.events(BOB, q, -1, 0)) == ["message"]


def test_hub_never_crosses_organisations():
    hub = Hub()
    q = hub.register("u", "acme")
    assert hub.emit(["u"], {"type": "x"}, org="evil") == 0
    assert hub.emit(["u"], {"type": "x"}, org="acme") == 1
    assert [e["id"] for e in hub.poll(q, "u", -1)] == [0]
    with pytest.raises(BadQueue):
        hub.poll(q, "someone-else", -1)


def test_sse_framing():
    frame = sse_frame({"id": 7, "type": "message", "message": {"body": "line1\nline2\r\nline3"}})
    text = frame.decode()
    assert text.startswith("id: 7\nevent: message\ndata: ") and text.endswith("\n\n") and text.count("\n\n") == 1
    data = text.split("data: ", 1)[1].rstrip("\n")
    assert "\n" not in data and json.loads(data)["message"]["body"] == "line1\nline2\r\nline3"
    assert sse_frame({"id": 1, "type": "a\nb: injected"}).decode().splitlines()[1] == "event: a b: injected"


def test_a_user_cannot_hold_unlimited_queues_or_long_polls():
    """KAN-69 SV2-07: every long poll holds a worker thread and every queue holds memory; both are capped per user."""
    import threading
    from velaris.chat import events as ev
    hub = ev.Hub()
    ids = [hub.register("alice", "acme") for _ in range(ev.MAX_QUEUES_PER_USER + 3)]
    assert hub.queues() == ev.MAX_QUEUES_PER_USER
    live = ids[-1]
    with pytest.raises(ev.BadQueue):
        hub.poll(ids[0], "alice", -1)                          # the oldest was evicted
    other = hub.register("bob", "acme")                        # another user is not affected
    assert hub.queues() == ev.MAX_QUEUES_PER_USER + 1
    started, outcome = threading.Barrier(ev.MAX_POLLS_PER_USER + 1), []

    def wait():
        started.wait()
        hub.poll(live, "alice", -1, timeout=0.6)
    ts = [threading.Thread(target=wait) for _ in range(ev.MAX_POLLS_PER_USER)]
    [t.start() for t in ts]
    started.wait()
    import time
    time.sleep(0.2)
    with pytest.raises(ev.TooManyPolls):
        hub.poll(live, "alice", -1, timeout=0.5)
    assert hub.poll(other, "bob", -1, timeout=0.01) == []     # bob can poll
    [t.join() for t in ts]
    assert hub.poll(live, "alice", -1, timeout=0.01) == []    # slots are released
