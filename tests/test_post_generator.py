import pytest

from linkedin_automation.post_generator import PostGenerationError, generate_post


def test_generate_post_has_expected_structure():
    draft = generate_post(
        "Lo que aprendi automatizando procesos internos con IA",
        tone="profesional",
        length="media",
    )

    assert "Lo que aprendi automatizando procesos internos con IA" in draft.text
    assert "\n\n" in draft.text
    assert "?" in draft.text
    assert "#" not in draft.text
    assert draft.tone == "profesional"
    assert draft.length == "media"


def test_generate_post_accepts_tone_aliases():
    draft = generate_post("Automatizar revisiones tecnicas sin perder criterio", tone="técnico", length="corta")

    assert draft.tone == "tecnico"
    assert "tecnica" in draft.text.lower()


def test_generate_post_rejects_invalid_tone():
    with pytest.raises(PostGenerationError):
        generate_post("Una idea suficientemente larga", tone="viral", length="media")


def test_generate_post_rejects_too_short_idea():
    with pytest.raises(PostGenerationError):
        generate_post("IA")
