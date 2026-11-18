"""KAN-125 and the confirm dialogs: the REAL public.js in Chromium (marker `browser`; skipped without playwright or a Chromium).

The public app runs under uvicorn on a loopback port; the page script drives the sign ceremony end to end against a real ESIGN
agent, and the styled confirm dialog is checked for what a keyboard or screen-reader user needs: a role=dialog named by its heading,
focus moved in and kept in, Escape = "go back", focus returned to the opener.
"""
import socket
import threading
import time

import pytest
import uvicorn

from velaris.api.public import PublicSettings, create_public_app
from velaris.agents.ESIGN.main import Esign
from velaris.tests.onboarding_helpers import Clock, FakeSender
from velaris.tests.test_api_public import make_request

pytestmark = pytest.mark.browser
playwright_sync = pytest.importorskip("playwright.sync_api")
EMAIL = "asha@example.in"


@pytest.fixture()
def esign_world():
    sender = FakeSender()
    return Esign({"sender": sender, "clock": Clock()}), sender


@pytest.fixture()
def server(esign_world):
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    app = create_public_app(PublicSettings(esign=esign_world[0], clock=time.time))
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    t = threading.Thread(target=srv.run, daemon=True)
    t.start()
    for _ in range(100):
        if srv.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    srv.should_exit = True
    t.join(5)


@pytest.fixture()
def page(server):
    with playwright_sync.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as e:                      # no Chromium installed: not a failure of the code under test
            pytest.skip(f"no usable Chromium: {str(e)[:100]}")
        pg = browser.new_page()
        pg.set_default_timeout(8000)
        yield pg
        browser.close()


def _token(esign_world):
    e, sender = esign_world
    make_request(e, sender, [{"name": "Asha Raman", "email": EMAIL}])
    return sender.token_for(EMAIL)


def _open(page, server, tok):
    page.goto(f"{server}/sign/{tok}")
    page.fill("#email", EMAIL)
    page.get_by_role("button", name="Open the document").click()
    try:
        page.wait_for_selector("text=Document fingerprint")
    except Exception:
        raise AssertionError("ceremony did not open: " + page.inner_text("#app")) from None


def test_signing_in_a_real_browser_end_to_end(page, server, esign_world):
    tok = _token(esign_world)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    _open(page, server, tok)
    assert "Asha Raman" in page.inner_text("#app")
    page.click("button:text-is('Sign')")                                     # without consent or a name: refused in the page, nothing sent
    assert "agree to electronic signing" in page.inner_text("[role=alert]")
    page.check("#agree")
    page.fill("#typed", "Someone Else")
    page.click("button:text-is('Sign')")
    page.wait_for_function("document.querySelector('[role=alert]').textContent.length > 0")
    assert "Signed" not in page.inner_text("#app h1")                       # a wrong name does not sign
    page.fill("#typed", "asha  RAMAN")
    page.click("button:text-is('Sign')")
    try:
        page.wait_for_selector("h1:text-is('Signed')")
    except Exception:
        raise AssertionError("not signed: " + page.inner_text("#app")) from None
    assert errors == []


def test_decline_uses_an_accessible_dialog_not_window_confirm(page, server, esign_world):
    tok = _token(esign_world)
    native = []
    page.on("dialog", lambda d: (native.append(d.message), d.dismiss()))        # a window.confirm would land here
    _open(page, server, tok)
    page.get_by_role("button", name="Decline to sign").click()
    dlg = page.get_by_role("dialog", name="Decline to sign?")
    dlg.wait_for()
    assert page.evaluate("document.activeElement.textContent") == "Go back"      # the safe answer has focus
    assert "closes the whole request" in dlg.get_attribute("aria-describedby") or page.locator("#dlg-text").inner_text()
    for _ in range(5):                                                            # focus cannot leave the dialog
        page.keyboard.press("Tab")
        assert page.evaluate("document.activeElement.closest('dialog') !== null")
    page.keyboard.press("Escape")                                                 # Escape = go back, nothing declined
    page.wait_for_selector("dialog", state="detached")
    assert page.evaluate("document.activeElement.textContent") == "Decline to sign"      # focus is back on the opener
    assert page.locator("h1", has_text="Declined").count() == 0
    page.get_by_role("button", name="Decline to sign").click()
    page.get_by_role("button", name="Yes, decline").click()
    page.wait_for_selector("h1:text-is('Declined')")
    assert native == []
