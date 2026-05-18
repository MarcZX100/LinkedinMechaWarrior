from __future__ import annotations

from dataclasses import dataclass

from .utils import normalize_text


TONES = {"profesional", "tecnico", "cercano", "fundador", "educativo"}
LENGTHS = {"corta", "media", "larga"}


@dataclass(frozen=True)
class PostDraft:
    text: str
    tone: str
    length: str


class PostGenerationError(ValueError):
    """Raised when the input cannot be transformed into a useful post."""


def normalize_tone(tone: str) -> str:
    aliases = {
        "técnico": "tecnico",
        "fundador/startup": "fundador",
        "startup": "fundador",
    }
    normalized = aliases.get(tone.strip().lower(), tone.strip().lower())
    if normalized not in TONES:
        raise PostGenerationError(f"Unsupported tone: {tone}. Use one of: {', '.join(sorted(TONES))}")
    return normalized


def normalize_length(length: str) -> str:
    normalized = length.strip().lower()
    if normalized not in LENGTHS:
        raise PostGenerationError(f"Unsupported length: {length}. Use one of: {', '.join(sorted(LENGTHS))}")
    return normalized


def generate_post(idea: str, tone: str = "profesional", length: str = "media") -> PostDraft:
    cleaned_idea = normalize_text(idea)
    if len(cleaned_idea) < 8:
        raise PostGenerationError("The idea is too short to produce a useful LinkedIn post.")

    normalized_tone = normalize_tone(tone)
    normalized_length = normalize_length(length)

    hook = _build_hook(cleaned_idea, normalized_tone)
    body = _build_body(cleaned_idea, normalized_tone, normalized_length)
    close = _build_close(normalized_tone)

    text = normalize_text("\n\n".join([hook, body, close]))
    return PostDraft(text=text, tone=normalized_tone, length=normalized_length)


def _build_hook(idea: str, tone: str) -> str:
    if tone == "tecnico":
        return f"Hay una leccion tecnica interesante detras de esto: {idea}."
    if tone == "cercano":
        return f"Ultimamente le estoy dando vueltas a esto: {idea}."
    if tone == "fundador":
        return f"Como fundador, pocas cosas ensenan mas que trabajar en algo concreto: {idea}."
    if tone == "educativo":
        return f"Una forma sencilla de entender este tema es partir de una idea: {idea}."
    return f"Hay aprendizajes que solo aparecen cuando pasas de la teoria a la practica: {idea}."


def _build_body(idea: str, tone: str, length: str) -> str:
    paragraphs_by_length = {
        "corta": [_core_paragraph(idea, tone)],
        "media": [_core_paragraph(idea, tone), _practical_paragraph(tone)],
        "larga": [_core_paragraph(idea, tone), _practical_paragraph(tone), _reflection_paragraph(tone)],
    }
    return "\n\n".join(paragraphs_by_length[length])


def _core_paragraph(idea: str, tone: str) -> str:
    if tone == "tecnico":
        return (
            "Lo valioso no fue automatizar por automatizar, sino separar el problema en pasos medibles: "
            "entrada, decision, ejecucion y revision. Cuando esa estructura esta clara, la tecnologia deja "
            "de ser una promesa amplia y empieza a ser una herramienta verificable."
        )
    if tone == "cercano":
        return (
            "Me quedo con algo bastante simple: una buena herramienta no sustituye el criterio, lo ordena. "
            "Cuando el proceso esta bien pensado, trabajar con ayuda de IA se siente menos como delegar a ciegas "
            "y mas como tener un segundo borrador con el que conversar."
        )
    if tone == "fundador":
        return (
            "En una startup, el tiempo que se pierde en tareas repetidas tambien es producto. Cada proceso interno "
            "que se vuelve mas claro libera energia para hablar con clientes, mejorar el servicio y tomar mejores decisiones."
        )
    if tone == "educativo":
        return (
            "Primero conviene describir el proceso sin tecnologia. Despues se identifican los pasos repetibles, "
            "los puntos donde hace falta criterio humano y los riesgos de automatizar demasiado pronto."
        )
    return (
        "La clave fue no empezar por la herramienta, sino por el proceso. Que tarea se repite, que decision requiere "
        "criterio humano y que resultado seria realmente util para el equipo."
    )


def _practical_paragraph(tone: str) -> str:
    if tone == "tecnico":
        return (
            "Tambien ayuda poner limites desde el inicio: logs claros, revision humana en los puntos sensibles y "
            "fallos visibles. Un flujo automatizado que no se puede auditar termina creando mas deuda de la que elimina."
        )
    if tone == "fundador":
        return (
            "El aprendizaje importante es que la automatizacion no deberia esconder el trabajo. Deberia hacerlo mas observable, "
            "mas facil de mejorar y menos dependiente de la memoria individual."
        )
    if tone == "educativo":
        return (
            "Una regla practica: si no puedes explicar como revisarias el resultado manualmente, todavia no deberias automatizar "
            "esa parte. La supervision no es un detalle; es parte del diseno."
        )
    return (
        "Por eso me parece importante mantener una revision humana al final. La automatizacion prepara, acelera y reduce friccion; "
        "la responsabilidad sigue estando en quien decide publicar, enviar o cambiar algo."
    )


def _reflection_paragraph(tone: str) -> str:
    if tone == "tecnico":
        return (
            "En la practica, los mejores resultados aparecen cuando el sistema es aburrido en el buen sentido: predecible, "
            "explicable y facil de detener. Esa sobriedad suele valer mas que una demo espectacular."
        )
    if tone == "fundador":
        return (
            "No todo proceso merece automatizarse. Pero cuando una tarea se repite, duele y tiene un criterio claro de calidad, "
            "convertirla en sistema puede cambiar bastante la velocidad de un equipo pequeno."
        )
    return (
        "Creo que ese equilibrio va a ser cada vez mas importante: usar IA para ganar claridad y velocidad, sin convertirla "
        "en una excusa para dejar de mirar con atencion lo que hacemos."
    )


def _build_close(tone: str) -> str:
    if tone == "tecnico":
        return "Que parte de vuestros procesos internos automatizariais primero, y cual dejariais siempre bajo revision humana?"
    if tone == "cercano":
        return "Os ha pasado algo parecido al llevar IA a procesos del dia a dia?"
    if tone == "fundador":
        return "Que proceso interno os ha dado mas retorno al automatizarlo con cuidado?"
    if tone == "educativo":
        return "Que criterio usais para decidir si un proceso ya esta listo para automatizarse?"
    return "Que aprendizaje os ha dejado automatizar procesos internos sin perder control sobre el resultado?"
