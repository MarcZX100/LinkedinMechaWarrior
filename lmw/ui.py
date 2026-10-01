"""Browser-UI flows: logging in and using the post composer.

Everything that reads data goes through the Voyager API instead. UI selectors
match LinkedIn's English and Spanish interfaces, since the UI language follows
the account settings.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from playwright.sync_api import Error as PlaywrightError, Locator, Page, TimeoutError as PlaywrightTimeoutError

from .browser import LINKEDIN_ORIGIN, BrowserSession
from .errors import AuthenticationRequiredError, ChallengeError, ComposerNotFoundError
from .utils import save_diagnostic_screenshot

FEED_URL = f"{LINKEDIN_ORIGIN}/feed/"
LOGIN_URL = f"{LINKEDIN_ORIGIN}/login"

_LOGGED_OUT_URL_MARKERS = ("/login", "/authwall", "/uas/", "/signup")
_CHALLENGE_URL_MARKERS = ("/checkpoint", "/challenge")

_START_POST = re.compile(r"start a post|(crear|comenzar) (una )?publicaci[oó]n", re.IGNORECASE)
_PUBLISH = re.compile(r"^\s*(post|publicar)\s*$", re.IGNORECASE)


@dataclass
class LinkedInUI:
    session: BrowserSession

    @property
    def page(self) -> Page:
        return self.session.page

    @property
    def config(self):
        return self.session.config

    def goto_feed(self) -> None:
        logging.info("Opening LinkedIn")
        self.page.goto(FEED_URL, wait_until="domcontentloaded")

    def is_logged_in(self) -> bool:
        url = self.page.url.lower()
        if any(marker in url for marker in _LOGGED_OUT_URL_MARKERS + _CHALLENGE_URL_MARKERS):
            return False
        return self.session.has_session_cookie()

    def needs_security_check(self) -> bool:
        url = self.page.url.lower()
        if any(marker in url for marker in _CHALLENGE_URL_MARKERS):
            return True
        selectors = "input[name='pin'], input[autocomplete='one-time-code'], iframe[src*='captcha']"
        try:
            return self.page.locator(selectors).count() > 0
        except PlaywrightError:
            return False

    def wait_for_manual_login(self) -> None:
        print("\nLog in to LinkedIn in the browser window and complete any security checks.")
        input("Press Enter here once you can see your LinkedIn feed...")
        self._verify_logged_in()

    def login_with_credentials(self, email: str, password: str) -> None:
        self.page.goto(LOGIN_URL, wait_until="domcontentloaded")
        try:
            username = self.page.locator("input#username, input[name='session_key']").first
            password_input = self.page.locator("input#password, input[name='session_password']").first
            username.wait_for(state="visible")
            username.fill(email)
            password_input.fill(password)
            self.page.locator("button[type='submit']").first.click()
            self.page.wait_for_url(
                lambda url: not url.rstrip("/").endswith("/login"), timeout=self.config.default_timeout_ms
            )
            self.page.wait_for_load_state("domcontentloaded")
        except PlaywrightTimeoutError as exc:
            save_diagnostic_screenshot(self.page, self.config.debug_dir, "login-failed")
            raise AuthenticationRequiredError(
                "LinkedIn did not accept the login form. Check your credentials, or use `auth login --manual`."
            ) from exc

        if self.is_logged_in():
            return
        if self.needs_security_check():
            print("\nLinkedIn wants an extra security check (2FA, captcha or checkpoint).")
            print("Complete it in the browser window.")
            input("Press Enter here once you can see your LinkedIn feed...")
        self._verify_logged_in()

    def _verify_logged_in(self) -> None:
        if not self.is_logged_in():
            self.goto_feed()
        if self.is_logged_in():
            return
        save_diagnostic_screenshot(self.page, self.config.debug_dir, "login-not-completed")
        if self.needs_security_check():
            raise ChallengeError("LinkedIn is still showing a security check. Finish it with `lmw open`.")
        raise AuthenticationRequiredError("The LinkedIn session was not detected after logging in.")

    def prepare_post(self, text: str) -> None:
        self.goto_feed()
        if not self.is_logged_in():
            raise AuthenticationRequiredError("You are not logged in. Run `lmw auth login` first.")
        try:
            start_button = self.page.get_by_role("button", name=_START_POST).first
            start_button.wait_for(state="visible")
            start_button.click()
            editor = self._composer().locator("[contenteditable='true']").first
            editor.wait_for(state="visible")
            editor.click()
            editor.fill(text)
        except PlaywrightError as exc:
            save_diagnostic_screenshot(self.page, self.config.debug_dir, "compose-failed")
            raise ComposerNotFoundError(
                "Could not open the LinkedIn post editor; the UI may have changed. "
                f"A screenshot was saved in {self.config.debug_dir}."
            ) from exc
        logging.info("Post text placed in the LinkedIn editor")

    def publish_prepared_post(self) -> None:
        composer = self._composer()
        button = composer.get_by_role("button", name=_PUBLISH).first
        try:
            button.wait_for(state="visible", timeout=10_000)
            if button.is_disabled():
                raise ComposerNotFoundError("LinkedIn's Post button is disabled; check the post in the browser.")
            button.click()
            # The composer closes once LinkedIn has accepted the post.
            composer.wait_for(state="hidden", timeout=self.config.default_timeout_ms)
        except PlaywrightError as exc:
            save_diagnostic_screenshot(self.page, self.config.debug_dir, "publish-failed")
            raise ComposerNotFoundError(
                "Could not confirm that the post was published. Check the browser before retrying."
            ) from exc
        logging.info("Post published")

    def _composer(self) -> Locator:
        return self.page.get_by_role("dialog").filter(has=self.page.locator("[contenteditable='true']")).first
