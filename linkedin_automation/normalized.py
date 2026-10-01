"""Helpers for Voyager's "normalized" JSON format.

With `accept: application/vnd.linkedin.normalized+json+2.1`, responses look like:

    {"data": {...}, "included": [{"entityUrn": "urn:li:...", "$type": "...", ...}, ...]}

Entities reference each other by URN through keys prefixed with "*", e.g.
`{"*socialDetail": "urn:li:fs_socialDetail:..."}`. This module resolves those
references and extracts text defensively, because the shapes are undocumented
and change over time.
"""

from __future__ import annotations

from typing import Any


class Normalized:
    def __init__(self, payload: Any) -> None:
        payload = payload if isinstance(payload, dict) else {}
        data = payload.get("data")
        self.data: dict = data if isinstance(data, dict) else {}
        included = payload.get("included")
        self.included: list[dict] = [item for item in included or [] if isinstance(item, dict)]
        self._by_urn = {item["entityUrn"]: item for item in self.included if isinstance(item.get("entityUrn"), str)}

    def get(self, urn: Any) -> dict | None:
        return self._by_urn.get(urn) if isinstance(urn, str) else None

    def ref(self, obj: Any, key: str) -> dict | None:
        """Return `obj[key]` if inlined, otherwise resolve the `*key` URN reference."""
        if not isinstance(obj, dict):
            return None
        value = obj.get(key)
        if isinstance(value, dict):
            return value
        return self.get(obj.get(f"*{key}"))

    def refs(self, obj: Any, key: str) -> list[dict]:
        """Like `ref`, for lists of entities."""
        if not isinstance(obj, dict):
            return []
        value = obj.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        urns = obj.get(f"*{key}")
        if isinstance(urns, list):
            return [entity for entity in (self.get(urn) for urn in urns) if entity is not None]
        return []

    def of_type(self, type_suffix: str) -> list[dict]:
        return [item for item in self.included if str(item.get("$type", "")).endswith(type_suffix)]


def text_of(value: Any) -> str | None:
    """Extract text from the many TextViewModel shapes: "x", {"text": "x"}, {"text": {"text": "x"}}."""
    for _ in range(5):
        if isinstance(value, str):
            return value.strip() or None
        if not isinstance(value, dict):
            return None
        value = value.get("text")
    return None


def dig(obj: Any, *keys: str) -> Any:
    for key in keys:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)
    return obj
