from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from playwright.async_api import BrowserContext, Page, Playwright, async_playwright

from .config import AppConfig


@dataclass
class BrowserSession:
    config: AppConfig
    playwright: Playwright | None = None
    context: BrowserContext | None = None

    async def __aenter__(self) -> "BrowserSession":
        self.config.ensure_directories()
        self.playwright = await async_playwright().start()
        profile_dir = Path(self.config.browser_profile_dir)
        logging.info("Opening Chromium with persistent profile: %s", profile_dir)
        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=self.config.headless,
            viewport={"width": 1440, "height": 1000},
            locale="es-ES",
            args=["--disable-dev-shm-usage"],
        )
        self.context.set_default_timeout(self.config.default_timeout_ms)
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        if self.context:
            await self.context.close()
        if self.playwright:
            await self.playwright.stop()

    async def new_page(self) -> Page:
        if not self.context:
            raise RuntimeError("Browser session has not been started")
        if self.context.pages:
            page = self.context.pages[0]
        else:
            page = await self.context.new_page()
        page.set_default_timeout(self.config.default_timeout_ms)
        return page
