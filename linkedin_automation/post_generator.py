"""Local, deterministic post scaffolding.

The generator does not invent content about a topic it knows nothing about.
It produces a structure (hook, sections to fill in, closing question) with
`[placeholders]` that you replace before posting; `validate_post_text`
refuses text that still has them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .errors import PostGenerationError, PostValidationError
from .utils import normalize_text

TONES = {"professional", "technical", "casual", "founder", "educational"}
LENGTHS = {"short", "medium", "long"}

_PLACEHOLDER = re.compile(r"\[[^\]\n]{3,}\]")

_HOOKS = {
    "professional": "Something I've been thinking about lately: {idea}",
    "technical": "A technical lesson worth sharing: {idea}",
    "casual": "Quick one today: {idea}",
    "founder": "Building a company teaches you things nothing else does. This week: {idea}",
    "educational": "Here's a simple way to think about it: {idea}",
}

_SECTIONS = {
    "technical": [
        "[The context: what you were building or fixing, in one or two sentences.]",
        "[The technical detail: the approach, the trade-off, or the result.]",
        "[A concrete number, snippet, or before/after that makes it credible.]",
        "[What you'd do differently, or what you're trying next.]",
    ],
    "educational": [
        "[The core idea, explained in plain words.]",
        "[A simple example that makes it click.]",
        "[A common mistake people make with it.]",
        "[One practical step readers can take today.]",
    ],
}
_DEFAULT_SECTIONS = [
    "[What happened or what you noticed, in one or two sentences.]",
    "[Why it matters: the insight or the lesson.]",
    "[A concrete example, number, or detail that makes it credible.]",
    "[What you'd do differently, or what you're trying next.]",
]
_SECTION_COUNT = {"short": 1, "medium": 2, "long": 4}

_CLOSINGS = {
    "professional": "What has your experience been?",
    "technical": "How would you have approached it?",
    "casual": "Has anything similar happened to you?",
    "founder": "Founders, what would you add?",
    "educational": "What would you add to this?",
}


@dataclass(frozen=True)
class PostDraft:
    text: str
    tone: str
    length: str


def normalize_tone(tone: str) -> str:
    normalized = tone.strip().lower()
    if normalized not in TONES:
        raise PostGenerationError(f"Unsupported tone: {tone}. Use one of: {', '.join(sorted(TONES))}")
    return normalized


def normalize_length(length: str) -> str:
    normalized = length.strip().lower()
    if normalized not in LENGTHS:
        raise PostGenerationError(f"Unsupported length: {length}. Use one of: {', '.join(sorted(LENGTHS))}")
    return normalized


def generate_post(idea: str, tone: str = "professional", length: str = "medium") -> PostDraft:
    cleaned_idea = " ".join(normalize_text(idea).split())
    if len(cleaned_idea) < 8:
        raise PostGenerationError("The idea is too short to build a useful post.")

    tone = normalize_tone(tone)
    length = normalize_length(length)

    hook = _HOOKS[tone].format(idea=_as_sentence(cleaned_idea))
    sections = _SECTIONS.get(tone, _DEFAULT_SECTIONS)[: _SECTION_COUNT[length]]
    text = "\n\n".join([hook, *sections, _CLOSINGS[tone]])
    return PostDraft(text=normalize_text(text), tone=tone, length=length)


def find_placeholders(text: str) -> list[str]:
    return _PLACEHOLDER.findall(text)


def validate_post_text(text: str, max_chars: int) -> None:
    if not text.strip():
        raise PostValidationError("The post is empty.")
    if len(text) > max_chars:
        raise PostValidationError(f"The post is {len(text)} characters long; the limit is {max_chars}.")
    placeholders = find_placeholders(text)
    if placeholders:
        raise PostValidationError(f"The post still has template placeholders to fill in, e.g. {placeholders[0]}")


def _as_sentence(idea: str) -> str:
    """End the idea with exactly one sentence terminator, keeping questions and exclamations."""
    if idea.endswith(("?", "!")):
        return idea
    return idea.rstrip(".!,;: ") + "."
