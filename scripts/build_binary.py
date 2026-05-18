from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "scripts" / "linkedin_cli_entry.py"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the linkedin-cli executable with PyInstaller.")
    parser.add_argument("--name", default="linkedin-cli", help="Executable name.")
    parser.add_argument("--onedir", action="store_true", help="Build a folder instead of a single-file executable.")
    parser.add_argument("--clean", action="store_true", help="Remove previous build artifacts before building.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        import PyInstaller.__main__
    except ImportError:
        print("PyInstaller is not installed. Run: pip install -e .[build]", file=sys.stderr)
        return 1

    if args.clean:
        shutil.rmtree(ROOT / "build", ignore_errors=True)
        shutil.rmtree(ROOT / "dist", ignore_errors=True)

    mode = "--onedir" if args.onedir else "--onefile"
    pyinstaller_args = [
        str(ENTRYPOINT),
        "--name",
        args.name,
        mode,
        "--console",
        "--noconfirm",
        "--clean",
        "--paths",
        str(ROOT),
        "--distpath",
        str(ROOT / "dist"),
        "--workpath",
        str(ROOT / "build"),
        "--specpath",
        str(ROOT / "build"),
        "--copy-metadata",
        "keyring",
        "--copy-metadata",
        "playwright",
        "--collect-submodules",
        "keyring.backends",
        "--collect-submodules",
        "playwright",
    ]

    PyInstaller.__main__.run(pyinstaller_args)

    output = ROOT / "dist" / args.name
    if sys.platform == "win32" and not args.onedir:
        output = output.with_suffix(".exe")
    print(f"Built executable at: {output}")
    print("Playwright Chromium must be installed on the target machine before browser commands are used.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
