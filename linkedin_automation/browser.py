from __future__ import annotations

import logging
from dataclasses import dataclass, field

from playwright.sync_api import BrowserContext, Error as PlaywrightError, Page, Playwright, sync_playwright

from .config import AppConfig
from .errors import BrowserProfileInUseError

LINKEDIN_ORIGIN = "https://www.linkedin.com"

_PROFILE_IN_USE_MARKERS = ("processsingleton", "profile is already in use", "user data directory is already in use")


@dataclass
class BrowserSession:
    """A Chromium instance on the persistent LinkedIn profile.

    `headless=None` uses the configured default. Interactive flows (login,
    composing, manual checks) should pass `headless=False`.
    `block_service_workers` keeps every request on the normal network path,
    which the API client relies on.
    """

    config: AppConfig
    headless: bool | None = None
    block_service_workers: bool = False
    playwright: Playwright | None = field(default=None, init=False)
    context: BrowserContext | None = field(default=None, init=False)
    _cdp_sessions: list = field(default_factory=list, init=False, repr=False)

    @property
    def is_headless(self) -> bool:
        return self.config.headless if self.headless is None else self.headless

    def __enter__(self) -> "BrowserSession":
        self.config.ensure_directories()
        self.playwright = sync_playwright().start()
        logging.debug("Opening Chromium with persistent profile: %s", self.config.browser_profile_dir)
        try:
            self.context = self.playwright.chromium.launch_persistent_context(
                user_data_dir=str(self.config.browser_profile_dir),
                headless=self.is_headless,
                viewport={"width": 1440, "height": 1000},
                locale="en-US",
                service_workers="block" if self.block_service_workers else "allow",
                args=["--disable-dev-shm-usage", "--disable-blink-features=AutomationControlled"],
            )
        except PlaywrightError as exc:
            self.playwright.stop()
            if any(marker in str(exc).lower() for marker in _PROFILE_IN_USE_MARKERS):
                raise BrowserProfileInUseError(
                    "The LinkedIn browser profile is already open in another linkedin-cli window. Close it and retry."
                ) from exc
            raise
        self.context.set_default_timeout(self.config.default_timeout_ms)
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        if self.context:
            self.context.close()
        if self.playwright:
            self.playwright.stop()

    @property
    def page(self) -> Page:
        if not self.context:
            raise RuntimeError("Browser session has not been started")
        page = self.context.pages[0] if self.context.pages else self.context.new_page()
        page.set_default_timeout(self.config.default_timeout_ms)
        return page

    def linkedin_cookies(self) -> dict[str, str]:
        if not self.context:
            raise RuntimeError("Browser session has not been started")
        return {cookie["name"]: cookie["value"] for cookie in self.context.cookies(LINKEDIN_ORIGIN)}

    def has_session_cookie(self) -> bool:
        return bool(self.linkedin_cookies().get("li_at"))

    def mask_headless_fingerprint(self, page: Page) -> None:
        """Make headless Chromium report the same identity as the headed browser.

        Headless Chromium advertises itself as "HeadlessChrome" both in the
        User-Agent and in the client hints. Must run on a secure (https) page.
        """
        info = page.evaluate(
            """async () => ({
                ua: navigator.userAgent,
                hints: navigator.userAgentData
                    ? await navigator.userAgentData.getHighEntropyValues(
                        ['platform', 'platformVersion', 'architecture', 'model', 'bitness', 'fullVersionList', 'uaFullVersion'])
                    : null,
            })"""
        )
        if "Headless" not in info["ua"]:
            return
        override: dict = {"userAgent": info["ua"].replace("HeadlessChrome", "Chrome")}
        hints = info.get("hints")
        if hints:
            def without_headless(items):
                return [item for item in items or [] if "Headless" not in item["brand"]]

            override["userAgentMetadata"] = {
                "brands": without_headless(hints.get("brands")),
                "fullVersionList": without_headless(hints.get("fullVersionList")),
                "fullVersion": hints.get("uaFullVersion", ""),
                "platform": hints.get("platform", ""),
                "platformVersion": hints.get("platformVersion", ""),
                "architecture": hints.get("architecture", ""),
                "model": hints.get("model", ""),
                "mobile": bool(hints.get("mobile")),
                "bitness": hints.get("bitness", ""),
            }
        cdp = page.context.new_cdp_session(page)
        cdp.send("Emulation.setUserAgentOverride", override)
        # Emulation overrides only last while the CDP session stays attached.
        self._cdp_sessions.append(cdp)
        logging.debug("Masked headless user agent")
