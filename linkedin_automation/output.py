from __future__ import annotations

import json
import shutil
import textwrap
from datetime import datetime
from typing import Any

from .models import FeedPost, Profile
from .pacing import PacerUsage

MAX_WIDTH = 100
PREVIEW_LINES = 6


def print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def _width() -> int:
    return min(shutil.get_terminal_size((MAX_WIDTH, 24)).columns, MAX_WIDTH)


def _wrap(text: str, indent: str = "") -> list[str]:
    width = _width() - len(indent)
    lines: list[str] = []
    for paragraph in text.split("\n"):
        wrapped = textwrap.wrap(paragraph, width=width) or [""]
        lines.extend(f"{indent}{line}" for line in wrapped)
    return lines


def format_profile(profile: Profile) -> str:
    lines = [profile.name]
    if profile.headline:
        lines.extend(_wrap(profile.headline))
    if profile.url:
        lines.append(profile.url)
    return "\n".join(lines)


def format_feed_post(post: FeedPost, full: bool = False) -> str:
    title = post.author or "(unknown author)"
    if post.age:
        title += f" · {post.age}"
    if post.promoted:
        title += " · promoted"
    lines = [title]
    if post.author_headline:
        lines.append(textwrap.shorten(post.author_headline, width=_width(), placeholder="…"))
    if post.context:
        lines.append(f"({post.context})")
    if post.reshared_author:
        lines.append(f"Reposting {post.reshared_author}")

    if post.text:
        body = _wrap(post.text, indent="  ")
        if not full and len(body) > PREVIEW_LINES:
            body = body[:PREVIEW_LINES] + ["  … (use --full to see everything)"]
        lines.append("")
        lines.extend(body)

    stats = [
        f"{value} {label}"
        for value, label in ((post.reactions, "reactions"), (post.comments, "comments"), (post.reposts, "reposts"))
        if value is not None
    ]
    footer = " · ".join(stats)
    if post.url:
        footer = f"{footer}   {post.url}" if footer else post.url
    if footer:
        lines.extend(["", footer])
    return "\n".join(lines)


def format_post_preview(text: str) -> str:
    separator = "-" * min(_width(), 60)
    return f"{separator}\n{text}\n{separator}\n{len(text)} characters"


def format_usage(usage: PacerUsage) -> str:
    lines = [
        f"Requests in the last hour: {usage.last_hour}/{usage.hourly_budget}",
        f"Requests in the last 24h:  {usage.last_day}/{usage.daily_budget}",
    ]
    if usage.cooldown_until:
        until = datetime.fromtimestamp(usage.cooldown_until).strftime("%Y-%m-%d %H:%M")
        lines.append(f"Cooldown active until {until}: {usage.cooldown_reason}")
    else:
        lines.append("No cooldown active")
    return "\n".join(lines)
