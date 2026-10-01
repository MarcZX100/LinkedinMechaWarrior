"""End-to-end test of the Voyager transport in a real Chromium, against a mocked linkedin.com.

Every request is intercepted: nothing reaches the network. Skipped when the
Playwright Chromium build is not installed.
"""

import pytest
from playwright.sync_api import Error as PlaywrightError, sync_playwright

from linkedin_automation.api import get_me
from linkedin_automation.browser import BrowserSession
from linkedin_automation.config import load_config
from linkedin_automation.errors import CooldownActiveError, RateLimitedError
from linkedin_automation.pacing import RequestPacer
from linkedin_automation.voyager import VoyagerClient

ME_PAYLOAD = {
    "data": {"*miniProfile": "urn:li:fs_miniProfile:1"},
    "included": [{"entityUrn": "urn:li:fs_miniProfile:1", "firstName": "Ada", "lastName": "Lovelace"}],
}


@pytest.fixture(scope="module")
def chromium_available():
    try:
        with sync_playwright() as playwright:
            playwright.chromium.launch().close()
    except PlaywrightError as exc:
        pytest.skip(f"Playwright Chromium is not available: {str(exc).splitlines()[0]}")


@pytest.fixture
def config(monkeypatch, tmp_path, chromium_available):
    monkeypatch.setenv("LINKEDIN_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("HEADLESS", "true")
    return load_config()


def add_session_cookies(context):
    context.add_cookies(
        [
            {"name": "li_at", "value": "token", "domain": ".www.linkedin.com", "path": "/", "secure": True, "httpOnly": True},
            {"name": "JSESSIONID", "value": '"ajax:42"', "domain": ".www.linkedin.com", "path": "/", "secure": True},
        ]
    )


def test_voyager_requests_run_in_the_browser_with_a_clean_fingerprint(config):
    api_requests = []
    unexpected = []

    pacer = RequestPacer(
        state_file=config.request_log_file,
        min_delay_s=1,
        max_delay_s=1,
        hourly_budget=10,
        daily_budget=10,
        sleep=lambda seconds: None,
    )

    with BrowserSession(config, block_service_workers=True) as browser:
        add_session_cookies(browser.context)

        def block_everything_else(route, request):
            unexpected.append(request.url)
            route.abort()

        def fake_voyager(route, request):
            api_requests.append((request.url, request.all_headers()))
            if request.url.endswith("/voyager/api/me"):
                route.fulfill(json=ME_PAYLOAD)
            else:
                route.fulfill(status=999, body="")

        # Routes run in reverse registration order: the catch-all goes first.
        browser.context.route("**/*", block_everything_else)
        browser.context.route("https://www.linkedin.com/voyager/api/**", fake_voyager)

        client = VoyagerClient(browser, pacer)
        client.connect()
        page = browser.page

        assert page.url == "https://www.linkedin.com/feed/"
        assert page.evaluate("navigator.webdriver") is False
        assert "Headless" not in page.evaluate("navigator.userAgent")
        assert all("Headless" not in b["brand"] for b in page.evaluate("navigator.userAgentData.brands"))

        assert get_me(client).name == "Ada Lovelace"

        with pytest.raises(RateLimitedError):
            client.get("/feed/updatesV2", {"q": "chronFeed"})
        with pytest.raises(CooldownActiveError):
            client.get("/me")

    assert unexpected == []
    assert len(api_requests) == 2, "the request during the cooldown must not be sent"
    headers = api_requests[0][1]
    assert headers["csrf-token"] == "ajax:42"
    assert "li_at=token" in headers["cookie"]
    assert "Headless" not in headers["user-agent"]
    assert "Headless" not in headers.get("sec-ch-ua", "")
    assert pacer.usage().last_day == 2


FEED_HTML = """<!doctype html>
<html><body>
<script>
  window.published = null;
  window.clicked = [];
  document.addEventListener('click', (event) => {
    const button = event.target.closest('button');
    if (button) window.clicked.push(button.textContent.trim());
  });
  function openComposer() {
    const dialog = document.createElement('div');
    dialog.setAttribute('role', 'dialog');
    dialog.innerHTML = '<div contenteditable="true" role="textbox"></div><button id="post">Post</button>';
    dialog.querySelector('#post').onclick = () => {
      window.published = dialog.querySelector('[contenteditable]').innerText;
      setTimeout(() => dialog.remove(), 200);
    };
    document.body.appendChild(dialog);
  }
</script>
<button onclick="openComposer()">Start a post</button>
<article>Someone's post <button>Repost</button> <button>Republicar</button></article>
</body></html>
"""


def serve_feed(browser):
    browser.context.route("**/*", lambda route: route.abort())
    browser.context.route(
        "https://www.linkedin.com/feed/", lambda route: route.fulfill(content_type="text/html", body=FEED_HTML)
    )


def test_composer_publishes_with_the_dialog_button_only(config):
    from linkedin_automation.ui import LinkedInUI

    with BrowserSession(config) as browser:
        add_session_cookies(browser.context)
        serve_feed(browser)
        ui = LinkedInUI(browser)

        ui.prepare_post("Hello from the CLI")
        ui.publish_prepared_post()

        page = browser.page
        assert page.evaluate("window.published") == "Hello from the CLI"
        assert page.evaluate("window.clicked") == ["Start a post", "Post"]


def test_capture_records_api_responses_while_waiting(config, monkeypatch):
    import json

    from linkedin_automation import capture

    def browse_then_press_enter(page, prompt):
        page.evaluate("fetch('/voyager/api/me?x=1', {headers: {'csrf-token': 'secret'}})")
        page.evaluate("fetch('/voyager/api/other')")
        page.wait_for_timeout(500)

    monkeypatch.setattr(capture, "wait_for_enter", browse_then_press_enter)

    with BrowserSession(config) as browser:
        serve_feed(browser)
        browser.context.route("https://www.linkedin.com/voyager/api/**", lambda route: route.fulfill(json=ME_PAYLOAD))
        output, count = capture.capture_voyager_traffic(browser, config.captures_dir, url_filter="/me")

    entries = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert count == 1 and len(entries) == 1
    assert entries[0]["url"].endswith("/voyager/api/me?x=1")
    assert entries[0]["response"] == ME_PAYLOAD
    assert "secret" not in output.read_text(encoding="utf-8")
