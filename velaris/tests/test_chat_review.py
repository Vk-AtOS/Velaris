"""Review findings on the assistant's approval path: the chat_admin registry, who is told about a proposal, and
authors hidden behind assistant text."""
import json

from velaris.chat.assistant import CONTEXT_MESSAGES as CONTEXT_WINDOW, Assistant
from velaris.chat.store import Store
from velaris.intel.llm import FakeLLM
from velaris.tests.chat_support import ADMIN, ALICE, BOB, CARA, ORG, service, who
from velaris.tests.test_chat_assistant import BOT, MENTION, World, code, fake, post_to_ops, proposal, reply, row


# ── review findings: admin registry, approver notification, context laundering ─
class Clock:
    def __init__(self):
        self.t = 1_000_000.0

    def __call__(self):
        return self.t


def dm_proposal(w, requester=BOB):
    dm = w.s.create_channel(requester, "direct", members=[BOT])["id"]
    return proposal(w, requester, channel=dm)


def test_a_chat_admin_claim_is_registered_only_after_the_identity_and_org_checks():
    s = service()
    s.list_channels(ALICE)                                                     # alice belongs to acme
    stranger = who("alice", org="evil", roles=["chat_admin"])
    assert code(s.list_channels, stranger) == "wrong_organisation"
    eve = who("eve", org="evil")
    dm = s.create_channel(eve, "direct", members=[BOT])["id"]
    llm = FakeLLM(lambda p, m: reply("", {"tool": "post_message", "args": {"channel_id": dm, "body": "x"}}))
    m = s.post(eve, dm, "do it")
    out = Assistant(s, llm=llm).handle(eve, m["id"])
    assert out[0]["proposal"]["status"] == "no_eligible_approver"


def test_a_revoked_chat_admin_is_pruned_on_their_next_call_and_no_longer_an_approver():
    w = World(fake())
    w.s.list_channels(ADMIN)
    w.s.list_channels(who("root"))                                             # same person, role gone from their assertion
    assert dm_proposal(w)["status"] == "no_eligible_approver"
    w.s.list_channels(ADMIN)                                                   # role granted again: eligible again
    assert dm_proposal(w)["status"] == "waiting_approval"


def test_a_chat_admin_not_heard_from_for_a_week_is_not_an_approver():
    clock = Clock()
    w = World(fake())
    w.s.clock = clock
    w.s.list_channels(ADMIN)
    clock.t += 8 * 86400
    assert dm_proposal(w)["status"] == "no_eligible_approver"


def test_an_approver_who_lost_the_role_is_not_notified_and_non_members_get_no_details():
    w = World(fake())
    w.s.list_channels(ADMIN)
    q = w.s.register(ADMIN)["queue_id"]
    p = dm_proposal(w)
    w.a.confirm_proposal(BOB, p["run_id"], p["call_hash"])
    got = [e for e in w.events(ADMIN, q) if e["type"] == "assistant_proposal"]
    assert [e["op"] for e in got] == ["waiting"] and "args" not in got[0] and "tool" not in got[0]
    assert w.a.proposals(ADMIN)[0]["args"]["body"] == "hello from the assistant"      # details only through the re-checking call
    assert w.a.proposals(who("root")) == []
    q2 = w.s.register(ADMIN)["queue_id"]
    p2 = dm_proposal(w)
    w.s.list_channels(who("root"))                                             # role revoked before the requester confirms
    w.a.confirm_proposal(BOB, p2["run_id"], p2["call_hash"])
    assert [e for e in w.events(who("root"), q2) if e["type"] == "assistant_proposal"] == []


def test_the_requester_confirming_notifies_only_approvers_who_still_qualify_by_membership():
    w = World(fake())
    p = proposal(w)                                                            # alice (owner) is the stored approver
    qa = w.s.register(ALICE)["queue_id"]
    w.s.set_role(ALICE, w.gen, "bob", "owner")
    w.s.set_role(ALICE, w.gen, "alice", "member")                              # demoted before the requester confirms
    w.a.confirm_proposal(BOB, p["run_id"], p["call_hash"])
    assert [e for e in w.events(ALICE, qa) if e["type"] == "assistant_proposal"] == []


def test_an_assistant_reply_carries_the_authors_it_was_built_from_into_later_proposals():
    clock = Clock()
    w = World(fake())
    w.s.clock = clock
    w.s.set_role(ALICE, w.gen, "cara", "admin")
    w.s.post(CARA, w.gen, "ops needs to hear hello")
    w.llm.script = lambda p, m: reply("Ops needs to hear hello.")
    w.say(ALICE, MENTION + "what does ops need?")
    clock.t += 2 * 86400                                                       # outside the recent-poster window
    for i in range(19):
        w.s.post(BOB, w.gen, f"filler {i}")
    w.llm.script = lambda p, m: reply("", post_to_ops(w))
    _, out = w.say(BOB, MENTION + "tell ops")
    approvers = json.loads(row(w, out[0]["proposal"]["run_id"])["approvers"])
    assert "cara" not in approvers and "alice" not in approvers
    assert {"cara", "alice"} <= set(json.loads(row(w, out[0]["proposal"]["run_id"])["context_authors"]))


def test_anyone_who_posted_in_the_topic_lately_is_not_an_approver_even_outside_the_window():
    w = World(fake())
    w.s.set_role(ALICE, w.gen, "cara", "admin")
    w.s.post(CARA, w.gen, "ops needs to hear hello")
    for i in range(CONTEXT_WINDOW + 1):
        w.s.post(BOB, w.gen, f"filler {i}")
    p = proposal(w)
    assert "cara" not in json.loads(row(w, p["run_id"])["approvers"])
    w.s.set_org_settings(ADMIN, {"approver_exclude_hours": 0})
    assert "cara" in json.loads(row(w, proposal(w)["run_id"])["approvers"])


def test_messages_written_before_the_provenance_column_widen_to_the_window_before_them():
    w = World(fake())
    w.s.set_role(ALICE, w.gen, "cara", "admin")
    w.s.post(CARA, w.gen, "ops needs to hear hello")
    m = w.s.post_as_assistant(ORG, BOT, w.gen, "Ops needs to hear hello.")
    with w.s._write() as db:
        db.execute("UPDATE messages SET context_authors=NULL WHERE id=?", (m["id"],))   # as if written by the old code
    w.s.set_org_settings(ADMIN, {"approver_exclude_hours": 0})
    p = proposal(w)
    assert "cara" in json.loads(row(w, p["run_id"])["context_authors"])


def test_an_old_database_gains_the_provenance_column_once(tmp_path):
    path = str(tmp_path / "old.db")
    Store(path).db.execute("ALTER TABLE messages DROP COLUMN context_authors")
    for _ in range(2):
        st = Store(path)
        assert "context_authors" in {r["name"] for r in st.all("PRAGMA table_info(messages)")}
        st.db.close()
