import pytest

from linkedin_automation.config import AppConfig


def test_config_from_env_reads_values(monkeypatch, tmp_path):
    monkeypatch.setenv("LINKEDIN_URL", "https://www.linkedin.com/feed/")
    monkeypatch.setenv("BROWSER_PROFILE_DIR", str(tmp_path / "profile"))
    monkeypatch.setenv("DEBUG_DIR", str(tmp_path / "debug"))
    monkeypatch.setenv("HEADLESS", "true")
    monkeypatch.setenv("DEFAULT_TIMEOUT_MS", "12000")
    monkeypatch.setenv("MAX_POST_CHARS", "3000")
    monkeypatch.setenv("ALLOW_AUTO_PUBLISH", "true")

    config = AppConfig.from_env(env_file=None)

    assert config.headless is True
    assert config.allow_auto_publish is True
    assert config.default_timeout_ms == 12000
    assert config.max_post_chars == 3000
    config.validate()


def test_config_rejects_non_linkedin_url(monkeypatch):
    monkeypatch.setenv("LINKEDIN_URL", "https://example.com")

    config = AppConfig.from_env(env_file=None)

    with pytest.raises(ValueError):
        config.validate()


def test_config_rejects_invalid_integer(monkeypatch):
    monkeypatch.setenv("DEFAULT_TIMEOUT_MS", "soon")

    with pytest.raises(ValueError):
        AppConfig.from_env(env_file=None)
