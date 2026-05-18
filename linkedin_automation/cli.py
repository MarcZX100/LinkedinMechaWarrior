from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from .browser import BrowserSession
from .config import load_config
from .linkedin import LinkedInClient, LinkedInAutomationError
from .post_generator import LENGTHS, TONES, PostGenerationError, generate_post
from .utils import configure_logging, normalize_text, read_text_file, require_interactive_confirmation, write_text_file


def build_parser() -> argparse.ArgumentParser:
    tone_choices = sorted(TONES | {"técnico", "startup", "fundador/startup"})
    parser = argparse.ArgumentParser(
        prog="linkedin-automation",
        description="Local assistant for drafting LinkedIn posts with manual review.",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logs.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    draft = subparsers.add_parser("draft", help="Generate a LinkedIn post from an idea or draft.")
    draft.add_argument("--idea", required=True, help="Idea, topic, or rough draft.")
    draft.add_argument("--tone", default="profesional", choices=tone_choices, help="Writing tone.")
    draft.add_argument("--length", default="media", choices=sorted(LENGTHS), help="Post length.")
    draft.add_argument("--output", help="Optional file where the generated post will be saved.")

    open_cmd = subparsers.add_parser("open", help="Open LinkedIn with the persistent browser profile.")
    open_cmd.add_argument("--keep-open", action="store_true", help="Wait for Enter before closing the browser.")

    prepare = subparsers.add_parser("prepare-post", help="Open LinkedIn and place text in the post editor.")
    prepare_text = prepare.add_mutually_exclusive_group(required=True)
    prepare_text.add_argument("--text", help="Final post text.")
    prepare_text.add_argument("--text-file", help="Path to a text file with the final post.")
    prepare.add_argument("--publish", action="store_true", help="Try to publish after placing the text. Heavily guarded.")

    preview = subparsers.add_parser("preview", help="Show final post text in the console.")
    preview_text = preview.add_mutually_exclusive_group(required=True)
    preview_text.add_argument("--text", help="Final post text.")
    preview_text.add_argument("--text-file", help="Path to a text file with the final post.")

    publish = subparsers.add_parser("publish", help="Publish the currently prepared post if all safeguards pass.")
    publish.add_argument("--publish", action="store_true", help="Required explicit publish flag.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    configure_logging(args.verbose)

    try:
        if args.command == "draft":
            return _cmd_draft(args)
        if args.command == "preview":
            return _cmd_preview(args)
        config = load_config()
        if args.command == "open":
            return asyncio.run(_cmd_open(args, config))
        if args.command == "prepare-post":
            return asyncio.run(_cmd_prepare_post(args, config))
        if args.command == "publish":
            return asyncio.run(_cmd_publish(args, config))
    except (ValueError, PostGenerationError, LinkedInAutomationError) as exc:
        logging.error("%s", exc)
        return 1
    except KeyboardInterrupt:
        logging.warning("Interrupted by user")
        return 130

    parser.error("Unknown command")
    return 2


def _cmd_draft(args: argparse.Namespace) -> int:
    draft = generate_post(args.idea, tone=args.tone, length=args.length)
    _print_post(draft.text)
    if args.output:
        write_text_file(args.output, draft.text)
        logging.info("Draft saved to %s", args.output)
    return 0


def _cmd_preview(args: argparse.Namespace) -> int:
    text = _resolve_text(args)
    _print_post(text)
    return 0


async def _cmd_open(args: argparse.Namespace, config) -> int:
    async with BrowserSession(config) as browser:
        page = await browser.new_page()
        client = LinkedInClient(page, config)
        await client.open_home()
        await client.ensure_authenticated()
        logging.info("LinkedIn is open with the persistent profile")
        if args.keep_open:
            input("Press Enter to close the browser...")
    return 0


async def _cmd_prepare_post(args: argparse.Namespace, config) -> int:
    text = _resolve_text(args)
    _print_post(text)
    if not require_interactive_confirmation("Prepare this text in LinkedIn? Type SI to continue: ", "SI"):
        logging.info("Cancelled before opening LinkedIn")
        return 0

    async with BrowserSession(config) as browser:
        page = await browser.new_page()
        client = LinkedInClient(page, config)
        await client.prepare_post(text)
        print("\nThe post is ready in LinkedIn for manual review.")
        if args.publish:
            if not _publish_safeguards_pass(config):
                logging.warning("Auto-publish blocked by safeguards")
                return 1
            await client.publish_prepared_post()
    return 0


async def _cmd_publish(args: argparse.Namespace, config) -> int:
    if not args.publish:
        logging.error("The publish command requires the explicit --publish flag.")
        return 1
    if not _publish_safeguards_pass(config):
        logging.warning("Auto-publish blocked by safeguards")
        return 1

    async with BrowserSession(config) as browser:
        page = await browser.new_page()
        client = LinkedInClient(page, config)
        if page.url == "about:blank":
            await client.open_home()
        await client.ensure_authenticated()
        print("Open the prepared LinkedIn composer in the browser if it is not already visible.")
        input("Press Enter when the prepared composer is visible...")
        await client.publish_prepared_post()
    return 0


def _publish_safeguards_pass(config) -> bool:
    if not config.allow_auto_publish:
        logging.error("ALLOW_AUTO_PUBLISH is not true.")
        return False
    return require_interactive_confirmation(
        "Auto-publish is enabled. Type PUBLICAR to click LinkedIn's publish button: ",
        "PUBLICAR",
    )


def _resolve_text(args: argparse.Namespace) -> str:
    if getattr(args, "text_file", None):
        return read_text_file(Path(args.text_file))
    return normalize_text(args.text)


def _print_post(text: str) -> None:
    print("\n--- LinkedIn post preview ---\n")
    print(normalize_text(text))
    print("\n--- End preview ---\n")


if __name__ == "__main__":
    raise SystemExit(main())
