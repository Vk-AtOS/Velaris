"""JIRA and CONFLUENCE connectors against httpx.MockTransport. No real Atlassian call.

Covers: auth header, token-paged search, 429 + Retry-After, address and host gates, redirects,
no secrets in errors, the guard on fetched text, markdown conversion, ingest into the document
library, and the approval path (direct calls refused; the allowlisted act path answers 202 and
executes only after a second person approves).
"""
import json
import secrets
import types

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from velaris.agents.CONFLUENCE.main import storage_to_markdown
from velaris.agents.JIRA import atlassian
from velaris.agents.JIRA.atlassian import AtlassianClient, AtlassianError
from velaris.agents.JIRA.main import CONSEQUENTIAL_METHODS, READ_ONLY_METHODS, JiraConnector
from velaris.api import allowlist
from velaris.api.allowlist import ACT, READ, rule_for
from velaris.api.app import Settings, create_app
from velaris.api.auth import make_assertion, sign
from velaris.backend.engine import BackendEngine
from velaris.intel.docs import DocStore
from velaris.intel.llm import FakeLLM
from velaris.tests.atlassian_kit import EMAIL, TOKEN, SITE, CREDS, PUBLIC, INJECTION, Site, jira, confluence, issue, page, RecordingLibrary, space_route, _run_in_execute


@pytest.fixture(autouse=True)
def _data(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))


# ── client: credentials, hosts, addresses, redirects, rate limits ─────────
def test_basic_auth_and_search_uses_token_paging():
    pages = [{"issues": [issue(1), issue(2)], "nextPageToken": "T1"}, {"issues": [issue(3)], "isLast": True}]

    def route(req):
        assert req.url.path == "/rest/api/3/search/jql"
        return httpx.Response(200, json=pages[1] if req.url.params.get("nextPageToken") == "T1" else pages[0])

    c, site = jira(route)
    out = c.search_issues("project = ABC ORDER BY created DESC", max_results=10)
    assert out["count"] == 3 and [i["key"] for i in out["issues"]] == ["ABC-1", "ABC-2", "ABC-3"]
    assert len(site.requests) == 2 and site.requests[0].url.params["jql"] == 'project in ("ABC") AND (project = ABC) ORDER BY created DESC'
    assert "nextPageToken" not in site.requests[0].url.params
    capped = jira(lambda r: httpx.Response(200, json=pages[0]))[0].search_issues("x = 1", max_results=2)
    assert capped["count"] == 2


def test_projects_use_start_at_paging():
    def route(req):
        start = int(req.url.params.get("startAt", 0))
        values = [{"key": f"P{i}", "name": f"Project {i}", "id": str(i)} for i in range(start, min(start + 2, 3))]
        return httpx.Response(200, json={"values": values, "startAt": start, "isLast": start + 2 >= 3})

    site = Site(route)
    c = JiraConnector({**CREDS, "jira_projects": "P0, P1,P2"}, **site.client_args())
    assert [p["key"] for p in c.list_projects()["projects"]] == ["P0", "P1", "P2"]


def test_429_retry_after_is_waited_out_then_succeeds():
    seen = []

    def route(req):
        seen.append(1)
        if len(seen) < 3:
            return httpx.Response(429, headers={"Retry-After": "2"})
        return httpx.Response(200, json=issue(1))

    c, site = jira(route)
    assert c.get_issue("ABC-1")["issue"]["key"] == "ABC-1" and site.sleeps == [2.0, 2.0]


def test_429_gives_up_and_caps_the_wait():
    c, site = jira(lambda r: httpx.Response(429, headers={"Retry-After": "9999"}))
    with pytest.raises(AtlassianError) as e:
        c.get_issue("ABC-1")
    assert e.value.reason == "rate_limited" and len(site.requests) == 4 and site.sleeps == [60.0] * 3


def test_errors_never_carry_credentials_or_personal_data():
    c, _ = jira(lambda r: httpx.Response(401, text="bad credentials for bob@acme.test"))
    with pytest.raises(AtlassianError) as e:
        c.get_issue("ABC-1")
    text = str(e.value)
    assert e.value.reason == "unauthorized" and TOKEN not in text and EMAIL not in text and "bob@acme.test" not in text
    assert "[EMAIL]" in text


def test_redirects_are_not_followed():
    c, site = jira(lambda r: httpx.Response(302, headers={"location": "https://evil.test/x"}))
    with pytest.raises(AtlassianError) as e:
        c.get_issue("ABC-1")
    assert e.value.reason == "redirect_refused" and len(site.requests) == 1


def test_private_address_is_blocked_before_any_request():
    site = Site(lambda r: httpx.Response(200, json={}))
    c = JiraConnector(dict(CREDS), transport=httpx.MockTransport(site.handler), resolver=lambda h: ["10.0.0.5"])
    with pytest.raises(AtlassianError) as e:
        c.get_issue("ABC-1")
    assert e.value.reason == "blocked" and site.requests == []


@pytest.mark.parametrize("site_url,ok", [("https://acme.atlassian.net", True), ("http://acme.atlassian.net", False),
                                         ("https://acme.example.com", False), ("https://atlassian.net.evil.test", False)])
def test_site_must_be_https_atlassian(site_url, ok):
    assert AtlassianClient({**CREDS, "site": site_url}).configured is ok
    assert AtlassianClient({**CREDS, "site": "https://wiki.corp.test", "allowed_hosts": ["wiki.corp.test"]}).configured


def test_credentials_come_from_the_vault_and_missing_ones_fail_closed():
    class Vault:
        def __init__(self, data):
            self.data = data

        def get_secret(self, name):
            return self.data.get(name)

    full = Vault({"ATLASSIAN_EMAIL": EMAIL, "ATLASSIAN_API_TOKEN": TOKEN, "ATLASSIAN_SITE": SITE})
    assert JiraConnector({}, vault=full, resolver=PUBLIC).health_check()["status"] == "ok"
    empty = JiraConnector({}, vault=Vault({}), resolver=PUBLIC)
    assert empty.health_check()["status"] == "unconfigured"
    with pytest.raises(AtlassianError) as e:
        empty.client.request("GET", "/rest/api/3/myself")
    assert e.value.reason == "not_configured"


# ── Jira reads ────────────────────────────────────────────────────────────
def test_fetched_issue_text_is_screened_by_the_guard():
    c, _ = jira(lambda r: httpx.Response(200, json=issue(7, "Ordinary title", INJECTION)))
    got = c.get_issue("ABC-7")["issue"]
    assert got["guard"] == "block" and "Ignore" not in got["description"] and got["summary"] == "Ordinary title"
    c2, _ = jira(lambda r: httpx.Response(200, json=issue(8, "Fix login", "Users cannot sign in on Safari.")))
    clean = c2.get_issue("ABC-8")["issue"]
    assert clean["guard"] == "none" and clean["description"] == "Users cannot sign in on Safari."


def test_issue_key_and_arguments_are_validated():
    c, site = jira(lambda r: httpx.Response(200, json={}))
    for bad in ("abc-1", "ABC-0", "ABC-1/../x", "ABC", ""):
        with pytest.raises(ValueError):
            c.get_issue(bad)
    with pytest.raises(ValueError):
        c.search_issues("   ")
    assert site.requests == []


def test_method_classification_is_declared():
    assert set(READ_ONLY_METHODS) == {"search_issues", "get_issue", "get_transitions", "list_projects"}
    assert CONSEQUENTIAL_METHODS == ("create_issue", "transition_issue")


# ── approval path ─────────────────────────────────────────────────────────
@pytest.mark.parametrize("call", [
    lambda c: c.create_issue("ABC", "Title"),
    lambda c: c.transition_issue("ABC-1", "31"),
])
def test_direct_calls_to_consequential_methods_are_refused(call):
    c, site = jira(lambda r: httpx.Response(201, json={"id": "1", "key": "ABC-1"}))
    out = call(c)
    assert out["status"] == "approval_required" and site.requests == []
    with pytest.raises(TypeError):          # there is no approval parameter to forge
        c.create_issue("ABC", "Title", approval_id="anything")
    with pytest.raises(TypeError):
        c.transition_issue("ABC-1", "31", approval_id="anything")
    assert site.requests == []


def test_in_an_approved_step_without_a_caller_is_still_refused():
    c, site = jira(lambda r: httpx.Response(201, json={"id": "1", "key": "ABC-1"}))
    out = _run_in_execute(lambda: c.create_issue("ABC", "Title"), (), {})
    assert out["status"] == "unauthenticated" and site.requests == []


def test_approved_step_with_a_caller_runs_the_write():
    from velaris.core.access import Caller, acting_as

    def route(req):
        if req.method == "GET" and req.url.path == "/rest/api/3/issue/ABC-10":        # live project check
            return httpx.Response(200, json={"fields": {"project": {"key": "ABC"}}})
        if req.url.path == "/rest/api/3/issue":
            body = json.loads(req.content)
            assert body["fields"]["project"] == {"key": "ABC"} and body["fields"]["summary"] == "Title"
            assert body["fields"]["description"]["content"][0]["content"][0]["text"] == "Line one"
            return httpx.Response(201, json={"id": "10", "key": "ABC-10"})
        assert req.url.path == "/rest/api/3/issue/ABC-10/transitions" and json.loads(req.content) == {"transition": {"id": "31"}}
        return httpx.Response(204)

    c, _ = jira(route)
    with acting_as(Caller("u1", "acme")):
        made = _run_in_execute(lambda: c.create_issue("ABC", "Title", "Task", "Line one"), (), {})
        moved = _run_in_execute(lambda: c.transition_issue("ABC-10", "31"), (), {})
    assert made == {"status": "created", "key": "ABC-10", "id": "10"} and moved["status"] == "transitioned"


def test_allowlist_declares_reads_and_acts():
    for m in READ_ONLY_METHODS:
        assert rule_for("JIRA", m).kind == READ
    for m in CONSEQUENTIAL_METHODS:
        assert rule_for("JIRA", m).kind == ACT
    assert [rule_for("CONFLUENCE", m).kind for m in ("search", "get_page_markdown", "list_spaces", "ingest_space")] == \
        [READ, READ, READ, ACT]
    assert rule_for("CONFLUENCE", "ingest_space").scope == "scope"


# ── through the real API: 202, then executes only after approval ──────────
SECRET, KEY = b"s" * 32, Ed25519PrivateKey.generate()
CREATED = []


class FakeJiraConnector(JiraConnector):
    def __init__(self, config=None):
        def route(req):
            CREATED.append((req.method, req.url.path))
            return httpx.Response(201, json={"id": "10", "key": "ABC-10"})
        site = Site(route)
        super().__init__(dict(CREDS), **site.client_args())


class _Router:
    departments, failed = {"JIRA": "connectors"}, {}

    def __init__(self):
        self.module = types.ModuleType("velaris_api_test_jira")
        FakeJiraConnector.__module__ = self.module.__name__
        self.module.JiraConnector = FakeJiraConnector

    def list_agents(self):
        return ["JIRA"]

    def get_agent(self, name):
        return self.module if name == "JIRA" else None


def _api(tmp_path):
    e = BackendEngine.__new__(BackendEngine)
    e.router = _Router()
    settings = Settings(secret=SECRET, identity_key=KEY.public_key(), gate=None, flow_db=str(tmp_path / "flow.db"), org="acme",
                        llm=FakeLLM(lambda p, m: pytest.fail("no model expected")))
    return TestClient(create_app(settings, engine=e))


def _send(client, path, body, *, sub="u1", roles=()):
    content = json.dumps(body).encode()
    nonce = secrets.token_urlsafe(16)
    ident = make_assertion(KEY, sub=sub, org="acme", roles=roles, employee_id=None, nonce=nonce)
    return client.request("POST", path, content=content, headers=sign(SECRET, "POST", path, content, ident, nonce=nonce))


def test_api_act_path_returns_202_and_executes_only_after_approval(tmp_path):
    c = _api(tmp_path)
    forged = _send(c, "/agents/JIRA/create_issue", {"project_key": "ABC", "summary": "T", "approval_id": "x"})
    assert forged.status_code == 400 and CREATED == []                      # no such parameter over HTTP
    r = _send(c, "/agents/JIRA/create_issue", {"project_key": "ABC", "summary": "Title"})
    assert r.status_code == 202 and r.json()["kind"] == ACT and CREATED == []
    run = r.json()["run"]
    assert run["status"] == "waiting_approval"
    own = _send(c, f"/flows/{run['run_id']}/decide", {"call_hash": run["pending"]["call_hash"], "approve": True})
    assert own.json()["error"]["code"] == "four_eyes" and CREATED == []
    done = _send(c, f"/flows/{run['run_id']}/decide", {"call_hash": run["pending"]["call_hash"], "approve": True},
                 sub="u2", roles=["flow_approver"])
    assert done.json()["status"] == "done" and CREATED == [("POST", "/rest/api/3/issue")]
    read = _send(c, "/agents/JIRA/get_issue", {"key": "ABC-1"}, roles=["atlassian_reader"])   # a read answers at once, not 202
    assert read.status_code != 202



def test_storage_format_becomes_markdown():
    md = storage_to_markdown('<h1>Onboarding</h1><p>Read the <strong>handbook</strong> first, then ask your buddy about '
                             'laptops and access.</p><ul><li>VPN</li><li>Email</li></ul>'
                             '<ac:structured-macro ac:name="info"><ac:rich-text-body><p>Badge on day one.</p></ac:rich-text-body>'
                             '</ac:structured-macro>', "Onboarding")
    assert "**handbook**" in md and "- VPN" in md and "Badge on day one." in md


def test_get_page_markdown_search_and_spaces():
    def route(req):
        if req.url.path.endswith("/restriction/byOperation/read"):
            return httpx.Response(200, json={"restrictions": {"user": {"results": []}, "group": {"results": []}}})
        if req.url.path in ("/wiki/api/v2/pages/1", "/wiki/api/v2/pages/2"):      # ancestor lookup for search hits
            return httpx.Response(200, json={"id": req.url.path.rsplit("/", 1)[1], "parentId": None})
        if req.url.path == "/wiki/api/v2/pages/123":
            assert req.url.params["body-format"] == "storage"
            return httpx.Response(200, json=page("123", "Runbook", "<p>Restart the worker, then check the queue length twice.</p>"))
        if req.url.path == "/wiki/rest/api/search":
            if req.url.params.get("start") == "1":
                return httpx.Response(200, json={"results": [{"title": "B", "content": {"id": "2", "type": "page"}, "excerpt": "b"}]})
            return httpx.Response(200, json={"results": [{"title": "A", "content": {"id": "1", "type": "page"},
                                                          "excerpt": "<b>hit</b> text", "url": "/spaces/ENG/pages/1"}],
                                             "_links": {"next": "/wiki/rest/api/search?cql=type%3Dpage&limit=25&start=1"}})
        assert req.url.path == "/wiki/api/v2/spaces"
        return httpx.Response(200, json={"results": [{"id": "10", "key": "ENG", "name": "Engineering", "type": "global"}]})

    c, site = confluence(route)
    got = c.get_page_markdown("123")
    assert got["title"] == "Runbook" and "Restart the worker" in got["markdown"] and got["version"] == 3
    found = c.search("type=page")
    assert [r["id"] for r in found["results"]] == ["1", "2"] and found["results"][0]["excerpt"] == "hit text"
    assert [r.url.params["cql"] for r in site.requests if r.url.path == "/wiki/rest/api/search"][0] == \
        'space in ("ENG") AND (type=page)'
    assert c.list_spaces()["spaces"][0]["key"] == "ENG"
    with pytest.raises(ValueError):
        c.get_page_markdown("12/../3")


def test_pagination_link_may_not_leave_the_site():
    c, _ = confluence(lambda r: httpx.Response(200, json={"results": [], "_links": {"next": "https://evil.test/wiki/x"}}))
    with pytest.raises(AtlassianError) as e:
        c.list_spaces()
    assert e.value.reason == "bad_next_link"



def test_ingest_space_is_refused_outside_an_approved_step():
    lib = RecordingLibrary()
    c, site = confluence(space_route, lib)
    assert c.ingest_space("ENG", scope="acme")["status"] == "approval_required"
    assert lib.calls == [] and site.requests == []


def test_ingest_space_feeds_the_library_and_withholds_injected_pages():
    from velaris.core.access import Caller, acting_as
    lib = RecordingLibrary()
    c, _ = confluence(space_route, lib)
    with acting_as(Caller("u1", "acme")):
        out = _run_in_execute(lambda: c.ingest_space("ENG", scope="acme:docs"), (), {})
    assert out["status"] == "ok" and out["pages_seen"] == 3 and out["ADDED"] == 2
    assert [w["id"] for w in out["withheld"]] == ["3"]
    assert [call[0] for call in lib.calls] == ["confluence ENG - Onboarding (1).md", "confluence ENG - Leave-Policy (2).md"]
    assert all(call[2] == "acme:docs" for call in lib.calls) and "laptop on day one" in lib.calls[0][1]


def test_ingested_pages_become_searchable_with_the_page_in_the_citation(tmp_path):
    from velaris.core.access import Caller, acting_as
    store = DocStore(FakeLLM({}), path=str(tmp_path / "docs.db"))

    class Library:
        def ingest(self, name, data, scope):
            return store.ingest(name, data, scope=scope)

    c, _ = confluence(space_route, Library())
    with acting_as(Caller("u1", "acme")):
        out = _run_in_execute(lambda: c.ingest_space("ENG", scope="acme"), (), {})
        again = _run_in_execute(lambda: c.ingest_space("ENG", scope="acme"), (), {})
    assert out["ADDED"] == 2 and again["UNCHANGED"] == 2 and again["ADDED"] == 0      # re-run is a no-op
    hit = store.search("how many days of paid leave", scope="acme", k=1)[0]
    assert hit.document == "confluence ENG - Leave-Policy (2).md" and "eighteen days" in hit.text
    assert store.search("laptop buddy", scope="other-company") == []


def test_ingest_space_arguments():
    from velaris.core.access import Caller, acting_as
    c, site = confluence(space_route, RecordingLibrary())
    with acting_as(Caller("u1", "acme")):
        for kw in ({"space_key": "E/NG", "scope": "a"}, {"space_key": "ENG", "scope": ""},
                   {"space_key": "ENG", "scope": "a", "max_pages": 0}):
            with pytest.raises(ValueError):
                _run_in_execute(lambda kw=kw: c.ingest_space(**kw), (), {})
    assert site.requests == []


def test_confluence_allowlist_scope_rule():
    assert allowlist.rule_for("CONFLUENCE", "search").kind == READ
    assert atlassian.in_approved_step() is False


# ── scope: the service account reaches more than the caller may ───────────
