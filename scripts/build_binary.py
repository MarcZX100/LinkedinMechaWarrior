from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "scripts" / "linkedin_cli_entry.py"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the linkedin-cli executable with PyInstaller.")
    parser.add_argument("--name", default="linkedin-cli", help="Executable name.")
    parser.add_argument("--onedir", action="store_true", help="Build a folder instead of a single-file executable.")
    parser.add_argument("--clean", action="store_true", help="Remove previous build artifacts before building.")
    parser.add_argument(
        "--skip-browser-install",
        action="store_true",
        help="Do not install bundled Playwright Chromium before building.",
    )
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

    build_env = os.environ.copy()
    build_env["PLAYWRIGHT_BROWSERS_PATH"] = "0"

    if not args.skip_browser_install:
        subprocess.run(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            cwd=ROOT,
            env=build_env,
            check=True,
        )

    mode = "--onedir" if args.onedir else "--onefile"
    os.environ.update(build_env)
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
    print("Playwright Chromium was bundled during build unless --skip-browser-install was used.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
