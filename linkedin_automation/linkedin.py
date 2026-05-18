from __future__ import annotations

import logging
from dataclasses import dataclass

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from .config import AppConfig
from .utils import normalize_text, save_diagnostic_screenshot


class LinkedInAutomationError(RuntimeError):
    """Base error for LinkedIn browser automation."""


class AuthenticationRequiredError(LinkedInAutomationError):
    """Raised when the user is not authenticated."""


class ComposerNotFoundError(LinkedInAutomationError):
    """Raised when the LinkedIn post editor cannot be found."""


class PostTooLongError(LinkedInAutomationError):
    """Raised when the post is longer than the configured safety limit."""


@dataclass
class LinkedInClient:
    page: Page
    config: AppConfig

    async def open_home(self) -> None:
        logging.info("Opening LinkedIn: %s", self.config.linkedin_url)
        await self.page.goto(self.config.linkedin_url, wait_until="domcontentloaded")
        await self.page.wait_for_load_state("networkidle")

    async def ensure_authenticated(self) -> None:
        if await self.is_authenticated():
            logging.info("LinkedIn session detected")
            return

        logging.warning("No active LinkedIn session detected")
        print("\nLinkedIn needs a manual login in the browser window.")
        print("Sign in normally, complete any checks, then return here.")
        input("Press Enter when you are logged in and can see the LinkedIn feed...")

        await self.open_home()
        if not await self.is_authenticated():
            raise AuthenticationRequiredError("LinkedIn session was not detected after manual login.")

    async def is_authenticated(self) -> bool:
        url = self.page.url.lower()
        if "/login" in url or "checkpoint" in url:
            return False

        login_markers = [
            "input#username",
            "input[name='session_key']",
            "button:has-text('Sign in')",
            "button:has-text('Iniciar sesión')",
        ]
        for selector in login_markers:
            try:
                if await self.page.locator(selector).first.count() > 0:
                    return False
            except PlaywrightError:
                continue

        authenticated_markers = [
            "a[href*='/feed/']",
            "input[placeholder*='Buscar']",
            "input[placeholder*='Search']",
            "button[aria-label*='Start a post']",
            "button[aria-label*='Crear una publicación']",
            "button:has-text('Comenzar publicación')",
            "button:has-text('Start a post')",
        ]
        for selector in authenticated_markers:
            try:
                locator = self.page.locator(selector).first
                if await locator.count() > 0:
                    return True
            except PlaywrightError:
                continue
        return "linkedin.com/feed" in url

    async def prepare_post(self, text: str) -> None:
        post_text = normalize_text(text)
        self._validate_post_text(post_text)

        await self.open_home()
        await self.ensure_authenticated()
        try:
            await self._open_composer()
            await self._fill_editor(post_text)
            logging.info("Post text has been placed in the LinkedIn editor")
        except Exception as exc:
            await save_diagnostic_screenshot(self.page, self.config.debug_dir, "prepare-post-failed")
            if isinstance(exc, LinkedInAutomationError):
                raise
            raise ComposerNotFoundError(f"Could not prepare the post editor: {exc}") from exc

    async def publish_prepared_post(self) -> None:
        try:
            button = await self._first_visible(
                [
                    "button:has-text('Publicar')",
                    "button:has-text('Post')",
                    "button[aria-label*='Publicar']",
                    "button[aria-label*='Post']",
                ],
                timeout_ms=5000,
            )
            if not button:
                raise ComposerNotFoundError("Publish button was not found.")
            if await button.is_disabled():
                raise LinkedInAutomationError("Publish button is disabled; review the post in LinkedIn.")
            await button.click()
            logging.info("Publish button clicked")
        except Exception:
            await save_diagnostic_screenshot(self.page, self.config.debug_dir, "publish-failed")
            raise

    async def _open_composer(self) -> None:
        selectors = [
            "button[aria-label*='Start a post']",
            "button[aria-label*='Crear una publicación']",
            "button:has-text('Start a post')",
            "button:has-text('Comenzar publicación')",
            "button:has-text('Crear publicación')",
            "div[role='button']:has-text('Start a post')",
            "div[role='button']:has-text('Comenzar publicación')",
        ]
        button = await self._first_visible(selectors, timeout_ms=self.config.default_timeout_ms)
        if not button:
            raise ComposerNotFoundError(
                "LinkedIn composer was not found. The UI language or layout may have changed."
            )
        await button.click()
        logging.info("Composer opened")

    async def _fill_editor(self, text: str) -> None:
        selectors = [
            ".ql-editor[contenteditable='true']",
            "div[contenteditable='true'][role='textbox']",
            "div[aria-label*='Text editor'][contenteditable='true']",
            "div[aria-label*='editor de texto'][contenteditable='true']",
            "div.share-creation-state__text-editor div[contenteditable='true']",
        ]
        editor = await self._first_visible(selectors, timeout_ms=self.config.default_timeout_ms)
        if not editor:
            raise ComposerNotFoundError(
                "LinkedIn post editor was not found. A diagnostic screenshot was saved if possible."
            )

        await editor.click()
        try:
            await editor.fill(text)
        except PlaywrightError:
            await self.page.keyboard.press("Control+A")
            await self.page.keyboard.insert_text(text)

        await self.page.wait_for_timeout(500)

    async def _first_visible(self, selectors: list[str], timeout_ms: int):
        deadline = timeout_ms / 1000
        for selector in selectors:
            try:
                locator = self.page.locator(selector).first
                await locator.wait_for(state="visible", timeout=deadline * 1000 / max(len(selectors), 1))
                return locator
            except PlaywrightTimeoutError:
                continue
            except PlaywrightError:
                continue
        return None

    def _validate_post_text(self, text: str) -> None:
        if not text:
            raise LinkedInAutomationError("Post text is empty.")
        if len(text) > self.config.max_post_chars:
            raise PostTooLongError(
                f"Post is {len(text)} characters long; configured limit is {self.config.max_post_chars}."
            )
