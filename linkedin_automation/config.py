from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .runtime import default_state_dir


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _as_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value.strip() == "":
        return default
    try:
        return int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw_value!r}") from exc


@dataclass(frozen=True)
class AppConfig:
    linkedin_url: str
    browser_profile_dir: Path
    debug_dir: Path
    headless: bool
    default_timeout_ms: int
    max_post_chars: int
    allow_auto_publish: bool

    @classmethod
    def from_env(cls, env_file: str | Path | None = None) -> "AppConfig":
        del env_file
        state_dir = default_state_dir()

        return cls(
            linkedin_url=os.getenv("LINKEDIN_URL", "https://www.linkedin.com/feed/"),
            browser_profile_dir=Path(os.getenv("BROWSER_PROFILE_DIR", state_dir / "browser-profile")),
            debug_dir=Path(os.getenv("DEBUG_DIR", state_dir / "debug")),
            headless=_as_bool(os.getenv("HEADLESS"), default=False),
            default_timeout_ms=_as_int("DEFAULT_TIMEOUT_MS", 30000),
            max_post_chars=_as_int("MAX_POST_CHARS", 3000),
            allow_auto_publish=_as_bool(os.getenv("ALLOW_AUTO_PUBLISH"), default=False),
        )

    def validate(self) -> None:
        if not self.linkedin_url.startswith(("https://www.linkedin.com", "https://linkedin.com")):
            raise ValueError("LINKEDIN_URL must point to linkedin.com")
        if self.default_timeout_ms < 5000:
            raise ValueError("DEFAULT_TIMEOUT_MS must be at least 5000")
        if self.max_post_chars < 280:
            raise ValueError("MAX_POST_CHARS must be at least 280")

    def ensure_directories(self) -> None:
        self.browser_profile_dir.mkdir(parents=True, exist_ok=True)
        self.debug_dir.mkdir(parents=True, exist_ok=True)


def load_config() -> AppConfig:
    config = AppConfig.from_env()
    config.validate()
    config.ensure_directories()
    return config
