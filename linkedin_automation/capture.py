"""Record the Voyager API calls that LinkedIn's own web app makes.

This is the tool for discovering and updating endpoints: browse to a page
(messages, notifications...) while capturing, then read the JSONL file to see
which endpoint, query parameters and response shape the web app uses.

Request headers are never written, because they contain session cookies and
the CSRF token. Response bodies are written as-is and can contain private
data (messages, profiles), so captures stay in the local state directory.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError, Response

from .browser import BrowserSession
from .ui import FEED_URL
from .utils import wait_for_enter

MAX_TEXT_BODY = 2000


def capture_voyager_traffic(session: BrowserSession, captures_dir: Path, url_filter: str | None = None) -> tuple[Path, int]:
    captures_dir.mkdir(parents=True, exist_ok=True)
    output = captures_dir / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}.jsonl"
    count = 0

    with output.open("a", encoding="utf-8") as handle:

        def on_response(response: Response) -> None:
            nonlocal count
            if "/voyager/api/" not in response.url or (url_filter and url_filter not in response.url):
                return
            handle.write(json.dumps(_entry(response), ensure_ascii=False) + "\n")
            handle.flush()
            count += 1
            logging.info("Captured %s %s", response.request.method, response.url.split("?")[0])

        session.context.on("response", on_response)
        page = session.page
        page.goto(FEED_URL, wait_until="domcontentloaded")
        print(f"\nCapturing LinkedIn API calls to {output}")
        print("Browse to the pages you want to inspect (messages, notifications, a profile...).")
        wait_for_enter(page, "Press Enter here to stop capturing...\n")
        session.context.remove_listener("response", on_response)

    return output, count


def _entry(response: Response) -> dict:
    request = response.request
    entry: dict = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "method": request.method,
        "url": response.url,
        "status": response.status,
        "request_body": request.post_data,
    }
    try:
        body = response.text()
    except PlaywrightError:
        body = None
    if body:
        try:
            entry["response"] = json.loads(body)
        except ValueError:
            entry["response_text"] = body[:MAX_TEXT_BODY]
    return entry
