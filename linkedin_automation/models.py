from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Profile:
    urn: str | None
    public_id: str | None
    first_name: str | None
    last_name: str | None
    headline: str | None

    @property
    def name(self) -> str:
        return " ".join(part for part in (self.first_name, self.last_name) if part) or "(unknown)"

    @property
    def url(self) -> str | None:
        return f"https://www.linkedin.com/in/{self.public_id}/" if self.public_id else None

    def to_dict(self) -> dict:
        return {**asdict(self), "name": self.name, "url": self.url}


@dataclass(frozen=True)
class FeedPost:
    urn: str | None
    author: str | None
    author_headline: str | None
    age: str | None
    text: str | None
    context: str | None
    reshared_author: str | None
    reactions: int | None
    comments: int | None
    reposts: int | None
    promoted: bool

    @property
    def url(self) -> str | None:
        return f"https://www.linkedin.com/feed/update/{self.urn}/" if self.urn else None

    def to_dict(self) -> dict:
        return {**asdict(self), "url": self.url}
