from __future__ import annotations

import logging
import re
import threading
from datetime import datetime
from pathlib import Path


def configure_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
    )


def read_text_file(path: str | Path) -> str:
    return normalize_text(Path(path).read_text(encoding="utf-8"))


def write_text_file(path: str | Path, text: str) -> None:
    Path(path).write_text(normalize_text(text) + "\n", encoding="utf-8")


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+$", "", line) for line in text.split("\n")]
    return "\n".join(lines).strip()


def confirm(prompt: str, expected: str) -> bool:
    return input(prompt).strip() == expected


def wait_for_enter(page, prompt: str) -> None:
    """Wait for Enter while letting Playwright keep dispatching browser events.

    A plain `input()` blocks the sync Playwright loop, so event handlers (such
    as response listeners) would not run until it returns.
    """
    pressed = threading.Event()

    def read_line() -> None:
        try:
            input(prompt)
        except EOFError:
            pass
        pressed.set()

    threading.Thread(target=read_line, daemon=True).start()
    while not pressed.is_set():
        page.wait_for_timeout(250)


def save_diagnostic_screenshot(page, debug_dir: Path, label: str) -> Path | None:
    """Save a screenshot of the visible viewport only, to limit how much private data ends up on disk."""
    debug_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_label = re.sub(r"[^a-zA-Z0-9_-]+", "-", label).strip("-") or "failure"
    path = debug_dir / f"{timestamp}-{safe_label}.png"
    try:
        page.screenshot(path=str(path))
    except Exception:
        logging.exception("Could not save diagnostic screenshot")
        return None
    logging.error("Diagnostic screenshot saved to %s", path)
    return path
