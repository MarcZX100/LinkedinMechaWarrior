from linkedin_automation.cli import build_parser


def test_auth_and_login_commands_are_available():
    parser = build_parser()

    auth_args = parser.parse_args(["auth", "--email", "me@example.com", "--keep-open"])
    login_args = parser.parse_args(["login", "--manual"])

    assert auth_args.command == "auth"
    assert auth_args.email == "me@example.com"
    assert auth_args.keep_open is True
    assert login_args.command == "login"
    assert login_args.manual is True


def test_status_command_is_available():
    parser = build_parser()

    args = parser.parse_args(["status"])

    assert args.command == "status"
    assert args.keep_open is False
