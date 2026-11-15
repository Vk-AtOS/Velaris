"""KAN-73: per-user OAuth 2.0 (3LO) for the Atlassian connectors: state, exchange, refresh, revoke, scope, a user without access."""
import json
import urllib.parse

import httpx
import pytest

from velaris.agents.JIRA.atlassian import AtlassianClient, AtlassianError
from velaris.core import atlassian_oauth as ao
from velaris.core.access import Caller, acting_as
from velaris.intel import trace
from velaris.intel.paths import data_dir

ALICE, BOB = Caller("alice", "acme"), Caller("bob", "acme")
PUBLIC = lambda host: ["93.184.216.34"]            # noqa: E731


class Atlassian:
    """auth.atlassian.com + api.atlassian.com in one handler. Codes: 'code-<user>'; refresh tokens rotate; per-user project access."""

    def __init__(self):
        self.now, self.calls, self.reject_refresh, self.revoked_access = 1_800_000_000.0, [], set(), set()
        self.access_of = {"alice": {"KAN"}, "bob": {"OPS"}}
        self.n = 0

    def handle(self, request: httpx.Request) -> httpx.Response:
        host = request.headers["host"]
        body = json.loads(request.content) if request.content else {}
        self.calls.append((request.method, host, request.url.path, body, request.headers.get("authorization", "")))
        if host == "auth.atlassian.com" and request.url.path == "/oauth/token":
            if body["grant_type"] == "authorization_code":
                user = body["code"].removeprefix("code-")
                self.n += 1
                return httpx.Response(200, json={"access_token": f"at-{user}-{self.n}", "refresh_token": f"rt-{user}-{self.n}", "expires_in": 3600, "scope": "read:jira-work offline_access"})
            user = body["refresh_token"].split("-")[1]
            if user in self.reject_refresh:
                return httpx.Response(403, json={"error": "invalid_grant"})
            self.n += 1
            return httpx.Response(200, json={"access_token": f"at-{user}-{self.n}", "refresh_token": f"rt-{user}-{self.n}", "expires_in": 3600})
        if host == "api.atlassian.com" and request.url.path == "/oauth/token/accessible-resources":
            return httpx.Response(200, json=[{"id": "cloud-1", "url": "https://acme.atlassian.net", "scopes": []}])
        if host == "api.atlassian.com" and request.url.path.startswith("/ex/jira/cloud-1/"):
            auth = request.headers.get("authorization", "")
            user = auth.removeprefix("Bearer at-").split("-")[0]
            if user in self.revoked_access:
                return httpx.Response(401, json={"message": "revoked"})
            if "/issue/" in request.url.path:
                project = request.url.path.rsplit("/", 1)[-1].split("-")[0]
                if project not in self.access_of.get(user, set()):
                    return httpx.Response(404, json={"errorMessages": ["Issue does not exist or you do not have permission to see it."]})
                return httpx.Response(200, json={"key": request.url.path.rsplit("/", 1)[-1], "fields": {"project": {"key": project}}})
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(500)


@pytest.fixture
def world():
    a = Atlassian()
    t = httpx.MockTransport(a.handle)
    oa = ao.OAuth(client_id="cid", client_secret="csecret", redirect_uri="https://aetheros.example/cb", site="https://acme.atlassian.net", transport=t, resolver=PUBLIC, clock=lambda: a.now)
    client = AtlassianClient({"auth": "oauth", "oauth": oa, "jira_projects": "KAN,OPS"}, transport=t, resolver=PUBLIC)
    return a, oa, client


def connect(oa, user):
    url = oa.authorize_url(user)
    state = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["state"][0]
    return oa.exchange(user, f"code-{user.id}", state)


def test_authorize_url_and_state_rules(world):
    a, oa, _ = world
    url = oa.authorize_url(ALICE)
    q = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
    assert url.startswith(ao.AUTH_URL) and q["client_id"] == ["cid"] and q["audience"] == ["api.atlassian.com"] and "offline_access" in q["scope"][0]
    state = q["state"][0]
    with pytest.raises(ao.OAuthError) as e:                                   # another person cannot finish alice's flow
        oa.exchange(BOB, "code-bob", state)
    assert e.value.code == "state_invalid"
    assert oa.exchange(ALICE, "code-alice", state)["connected"] is True
    with pytest.raises(ao.OAuthError):                                        # single use
        oa.exchange(ALICE, "code-alice", state)
    expired = urllib.parse.parse_qs(urllib.parse.urlsplit(oa.authorize_url(ALICE)).query)["state"][0]
    a.now += ao.STATE_TTL_S + 1
    with pytest.raises(ao.OAuthError):
        oa.exchange(ALICE, "code-alice", expired)
    with pytest.raises(ao.OAuthError):
        oa.exchange(ALICE, "code-alice", expired[:-3] + "xyz")                # tampered
    assert not ao.OAuth().configured and ao.OAuth().redirect_uri == ""        # nothing configured: refuses to start a flow
    with pytest.raises(ao.OAuthError) as e:
        ao.OAuth().authorize_url(ALICE)
    assert e.value.code == "not_configured"


def test_tokens_are_sealed_on_disk_and_each_user_acts_with_their_own(world):
    a, oa, client = world
    connect(oa, ALICE)
    connect(oa, BOB)
    raw = (data_dir() / "agents" / "ATLASSIAN_OAUTH" / "tokens.json").read_bytes()
    assert b"at-alice" not in raw and b"rt-alice" not in raw and b"csecret" not in raw
    with acting_as(ALICE):
        assert client.request("GET", "/rest/api/3/issue/KAN-1")["key"] == "KAN-1"
    with acting_as(BOB):
        assert client.request("GET", "/rest/api/3/issue/OPS-9")["key"] == "OPS-9"
    sent = [(c[4], c[2]) for c in a.calls if c[2].startswith("/ex/jira/")]
    assert sent == [("Bearer at-alice-1", "/ex/jira/cloud-1/rest/api/3/issue/KAN-1"), ("Bearer at-bob-2", "/ex/jira/cloud-1/rest/api/3/issue/OPS-9")]


def test_a_user_without_access_gets_atlassians_refusal_and_no_caller_or_unconnected_user_gets_nothing(world):
    a, oa, client = world
    connect(oa, ALICE)
    with acting_as(ALICE):
        with pytest.raises(AtlassianError) as e:
            client.request("GET", "/rest/api/3/issue/OPS-9")                  # alice has no access to OPS: Atlassian says 404
        assert e.value.reason == "not_found" and e.value.status == 404
    with acting_as(BOB):                                                       # bob never connected: no fallback to a shared account
        with pytest.raises(AtlassianError) as e:
            client.request("GET", "/rest/api/3/issue/OPS-9")
        assert e.value.reason == "user_not_connected"
    with pytest.raises(AtlassianError) as e:                                   # no authenticated caller at all
        client.request("GET", "/rest/api/3/issue/KAN-1")
    assert e.value.reason == "unauthenticated"
    assert not [c for c in a.calls if c[1] == "api.atlassian.com" and "OPS-9" in c[2] and c[4].startswith("Bearer at-bob")]


def test_refresh_before_expiry_rotates_the_refresh_token_and_a_revoked_grant_needs_reauthorisation(world):
    a, oa, client = world
    connect(oa, ALICE)
    a.now += 3600 - 30                                                         # inside the refresh margin
    with acting_as(ALICE):
        assert client.request("GET", "/rest/api/3/issue/KAN-1")["key"] == "KAN-1"
    refreshes = [c for c in a.calls if c[3].get("grant_type") == "refresh_token"]
    assert len(refreshes) == 1 and refreshes[0][3]["refresh_token"] == "rt-alice-1"
    a.now += 3600
    with acting_as(ALICE):
        client.request("GET", "/rest/api/3/issue/KAN-1")
    assert [c[3]["refresh_token"] for c in a.calls if c[3].get("grant_type") == "refresh_token"] == ["rt-alice-1", "rt-alice-2"]   # the NEW one is used
    a.now += 3600
    a.reject_refresh.add("alice")                                              # revoked at Atlassian, or the refresh token expired
    with acting_as(ALICE), pytest.raises(AtlassianError) as e:
        client.request("GET", "/rest/api/3/issue/KAN-1")
    assert e.value.reason == "reauthorize_required" and oa.status(ALICE)["connected"] is False
    with acting_as(ALICE), pytest.raises(AtlassianError) as e:
        client.request("GET", "/rest/api/3/issue/KAN-1")
    assert e.value.reason == "user_not_connected"


def test_a_token_revoked_before_it_expires_is_refreshed_once_then_refused(world):
    a, oa, client = world
    connect(oa, ALICE)
    a.revoked_access.add("alice")
    with acting_as(ALICE), pytest.raises(AtlassianError) as e:
        client.request("GET", "/rest/api/3/issue/KAN-1")
    assert e.value.reason == "unauthorized"
    assert len([c for c in a.calls if c[3].get("grant_type") == "refresh_token"]) == 1      # exactly one forced refresh, no loop


def test_only_the_configured_site_can_be_bound_and_the_binding_is_rechecked(world):
    a, oa, client = world
    real = a.handle

    def two_sites(request):
        if request.url.path == "/oauth/token/accessible-resources":
            return httpx.Response(200, json=[{"id": "cloud-9", "url": "https://other.atlassian.net"}, {"id": "cloud-1", "url": "https://acme.atlassian.net"}])
        return real(request)
    oa._http = httpx.Client(transport=httpx.MockTransport(two_sites))
    assert connect(oa, ALICE)["site"] == "https://acme.atlassian.net"           # not sites[0]
    with acting_as(ALICE):
        client.request("GET", "/rest/api/3/issue/KAN-1")
    assert a.calls[-1][2].startswith("/ex/jira/cloud-1/")                          # the call went to the configured site's cloud id
    only_other = httpx.MockTransport(lambda r: httpx.Response(200, json=[{"id": "cloud-9", "url": "https://other.atlassian.net"}]) if r.url.path.endswith("accessible-resources") else real(r))
    oa._http = httpx.Client(transport=only_other)
    with pytest.raises(ao.OAuthError) as e:
        connect(oa, BOB)
    assert e.value.code == "exchange_failed" and oa.status(BOB)["connected"] is False
    assert not ao.OAuth(client_id="c", client_secret="s", redirect_uri="https://x/cb").configured       # no site configured: refuses to run
    oa.site = "https://moved.atlassian.net"                                      # the configured site changed after alice connected
    with acting_as(ALICE), pytest.raises(AtlassianError) as e:
        client.request("GET", "/rest/api/3/issue/KAN-1")
    assert e.value.reason == "reauthorize_required" and oa.status(ALICE)["connected"] is False


def test_a_revoke_during_a_refresh_is_not_resurrected(world):
    a, oa, client = world
    connect(oa, ALICE)
    a.now += 3600
    real = a.handle

    def revoke_mid_refresh(request):
        if request.url.path == "/oauth/token" and json.loads(request.content).get("grant_type") == "refresh_token":
            oa.revoke_user("acme", "alice", by="hr")                             # offboarding lands while the refresh is in flight
        return real(request)
    oa._http = httpx.Client(transport=httpx.MockTransport(revoke_mid_refresh))
    with acting_as(ALICE), pytest.raises(AtlassianError) as e:
        client.request("GET", "/rest/api/3/issue/KAN-1")
    assert e.value.reason == "user_not_connected" and oa.status(ALICE)["connected"] is False
    assert b"at-alice" not in (data_dir() / "agents" / "ATLASSIAN_OAUTH" / "tokens.json").read_bytes()


def test_revoking_a_user_on_offboarding_forgets_the_tokens_and_is_traced(world):
    a, oa, client = world
    connect(oa, ALICE)
    assert oa.revoke_user("acme", "alice", by="hr1") is True and oa.revoke_user("acme", "alice", by="hr1") is False
    with acting_as(ALICE), pytest.raises(AtlassianError) as e:
        client.request("GET", "/rest/api/3/issue/KAN-1")
    assert e.value.reason == "user_not_connected"
    assert any(x["action"] == "oauth.revoked" and x["payload"]["user"] == "alice" and x["payload"]["by"] == "hr1" for x in trace.entries())
    assert "at-alice" not in json.dumps(list(trace.entries()))                 # the trace never holds a token


def test_the_api_routes_connect_callback_status_disconnect_and_admin_revoke(tmp_path):
    from fastapi.testclient import TestClient
    from velaris.api.app import Settings, create_app
    from velaris.tests.test_api_service import KEY, SECRET, engine, send
    a = Atlassian()
    oa = ao.OAuth(client_id="cid", client_secret="csecret", redirect_uri="https://aetheros.example/cb", site="https://acme.atlassian.net", transport=httpx.MockTransport(a.handle),
                  resolver=PUBLIC, clock=lambda: a.now)
    import velaris.api.app as appmod
    real = appmod.mount_atlassian
    appmod.mount_atlassian = lambda app, authed, record, in_thread: real(app, authed, record, in_thread, oauth=oa)
    try:
        c = TestClient(create_app(Settings(secret=SECRET, identity_key=KEY.public_key(), flow_db=str(tmp_path / "f.db"), org="acme"), engine=engine()))
    finally:
        appmod.mount_atlassian = real
    assert send(c, "GET", "/integrations/atlassian/status", sub="alice").json() == {"configured": True, "connected": False, "site": None, "scope": []}
    url = send(c, "POST", "/integrations/atlassian/connect", {}, sub="alice").json()["authorize_url"]
    state = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)["state"][0]
    other = send(c, "GET", f"/integrations/atlassian/callback?code=code-alice&state={urllib.parse.quote(state)}", sub="bob")
    assert other.status_code == 400 and other.json()["error"]["code"] == "state_invalid"
    ok = send(c, "GET", f"/integrations/atlassian/callback?code=code-alice&state={urllib.parse.quote(state)}", sub="alice")
    assert ok.status_code == 200 and ok.json()["connected"] is True and "token" not in ok.text
    assert send(c, "GET", "/integrations/atlassian/status", sub="alice").json()["connected"] is True
    assert send(c, "POST", "/integrations/atlassian/revoke", {"user_id": "alice"}, sub="bob").status_code == 403
    assert send(c, "POST", "/integrations/atlassian/revoke", {"user_id": "alice"}, sub="hr", roles=["hr_admin"]).json() == {"revoked": True}
    assert send(c, "GET", "/integrations/atlassian/status", sub="alice").json()["connected"] is False
