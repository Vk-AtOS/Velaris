"""velaris.chat.policy: the access matrix, organisation check, rate limits, mentions."""
import itertools

import pytest

from velaris.chat import policy
from velaris.chat.policy import Limits, TokenBucket, decide

ORG = "acme"
ALL = set(policy.ACTIONS)


def allowed(kind, role, **facts):
    return {a for a in policy.ACTIONS
            if decide(action=a, kind=kind, role=role, caller_org=ORG, record_org=ORG, **facts).allowed}


# role -> actions allowed when the caller is NOT the author of the message and nothing is archived or held
NAMED_OWNER = {"view", "post", "react", "delete", "invite", "remove", "pin", "manage", "set_role", "leave"}
NAMED_ADMIN = {"view", "post", "react", "delete", "invite", "remove", "pin", "manage", "leave"}
PUBLIC_MEMBER = {"view", "post", "react", "invite", "leave"}
PRIVATE_MEMBER = {"view", "post", "react", "leave"}
FIXED = {"view", "post", "react", "pin"}

MATRIX = {
    ("public", "owner"): NAMED_OWNER, ("public", "admin"): NAMED_ADMIN, ("public", "member"): PUBLIC_MEMBER,
    ("public", None): {"join"},
    ("private", "owner"): NAMED_OWNER, ("private", "admin"): NAMED_ADMIN, ("private", "member"): PRIVATE_MEMBER,
    ("private", None): set(),
    ("direct", "member"): FIXED, ("direct", None): set(),
    ("group", "member"): FIXED | {"leave"}, ("group", None): set(),
}


@pytest.mark.parametrize("kind,role", sorted(MATRIX, key=str))
def test_matrix_roles_by_kinds_by_actions(kind, role):
    assert allowed(kind, role) == MATRIX[(kind, role)]


def test_fixed_conversations_give_no_admin_powers_whatever_the_role():
    for kind, role in itertools.product(("direct", "group"), ("owner", "admin", "member")):
        got = allowed(kind, role)
        assert not got & {"invite", "remove", "manage", "set_role", "delete", "edit"}


def test_author_rules():
    for kind, role in (("public", "member"), ("private", "member"), ("direct", "member"), ("group", "member")):
        assert {"edit", "delete"} <= allowed(kind, role, author=True)
    assert "edit" not in allowed("public", "owner")            # nobody edits another person's words, owners included
    assert "delete" in allowed("public", "admin") and "delete" not in allowed("private", "member")


def test_archived_channel_is_read_and_delete_only():
    got = allowed("public", "owner", archived=True, author=True)
    assert got == {"view", "delete", "remove", "manage", "set_role", "leave"}
    assert "join" not in allowed("public", None, archived=True)


def test_legal_hold_blocks_every_delete():
    for kind, role in MATRIX:
        if role:
            assert "delete" not in allowed(kind, role, author=True, legal_hold=True)
    assert decide(action="delete", kind="public", role="owner", caller_org=ORG, record_org=ORG, legal_hold=True).reason == "legal hold"


def test_admin_cannot_remove_an_owner():
    d = lambda role, target: decide(action="remove", kind="public", role=role, caller_org=ORG, record_org=ORG, target_role=target)
    assert not d("admin", "owner").allowed and d("owner", "owner").allowed and d("admin", "member").allowed


def test_deny_by_default_and_organisation_check():
    assert not decide(action="launch", kind="public", role="owner", caller_org=ORG, record_org=ORG).allowed
    assert not decide(action="view", kind="wiki", role="owner", caller_org=ORG, record_org=ORG).allowed
    assert not decide(action="view", kind="public", role="root", caller_org=ORG, record_org=ORG).allowed
    assert not decide(action="view", kind="public", role="owner", caller_org="", record_org="").allowed
    assert not decide(action="view", kind="public", role="owner", caller_org=ORG, record_org="other").allowed
    assert not decide(action="view", kind="public", role="owner", caller_org=ORG, record_org=ORG, deployment_org="other").allowed
    assert not decide(action="join", kind="public", role=None, caller_org=ORG, record_org="other").allowed
    assert decide(action="view", kind="public", role="member", caller_org=ORG, record_org=ORG, deployment_org=ORG).allowed


def test_decide_is_deterministic():
    args = dict(action="pin", kind="private", role="admin", caller_org=ORG, record_org=ORG)
    assert len({decide(**args) for _ in range(20)}) == 1


def test_token_bucket_burst_then_refill():
    now = [0.0]
    b = TokenBucket(3, 1.0, clock=lambda: now[0])
    assert [b.allow("u") for _ in range(4)] == [True, True, True, False]
    assert b.allow("v")                                          # per sender
    now[0] = 2.0
    assert b.allow("u") and b.allow("u") and not b.allow("u")
    now[0] = 1000.0
    assert sum(b.allow("u") for _ in range(10)) == 3             # never above capacity


def test_mentions_and_ids():
    assert policy.mentions("hi @[bob] and @[assistant:velaris], @[bob] again @[all]") == ["bob", "assistant:velaris", "all"]
    assert policy.mentions("@bob no brackets, @[] empty, @[a b] spaced") == []
    assert policy.strip_mention("@[assistant:velaris] summarise this", "assistant:velaris") == "summarise this"
    assert policy.valid_user_id("alice@acme.com") and not policy.valid_user_id("assistant:velaris")
    assert not policy.valid_user_id("a b") and not policy.valid_user_id("") and not policy.valid_user_id("x" * 129)
    assert policy.valid_assistant_id("assistant:velaris") and not policy.valid_assistant_id("assistant:")
    assert policy.valid_emoji("thumbs_up") and policy.valid_emoji("👍") and not policy.valid_emoji("a b")
    assert Limits().max_body == 10_000
