"""JIRA and CONFLUENCE connector scope rules: the service account reaches more than the caller may, so every read and write is judged against the configured projects and spaces, restricted pages and the caller role. Fake site from atlassian_kit; no real Atlassian call."""
import httpx
import pytest
from velaris.agents.CONFLUENCE.main import ConfluenceConnector
from velaris.agents.JIRA.atlassian import AtlassianError
from velaris.agents.JIRA.main import JiraConnector
from velaris.api import allowlist
from velaris.tests.atlassian_kit import CREDS, Site, jira, confluence, issue, page, RecordingLibrary, RESTRICTED, space_route, _run_in_execute


@pytest.fixture(autouse=True)
def _data(tmp_path, monkeypatch):
    monkeypatch.setenv("VELARIS_DATA", str(tmp_path))

def _no_call(req):
    pytest.fail("no request expected")


EVIL = ['x = 1) OR project = SECRET', '(x = 1', 'x = "a) OR project = SECRET', "x = 'a", 'x = 1)) OR (project = SECRET',
        'x = 1 ORDER BY created) OR (project = SECRET', 'x = 1 ORDER BY a = 1 OR project = SECRET']


@pytest.mark.parametrize("q", EVIL)
def test_query_wrapper_cannot_be_escaped(q):
    c, site = jira(_no_call)
    with pytest.raises(ValueError):
        c.search_issues(q)
    k, site2 = confluence(_no_call)
    with pytest.raises(ValueError):
        k.search(q)
    assert site.requests == [] and site2.requests == []


def test_wrapper_keeps_quoted_parens_and_appends_order_by():
    seen = []

    def route(req):
        seen.append(req.url.params["jql"])
        return httpx.Response(200, json={"issues": [issue(1)], "isLast": True})

    c, _ = jira(route)
    c.search_issues('summary ~ "a) OR b" AND (status = Done) order by created desc, key')
    c.search_issues("ORDER BY created")
    assert seen == ['project in ("ABC") AND (summary ~ "a) OR b" AND (status = Done)) order by created desc, key',
                    'project in ("ABC") ORDER BY created']


def test_jira_results_from_other_projects_are_dropped():
    other = issue(1)
    other["fields"]["project"] = {"key": "SECRET"}
    c, _ = jira(lambda r: httpx.Response(200, json={"issues": [other, issue(2)], "isLast": True}))
    assert [i["key"] for i in c.search_issues("x = 1")["issues"]] == ["ABC-2"]


def test_jira_out_of_scope_refused_for_every_method():
    c, site = jira(_no_call)
    for call in (lambda: c.get_issue("SEC-1"), lambda: c.get_transitions("SEC-1")):
        with pytest.raises(AtlassianError) as e:
            call()
        assert e.value.reason == "out_of_scope"
    with pytest.raises(AtlassianError):
        _run_in_execute_as(lambda: c.create_issue("SEC", "T"))
    with pytest.raises(AtlassianError):
        _run_in_execute_as(lambda: c.transition_issue("SEC-1", "31"))
    assert site.requests == []


def _run_in_execute_as(fn):
    from velaris.core.access import Caller, acting_as
    with acting_as(Caller("u1", "acme")):
        return _run_in_execute(fn, (), {})


def test_moved_issue_is_judged_by_its_current_project():
    moved = issue(1)
    moved["fields"]["project"] = {"key": "SECRET"}          # ABC-1 was moved to SECRET; the old key still resolves
    c, _ = jira(lambda r: httpx.Response(200, json=moved))
    with pytest.raises(AtlassianError) as e:
        c.get_issue("ABC-1")
    assert e.value.reason == "out_of_scope"


def test_list_projects_returns_only_configured_ones():
    c, _ = jira(lambda r: httpx.Response(200, json={"values": [{"key": "ABC"}, {"key": "SECRET"}], "isLast": True}))
    assert [p["key"] for p in c.list_projects()["projects"]] == ["ABC"]


def test_empty_or_unset_config_reads_nothing():
    class Vault:
        def get_secret(self, name):
            return None

    for cfg in ({**CREDS, "jira_projects": [], "confluence_spaces": ""}, {k: v for k, v in CREDS.items() if "_" not in k or k == "api_token"}):
        site = Site(_no_call)
        j = JiraConnector(dict(cfg), vault=Vault(), **site.client_args())
        k = ConfluenceConnector(dict(cfg), vault=Vault(), library=RecordingLibrary(), **site.client_args())
        with pytest.raises(AtlassianError):
            j.search_issues("x = 1")
        with pytest.raises(AtlassianError):
            j.get_issue("ABC-1")
        with pytest.raises(AtlassianError):
            k.search("type=page")
        with pytest.raises(AtlassianError):
            k.get_page_markdown("123")
        assert j.list_projects()["projects"] == [] and k.list_spaces()["spaces"] == []
        with pytest.raises(AtlassianError):
            _run_in_execute_as(lambda: k.ingest_space("ENG", scope="acme"))
        assert site.requests == []


def test_confluence_out_of_scope_space_refused():
    def route(req):
        if req.url.path == "/wiki/api/v2/pages/9":
            return httpx.Response(200, json=page("9", "Salaries", "<p>secret</p>", space="99"))
        assert req.url.path == "/wiki/api/v2/spaces"
        return httpx.Response(200, json={"results": [{"id": "10", "key": "ENG"}, {"id": "99", "key": "HR"}]})

    c, _ = confluence(route)
    with pytest.raises(AtlassianError) as e:
        c.get_page_markdown("9")
    assert e.value.reason == "out_of_scope"
    assert [s["key"] for s in c.list_spaces()["spaces"]] == ["ENG"]
    lib = RecordingLibrary()
    c2, site = confluence(_no_call, lib)
    with pytest.raises(AtlassianError):
        _run_in_execute_as(lambda: c2.ingest_space("HR", scope="acme"))
    assert lib.calls == [] and site.requests == []


def test_ingest_skips_restricted_pages_and_pages_under_restricted_parents():
    def route(req):
        if req.url.path == "/wiki/api/v2/spaces/10/pages":
            kid = page("2", "Child", "<p>Child of a restricted page with enough words to keep.</p>")
            kid["parentId"] = "1"
            return httpx.Response(200, json={"results": [
                page("1", "Board", "<p>Board minutes, restricted to a few people only.</p>"), kid,
                page("3", "Open", "<p>Public handbook text that everybody may read.</p>")]})
        return space_route(req)

    RESTRICTED.add("1")
    try:
        lib = RecordingLibrary()
        c, _ = confluence(route, lib)
        out = _run_in_execute_as(lambda: c.ingest_space("ENG", scope="acme"))
    finally:
        RESTRICTED.clear()
    assert [r["id"] for r in out["restricted"]] == ["1", "2"] and out["ADDED"] == 1
    assert [call[0] for call in lib.calls] == ["confluence ENG - Open (3).md"]
    assert lib.calls[0][1].startswith("Source: Confluence space ENG, page 3")


def test_an_ancestor_outside_the_listing_is_walked_and_a_failed_lookup_is_restricted():
    """Page 2's parent 50 is not in the space listing; 50 is itself restricted-through its parent 60."""
    def route(req):
        if req.url.path == "/wiki/api/v2/spaces/10/pages":
            kid = page("2", "Child", "<p>Child of an outside parent with enough words to keep.</p>")
            kid["parentId"] = "50"
            return httpx.Response(200, json={"results": [kid]})
        if req.url.path == "/wiki/api/v2/pages/50":
            return httpx.Response(200, json={"id": "50", "parentId": "60"})
        if req.url.path == "/wiki/api/v2/pages/60":
            return httpx.Response(200, json={"id": "60", "parentId": None})
        return space_route(req)

    RESTRICTED.add("60")
    try:
        lib = RecordingLibrary()
        c, _ = confluence(route, lib)
        out = _run_in_execute_as(lambda: c.ingest_space("ENG", scope="acme"))
    finally:
        RESTRICTED.clear()
    assert lib.calls == [] and [r["id"] for r in out["restricted"]] == ["2"]

    def broken(req):                                    # the ancestor lookup itself fails
        if req.url.path == "/wiki/api/v2/spaces/10/pages":
            kid = page("2", "Child", "<p>Child of an outside parent with enough words to keep.</p>")
            kid["parentId"] = "50"
            return httpx.Response(200, json={"results": [kid]})
        if req.url.path == "/wiki/api/v2/pages/50":
            return httpx.Response(500)
        return space_route(req)

    lib2 = RecordingLibrary()
    c2, _ = confluence(broken, lib2)
    out2 = _run_in_execute_as(lambda: c2.ingest_space("ENG", scope="acme"))
    assert lib2.calls == [] and [r["id"] for r in out2["restricted"]] == ["2"]


def test_ingest_fails_closed_when_the_restriction_check_fails():
    def route(req):
        if "/restriction/" in req.url.path:
            return httpx.Response(500)
        return space_route(req)

    lib = RecordingLibrary()
    c, _ = confluence(route, lib)
    out = _run_in_execute_as(lambda: c.ingest_space("ENG", scope="acme"))
    assert lib.calls == [] and len(out["restricted"]) == 3


@pytest.mark.parametrize("agent,cls,method,params", [
    ("JIRA", JiraConnector, "search_issues", {"jql": "x = 1"}), ("JIRA", JiraConnector, "get_issue", {"key": "ABC-1"}),
    ("JIRA", JiraConnector, "get_transitions", {"key": "ABC-1"}), ("JIRA", JiraConnector, "list_projects", {}),
    ("CONFLUENCE", ConfluenceConnector, "search", {"cql": "type=page"}),
    ("CONFLUENCE", ConfluenceConnector, "get_page_markdown", {"page_id": "1"}),
    ("CONFLUENCE", ConfluenceConnector, "list_spaces", {})])
def test_api_reads_need_the_atlassian_reader_role(agent, cls, method, params):
    from velaris.core.access import ATLASSIAN_READERS, AccessDenied, Caller
    fn = getattr(cls, method)
    for roles in ((), ("hr_admin",), ("payroll_admin",)):
        with pytest.raises(AccessDenied):
            allowlist.prepare(agent, method, fn, params, Caller("u1", "acme", frozenset(roles)))
    for role in ATLASSIAN_READERS:
        assert allowlist.prepare(agent, method, fn, params, Caller("u1", "acme", frozenset({role}))) == params
    assert "governance_admin" in ATLASSIAN_READERS and "atlassian_reader" in ATLASSIAN_READERS


def test_transitions_judge_the_project_the_issue_is_in_now():
    """A moved issue answers to its old key: get_transitions and transition_issue must not use the key prefix."""
    moved = {"ABC-7": "SECRET", "ABC-8": "ABC"}

    def route(req):
        key = req.url.path.split("/")[5]
        if req.method == "GET" and req.url.path == f"/rest/api/3/issue/{key}":
            return httpx.Response(200, json={"fields": {"project": {"key": moved[key]}}})
        return httpx.Response(200, json={"transitions": [{"id": "31", "name": "Done", "to": {"name": "Done"}}]})

    c, site = jira(route)
    with pytest.raises(AtlassianError) as e:
        c.get_transitions("ABC-7")
    assert e.value.reason == "out_of_scope"
    assert c.get_transitions("ABC-8")["transitions"][0]["id"] == "31"
    assert not any(r.url.path.endswith("/transitions") and "ABC-7" in r.url.path for r in site.requests)


def test_get_page_markdown_and_search_leave_out_restricted_content():
    def route(req):
        if req.url.path == "/wiki/api/v2/pages/124":
            return httpx.Response(200, json={"id": "124", "parentId": None})
        if req.url.path == "/wiki/api/v2/pages/123":
            p = page("123", "Board", "<p>Board minutes restricted to a few people only please.</p>")
            return httpx.Response(200, json=p)
        if req.url.path == "/wiki/rest/api/search":
            return httpx.Response(200, json={"results": [
                {"title": "Board", "content": {"id": "123", "type": "page"}, "excerpt": "x"},
                {"title": "Open", "content": {"id": "124", "type": "page"}, "excerpt": "y"}]})
        return space_route(req)

    RESTRICTED.add("123")
    try:
        c, _ = confluence(route)
        with pytest.raises(AtlassianError) as e:
            c.get_page_markdown("123")
        found = c.search("type=page")
    finally:
        RESTRICTED.clear()
    assert e.value.reason == "restricted"
    assert [r["id"] for r in found["results"]] == ["124"] and found["restricted_omitted"] == 1
