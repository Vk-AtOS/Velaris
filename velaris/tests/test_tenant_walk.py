"""KAN-104 / KAN-115 (Velaris side): a tenant-isolation walk over every route of the real app.

A caller whose signed identity names another organisation than the deployment's (Settings.org) must get a refusal from EVERY
route that serves identities (chat, mail, hr, control, flows, memory, brain ...), whatever its path parameters name and whether
or not the target exists: never a 2xx, never a 5xx, never a body that names the deployment's data. A positive control with
the right organisation proves the walk reaches handlers (most routes then answer something other than wrong_organisation)."""
import re

import pytest
from fastapi.testclient import TestClient

from velaris.api.app import Settings, create_app
from velaris.tests.chat_support import KEY, ORG, SECRET, send

OPEN = {"/health", "/healthz", "/readyz", "/chat/health", "/openapi.json", "/docs", "/redoc", "/docs/oauth2-redirect"}   # unauthenticated by design
SAMPLE = {"hash": "a" * 64, "sha": "a" * 64}


@pytest.fixture(scope="module")
def api():
    app = create_app(Settings(secret=SECRET, identity_key=KEY.public_key(), org=ORG), engine=object())
    return TestClient(app, raise_server_exceptions=False)     # engine=object(): handlers that need an engine answer 500 for anyone


def routes(api):
    out = []
    for r in api.app.routes:
        if not hasattr(r, "methods") or r.path in OPEN:
            continue
        for m in sorted(r.methods - {"HEAD", "OPTIONS"}):
            out.append((m, re.sub(r"\{([^}:]+)(?::[^}]*)?\}", lambda g: SAMPLE.get(g.group(1), "1"), r.path)))
    return sorted(out)


def test_every_route_refuses_another_organisation(api):
    leaks = []
    seen = routes(api)
    assert len(seen) > 40, "the walk found too few routes to mean anything"
    for method, path in seen:
        body = {} if method in ("POST", "PUT", "PATCH", "DELETE") else None
        r = send(api, method, path, body, sub="mallory", org="evil")
        if r.status_code < 400 or r.status_code >= 500 or "wrong_organisation" not in r.text and r.status_code not in (401, 403, 404):
            leaks.append((method, path, r.status_code, r.text[:120]))
    assert not leaks, leaks


def test_the_walk_reaches_handlers_for_the_right_organisation(api):
    reached = 0
    for method, path in routes(api):
        body = {} if method in ("POST", "PUT", "PATCH", "DELETE") else None
        r = send(api, method, path, body, sub="alice", org=ORG)
        reached += "wrong_organisation" not in r.text and r.status_code != 401
    assert reached > 30
