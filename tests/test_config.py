import sys

import pytest

from linkedin_automation.config import AppConfig

CONFIG_VARS = (
    "LINKEDIN_STATE_DIR",
    "BROWSER_PROFILE_DIR",
    "DEBUG_DIR",
    "HEADLESS",
    "DEFAULT_TIMEOUT_MS",
    "MAX_POST_CHARS",
    "REQUEST_MIN_DELAY",
    "REQUEST_MAX_DELAY",
    "HOURLY_REQUEST_BUDGET",
    "DAILY_REQUEST_BUDGET",
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for name in CONFIG_VARS:
        monkeypatch.delenv(name, raising=False)


def test_config_from_env_reads_values(monkeypatch, tmp_path):
    monkeypatch.setenv("LINKEDIN_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.setenv("BROWSER_PROFILE_DIR", str(tmp_path / "profile"))
    monkeypatch.setenv("HEADLESS", "false")
    monkeypatch.setenv("DEFAULT_TIMEOUT_MS", "12000")
    monkeypatch.setenv("REQUEST_MIN_DELAY", "3")
    monkeypatch.setenv("REQUEST_MAX_DELAY", "9.5")
    monkeypatch.setenv("HOURLY_REQUEST_BUDGET", "20")
    monkeypatch.setenv("DAILY_REQUEST_BUDGET", "100")

    config = AppConfig.from_env()

    assert config.browser_profile_dir == tmp_path / "profile"
    assert config.debug_dir == tmp_path / "state" / "debug"
    assert config.request_log_file == tmp_path / "state" / "request-log.json"
    assert config.headless is False
    assert config.default_timeout_ms == 12000
    assert (config.request_min_delay_s, config.request_max_delay_s) == (3.0, 9.5)
    assert (config.hourly_request_budget, config.daily_request_budget) == (20, 100)
    config.validate()


def test_defaults_are_headless_and_conservative():
    config = AppConfig.from_env()
    assert config.headless is True
    assert config.request_min_delay_s >= 2
    assert config.hourly_request_budget <= 60
    config.validate()


@pytest.mark.parametrize(
    "name, value",
    [
        ("DEFAULT_TIMEOUT_MS", "soon"),
        ("REQUEST_MIN_DELAY", "fast"),
    ],
)
def test_config_rejects_invalid_numbers(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(ValueError):
        AppConfig.from_env()


@pytest.mark.parametrize(
    "overrides",
    [
        {"REQUEST_MIN_DELAY": "0.2"},
        {"REQUEST_MIN_DELAY": "5", "REQUEST_MAX_DELAY": "3"},
        {"HOURLY_REQUEST_BUDGET": "500", "DAILY_REQUEST_BUDGET": "100"},
        {"DAILY_REQUEST_BUDGET": "0"},
        {"MAX_POST_CHARS": "10"},
    ],
)
def test_config_rejects_unsafe_values(monkeypatch, overrides):
    for name, value in overrides.items():
        monkeypatch.setenv(name, value)
    with pytest.raises(ValueError):
        AppConfig.from_env().validate()


def test_default_state_dir_follows_platform_conventions(monkeypatch, tmp_path):
    if sys.platform == "win32":
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
        expected_state_dir = tmp_path / "LinkedinMechaWarrior"
    else:
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
        expected_state_dir = tmp_path / "linkedin-mecha-warrior"

    config = AppConfig.from_env()

    assert config.browser_profile_dir == expected_state_dir / "browser-profile"
    assert config.debug_dir == expected_state_dir / "debug"
