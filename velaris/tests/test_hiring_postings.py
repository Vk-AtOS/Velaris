"""JOB_POSTINGS: JobPosting JSON-LD, careers fragment, Google Indexing payload and sender, posting packs, approvals, tracked links."""
import json

import httpx
import pytest
from velaris.agentkit.hiring_testkit import ORG, advance, as_, bootstrap, clean_keys, trace_text, who

from velaris.agentkit import hiring_common as hc
from velaris.agentkit import hiring_posting as hp
from velaris.agentkit import hiring_skills as sk
from velaris.agents.ATS_CORE.main import AtsCore
from velaris.agents.JOB_POSTINGS import main as jp
from velaris.agents.JOB_POSTINGS.main import JobPostings


class Vault:
    def __init__(self, token=None):
        self.token = token

    def get_secret(self, name):
        assert name == "GOOGLE_INDEXING_ACCESS_TOKEN"
        return self.token


def valid_through(days=60):
    return hc.iso(hc.now() + days * hc.DAY)[:10]


@pytest.fixture()
def env():
    ats = AtsCore()
    rid, c = bootstrap(ats)
    seen = []

    def handler(request: httpx.Request):
        seen.append(request)
        return httpx.Response(200, json={"urlNotificationMetadata": {}})
    cfg = {"transport": httpx.MockTransport(handler), "resolver": lambda host: ["142.250.80.10"], "vault": Vault("tok-secret-123")}
    return JobPostings(cfg), rid, c, seen


def profile(post, c):
    with as_(c["rec"]):
        return post.set_company_profile(name="Chennai Tech Services", website="https://ctspl.example", careers_base_url="https://ctspl.example/careers",
                                       contact_email="hr@ctspl.example")


def prepared(post, rid, c, **kw):
    profile(post, c)
    with as_(c["rec"]):
        return post.prepare_careers_posting(requisition_id=rid, valid_through=kw.pop("vt", valid_through()), **kw)


def test_jsonld_has_every_required_field_and_validates(env):
    post, rid, c, _ = env
    r = prepared(post, rid, c, salary={"min": "40000", "max": "60000.50", "unit": "MONTH"})
    assert r["status"] == "ok"
    ld = r["posting"]["jsonld"]
    assert ld["@type"] == "JobPosting" and ld["hiringOrganization"]["name"] == "Chennai Tech Services"
    assert ld["jobLocation"]["address"] == {"@type": "PostalAddress", "addressLocality": "Chennai", "addressRegion": "Tamil Nadu", "addressCountry": "IN"}
    assert ld["baseSalary"]["value"] == {"@type": "QuantitativeValue", "minValue": 40000, "maxValue": 60000.5, "unitText": "MONTH"} and ld["baseSalary"]["currency"] == "INR"
    assert hp.validate_jsonld(ld) == [] and "Python" in ld["description"] and "(2+ years)" in ld["description"] and "never ask applicants for any fee" in ld["description"]
    frag = r["posting"]["fragment_html"]
    assert frag.count('<script type="application/ld+json">') == 1 and "</script>" in frag and "src=careers_page" in frag
    inner = frag.split('<script type="application/ld+json">')[1].split("</script>")[0]
    assert json.loads(inner)["title"] == "Backend Engineer"                                  # the embedded markup parses
    assert r["posting"]["org"] == ORG and r["indexing_payload"]["sent"] is False and r["indexing_payload"]["body"]["type"] == "URL_UPDATED"


def test_validation_catches_bad_markup(env):
    post, rid, c, _ = env
    good = prepared(post, rid, c)["posting"]["jsonld"]
    for mutate, expect in ((lambda d: d.pop("title"), "title"), (lambda d: d.__setitem__("description", "short"), "description"),
                           (lambda d: d.__setitem__("datePosted", "yesterday"), "datePosted"),
                           (lambda d: d.__setitem__("validThrough", "2000-01-01"), "validThrough"),
                           (lambda d: d.__setitem__("employmentType", "SOMETIMES"), "employmentType"),
                           (lambda d: d.pop("hiringOrganization"), "hiringOrganization"),
                           (lambda d: d["jobLocation"]["address"].pop("addressCountry"), "addressCountry"),
                           (lambda d: d.__setitem__("baseSalary", {"currency": "USD", "value": {}}), "baseSalary")):
        ld = json.loads(json.dumps(good))
        mutate(ld)
        assert any(expect in p for p in hp.validate_jsonld(ld)), expect
    with as_(c["rec"]):
        assert post.take_down_posting(posting_id="post-nope")["status"] == "not_found"


def test_preconditions_company_profile_requisition_state_and_dates(env):
    post, rid, c, _ = env
    with as_(c["rec"]):
        assert post.prepare_careers_posting(requisition_id=rid, valid_through=valid_through())["status"] == "not_configured"
    profile(post, c)
    with as_(c["rec"]):
        for vt in ("2001-01-01", valid_through(400), "soon"):
            assert post.prepare_careers_posting(requisition_id=rid, valid_through=vt)["status"] == "invalid_input"
        assert post.prepare_careers_posting(requisition_id="req-nope", valid_through=valid_through())["status"] == "conflict"
        assert post.prepare_careers_posting(requisition_id=rid, valid_through=valid_through(), salary={"min": "50000", "max": "40000"})["status"] == "invalid_input"
        assert post.prepare_careers_posting(requisition_id=rid, valid_through=valid_through(), salary={"min": 50000.5, "max": 60000})["status"] == "invalid_input"
        assert post.set_company_profile(name="X", website="http://insecure.example", careers_base_url="https://x.example")["status"] == "invalid_input"
        assert post.prepare_careers_posting(requisition_id=rid, valid_through=valid_through())["status"] == "ok"
        assert post.prepare_careers_posting(requisition_id=rid, valid_through=valid_through())["status"] == "conflict"      # one active posting


def test_approval_gate_before_anything_is_live_or_posted(env):
    post, rid, c, _ = env
    pid = prepared(post, rid, c)["posting"]["id"]
    with as_(c["rec"]):
        assert post.mark_posting_live(posting_id=pid)["status"] == "conflict"             # not approved
        assert post.approve_posting(posting_id=pid)["status"] == "denied"                  # recruiter cannot approve
    with as_(who("hr_admin", id="adm")):
        assert post.prepare_careers_posting(requisition_id=rid, valid_through=valid_through())["status"] == "conflict"
    with as_(c["mgr"]):
        assert post.approve_posting(posting_id=pid)["posting"]["approved_by"] == "hiring_manager-1"
    with as_(c["rec"]):
        assert post.mark_posting_live(posting_id=pid)["posting"]["status"] == "live"
    # packs: prepared -> approved (someone else) -> posted
    with as_(c["rec"]):
        pack = post.prepare_pack(posting_id=pid, board="linkedin")["pack"]
        assert post.mark_pack_posted(pack_id=pack["id"], live_url="https://www.linkedin.com/jobs/view/1")["status"] == "conflict"   # nobody approved it
        assert post.approve_pack(pack_id=pack["id"])["status"] == "denied"
    with as_(who("hr_admin", id="prep")):
        mine = post.prepare_pack(posting_id=pid, board="indeed")["pack"]
        assert post.approve_pack(pack_id=mine["id"])["status"] == "denied"                 # not by whoever prepared it
    with as_(c["mgr"]):
        assert post.approve_pack(pack_id=pack["id"])["pack"]["status"] == "approved"
    with as_(c["rec"]):
        out = post.mark_pack_posted(pack_id=pack["id"], live_url="https://www.linkedin.com/jobs/view/1")["pack"]
        assert out["status"] == "posted" and out["posted_by"] == "recruiter-1" and out["posted_at"]
        assert post.mark_pack_posted(pack_id=pack["id"])["status"] == "conflict"


def test_posting_pack_content_tracking_and_takedown(env, monkeypatch):
    post, rid, c, _ = env
    pid = prepared(post, rid, c)["posting"]["id"]
    with as_(c["rec"]):
        assert post.prepare_pack(posting_id=pid, board="myspace")["status"] == "invalid_input"
        pk = post.prepare_pack(posting_id=pid, board="naukri")["pack"]
        assert post.prepare_pack(posting_id=pid, board="naukri")["status"] == "conflict"
        li = post.prepare_pack(posting_id=pid, board="linkedin")["pack"]
    assert {"text", "fields", "manual_steps", "tracking_url", "tracking_code", "takedown_date", "takedown_task"} <= set(pk)
    assert pk["tracking_url"].endswith(f"?src=naukri&t={pk['tracking_code']}") and pk["tracking_url"] in pk["text"]
    assert pk["fields"]["must_have_skills"] == ["Python (2+ yrs)", "SQL"] and pk["board_facts_verified"] is False and "Unverified" in pk["board_note"]
    assert li["board_facts_verified"] is True and pk["takedown_date"] == hc.iso(hc.now() + 7 * hc.DAY)[:10] and li["takedown_date"] == hc.iso(hc.now() + 14 * hc.DAY)[:10]
    assert "Take down" in pk["takedown_task"] and pk["org"] == ORG
    with as_(c["rec"]):
        assert post.resolve_tracking(code=pk["tracking_code"])["source"] == "naukri"                     # feeds the ATS source
        assert post.resolve_tracking(code="tdeadbeef")["source"] == "careers_page"
    for who_, pack in ((c["mgr"], pk), (c["mgr"], li)):
        with as_(who_):
            post.approve_pack(pack_id=pack["id"])
        with as_(c["rec"]):
            post.mark_pack_posted(pack_id=pack["id"], live_url="https://example.com/job")
    with as_(c["rec"]):
        assert post.takedown_due(within_days=0)["tasks"] == []
    advance(monkeypatch, 8 * hc.DAY)
    with as_(c["rec"]):
        t = post.takedown_due(within_days=0)["tasks"]
        assert [x["board"] for x in t] == ["Naukri"] and t[0]["overdue"] is True
        assert post.mark_pack_taken_down(pack_id=pk["id"])["pack"]["status"] == "taken_down"
        assert post.takedown_due(within_days=0)["tasks"] == []
    # the tracked source reaches the ATS: an application recorded with the resolved source
    ats = AtsCore()
    with as_(c["rec"]):
        src = post.resolve_tracking(code=li["tracking_code"])["source"]
        out = ats.add_candidate(name="Tracked Person", email="t@example.com", source=src, requisition_id=rid, tracking_code=li["tracking_code"],
                                consent={"purpose": "recruitment", "notice_version": "v1", "retention_until": hc.iso(hc.now() + 30 * hc.DAY)[:10]})
        assert out["status"] == "ok" and ats.aggregate_counts()["by_source"] == {"linkedin": 1}


def test_discriminatory_wording_is_flagged_for_the_approver(env):
    assert hp.wording_flags("Male only, age below 30, young and energetic") == ["age below", "male only", "young and energetic"]
    assert hp.wording_flags("Experience with Python") == []


def test_indexing_notification_runs_only_as_an_approved_step_with_a_vault_token(env, monkeypatch):
    post, rid, c, seen = env
    pid = prepared(post, rid, c)["posting"]["id"]
    with as_(c["mgr"]):
        post.approve_posting(posting_id=pid)
    with as_(c["rec"]):
        post.mark_posting_live(posting_id=pid)
        assert post.send_indexing_notification(posting_id=pid)["status"] == "approval_required" and seen == []   # direct calls are refused
    monkeypatch.setattr(jp, "refuse_unless_approved", lambda *a, **k: None)
    with as_(c["rec"]):
        r = post.send_indexing_notification(posting_id=pid)
        assert r["status"] == "ok" and r["accepted"] is True and r["sent"] == "URL_UPDATED"
        assert post.send_indexing_notification(posting_id=pid, kind="URL_DELETED")["status"] == "conflict"       # not taken down
        assert post.send_indexing_notification(posting_id=pid, kind="URL_REMOVED")["status"] == "conflict"
    req = seen[0]
    assert req.method == "POST" and req.url.host == "142.250.80.10" and req.headers["Host"] == "indexing.googleapis.com"
    assert req.headers["Authorization"] == "Bearer tok-secret-123" and json.loads(req.content)["type"] == "URL_UPDATED"
    assert json.loads(req.content)["url"].startswith("https://ctspl.example/careers/jobs/")
    assert "tok-secret-123" not in trace_text() and "tok-secret-123" not in json.dumps(r)
    with as_(c["rec"]):
        post.take_down_posting(posting_id=pid)
        assert post.send_indexing_notification(posting_id=pid, kind="URL_DELETED")["sent"] == "URL_DELETED"
    # no token in the vault: refused, nothing sent
    post2 = JobPostings({**post.config, "vault": Vault(None)})
    with as_(c["rec"]):
        pid2 = post2.prepare_careers_posting(requisition_id=rid, valid_through=valid_through())["posting"]["id"]
    with as_(c["mgr"]):
        post2.approve_posting(posting_id=pid2)
    with as_(c["rec"]):
        post2.mark_posting_live(posting_id=pid2)
        n = len(seen)
        assert post2.send_indexing_notification(posting_id=pid2)["status"] == "not_configured" and len(seen) == n
    # a non-public address is refused before any connection
    post3 = JobPostings({**post.config, "resolver": lambda host: ["10.0.0.5"]})
    with as_(c["rec"]):
        assert post3.send_indexing_notification(posting_id=pid2)["status"] == "blocked" and len(seen) == n


def test_denied_cases_and_clean_keys(env):
    post, rid, c, _ = env
    assert post.get_company_profile()["status"] == "unauthenticated"
    with as_(who("interviewer")):
        assert post.get_company_profile()["status"] == "denied"
        assert post.set_company_profile(name="x", website="https://x.example", careers_base_url="https://x.example")["status"] == "denied"
    r = prepared(post, rid, c)
    clean_keys(r)
    with as_(who("recruiter", org="other")):
        assert post.get_posting(posting_id=r["posting"]["id"])["status"] == "not_found"
        assert post.list_packs()["packs"] == []
