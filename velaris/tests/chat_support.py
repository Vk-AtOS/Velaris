"""Shared helpers for the test_chat_*.py files."""
import json
import secrets

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from velaris.api.app import Settings, create_app
from velaris.api.auth import make_assertion, sign
from velaris.chat.policy import Limits
from velaris.chat.service import ChatService
from velaris.core.access import Caller
from velaris.intel import trace

SECRET = b"c" * 32
KEY = Ed25519PrivateKey.generate()
ORG = "acme"


def who(name, org=ORG, roles=()):
    return Caller(id=name, org=org, roles=frozenset(roles))


ALICE, BOB, CARA, DAN = who("alice"), who("bob"), who("cara"), who("dan")
ADMIN = who("root", roles=["chat_admin"])


def service(**kw):
    """A service whose rate limit is out of the way (the rate-limit tests install their own bucket)."""
    kw.setdefault("limits", Limits(rate_capacity=10_000, rate_per_second=10_000))
    return ChatService(**kw)


def chat_trace(action=None):
    return [e["payload"] for e in trace.entries() if e["actor"] == "chat" and (action is None or e["action"] == action)]


def trace_text():
    return json.dumps(list(trace.entries()))


def api_client(llm=None, tools=None, svc=None):
    """A TestClient for the whole app (the chat router is mounted by create_app); `llm` is the assistant's model."""
    settings = Settings(secret=SECRET, identity_key=KEY.public_key(), org=ORG, llm=llm)
    app = create_app(settings, engine=object())
    return TestClient(app)


def signed(method, path, content=b"", *, sub="alice", org=ORG, roles=(), nonce=None):
    nonce = nonce or secrets.token_urlsafe(16)
    identity = make_assertion(KEY, sub=sub, org=org, roles=roles, nonce=nonce)
    return sign(SECRET, method, path, content, identity, nonce=nonce)


def send(client, method, path, body=None, *, sub="alice", org=ORG, roles=(), raw=None, nonce=None, headers=None):
    content = raw if raw is not None else (b"" if body is None else json.dumps(body).encode())
    nonce = nonce or secrets.token_urlsafe(16)
    identity = make_assertion(KEY, sub=sub, org=org, roles=roles, nonce=nonce)
    h = headers or sign(SECRET, method, path, content, identity, nonce=nonce)
    return client.request(method, path, content=content, headers=h)
