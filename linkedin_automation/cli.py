from __future__ import annotations

import argparse
import getpass
import logging
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Callable, Iterator

from playwright.sync_api import Error as PlaywrightError

from . import __version__
from .api import MAX_FEED_POSTS, get_feed, get_me
from .browser import BrowserSession
from .capture import capture_voyager_traffic
from .config import AppConfig, load_config
from .credentials import CredentialStore
from .errors import AuthenticationRequiredError, CredentialStoreError, MechaError
from .output import format_feed_post, format_post_preview, format_profile, format_usage, print_json
from .pacing import RequestPacer
from .post_generator import LENGTHS, TONES, find_placeholders, generate_post, validate_post_text
from .ui import LinkedInUI
from .utils import configure_logging, confirm, normalize_text, read_text_file, write_text_file
from .voyager import VoyagerClient

Handler = Callable[[argparse.Namespace, AppConfig], int]


# --- Parser -----------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="linkedin-cli",
        description="A command-line client for LinkedIn, built on the persistent browser session.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    _add_global_options(parser, defaults=True)
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")
    common = argparse.ArgumentParser(add_help=False)
    _add_global_options(common, defaults=False)

    def add(subparsers, name: str, handler: Handler | None, help_text: str, **kwargs) -> argparse.ArgumentParser:
        sub = subparsers.add_parser(name, help=help_text, description=help_text, parents=[common], **kwargs)
        if handler:
            sub.set_defaults(handler=handler)
        return sub

    # auth
    auth = add(commands, "auth", None, "Log in, check or end the LinkedIn session.")
    auth_commands = auth.add_subparsers(dest="auth_command", required=True, metavar="ACTION")
    login = add(auth_commands, "login", _cmd_auth_login, "Log in through the browser.")
    login.add_argument("--email", help="LinkedIn email. Defaults to the last saved account, or is prompted.")
    login.add_argument("--manual", action="store_true", help="Type everything in the browser instead of the terminal.")
    login.add_argument("--save-password", action="store_true", help="Save the password in the system keyring.")
    add(auth_commands, "status", _cmd_auth_status, "Check whether the session is valid (one API request).")
    add(auth_commands, "logout", _cmd_auth_logout, "Delete the LinkedIn cookies from the browser profile.")
    forget = add(auth_commands, "forget-password", _cmd_auth_forget_password, "Delete a saved password.")
    forget.add_argument("--email", help="Account whose password to delete. Defaults to the last saved account.")

    # browsing and reading
    add(commands, "open", _cmd_open, "Open LinkedIn in the browser, e.g. to clear a security check.")
    add(commands, "me", _cmd_me, "Show your own profile.")
    feed = add(commands, "feed", _cmd_feed, "Show your home feed.")
    feed.add_argument("-n", "--limit", type=int, default=10, help=f"Number of posts (1-{MAX_FEED_POSTS}, default 10).")
    feed.add_argument("--full", action="store_true", help="Show complete post texts.")

    # posts
    post = add(commands, "post", None, "Draft, preview and publish posts.")
    post_commands = post.add_subparsers(dest="post_command", required=True, metavar="ACTION")
    draft = add(post_commands, "draft", _cmd_post_draft, "Build a post outline from an idea (offline).")
    draft.add_argument("idea", help="Idea or topic of the post.")
    draft.add_argument("--tone", default="professional", choices=sorted(TONES))
    draft.add_argument("--length", default="medium", choices=sorted(LENGTHS))
    draft.add_argument("-o", "--output", help="Save the draft to this file.")
    preview = add(post_commands, "preview", _cmd_post_preview, "Preview a post and check it (offline).")
    _add_text_source(preview)
    compose = add(post_commands, "compose", _cmd_post_compose, "Put a post in LinkedIn's editor, then publish on request.")
    _add_text_source(compose)

    # developer tools
    api = add(commands, "api", None, "Send raw requests to LinkedIn's internal API.")
    api_commands = api.add_subparsers(dest="api_command", required=True, metavar="METHOD")
    api_get = add(api_commands, "get", _cmd_api_get, "GET an internal API path and print the JSON.")
    api_get.add_argument("path", help="Path such as /me or /voyager/api/me.")
    api_get.add_argument("-p", "--param", action="append", default=[], metavar="KEY=VALUE", help="Query parameter.")
    capture = add(commands, "capture", _cmd_capture, "Record the API calls LinkedIn's web app makes while you browse.")
    capture.add_argument("--filter", help="Only record URLs containing this text.")
    limits = add(commands, "limits", _cmd_limits, "Show request budgets and cooldowns.")
    limits.add_argument("--clear-cooldown", action="store_true", help="Lift a cooldown after checking the account.")

    return parser


def _add_global_options(parser: argparse.ArgumentParser, defaults: bool) -> None:
    """Global options are accepted both before and after the subcommand."""

    def default(value):
        return value if defaults else argparse.SUPPRESS

    parser.add_argument("-v", "--verbose", action="store_true", default=default(False), help="Show debug logs.")
    parser.add_argument("--json", action="store_true", default=default(False), help="Print JSON output.")
    parser.add_argument(
        "--headed", action="store_true", default=default(False), help="Show the browser window for API commands."
    )


def _add_text_source(parser: argparse.ArgumentParser) -> None:
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--text", help="Post text.")
    source.add_argument("--text-file", help="File with the post text.")


# --- Entry point ------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(args.verbose)

    try:
        return args.handler(args, load_config())
    except MechaError as exc:
        logging.error("%s", exc)
        return 1
    except ValueError as exc:
        logging.error("%s", exc)
        return 2
    except OSError as exc:
        logging.error("%s", exc)
        return 1
    except PlaywrightError as exc:
        message = str(exc).strip().splitlines()[0].lstrip(": ")
        if "Executable doesn't exist" in message:
            message += " (run `python -m playwright install chromium`)"
        logging.error("Browser error: %s", message)
        return 1
    except (KeyboardInterrupt, EOFError):
        logging.warning("Interrupted")
        return 130


# --- Helpers ----------------------------------------------------------------


def _make_pacer(config: AppConfig) -> RequestPacer:
    return RequestPacer(
        state_file=config.request_log_file,
        min_delay_s=config.request_min_delay_s,
        max_delay_s=config.request_max_delay_s,
        hourly_budget=config.hourly_request_budget,
        daily_budget=config.daily_request_budget,
    )


@contextmanager
def _api_client(args: argparse.Namespace, config: AppConfig) -> Iterator[VoyagerClient]:
    headless = False if args.headed else None
    with BrowserSession(config, headless=headless, block_service_workers=True) as browser:
        client = VoyagerClient(browser, _make_pacer(config))
        client.connect()
        yield client


def _resolve_text(args: argparse.Namespace) -> str:
    if args.text_file:
        return read_text_file(Path(args.text_file))
    return normalize_text(args.text)


def _resolve_email(email: str | None, store: CredentialStore) -> str:
    if email:
        return email.strip()
    try:
        saved = store.get_default_email()
    except CredentialStoreError:
        saved = None
    return (saved or input("LinkedIn email: ")).strip()


def _saved_password(email: str, store: CredentialStore) -> str | None:
    try:
        return store.get_password(email)
    except CredentialStoreError:
        logging.debug("No usable system keyring; asking for the password")
        return None


# --- auth -------------------------------------------------------------------


def _cmd_auth_login(args: argparse.Namespace, config: AppConfig) -> int:
    if args.manual and args.save_password:
        raise ValueError("--save-password cannot be combined with --manual: no password is typed in the terminal.")
    store = CredentialStore()
    if args.save_password:
        store.ensure_available()

    with BrowserSession(config, headless=False) as browser:
        ui = LinkedInUI(browser)
        ui.goto_feed()
        if ui.is_logged_in():
            print("Already logged in; no new login needed.")
            if args.save_password:
                email = _resolve_email(args.email, store)
                store.set_password(email, getpass.getpass("LinkedIn password: "))
                print("Password saved in the system keyring (not verified, since no login happened).")
            return 0

        if args.manual:
            ui.wait_for_manual_login()
        else:
            email = _resolve_email(args.email, store)
            password = _saved_password(email, store)
            if password:
                logging.info("Using the password saved in the system keyring")
            else:
                password = getpass.getpass("LinkedIn password: ")
            if not email or not password:
                raise ValueError("Email and password are required. Use --manual to log in in the browser instead.")
            ui.login_with_credentials(email, password)
            if args.save_password:
                store.set_password(email, password)
                print("Password saved in the system keyring.")
    print("Logged in. The session is kept in the browser profile.")
    return 0


def _cmd_auth_status(args: argparse.Namespace, config: AppConfig) -> int:
    try:
        with _api_client(args, config) as client:
            profile = get_me(client)
    except AuthenticationRequiredError as exc:
        if args.json:
            print_json({"authenticated": False, "reason": str(exc)})
        else:
            print(exc)
        return 1
    if args.json:
        print_json({"authenticated": True, "profile": profile.to_dict()})
    else:
        print(f"Logged in as {profile.name}" + (f" ({profile.url})" if profile.url else ""))
    return 0


def _cmd_auth_logout(args: argparse.Namespace, config: AppConfig) -> int:
    if not confirm("Type 'logout' to delete the LinkedIn session from this computer: ", "logout"):
        print("Cancelled.")
        return 0
    with BrowserSession(config) as browser:
        browser.context.clear_cookies()
    print("LinkedIn cookies deleted. Saved passwords were kept; use `auth forget-password` to remove them.")
    return 0


def _cmd_auth_forget_password(args: argparse.Namespace, config: AppConfig) -> int:
    store = CredentialStore()
    email = _resolve_email(args.email, store)
    store.delete_password(email)
    print(f"Saved password for {email} removed.")
    return 0


# --- browsing and reading ---------------------------------------------------


def _cmd_open(args: argparse.Namespace, config: AppConfig) -> int:
    with BrowserSession(config, headless=False) as browser:
        LinkedInUI(browser).goto_feed()
        input("LinkedIn is open. Press Enter here to close the browser...")
    return 0


def _cmd_me(args: argparse.Namespace, config: AppConfig) -> int:
    with _api_client(args, config) as client:
        profile = get_me(client)
    if args.json:
        print_json(profile.to_dict())
    else:
        print(format_profile(profile))
    return 0


def _cmd_feed(args: argparse.Namespace, config: AppConfig) -> int:
    if not 1 <= args.limit <= MAX_FEED_POSTS:
        raise ValueError(f"--limit must be between 1 and {MAX_FEED_POSTS}")
    with _api_client(args, config) as client:
        posts = get_feed(client, args.limit)
    if args.json:
        print_json([post.to_dict() for post in posts])
    elif not posts:
        print("No posts found. If your feed is not empty, LinkedIn may have changed its API; see `linkedin-cli capture`.")
    else:
        print("\n\n".join(format_feed_post(post, full=args.full) for post in posts))
    return 0


# --- posts ------------------------------------------------------------------


def _cmd_post_draft(args: argparse.Namespace, config: AppConfig) -> int:
    draft = generate_post(args.idea, tone=args.tone, length=args.length)
    if args.json:
        print_json({"text": draft.text, "tone": draft.tone, "length": draft.length})
    else:
        print(format_post_preview(draft.text))
        print("Replace the [placeholders] before posting.")
    if args.output:
        write_text_file(args.output, draft.text)
        logging.info("Draft saved to %s", args.output)
    return 0


def _cmd_post_preview(args: argparse.Namespace, config: AppConfig) -> int:
    text = _resolve_text(args)
    print(format_post_preview(text))
    for placeholder in find_placeholders(text):
        print(f"Unfilled placeholder: {placeholder}")
    validate_post_text(text, config.max_post_chars)
    print("Ready to post.")
    return 0


def _cmd_post_compose(args: argparse.Namespace, config: AppConfig) -> int:
    text = _resolve_text(args)
    validate_post_text(text, config.max_post_chars)
    print(format_post_preview(text))

    with BrowserSession(config, headless=False) as browser:
        ui = LinkedInUI(browser)
        ui.prepare_post(text)
        print("\nThe post is in LinkedIn's editor. Review it in the browser; you can still edit it there.")
        if confirm("Type 'publish' to publish it now, or press Enter to finish by hand: ", "publish"):
            ui.publish_prepared_post()
            print("Published.")
        else:
            input("Press Enter here to close the browser when you are done...")
    return 0


# --- developer tools --------------------------------------------------------


def _cmd_api_get(args: argparse.Namespace, config: AppConfig) -> int:
    params = {}
    for item in args.param:
        key, separator, value = item.partition("=")
        if not separator or not key:
            raise ValueError(f"Query parameters must look like KEY=VALUE, got {item!r}")
        params[key] = value
    with _api_client(args, config) as client:
        print_json(client.get(args.path, params or None))
    return 0


def _cmd_capture(args: argparse.Namespace, config: AppConfig) -> int:
    with BrowserSession(config, headless=False) as browser:
        output, count = capture_voyager_traffic(browser, config.captures_dir, args.filter)
    print(f"Captured {count} API calls in {output}")
    print("The file can contain private data such as messages; don't share it as-is.")
    return 0


def _cmd_limits(args: argparse.Namespace, config: AppConfig) -> int:
    pacer = _make_pacer(config)
    if args.clear_cooldown:
        pacer.clear_cooldown()
        print("Cooldown cleared.")
    usage = pacer.usage()
    if args.json:
        print_json(asdict(usage))
    else:
        print(format_usage(usage))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
