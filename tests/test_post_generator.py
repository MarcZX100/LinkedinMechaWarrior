import pytest

from linkedin_automation.errors import PostGenerationError, PostValidationError
from linkedin_automation.post_generator import find_placeholders, generate_post, validate_post_text


def test_generate_post_has_hook_sections_and_closing_question():
    draft = generate_post("What I learned running a marathon at 40", tone="casual", length="medium")

    paragraphs = draft.text.split("\n\n")
    assert paragraphs[0] == "Quick one today: What I learned running a marathon at 40."
    assert len(find_placeholders(draft.text)) == 2
    assert paragraphs[-1].endswith("?")
    assert (draft.tone, draft.length) == ("casual", "medium")


def test_generate_post_is_not_tied_to_one_topic():
    text = generate_post("My first year as an ER nurse", tone="professional", length="long").text
    assert "automat" not in text.lower() and " ai " not in f" {text.lower()} "


@pytest.mark.parametrize(
    "idea, expected_hook_end",
    [
        ("Is a marathon at 40 worth it?", "worth it?"),
        ("We shipped it!", "shipped it!"),
        ("Lessons from shipping v2...", "shipping v2."),
        ("Lessons from shipping v2.", "shipping v2."),
    ],
)
def test_generate_post_punctuates_the_idea_once(idea, expected_hook_end):
    hook = generate_post(idea).text.split("\n\n")[0]
    assert hook.endswith(expected_hook_end)
    assert ".." not in hook and "?." not in hook and "!." not in hook


@pytest.mark.parametrize("length, sections", [("short", 1), ("medium", 2), ("long", 4)])
def test_length_controls_number_of_sections(length, sections):
    assert len(find_placeholders(generate_post("A long enough idea", length=length).text)) == sections


def test_generate_post_rejects_invalid_input():
    with pytest.raises(PostGenerationError):
        generate_post("A long enough idea", tone="viral")
    with pytest.raises(PostGenerationError):
        generate_post("A long enough idea", length="huge")
    with pytest.raises(PostGenerationError):
        generate_post("AI")


def test_validate_post_text():
    validate_post_text("A finished post. Thoughts?", max_chars=3000)
    with pytest.raises(PostValidationError, match="empty"):
        validate_post_text("   ", max_chars=3000)
    with pytest.raises(PostValidationError, match="characters"):
        validate_post_text("x" * 3001, max_chars=3000)
    with pytest.raises(PostValidationError, match="placeholder"):
        validate_post_text(generate_post("A long enough idea").text, max_chars=3000)


def test_short_brackets_are_not_placeholders():
    validate_post_text("Arrays start at [0] in Python.", max_chars=3000)
