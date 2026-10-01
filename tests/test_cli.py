import json

import pytest

from linkedin_automation import cli
from linkedin_automation.cli import build_parser, main


@pytest.fixture(autouse=True)
def isolated_state(monkeypatch, tmp_path):
    monkeypatch.setenv("LINKEDIN_STATE_DIR", str(tmp_path / "state"))


def test_auth_subcommands_parse():
    parser = build_parser()

    login = parser.parse_args(["auth", "login", "--email", "me@example.com", "--save-password"])
    assert (login.command, login.auth_command) == ("auth", "login")
    assert login.email == "me@example.com" and login.save_password is True and login.manual is False
    assert login.handler is cli._cmd_auth_login

    assert parser.parse_args(["auth", "status"]).handler is cli._cmd_auth_status
    assert parser.parse_args(["auth", "forget-password"]).email is None


def test_global_options_work_before_and_after_the_command():
    parser = build_parser()

    before = parser.parse_args(["--json", "--verbose", "feed", "-n", "5"])
    after = parser.parse_args(["feed", "--json", "--headed"])
    neither = parser.parse_args(["feed"])

    assert before.json and before.verbose and before.limit == 5
    assert after.json and after.headed and not after.verbose
    assert not neither.json and not neither.headed and neither.limit == 10


def test_api_get_params_are_collected():
    args = build_parser().parse_args(["api", "get", "/me", "-p", "a=1", "-p", "b=(x:y)"])
    assert args.path == "/me" and args.param == ["a=1", "b=(x:y)"]


def test_post_draft_prints_and_saves(tmp_path, capsys):
    output = tmp_path / "post.txt"

    assert main(["post", "draft", "Shipping a CLI for LinkedIn", "--tone", "technical", "-o", str(output)]) == 0

    assert "A technical lesson worth sharing" in capsys.readouterr().out
    assert output.read_text(encoding="utf-8").startswith("A technical lesson worth sharing")


def test_post_draft_json(capsys):
    assert main(["post", "draft", "Shipping a CLI for LinkedIn", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["tone"] == "professional"


def test_post_preview_flags_placeholders(tmp_path, capsys):
    path = tmp_path / "post.txt"
    path.write_text("Hello\n\n[Fill this part in]\n", encoding="utf-8")

    assert main(["post", "preview", "--text-file", str(path)]) == 1
    assert "Unfilled placeholder: [Fill this part in]" in capsys.readouterr().out

    assert main(["post", "preview", "--text", "All done. Thoughts?"]) == 0


def test_missing_text_file_is_a_clean_error(tmp_path):
    assert main(["post", "preview", "--text-file", str(tmp_path / "missing.txt")]) == 1


def test_feed_limit_is_validated_before_opening_the_browser():
    assert main(["feed", "-n", "500"]) == 2


def test_limits_shows_usage_and_clears_cooldown(capsys):
    assert main(["limits", "--json"]) == 0
    usage = json.loads(capsys.readouterr().out)
    assert usage["last_day"] == 0 and usage["cooldown_until"] is None

    assert main(["limits", "--clear-cooldown"]) == 0
    assert "Cooldown cleared" in capsys.readouterr().out
