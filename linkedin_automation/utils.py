from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path


def configure_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%H:%M:%S",
    )


def read_text_file(path: str | Path) -> str:
    text = Path(path).read_text(encoding="utf-8")
    return normalize_text(text)


def write_text_file(path: str | Path, text: str) -> None:
    Path(path).write_text(normalize_text(text) + "\n", encoding="utf-8")


def normalize_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+$", "", line) for line in text.split("\n")]
    return "\n".join(lines).strip()


def require_interactive_confirmation(prompt: str, expected: str) -> bool:
    value = input(prompt).strip()
    return value == expected


async def save_diagnostic_screenshot(page, debug_dir: Path, label: str) -> Path | None:
    debug_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_label = re.sub(r"[^a-zA-Z0-9_-]+", "-", label).strip("-") or "failure"
    path = debug_dir / f"{timestamp}-{safe_label}.png"
    try:
        await page.screenshot(path=str(path), full_page=True)
    except Exception:
        logging.exception("Could not save diagnostic screenshot")
        return None
    logging.error("Diagnostic screenshot saved to %s", path)
    return path
