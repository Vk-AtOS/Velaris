"""KAN-123/124: the real pages in a real browser against a live public app (skipped where no Chromium is installed: UNVERIFIED there)."""
# ruff: noqa: F811  (pytest fixtures imported from test_api_public are named again as test arguments)
import socket
import threading
import time

import pytest
import uvicorn

from velaris.agentkit.hiring_testkit import as_, tiny_pdf
from velaris.agents.SCREENING_FORMS.main import ScreeningForms
from velaris.api.public import PublicSettings, create_public_app
from velaris.tests.test_api_public import esign_world, fast_pow, world  # noqa: F401  (fixtures)

sync_api = pytest.importorskip("playwright.sync_api")


@pytest.fixture()
def base(esign_world):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(create_public_app(PublicSettings(esign=esign_world[0])), host="127.0.0.1", port=port, log_config=None))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    t.join(5)


@pytest.fixture()
def page(tmp_path):
    with sync_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as e:                      # no browser binary installed
            pytest.skip(f"no Chromium: {type(e).__name__}")
        ctx = browser.new_context()
        pg = ctx.new_page()
        pg.problems = []
        pg.on("console", lambda m: pg.problems.append(m.text) if m.type in ("error", "warning") else None)
        pg.on("pageerror", lambda e: pg.problems.append(str(e)))
        pg.ctx = ctx
        yield pg
        browser.close()


def test_apply_then_status_then_withdraw_in_a_browser(base, world, page, tmp_path):
    fid = world["fid"]
    cv = tmp_path / "cv.pdf"
    cv.write_bytes(tiny_pdf("Skills: Python and SQL, 4 years"))
    page.goto(f"{base}/apply/{fid}")
    page.get_by_label("Full name").fill("Asha Kumar")
    page.get_by_label("email", exact=False).first.fill("asha@example.com")
    page.get_by_label("years").fill("4")
    page.get_by_label("cv", exact=False).set_input_files(str(cv))
    page.get_by_role("button", name="Submit application").click()
    page.get_by_text("Please tick the box").wait_for()                       # consent is required before anything is sent
    page.get_by_label("I have read the notice").check()
    page.get_by_role("button", name="Submit application").click()
    page.get_by_role("heading", name="Application received").wait_for(timeout=30000)
    assert page.ctx.cookies() == [] and not page.problems, page.problems

    with as_(world["c"]["rec"]):
        sub = ScreeningForms().pending_submissions()["submissions"][0]["id"]
        acc = ScreeningForms().accept_submission(submission_id=sub)
        token = acc["status_token"]
        wtoken = ScreeningForms().issue_candidate_token(application_id=acc["application"]["id"], purpose="withdraw")["token"]
    page.goto(f"{base}/status/{token}")
    page.get_by_role("heading", name="Your application").wait_for()
    assert page.get_by_role("button").count() == 0                              # a status link cannot withdraw
    page.goto(f"{base}/withdraw/{wtoken}")
    page.get_by_role("button", name="Withdraw").click()
    page.get_by_role("dialog", name="Withdraw your application?").get_by_role("button", name="Yes, withdraw").click()
    page.get_by_role("heading", name="Withdrawal requested").wait_for()
    page.goto(f"{base}/status/{'q' * 40}")                                       # the browser logs the API's 404 itself
    page.get_by_text("not valid or has expired").wait_for()
    assert page.ctx.cookies() == [] and all("404" in x for x in page.problems), page.problems          # and nothing else (no CSP violation)


def test_schedule_page_picks_and_cancels(base, world, page):
    page.goto(f"{base}/schedule/{world['sched']}")
    page.get_by_role("radio").first.check()
    page.get_by_role("button", name="Confirm this time").click()
    page.get_by_text("Booked for").wait_for()
    page.get_by_role("button", name="Cancel my booking").click()
    page.get_by_role("dialog", name="Cancel your booking?").get_by_role("button", name="Yes, cancel booking").click()
    page.get_by_text("Your booking is cancelled").wait_for()
    assert not page.problems, page.problems


def test_interview_page_consents_streams_and_withdraws(base, world, page):
    page.goto(f"{base}/interview/{world['itok']}")
    page.get_by_role("button", name="Agree and join").click()
    page.get_by_text("You have joined").wait_for()
    page.get_by_role("button", name="Withdraw consent").click()
    page.get_by_role("dialog", name="Leave the interview?").get_by_role("button", name="Yes, withdraw and leave").click()
    page.get_by_role("heading", name="Consent withdrawn").wait_for()
    assert not page.problems, page.problems
