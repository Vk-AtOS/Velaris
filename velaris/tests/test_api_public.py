"""The public app: only token routes, no identity, strict limits, closed CORS, structured errors, and the signing ceremony end to end."""
import base64
import json

import pytest
from fastapi.testclient import TestClient

from velaris.agentkit import hiring_common as hc
from velaris.agentkit import hiring_forms as hf
from velaris.agentkit import hiring_intake as intake
from velaris.agentkit.hiring_testkit import advance, as_, bootstrap, consent, tiny_pdf
from velaris.agentkit.onboarding_pdf import build_pdf
from velaris.agents.ATS_CORE.main import AtsCore
from velaris.agents.ESIGN.main import Esign
from velaris.agents.INTERVIEW_RECORD.main import InterviewRecord
from velaris.agents.INTERVIEW_SCHEDULER.main import InterviewScheduler
from velaris.agents.JOB_POSTINGS.main import JobPostings
from velaris.agents.SCREENING_FORMS.main import ScreeningForms
from velaris.api import public
from velaris.api.public import PublicSettings, RouteLimit, create_public_app
from velaris.core.access import acting_as
from velaris.tests.onboarding_helpers import HR1, Clock, FakeSender
from velaris.tests.test_hiring_scheduler import WEEKLY
from velaris.tests.test_hiring_forms import ANSWERS, DEFINITION

TOKEN = "t" * 32                      # well-formed, unknown
EXPECTED = {("GET", "/careers/forms/{form_id}"), ("GET", "/careers/challenge/{form_id}"), ("POST", "/careers/apply/{form_id}"),
            ("GET", "/careers/status/{token}"), ("POST", "/careers/withdraw/{token}"),
            ("GET", "/schedule/{token}/slots"), ("POST", "/schedule/{token}/pick"), ("POST", "/schedule/{token}/cancel"),
            ("POST", "/interview/{token}/consent"), ("POST", "/interview/{token}/events"), ("POST", "/interview/{token}/withdraw"),
            ("POST", "/interview/{token}/audio"), ("POST", "/sign/{token}/open"), ("POST", "/sign/{token}/otp/request"), ("POST", "/sign/{token}/otp/verify"),
            ("POST", "/sign/{token}/consent"), ("POST", "/sign/{token}/sign"), ("POST", "/sign/{token}/decline"),
            # the HTML pages (KAN-123..127): shells only, behaviour is in /static/public.js; see test_public_pages.py
            ("GET", "/apply/{form_id}"), ("GET", "/status/{token}"), ("GET", "/withdraw/{token}"), ("GET", "/schedule/{token}"), ("GET", "/sign/{token}"),
            ("GET", "/interview/{token}"), ("GET", "/static/{name}"), ("GET", "/jobs/{slug}"), ("GET", "/jobs/{slug}/apply"),
            ("GET", "/sitemap.xml"), ("GET", "/schedule/{token}/calendar.ics")}
BODIES = {"/schedule/{token}/pick": {"start": 1}, "/interview/{token}/consent": {"scopes": ["events"], "notice_version": "v"},
          "/interview/{token}/events": {"type": "join"}, "/sign/{token}/open": {"email": "a@b.co"}, "/sign/{token}/otp/request": {"email": "a@b.co"},
          "/sign/{token}/otp/verify": {"email": "a@b.co", "code": "1"}, "/sign/{token}/consent": {"email": "a@b.co", "consent_text_version": "v1"},
          "/sign/{token}/sign": {"email": "a@b.co", "typed_name": "x"}, "/sign/{token}/decline": {"email": "a@b.co"}}


class Tick:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


@pytest.fixture(autouse=True)
def fast_pow(monkeypatch):
    monkeypatch.setattr(hf, "POW_BITS", 10)


@pytest.fixture()
def esign_world():
    sender, clock = FakeSender(), Clock()
    return Esign({"sender": sender, "clock": clock}), sender


@pytest.fixture()
def tick():
    return Tick()


@pytest.fixture()
def client(esign_world, tick):
    app = create_public_app(PublicSettings(esign=esign_world[0], clock=tick))
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def world():
    """Requisition with a published form, three candidates, interviewers with hours, an interview session."""
    ats = AtsCore()
    rid, c = bootstrap(ats)
    with as_(c["rec"]):
        JobPostings().set_company_profile(name="Chennai Tech", website="https://cts.example", careers_base_url="https://cts.example/c", contact_email="hr@cts.example")
        fid = ScreeningForms().create_form(requisition_id=rid, definition=DEFINITION)["form"]["id"]
        assert ScreeningForms().publish_form(form_id=fid)["status"] == "ok"
        apps = [ats.add_candidate(name=f"Person Number{i}", email=f"p{i}@example.com", phone=f"+91 9{i}000 1234{i}", source="careers_page",
                                  requisition_id=rid, consent=consent())["application"]["id"] for i in range(2)]
        sch = InterviewScheduler()
        assert sch.set_availability(interviewer_id="iv-a", name="Anita Rao", email="iv-a@cts.example", weekly=WEEKLY)["status"] == "ok"
        sched_tok = sch.issue_schedule_token(application_id=apps[0], interviewer_ids=["iv-a"], duration_min=60, title="Round 1", days=3)["token"]
        rec = InterviewRecord()
        sess = rec.create_session(application_id=apps[1], interviewer_ids=["iv-1"])["session"]["id"]
        itok = rec.issue_participant_token(session_id=sess)["token"]
    return {"ats": ats, "rid": rid, "c": c, "fid": fid, "apps": apps, "sched": sched_tok, "itok": itok}


def routes(client):
    return {(m, r.path) for r in client.app.routes if hasattr(r, "methods") for m in r.methods if m not in ("HEAD", "OPTIONS")}


def err(r, status, code):
    assert r.status_code == status, r.text
    assert r.json()["error"]["code"] == code
    assert set(r.json()) == {"error"}
    return r.json()["error"]


# ---- what is served ---------------------------------------------------------------------------------------------------------
def test_only_the_token_functions_are_served_and_docs_are_off(client):
    assert routes(client) == EXPECTED
    for path in ("/docs", "/openapi.json", "/redoc", "/agents", "/flows", "/health", "/trace/verify", "/chat/rooms", "/mail/mailboxes"):
        assert client.get(path).status_code == 404
    from velaris.api import app as main_app
    assert "velaris.api.public" not in open(main_app.__file__).read() and "create_public_app" not in open(main_app.__file__).read()


def test_no_route_is_reachable_without_a_token_or_proof(client):
    for method, path in sorted(EXPECTED):
        if method == "GET" and not path.startswith(("/careers", "/schedule/{token}/slots")) and path not in ("/careers/status/{token}",):
            continue                      # the HTML shells hold no data; the JSON routes behind them are what this test covers
        if "{token}" in path:
            url = path.replace("{token}", TOKEN)
            for bad in (TOKEN, "short", "x" * 200, "tok en%20" + "y" * 24):                    # unknown, too short, too long, malformed
                r = client.request(method, path.replace("{token}", bad), json={} if method == "POST" else None)
                assert r.status_code in (404, 400, 422, 429), (method, path, r.status_code)
                assert r.status_code != 200
            r = client.request(method, url, json=BODIES.get(path, {}) if method == "POST" else None)
            assert r.status_code == 404 and r.json()["error"]["code"] == "not_found", (method, path)       # a well-formed but unknown token
    r = client.post("/careers/apply/nope", json={"answers": {}, "pow_solution": {}})
    err(r, 404, "not_found")


def test_a_valid_token_of_another_purpose_gets_the_same_answer(client, world):
    sched = world["sched"]                                                     # a real schedule token, offered to routes of other kinds
    err(client.get(f"/careers/status/{sched}"), 404, "not_found")
    err(client.post(f"/careers/withdraw/{sched}"), 404, "not_found")
    err(client.post(f"/interview/{sched}/withdraw"), 404, "not_found")
    err(client.post(f"/sign/{sched}/open", json={"email": "a@b.co"}), 404, "not_found")


# ---- careers ----------------------------------------------------------------------------------------------------------------
def form_version(client, fid):
    return client.get(f"/careers/forms/{fid}").json()["result"]["consent_version"]


def solved(client, fid):
    ch = client.get(f"/careers/challenge/{fid}").json()["result"]["challenge"]
    return {**ch, "n": hf.solve(ch)}


def test_apply_refuses_a_stale_or_missing_consent_version(client, world):
    fid = world["fid"]
    body = {"answers": ANSWERS, "pow_solution": solved(client, fid)}
    err(client.post(f"/careers/apply/{fid}", json={**body, "consent_version": "stale"}), 409, "consent_outdated")
    err(client.post(f"/careers/apply/{fid}", json={**body, "pow_solution": solved(client, fid)}), 409, "consent_outdated")


def test_apply_with_proof_of_work_then_status_and_withdraw_by_token(client, world):
    fid, c = world["fid"], world["c"]
    form = client.get(f"/careers/forms/{fid}")
    assert form.status_code == 200 and form.json()["result"]["consent_version"] and "set-cookie" not in form.headers
    body = {"answers": ANSWERS, "pow_solution": solved(client, fid), "file_name": "cv.pdf", "consent_version": form_version(client, fid),
            "file_base64": base64.b64encode(tiny_pdf("Skills: Python and SQL, 4 years")).decode()}
    err(client.post(f"/careers/apply/{fid}", json={**body, "pow_solution": {"salt": "x"}}), 400, "challenge_failed")
    r = client.post(f"/careers/apply/{fid}", json=body)
    assert r.status_code == 200 and r.json()["result"]["reference"].startswith("sub-")
    assert client.post(f"/careers/apply/{fid}", json=body).status_code == 400            # the same solved challenge cannot be replayed
    err(client.post(f"/careers/apply/{fid}", json={**body, "pow_solution": solved(client, fid), "file_base64": "not base64!!"}), 400, "invalid_input")
    with as_(c["rec"]):
        sub = ScreeningForms().pending_submissions()["submissions"][0]["id"]
        token = ScreeningForms().accept_submission(submission_id=sub)["status_token"]
    s = client.get(f"/careers/status/{token}")
    assert s.status_code == 200 and s.json()["result"]["progress"]
    err(client.post(f"/careers/withdraw/{token}", json={}), 404, "not_found")             # a status token cannot withdraw
    assert client.post(f"/careers/withdraw/{world['sched']}").status_code == 404
    err(client.get(f"/careers/status/{'z' * 40}"), 404, "not_found")


def test_expired_tokens_are_refused_like_unknown_ones(client, world, monkeypatch):
    start = client.get(f"/schedule/{world['sched']}/slots").json()["result"]["starts"][0]
    assert client.post(f"/schedule/{world['sched']}/pick", json={"start": start}).status_code == 200
    advance(monkeypatch, 4 * hc.DAY)
    err(client.get(f"/schedule/{world['sched']}/slots"), 404, "not_found")
    err(client.post(f"/schedule/{world['sched']}/pick", json={"start": start}), 404, "not_found")
    err(client.post(f"/schedule/{world['sched']}/cancel", json={}), 404, "not_found")


# ---- self-schedule and interview events --------------------------------------------------------------------------------------
def test_self_schedule_pick_move_cancel(client, world):
    tok = world["sched"]
    slots = client.get(f"/schedule/{tok}/slots").json()["result"]
    assert slots["slots"] and len(slots["starts"]) == len(slots["slots"])
    err(client.post(f"/schedule/{tok}/pick", json={"start": slots["starts"][0] + 60}), 409, "conflict")        # not an offered time
    err(client.post(f"/schedule/{tok}/pick", json={"start": True}), 400, "invalid_input")
    err(client.post(f"/schedule/{tok}/pick", json={"start": "9"}), 400, "invalid_input")
    ok = client.post(f"/schedule/{tok}/pick", json={"start": slots["starts"][0]})
    assert ok.status_code == 200 and "confirmed_for" in ok.json()["result"]
    assert client.post(f"/schedule/{tok}/pick", json={"start": slots["starts"][2]}).status_code == 200       # moving it
    assert client.post(f"/schedule/{tok}/cancel").status_code == 200
    err(client.post(f"/schedule/{tok}/cancel"), 404, "not_found")


def test_booked_slot_downloads_as_a_calendar_file_without_other_people(client, world):
    """KAN-124: the candidate can add the booked time to a calendar; nothing about the interviewers' addresses is in it."""
    tok = world["sched"]
    assert client.get(f"/schedule/{tok}/calendar.ics").status_code == 404                              # nothing booked yet
    start = client.get(f"/schedule/{tok}/slots").json()["result"]["starts"][0]
    assert client.post(f"/schedule/{tok}/pick", json={"start": start}).status_code == 200
    r = client.get(f"/schedule/{tok}/calendar.ics")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/calendar")
    assert "attachment" in r.headers["content-disposition"] and r.headers["cache-control"] == "no-store"
    assert r.text.startswith("BEGIN:VCALENDAR") and "METHOD:PUBLISH" in r.text and "STATUS:CONFIRMED" in r.text and "ATTENDEE" not in r.text
    assert client.get(f"/schedule/{'z' * 32}/calendar.ics").status_code == 404
    assert client.post(f"/schedule/{tok}/cancel").status_code == 200
    assert client.get(f"/schedule/{tok}/calendar.ics").status_code == 404                              # cancelled: no file


def test_interview_events_need_participant_token_and_consent(client, world):
    tok = world["itok"]
    err(client.post(f"/interview/{tok}/events", json={"type": "join"}), 403, "denied")                          # no consent yet
    err(client.post(f"/interview/{tok}/consent", json={"scopes": ["telepathy"], "notice_version": "v1"}), 400, "invalid_input")
    assert client.post(f"/interview/{tok}/consent", json={"scopes": ["events"], "notice_version": "v1"}).status_code == 200
    r = client.post(f"/interview/{tok}/events", json={"type": "join", "client_t": 1.5})
    assert r.status_code == 200 and r.json()["result"]["seq"] == 1
    assert client.post(f"/interview/{tok}/events", json={"type": "join"}).json()["result"]["seq"] == 2
    err(client.post(f"/interview/{tok}/events", json={"data": {}}), 400, "invalid_input")                       # missing "type"
    assert client.post(f"/interview/{tok}/withdraw").status_code == 200
    err(client.post(f"/interview/{tok}/events", json={"type": "join"}), 403, "denied")                          # recording stopped


def wav(n=2000):
    return b"RIFF" + (n + 28).to_bytes(4, "little") + b"WAVEfmt " + bytes(range(256)) * (n // 256 + 1)


def test_audio_upload_streams_seals_and_obeys_consent_type_size_and_one_track(client, world, monkeypatch):
    """KAN-74: the HTTP ingress for audio: consent first, a file that is what it claims, capped size, sealed at rest, once."""
    from velaris.core import vault
    from velaris.intel.paths import data_dir
    tok, url = world["itok"], None
    url = f"/interview/{tok}/audio?duration_s=12.5"
    hdr = {"content-type": "audio/wav"}
    monkeypatch.setitem(public.DEFAULT_LIMITS, "i_audio", RouteLimit(10_000_000, 50, 50))
    err(client.post(url, content=wav(), headers=hdr), 403, "denied")                                           # no audio consent yet
    assert client.post(f"/interview/{tok}/consent", json={"scopes": ["audio"], "notice_version": "v1"}).status_code == 200
    err(client.post(url, content=wav(), headers={"content-type": "text/plain"}), 415, "unsupported_media_type")
    err(client.post(f"/interview/{tok}/audio", content=wav(), headers=hdr), 400, "invalid_input")               # no duration
    err(client.post(url, content=b"not audio at all, just text", headers=hdr), 400, "invalid_input")           # wrong magic bytes
    monkeypatch.setitem(public.DEFAULT_LIMITS, "i_audio", RouteLimit(1500, 50, 50))
    err(client.post(url, content=wav(), headers=hdr), 413, "too_large")                                       # over the route's cap
    monkeypatch.setitem(public.DEFAULT_LIMITS, "i_audio", RouteLimit(10_000_000, 50, 50))
    data = wav(3_000_000)
    r = client.post(url, content=data, headers=hdr)
    assert r.status_code == 200, r.text
    sha = r.json()["result"]["sha256"]
    stored = data_dir() / "agents" / "INTERVIEW_RECORD" / "audio" / f"{sha}.bin"
    assert stored.exists() and stored.read_bytes()[:4] == vault.STREAM_MAGIC and data[:300] not in stored.read_bytes()
    assert vault.read_sealed(stored, "hiring:INTERVIEW_RECORD", vault.path_context(stored)) == data
    err(client.post(url, content=wav(), headers=hdr), 409, "conflict")                                        # one track per participant
    assert not list((data_dir() / "uploads").glob("*"))                                                        # no temp file left behind
    with pytest.raises(vault.VaultError):
        stored.write_bytes(stored.read_bytes()[:-30])                                                         # cut short: refused when read
        vault.read_sealed(stored, "hiring:INTERVIEW_RECORD", vault.path_context(stored))


# ---- the signing ceremony, end to end against ESIGN ----------------------------------------------------------------------------
def make_request(e, sender, signers, ref="ofr-1"):
    with acting_as(HR1):
        rid = e.create_request("Offer for Asha", base64.b64encode(build_pdf([("h1", "Offer"), ("p", "Please sign")])).decode(), signers,
                               document_ref=ref)["request"]["id"]
        assert e.send_request(rid)["status"] == "ok"
    return rid


def test_signing_ceremony_open_otp_consent_sign_and_seal(client, esign_world):
    e, sender = esign_world
    rid = make_request(e, sender, [{"name": "Asha Raman", "email": "asha@example.in", "otp_required": True, "phone": "9000000000"}])
    tok, who_ = sender.token_for("asha@example.in"), {"email": "asha@example.in"}
    path = lambda step: f"/sign/{tok}/{step}"
    err(client.post(path("open"), json={"email": "mallory@example.in"}), 403, "identity_mismatch")
    r = client.post(path("open"), json=who_)
    assert r.status_code == 200 and r.json()["result"]["otp_required"] is True and r.json()["result"]["document_sha256"] and r.json()["result"]["legal_notice"]
    err(client.post(path("consent"), json={**who_, "consent_text_version": "v1"}), 409, "otp_required")        # code first
    assert client.post(path("otp/request"), json=who_).status_code == 200
    err(client.post(path("otp/verify"), json={**who_, "code": "000000"}), 400, "otp_wrong")
    assert client.post(path("otp/verify"), json={**who_, "code": sender.otp_for("9000000000")}).status_code == 200
    err(client.post(path("consent"), json={**who_, "consent_text_version": "v0"}), 400, "invalid_input")
    assert client.post(path("consent"), json={**who_, "consent_text_version": "v1"}).status_code == 200
    err(client.post(path("sign"), json={**who_, "typed_name": "Someone Else"}), 400, "name_mismatch")
    r = client.post(path("sign"), json={**who_, "typed_name": "asha  RAMAN"})
    assert r.status_code == 200 and r.json()["result"]["signer_state"] == "signed" and r.json()["result"]["request_status"] == "completed"
    assert r.json()["result"]["seal"]["seal_hash"]
    err(client.post(path("sign"), json={**who_, "typed_name": "Asha Raman"}), 404, "not_found")                # the token was good for one signature
    with acting_as(HR1):
        assert e.request_info(rid, "acme")["status"] == "sealed" and e.verify(rid)["valid"] is True
    ev = json.dumps(r.json())
    assert tok not in ev and "token_sha256" not in ev and "sealed_pdf" not in ev


def test_signing_decline_closes_the_request_and_nothing_can_be_signed_after(client, esign_world):
    e, sender = esign_world
    rid = make_request(e, sender, [{"name": "Asha Raman", "email": "asha@example.in"}, {"name": "Ravi Kumar", "email": "ravi@example.in"}], "ofr-2")
    a, r_ = sender.token_for("asha@example.in"), sender.token_for("ravi@example.in")
    assert client.post(f"/sign/{a}/open", json={"email": "asha@example.in"}).status_code == 200
    d = client.post(f"/sign/{a}/decline", json={"email": "asha@example.in", "reason": "terms"})
    assert d.status_code == 200 and d.json()["result"]["request_status"] == "declined"
    err(client.post(f"/sign/{r_}/open", json={"email": "ravi@example.in"}), 404, "not_found")        # the other signer's code died too
    with acting_as(HR1):
        assert e.request_info(rid, "acme")["status"] == "declined"


def test_ceremony_steps_take_ip_and_agent_from_the_request_not_the_body(client, esign_world):
    e, sender = esign_world
    make_request(e, sender, [{"name": "Asha Raman", "email": "asha@example.in"}], "ofr-3")
    tok = sender.token_for("asha@example.in")
    err(client.post(f"/sign/{tok}/open", json={"email": "asha@example.in", "ip": "1.2.3.4"}), 400, "invalid_input")      # no client-asserted ip


# ---- limits -----------------------------------------------------------------------------------------------------------------
def test_rate_limit_per_token_and_per_ip_bucket_with_window_reset(client, tick):
    per_token = public.DEFAULT_LIMITS["cancel"].per_token                 # 5
    for _ in range(per_token):
        err(client.post(f"/schedule/{TOKEN}/cancel"), 404, "not_found")
    err(client.post(f"/schedule/{TOKEN}/cancel"), 429, "rate_limited")      # that token is spent ...
    err(client.post(f"/schedule/{'u' * 32}/cancel"), 404, "not_found")      # ... another token from the same client is not
    per_ip = public.DEFAULT_LIMITS["cancel"].per_ip                         # 10, including the 6 above that were counted (1 refused)
    seen = 0
    for i in range(per_ip + 2):
        r = client.post(f"/schedule/{chr(97 + i) * 32}/cancel")
        seen += r.status_code == 429
    assert seen >= 1                                                         # the IP bucket ran out across different tokens
    tick.t += 61                                                              # the window passes
    err(client.post(f"/schedule/{TOKEN}/cancel"), 404, "not_found")


def test_ip_buckets_are_separate_and_x_forwarded_for_is_only_trusted_when_set(esign_world, tick, monkeypatch):
    lim = {"cancel": RouteLimit(1024, 100, 2)}
    plain = TestClient(create_public_app(PublicSettings(esign=esign_world[0], clock=tick, limits=lim)), raise_server_exceptions=False)
    for xff in ("198.51.100.1", "198.51.100.2", "198.51.100.3"):               # spoofed header, untrusted: one bucket
        r = plain.post(f"/schedule/{'a' * 32}/cancel", headers={"x-forwarded-for": xff})
    assert r.status_code == 429
    monkeypatch.setattr(public, "_from_trusted_proxy", lambda peer: True)          # the test client's peer is not an address
    proxied = TestClient(create_public_app(PublicSettings(esign=esign_world[0], clock=tick, limits=lim, trust_proxy=True)), raise_server_exceptions=False)
    codes = [proxied.post(f"/schedule/{chr(98 + i) * 32}/cancel", headers={"x-forwarded-for": f"spoof, 198.51.100.{i}"}).status_code for i in range(3)]
    assert codes == [404, 404, 404]                                           # the proxy's own entry (last) separates clients


def test_counter_table_is_bounded_and_fails_closed_for_addresses_but_random_ids_cannot_lock_clients_out(esign_world, tick, monkeypatch):
    """KAN-64 review: random tokens in the URL used to create rate keys until the table was full and every new client got 429."""
    monkeypatch.setattr(public, "_from_trusted_proxy", lambda peer: True)
    c = TestClient(create_public_app(PublicSettings(esign=esign_world[0], clock=tick, max_keys=4, trust_proxy=True)), raise_server_exceptions=False)
    flood = [c.post(f"/schedule/{chr(97 + i) * 32}/cancel", headers={"x-forwarded-for": "198.51.100.200"}).status_code for i in range(8)]
    assert 429 not in flood                                           # ids are not counted once their table is full
    legit = c.post(f"/schedule/{'z' * 32}/cancel", headers={"x-forwarded-for": "198.51.100.7"})
    assert legit.status_code == 404                                   # a real client is still served (and told "not found", not "busy")
    for i in range(6):                                                # distinct ADDRESSES do fill the address table: fail closed
        last = c.post(f"/schedule/{'y' * 32}/cancel", headers={"x-forwarded-for": f"198.51.100.{20 + i}"})
    assert last.status_code == 429


def test_malformed_ids_never_reach_a_counter_and_deep_json_is_a_400(client, world, tick):
    for i in range(30):
        client.post(f"/schedule/short{i}/cancel")
    deep = b"[" * 1000 + b"]" * 1000
    err(client.post(f"/schedule/{world['sched']}/pick", content=deep, headers={"content-type": "application/json"}), 400, "invalid_input")
    err(client.post(f"/schedule/{world['sched']}/pick", json={"start": 10 ** 400}), 400, "invalid_input")


def test_body_size_limits_content_type_and_shape(client, world):
    fid, tok = world["fid"], world["itok"]
    big = {"answers": {"x": "y" * (2 * 1024 * 1024)}, "pow_solution": {}}
    err(client.post(f"/careers/apply/{fid}", json=big), 413, "too_large")                                  # declared length
    err(client.post(f"/interview/{tok}/events", json={"type": "t", "data": {"text": "z" * 70_000}}), 413, "too_large")
    err(client.post(f"/schedule/{tok}/pick", content=b'{"start": 1}' + b" " * 3000, headers={"content-type": "application/json"}), 413, "too_large")

    def chunks():                                                                                            # no Content-Length: counted while streaming
        for _ in range(10):
            yield b" " * 1000
    err(client.post(f"/schedule/{tok}/pick", content=chunks(), headers={"content-type": "application/json"}), 413, "too_large")
    err(client.post(f"/schedule/{tok}/pick", content=b"start=1", headers={"content-type": "application/x-www-form-urlencoded"}), 415, "unsupported_media_type")
    err(client.post(f"/schedule/{tok}/pick", content=b"{not json", headers={"content-type": "application/json"}), 400, "invalid_input")
    err(client.post(f"/schedule/{tok}/pick", content=b"[1]", headers={"content-type": "application/json"}), 400, "invalid_input")
    e = err(client.post(f"/schedule/{tok}/pick", json={"start": 1, "evil": {"$ne": 1}}), 400, "invalid_input")
    assert "evil" not in e["message"]                                                                        # unknown names are counted, not echoed


# ---- CORS, identity, cookies, errors ---------------------------------------------------------------------------------------------
def test_cors_is_closed_by_default_and_an_allow_list_opens_exact_origins_only(client, esign_world, tick):
    r = client.get("/careers/forms/nope", headers={"origin": "https://evil.example"})
    assert "access-control-allow-origin" not in r.headers
    assert "access-control-allow-origin" not in client.options("/careers/forms/nope", headers={"origin": "https://evil.example",
                                                                                              "access-control-request-method": "GET"}).headers
    for bad in ("*", "https://a.example/", "javascript:alert(1)", "http://"):
        with pytest.raises(ValueError):
            PublicSettings(cors_origins=(bad,))
    c = TestClient(create_public_app(PublicSettings(esign=esign_world[0], clock=tick, cors_origins=("https://careers.example.com",))),
                   raise_server_exceptions=False)
    ok = c.get("/careers/forms/nope", headers={"origin": "https://careers.example.com"})
    assert ok.headers["access-control-allow-origin"] == "https://careers.example.com" and "access-control-allow-credentials" not in ok.headers
    assert "access-control-allow-origin" not in c.get("/careers/forms/nope", headers={"origin": "https://evil.example"}).headers


def test_no_identity_no_cookies_no_cache_and_handlers_run_without_a_caller(client, monkeypatch):
    seen = []
    monkeypatch.setattr(intake, "public_status", lambda token: seen.append(__import__("velaris.core.access", fromlist=["x"]).current_caller()) or {"status": "not_found"})
    with acting_as(HR1):                                                       # a caller in the surrounding context must not leak in
        r = client.get(f"/careers/status/{TOKEN}", headers={"authorization": "Bearer x", "cookie": "session=abc", "x-velaris-identity": "hr_admin"})
    assert seen == [None] and r.status_code == 404
    assert "set-cookie" not in r.headers and r.headers["cache-control"] == "no-store" and r.headers["x-content-type-options"] == "nosniff"
    src = open(public.__file__).read()
    assert "set_cookie" not in src and "check_caller" not in src and "Caller(" not in src


def test_failures_never_leak_exception_text(client, monkeypatch):
    def boom(token):
        raise RuntimeError("secret-internal-detail /var/lib/velaris")
    monkeypatch.setattr(intake, "public_status", boom)
    r = client.get(f"/careers/status/{TOKEN}")
    assert r.status_code == 500 and "secret-internal-detail" not in r.text and r.json() == {"error": {"code": "error", "message": "the request could not be completed"}}
    monkeypatch.setattr(intake, "public_status", lambda token: {"status": "weird", "reason": "internal /etc/passwd"})
    r = client.get(f"/careers/status/{TOKEN}")
    assert r.status_code == 500 and "passwd" not in r.text
    monkeypatch.setattr(intake, "public_status", lambda token: {"status": "not_configured", "reason": "vault path /root/x"})
    r = client.get(f"/careers/status/{TOKEN}")
    assert r.status_code == 503 and "/root" not in r.text
    assert client.get("/nope").json() == {"error": {"code": "not_found", "message": "no such endpoint"}}
    assert client.put(f"/careers/status/{TOKEN}").json()["error"]["code"] == "method_not_allowed"


def test_a_withdrawal_stops_new_bookings_and_asking_twice_keeps_the_first_date(client, world):
    """KAN-64 review: a candidate who had withdrawn could still book interviews, and a repeat call reset the request."""
    app_id, sched_tok = world["apps"][0], world["sched"]
    wtok = hf.issue_token("acme", app_id, "withdraw", 3)
    assert client.get(f"/schedule/{sched_tok}/slots").status_code == 200
    assert client.post(f"/careers/withdraw/{wtok}").status_code == 200
    stamp = hf._st().load()["withdrawals"][app_id]["requested_at"]
    assert client.post(f"/careers/withdraw/{wtok}").status_code == 200
    assert hf._st().load()["withdrawals"][app_id]["requested_at"] == stamp
    err(client.get(f"/schedule/{sched_tok}/slots"), 404, "not_found")
    err(client.post(f"/schedule/{sched_tok}/pick", json={"start": 1}), 404, "not_found")


def test_forwarded_for_is_believed_only_from_the_proxy_address():
    """KAN-64: with TRUST_PROXY any direct client could choose its own rate-limit key by sending X-Forwarded-For."""
    from starlette.requests import Request

    def req(peer, xff):
        return Request({"type": "http", "headers": [(b"x-forwarded-for", xff.encode())], "client": (peer, 1234), "method": "GET", "path": "/"})
    assert public._client_ip(req("127.0.0.1", "9.9.9.9, 203.0.113.7"), True) == "203.0.113.7"        # nginx on loopback
    assert public._client_ip(req("172.18.0.1", "203.0.113.7"), True) == "203.0.113.7"                  # docker bridge gateway
    assert public._client_ip(req("93.184.216.34", "203.0.113.7"), True) == "93.184.216.34"             # a direct public client: ignored
    assert public._client_ip(req("127.0.0.1", "203.0.113.7"), False) == "127.0.0.1"                    # not trusting a proxy at all
