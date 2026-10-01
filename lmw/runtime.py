from __future__ import annotations

import os
import sys
from pathlib import Path


APP_NAME = "linkedin-mecha-warrior"


def configure_runtime() -> None:
    """Configure paths that make the compiled CLI self-contained."""
    if is_frozen():
        os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "0")


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def default_state_dir() -> Path:
    if sys.platform == "win32":
        base = Path(os.getenv("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        return base / "LinkedinMechaWarrior"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "LinkedinMechaWarrior"

    base = Path(os.getenv("XDG_STATE_HOME") or Path.home() / ".local" / "state")
    return base / APP_NAME
