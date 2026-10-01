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


def _as_float(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value.strip() == "":
        return default
    try:
        return float(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number, got {raw_value!r}") from exc


@dataclass(frozen=True)
class AppConfig:
    state_dir: Path
    browser_profile_dir: Path
    debug_dir: Path
    headless: bool
    default_timeout_ms: int
    max_post_chars: int
    request_min_delay_s: float
    request_max_delay_s: float
    hourly_request_budget: int
    daily_request_budget: int

    @classmethod
    def from_env(cls) -> "AppConfig":
        state_dir = Path(os.getenv("LINKEDIN_STATE_DIR") or default_state_dir())

        return cls(
            state_dir=state_dir,
            browser_profile_dir=Path(os.getenv("BROWSER_PROFILE_DIR") or state_dir / "browser-profile"),
            debug_dir=Path(os.getenv("DEBUG_DIR") or state_dir / "debug"),
            headless=_as_bool(os.getenv("HEADLESS"), default=True),
            default_timeout_ms=_as_int("DEFAULT_TIMEOUT_MS", 30000),
            max_post_chars=_as_int("MAX_POST_CHARS", 3000),
            request_min_delay_s=_as_float("REQUEST_MIN_DELAY", 2.0),
            request_max_delay_s=_as_float("REQUEST_MAX_DELAY", 6.0),
            hourly_request_budget=_as_int("HOURLY_REQUEST_BUDGET", 60),
            daily_request_budget=_as_int("DAILY_REQUEST_BUDGET", 300),
        )

    @property
    def request_log_file(self) -> Path:
        return self.state_dir / "request-log.json"

    @property
    def captures_dir(self) -> Path:
        return self.state_dir / "captures"

    def validate(self) -> None:
        if self.default_timeout_ms < 5000:
            raise ValueError("DEFAULT_TIMEOUT_MS must be at least 5000")
        if self.max_post_chars < 280:
            raise ValueError("MAX_POST_CHARS must be at least 280")
        if self.request_min_delay_s < 1:
            raise ValueError("REQUEST_MIN_DELAY must be at least 1 second")
        if self.request_max_delay_s < self.request_min_delay_s:
            raise ValueError("REQUEST_MAX_DELAY must be greater than or equal to REQUEST_MIN_DELAY")
        if self.hourly_request_budget < 1 or self.daily_request_budget < 1:
            raise ValueError("Request budgets must be positive")
        if self.hourly_request_budget > self.daily_request_budget:
            raise ValueError("HOURLY_REQUEST_BUDGET cannot exceed DAILY_REQUEST_BUDGET")

    def ensure_directories(self) -> None:
        for directory in (self.state_dir, self.browser_profile_dir, self.debug_dir):
            directory.mkdir(parents=True, exist_ok=True)


def load_config() -> AppConfig:
    config = AppConfig.from_env()
    config.validate()
    config.ensure_directories()
    return config
