"""Client for LinkedIn's internal "Voyager" API.

Requests are sent with `fetch()` from a page on the linkedin.com origin inside
the persistent Chromium profile, so they carry the browser's own cookies,
headers and fingerprint instead of those of a Python HTTP client.

To avoid loading the full LinkedIn web app (and the burst of requests it
makes) on every command, the bootstrap navigation to /feed/ is answered
locally with an empty document. Nothing about that navigation reaches
LinkedIn; only the explicit API calls below do.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import quote

from playwright.sync_api import Page

from .browser import LINKEDIN_ORIGIN, BrowserSession
from .errors import (
    AuthenticationRequiredError,
    ChallengeError,
    RateLimitedError,
    VoyagerError,
    VoyagerHTTPError,
)
from .pacing import RequestPacer

API_PREFIX = "/voyager/api"
BOOTSTRAP_URL = f"{LINKEDIN_ORIGIN}/feed/"
NORMALIZED_JSON = "application/vnd.linkedin.normalized+json+2.1"

RATE_LIMIT_COOLDOWN_S = 60 * 60
CHALLENGE_COOLDOWN_S = 6 * 60 * 60

_BLANK_DOCUMENT = "<!doctype html><html><head><title>LinkedIn</title></head><body></body></html>"
_LOGIN_URL_MARKERS = ("/login", "/authwall", "/uas/")
_CHALLENGE_URL_MARKERS = ("/checkpoint", "/challenge")
# Characters that Rest.li needs verbatim in query values. "%" is kept so callers
# can pass values that are already encoded, such as URNs inside `variables=(...)`.
_QUERY_SAFE = "(),:%"

_FETCH_SCRIPT = """
async ({url, method, headers, body, timeoutMs}) => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
        const response = await fetch(url, {
            method, headers, body, credentials: 'include', signal: controller.signal,
        });
        return {
            status: response.status,
            url: response.url,
            contentType: response.headers.get('content-type') || '',
            text: await response.text(),
        };
    } catch (error) {
        return {status: 0, url, contentType: '', text: '', error: String(error)};
    } finally {
        clearTimeout(timer);
    }
}
"""


@dataclass(frozen=True)
class RawResponse:
    status: int
    url: str
    content_type: str
    text: str
    error: str | None = None


def build_url(path: str, params: Mapping[str, Any] | None = None) -> str:
    if path.startswith(("http://", "https://")):
        if not path.startswith(f"{LINKEDIN_ORIGIN}{API_PREFIX}/"):
            raise ValueError(f"Only {LINKEDIN_ORIGIN}{API_PREFIX}/ URLs are allowed, got {path!r}")
        url = path
    else:
        if not path.startswith("/"):
            path = f"/{path}"
        if not path.startswith(f"{API_PREFIX}/"):
            path = f"{API_PREFIX}{path}"
        url = f"{LINKEDIN_ORIGIN}{path}"

    if params:
        query = "&".join(f"{quote(str(key), safe='')}={quote(str(value), safe=_QUERY_SAFE)}" for key, value in params.items())
        url = f"{url}{'&' if '?' in url else '?'}{query}"
    return url


class VoyagerClient:
    def __init__(self, session: BrowserSession, pacer: RequestPacer) -> None:
        self.session = session
        self.pacer = pacer
        self._page: Page | None = None

    def connect(self) -> None:
        if not self.session.has_session_cookie():
            raise AuthenticationRequiredError("You are not logged in. Run `linkedin-cli auth login` first.")

        page = self.session.page
        page.route(
            BOOTSTRAP_URL,
            lambda route: route.fulfill(status=200, content_type="text/html", body=_BLANK_DOCUMENT),
            times=1,
        )
        page.goto(BOOTSTRAP_URL, wait_until="domcontentloaded")
        if self.session.is_headless:
            self.session.mask_headless_fingerprint(page)
        self._page = page

    def get(self, path: str, params: Mapping[str, Any] | None = None, *, accept: str = NORMALIZED_JSON) -> Any:
        return self.request("GET", path, params=params, accept=accept)

    def post(
        self,
        path: str,
        payload: Any,
        params: Mapping[str, Any] | None = None,
        *,
        accept: str = NORMALIZED_JSON,
    ) -> Any:
        return self.request("POST", path, params=params, payload=payload, accept=accept)

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        payload: Any = None,
        accept: str = NORMALIZED_JSON,
    ) -> Any:
        if self._page is None:
            self.connect()
        url = build_url(path, params)

        csrf_token = self.session.linkedin_cookies().get("JSESSIONID", "").strip('"')
        if not csrf_token:
            raise AuthenticationRequiredError("The LinkedIn session cookies are incomplete. Run `linkedin-cli auth login`.")

        headers = {
            "accept": accept,
            "csrf-token": csrf_token,
            "x-restli-protocol-version": "2.0.0",
            "x-li-lang": "en_US",
        }
        body = None
        if payload is not None:
            headers["content-type"] = "application/json; charset=UTF-8"
            body = json.dumps(payload)

        self.pacer.before_request()
        self.pacer.record_request()
        logging.debug("Voyager %s %s", method, url)
        result = self._page.evaluate(
            _FETCH_SCRIPT,
            {
                "url": url,
                "method": method,
                "headers": headers,
                "body": body,
                "timeoutMs": self.session.config.default_timeout_ms,
            },
        )
        response = RawResponse(
            status=int(result.get("status", 0)),
            url=result.get("url") or url,
            content_type=result.get("contentType") or "",
            text=result.get("text") or "",
            error=result.get("error"),
        )
        return self._handle(response, url)

    def _handle(self, response: RawResponse, requested_url: str) -> Any:
        final_url = response.url.lower()
        snippet = response.text[:300].replace("\n", " ")

        if response.status == 0:
            raise VoyagerError(f"Request to {requested_url} failed: {response.error or 'network error'}")
        if any(marker in final_url for marker in _CHALLENGE_URL_MARKERS):
            self._challenge("LinkedIn redirected the request to a security checkpoint")
        if any(marker in final_url for marker in _LOGIN_URL_MARKERS):
            raise AuthenticationRequiredError("The LinkedIn session has expired. Run `linkedin-cli auth login`.")
        if response.status in (429, 999):
            reason = f"HTTP {response.status} (too many requests)"
            self.pacer.start_cooldown(RATE_LIMIT_COOLDOWN_S, reason)
            raise RateLimitedError(f"LinkedIn rate-limited the session: {reason}. Requests are paused for an hour.")
        if response.status == 401:
            raise AuthenticationRequiredError("The LinkedIn session has expired. Run `linkedin-cli auth login`.")
        if response.status == 403:
            lowered = response.text.lower()
            if "csrf" in lowered:
                raise AuthenticationRequiredError(
                    "LinkedIn rejected the session token (CSRF). Run `linkedin-cli auth login`."
                )
            if "challenge" in lowered:
                self._challenge("LinkedIn answered with a CHALLENGE")
        if response.status >= 400:
            raise VoyagerHTTPError(response.status, requested_url, snippet)

        if not response.text.strip():
            return {}
        try:
            return json.loads(response.text)
        except ValueError as exc:
            raise VoyagerError(
                f"Expected JSON from {requested_url} but got {response.content_type or 'unknown content'}: {snippet}"
            ) from exc

    def _challenge(self, reason: str) -> None:
        self.pacer.start_cooldown(CHALLENGE_COOLDOWN_S, reason)
        raise ChallengeError(
            f"{reason}. Requests are paused. Open the browser with `linkedin-cli open`, "
            "complete the security check by hand, then run `linkedin-cli limits --clear-cooldown`."
        )
