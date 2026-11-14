"""KAN-107: approved interview invitations are handed to velaris.mail as DRAFTS, once, under consent, and never sent."""
from velaris.agentkit import hr_wiring
from velaris.agentkit.hiring_testkit import as_
from velaris.agents.INTERVIEW_SCHEDULER.main import InterviewScheduler
from velaris.tests.mail_helpers import ADMIN, make_world
from velaris.tests.test_hiring_scheduler import book, env  # noqa: F401  (fixture)


def _box_for(c):
    store, _ob, _ib, _clock, relay, _boxes = make_world()
    box = store.create_mailbox(ADMIN, "hr@acme.com", owner_id=c["rec"].id)
    return store, relay, box["id"]


def _count(store, box):
    return store.one("SELECT COUNT(*) AS n FROM message WHERE mailbox_id=?", (box,))["n"]


def test_approved_invitation_becomes_a_mail_draft_once_and_is_never_sent(env):  # noqa: F811
    ats, sch, rid, apps, c = env
    store, relay, box = _box_for(c)
    sch2 = InterviewScheduler({"sender": hr_wiring.MailDraftSender(store, box)})
    with as_(c["rec"]):
        did = book(sch, apps[0], ["iv-a"], "14:00", "Round 1")["invitation_draft_id"]
        assert sch2.hand_off_to_mail(draft_id=did)["status"] == "conflict"          # not approved yet
        sch.approve_draft(draft_id=did)
        out = sch2.hand_off_to_mail(draft_id=did)
        assert out["status"] == "ok" and out["sent"] is False and _count(store, box) == 1
        assert sch2.hand_off_to_mail(draft_id=did)["status"] == "conflict"          # once only
        assert [d for d in sch.list_drafts(status="handed_off")["drafts"]][0]["id"] == did
    assert relay.sent == [] and _count(store, box) == 1
    msg = store.one("SELECT * FROM message WHERE mailbox_id=?", (box,))
    assert msg["draft"] == 1 and "Hello Person Number0" in msg["body_text"] and "{" not in msg["body_text"]


def test_hand_off_needs_a_mailbox_and_candidate_consent(env):  # noqa: F811
    ats, sch, rid, apps, c = env
    with as_(c["rec"]):
        did = book(sch, apps[0], ["iv-a"], "14:00", "Round 1")["invitation_draft_id"]
        sch.approve_draft(draft_id=did)
        assert sch.hand_off_to_mail(draft_id=did)["status"] == "not_configured"
    store, relay, box = _box_for(c)
    sch2 = InterviewScheduler({"sender": hr_wiring.MailDraftSender(store, box)})
    with as_(c["rec"]):
        cid = [d for d in sch.list_drafts(status="approved")["drafts"]][0]["to"]["candidate_id"]
        assert ats.withdraw_consent(candidate_id=cid)["status"] == "ok"
        assert sch2.hand_off_to_mail(draft_id=did)["status"] == "denied"             # consent withdrawn: no contact details
        assert [d["status"] for d in sch.list_drafts(status="approved")["drafts"]] == ["approved"]      # released, can be retried
    assert _count(store, box) == 0 and relay.sent == []
