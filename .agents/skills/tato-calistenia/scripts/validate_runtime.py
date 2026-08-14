#!/usr/bin/env python3
"""Validacion estatica del runtime local de Tato Calistenia."""

from __future__ import annotations

import re
import sys
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SKILL_ROOT.parents[2]

RUNTIME_FILES = [
    SKILL_ROOT / "SKILL.md",
    SKILL_ROOT / "agents" / "openai.yaml",
    SKILL_ROOT / "references" / "motor-agentico.md",
    SKILL_ROOT / "references" / "voz-escrita-tato.md",
    SKILL_ROOT / "references" / "operativa-dm.md",
    SKILL_ROOT / "references" / "contexto-maestro.md",
    SKILL_ROOT / "references" / "biblioteca-tecnica-tato.md",
]

REQUIRED_MARKERS = {
    "SKILL.md": [
        "references/motor-agentico.md",
        "references/voz-escrita-tato.md",
        "references/operativa-dm.md",
        "references/contexto-maestro.md",
        "references/biblioteca-tecnica-tato.md",
        "como maximo una pregunta",
        "no usar signos de apertura",
    ],
    "motor-agentico.md": [
        "## Estado interno",
        "## Ciclo de decision",
        "## Revision silenciosa",
        "objetivo concreto",
        "interes demostrado",
        "madurez conversacional",
        "ningun signo de apertura",
    ],
    "voz-escrita-tato.md": [
        "## Autoridad primero",
        "## Tecnica escrita, no clase hablada",
        "## Invitacion natural",
        "Los LOOM calibran criterio tecnico",
    ],
    "operativa-dm.md": [
        "## Objeciones",
        "### ETAPA 4 - Agenda",
        "### Molestia, dolor o lesion",
    ],
    "contexto-maestro.md": [
        "## Reglas comerciales",
        "## Seguridad y salud",
    ],
    "biblioteca-tecnica-tato.md": [
        "## Mapa de las primeras cinco dominadas",
        "## Dominadas y control escapular",
        "## Limite de ayuda gratuita",
    ],
}


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def read_utf8(path: Path, errors: list[str]) -> str:
    if not path.is_file():
        fail(errors, f"falta {path.relative_to(REPO_ROOT)}")
        return ""
    try:
        raw = path.read_bytes()
        if b"\x00" in raw:
            fail(errors, f"byte nulo en {path.relative_to(REPO_ROOT)}")
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        fail(errors, f"UTF-8 invalido en {path.relative_to(REPO_ROOT)}")
        return ""


def validate_frontmatter(text: str, errors: list[str]) -> None:
    match = re.match(r"\A---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        fail(errors, "SKILL.md no tiene frontmatter valido")
        return
    keys = []
    for line in match.group(1).splitlines():
        if ":" in line and not line.startswith((" ", "\t")):
            keys.append(line.split(":", 1)[0].strip())
    if keys != ["name", "description"]:
        fail(errors, "SKILL.md debe declarar solo name y description")
    if not re.search(r"^name:\s*tato-calistenia\s*$", match.group(1), re.MULTILINE):
        fail(errors, "nombre del skill invalido")


def validate_references(skill_text: str, errors: list[str]) -> None:
    for relative in re.findall(r"`((?:references|assets)/[^`]+)`", skill_text):
        if not (SKILL_ROOT / relative).is_file():
            fail(errors, f"referencia inexistente en SKILL.md: {relative}")


def validate_runtime() -> list[str]:
    errors: list[str] = []
    contents = {path.name: read_utf8(path, errors) for path in RUNTIME_FILES}

    skill_text = contents.get("SKILL.md", "")
    validate_frontmatter(skill_text, errors)
    validate_references(skill_text, errors)

    if skill_text.count("\n") + 1 > 500:
        fail(errors, "SKILL.md supera 500 lineas")

    for filename, markers in REQUIRED_MARKERS.items():
        text = contents.get(filename, "")
        for marker in markers:
            if marker not in text:
                fail(errors, f"falta marcador en {filename}: {marker}")

    library = contents.get("biblioteca-tecnica-tato.md", "")
    if re.search(r"(?m)^\d{1,2}:\d{2}\s", library):
        fail(errors, "la biblioteca tecnica parece contener timestamps de transcripcion")

    return errors


def main() -> int:
    errors = validate_runtime()
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("runtime valido")
    return 0


if __name__ == "__main__":
    sys.exit(main())
