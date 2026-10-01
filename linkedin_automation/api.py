"""High-level LinkedIn operations on top of the Voyager client.

Endpoints and response shapes are undocumented. Parsers here never assume a
field exists; when LinkedIn changes something, use `linkedin-cli api get` or
`linkedin-cli capture` to inspect the current responses.
"""

from __future__ import annotations

import re
from typing import Any

from .errors import VoyagerError
from .models import FeedPost, Profile
from .normalized import Normalized, dig, text_of
from .voyager import VoyagerClient

FEED_PAGE_SIZE = 10
MAX_FEED_POSTS = 50

_ACTIVITY_URN = re.compile(r"urn:li:activity:\d+")


def get_me(client: VoyagerClient) -> Profile:
    return parse_me(client.get("/me"))


def get_feed(client: VoyagerClient, limit: int) -> list[FeedPost]:
    if not 1 <= limit <= MAX_FEED_POSTS:
        raise ValueError(f"--limit must be between 1 and {MAX_FEED_POSTS}")

    posts: list[FeedPost] = []
    start = 0
    # Hard cap on pages, in case pages keep coming back with elements we can't parse.
    max_pages = -(-limit // FEED_PAGE_SIZE) + 1
    for _ in range(max_pages):
        payload = client.get("/feed/updatesV2", {"count": FEED_PAGE_SIZE, "q": "chronFeed", "start": start})
        page_posts, element_count = parse_feed(payload)
        posts.extend(page_posts)
        if element_count == 0 or len(posts) >= limit:
            break
        start += element_count
    return posts[:limit]


def parse_me(payload: Any) -> Profile:
    normalized = Normalized(payload)
    mini = normalized.ref(normalized.data, "miniProfile")
    if mini is None:
        candidates = normalized.of_type("MiniProfile")
        mini = candidates[0] if candidates else None
    if mini is None:
        raise VoyagerError("Unexpected response from /me: no profile found. Inspect it with `linkedin-cli api get /me`.")
    return Profile(
        urn=mini.get("dashEntityUrn") or mini.get("entityUrn"),
        public_id=mini.get("publicIdentifier"),
        first_name=mini.get("firstName"),
        last_name=mini.get("lastName"),
        headline=mini.get("occupation"),
    )


def parse_feed(payload: Any) -> tuple[list[FeedPost], int]:
    """Return the posts on one feed page and how many elements the page had."""
    normalized = Normalized(payload)
    element_urns = normalized.data.get("*elements")
    if isinstance(element_urns, list):
        updates = [normalized.get(urn) for urn in element_urns]
        element_count = len(element_urns)
    else:
        updates = normalized.of_type("UpdateV2")
        element_count = len(updates)

    posts = [post for post in (_parse_update(normalized, update) for update in updates if update) if post]
    return posts, element_count


def _parse_update(normalized: Normalized, update: dict) -> FeedPost | None:
    actor = update.get("actor") if isinstance(update.get("actor"), dict) else {}
    author = text_of(actor.get("name"))
    text = text_of(update.get("commentary"))

    reshared = normalized.ref(update, "resharedUpdate")
    reshared_author = None
    if reshared:
        reshared_author = text_of(dig(reshared, "actor", "name"))
        if not text:
            text = text_of(reshared.get("commentary"))

    if not author and not text:
        return None

    social_detail = normalized.ref(update, "socialDetail")
    counts = normalized.ref(social_detail, "totalSocialActivityCounts") or {}

    age = text_of(actor.get("subDescription"))
    headline = text_of(actor.get("description"))
    promoted = any("promoted" in (value or "").lower() for value in (age, headline))

    return FeedPost(
        urn=_activity_urn(update),
        author=author,
        author_headline=headline,
        age=_clean_age(age),
        text=text,
        context=text_of(dig(update, "header", "text")),
        reshared_author=reshared_author,
        reactions=_as_int(counts.get("numLikes")),
        comments=_as_int(counts.get("numComments")),
        reposts=_as_int(counts.get("numShares")),
        promoted=promoted,
    )


def _activity_urn(update: dict) -> str | None:
    for candidate in (dig(update, "updateMetadata", "urn"), update.get("entityUrn"), update.get("urn")):
        if isinstance(candidate, str):
            match = _ACTIVITY_URN.search(candidate)
            if match:
                return match.group(0)
    return None


def _clean_age(value: str | None) -> str | None:
    """Turn "3h • Edited • " into "3h"."""
    if not value:
        return None
    return value.split("•")[0].strip() or None


def _as_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None
