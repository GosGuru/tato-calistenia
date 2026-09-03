#!/usr/bin/env python3
"""Validación estática del runtime local de Tato Calistenia."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SKILL_ROOT.parents[2]
REFERENCES = SKILL_ROOT / "references"
ASSETS = SKILL_ROOT / "assets"
OFFICIAL_CAL_URL = "https://cal.com/tato-ramon/reunion-auditoria"

RUNTIME_FILES = [
    SKILL_ROOT / "SKILL.md",
    SKILL_ROOT / "agents" / "openai.yaml",
    REFERENCES / "motor-agentico.md",
    REFERENCES / "voz-escrita-tato.md",
    REFERENCES / "operativa-dm.md",
    REFERENCES / "operativa-maseteo.md",
    REFERENCES / "objeciones-agenda.md",
    REFERENCES / "handoff-llamada.md",
    REFERENCES / "contexto-maestro.md",
    REFERENCES / "biblioteca-tecnica-tato.md",
    REFERENCES / "casos-calibracion.md",
    ASSETS / "forward-cases.json",
    REPO_ROOT / "AGENTS.md",
    REPO_ROOT / "README.md",
    REPO_ROOT / "docs" / "sdd" / "call-first-dm.md",
    REPO_ROOT / ".gitignore",
]

MAINTENANCE_FILES = [
    REFERENCES / "criterio-fuentes-curadas.md",
]

VALIDATED_FILES = RUNTIME_FILES + MAINTENANCE_FILES

REQUIRED_MARKERS = {
    "SKILL.md": [
        "## Activation Contract",
        "## Hard Rules",
        "## Decision Gates",
        "## Execution Steps",
        "## Output Contract",
        "## References",
        "references/objeciones-agenda.md",
        "references/handoff-llamada.md",
        "references/casos-calibracion.md",
        "references/operativa-maseteo.md",
        "references/criterio-fuentes-curadas.md",
        "assets/forward-cases.json",
        "pregunta de dirección",
    ],
    "openai.yaml": [
        "Setter de Instagram y briefs de llamada",
        "allow_implicit_invocation: true",
    ],
    "motor-agentico.md": [
        "## Estado interno",
        "## Precedencia",
        "## Ciclo de decisión",
        "destino_funcional",
        "destino_vital",
        "senal_economica",
        "subestado_conversion",
        "outbound_batch",
        "bloqueo_operativo",
        "## Revisión silenciosa",
        "Toda conversación activa termina con una pregunta de dirección",
        "profundidad_del_aporte",
        "huella_reciente",
        "No pensar mediante una respuesta modelo",
    ],
    "operativa-dm.md": [
        "## Siete fases adaptativas",
        "### FASE 1 — Contexto actual",
        "### FASE 2 — Destino",
        "### FASE 3 — Brecha e intentos",
        "### FASE 4 — Sentido personal",
        "### FASE 5 — Disposición práctica",
        "### FASE 6 — Ruta Tato",
        "### FASE 7 — Conversión",
        "USD 300",
        "## Dirección eficiente",
        "pregunta final de dirección",
        "pregunta directa sin prefacio",
        "frase final no se recupera ni se copia",
    ],
    "voz-escrita-tato.md": [
        "## Huella comprobada de Tato",
        "## Escucha visible",
        "## Destino antes que skill",
        "## Ruta sin voz de vendedor",
        "## Movimientos comerciales con voz humana",
        "Dirección es",
        "pregunta de dirección",
        "## Redacción desde criterio",
        "## Longitud proporcional",
        "No buscar ejemplos similares",
    ],
    "operativa-maseteo.md": [
        "## Alcance",
        "## Contrato del lote",
        "## Elegibilidad",
        "## Prioridad",
        "## Dirección eficiente",
        "## Salida",
        "eligible",
        "needs_context",
        "skip",
        "nunca envía",
    ],
    "objeciones-agenda.md": [
        "## Dinero solo si el lead lo trae",
        "## Precio",
        "## Agenda oficial",
        OFFICIAL_CAL_URL,
        "## Follow-up en cualquier fase",
        "como máximo dos",
    ],
    "handoff-llamada.md": [
        "## Formato de salida",
        "### Destino en sus palabras",
        "### Disposición a invertir",
        "### Ángulo recomendado",
        "### No repetir ni asumir",
    ],
    "contexto-maestro.md": [
        "Público prioritario",
        "avatar ideal",
        "USD 300",
        "## Posicionamiento",
        "## Seguridad y salud",
        "trastorno alimentario",
        "salud mental",
    ],
    "biblioteca-tecnica-tato.md": [
        "## Criterio Trainology aprobado",
        "### Entrevista y comunicacion humana",
        "### Biomecanica contextual",
        "### Programacion e individualizacion",
        "### Comunicacion sobre dolor",
        "## Mapa de las primeras cinco dominadas",
        "## Dominadas y control escapular",
        "## Limite de ayuda gratuita",
        "no activa derivacion automatica",
        "criterio-fuentes-curadas.md",
    ],
    "casos-calibracion.md": [
        "## Rúbrica",
        "## Hard fails",
        "## Calibraciones prospect_dm",
        "## Calibración call_brief",
        "## Calibración Trainology aprobada",
        "Decisión esperada:",
        "no contienen una salida para imitar",
        OFFICIAL_CAL_URL,
        "## Calibración outbound_batch",
        "Hard fails del lote",
    ],
    "criterio-fuentes-curadas.md": [
        "## Contrato de curación",
        "## Julio Rondinelli",
        "## Psychoselling",
        "## De 0 a 10",
        "## Trainology",
        "## Corpus propio de Instagram",
        "Maxi aprobó las cuatro fichas",
        "## Reglas de promoción",
        "**Rescatar:**",
        "**Rechazar:**",
        "**Traducción Tato:**",
        "`candidate`",
        "`approved`",
    ],
    "AGENTS.md": [
        "primer turno de cada chat nuevo",
        "contexto, destino, brecha, sentido, disposición, ruta y conversión",
        "acompañamiento pago de 90 días",
        OFFICIAL_CAL_URL,
        "Brief de llamada",
    ],
    "README.md": [
        "50 fixtures v3",
        "Público prioritario 40+",
        "USD 300",
        "call_brief",
        "outbound_batch",
        "forward-cases.json",
    ],
    "call-first-dm.md": [
        "Cada chat nuevo del workspace reconstruye la v3",
        "## Interfaces",
        "contexto -> destino -> brecha -> sentido -> disposición -> ruta -> conversión",
        "USD 300",
        OFFICIAL_CAL_URL,
        "## Criterios de aceptación",
        "redacción se construye de cero",
    ],
    ".gitignore": ["*.bak", "chats/"],
}

FORBIDDEN_LEGACY = [
    "28 a 45",
    "treinta y pico",
    "cuatro condiciones",
    "flujo comprimido",
    "objetos_brillantes",
    "presentar exactamente tres",
    "los tres elementos aparecen",
    "tarde o noche",
    "un unico mensaje detallado y de alta intencion",
]

FORBIDDEN_MANIPULATION = [
    "ganar ventaja sobre el lead",
    "hacerlo dudar de sus logros",
    "serial killer",
    "tinder effect",
    "queres quedarte como estas",
    "te estas dejando plata",
    "ganar el marco",
    "todos los leads son cerrables",
    "hacerle ver el dolor a mas no poder",
    "si no tenes una hora",
]

FORBIDDEN_PROACTIVE_ECONOMIC = [
    "pendiente_inversion",
    "disposicion_inversion",
    "validar disposición de inversión",
    "confirmó que está en un momento de invertir",
    "ruta e inversión positivas",
]

REQUIRED_FIXTURE_FIELDS = {
    "id",
    "mode",
    "title",
    "phase",
    "input_summary",
    "expected_move",
    "required",
    "forbidden",
}

VALID_PHASES = {
    "contexto",
    "destino",
    "brecha",
    "sentido",
    "disposicion",
    "ruta",
    "conversion",
}

REQUIRED_FORWARD_IDS = {
    "avatar-padre-45",
    "capacidad-cotidiana-52",
    "muscle-up-43",
    "adulto-menor-40",
    "destino-sin-sentido",
    "audio-largo-incompleto",
    "consulta-tecnica-temprana",
    "ruta-contextual",
    "ruta-aceptada",
    "dinero-espontaneo",
    "sin-capacidad-hoy",
    "pregunta-precio",
    "llamada-aceptada",
    "reserva-confirmada",
    "presencial-con-antecedente",
    "presencial-sin-oferta",
    "objecion-ego-regateo",
    "lesion-musculoesqueletica",
    "salud-fuera-alcance",
    "minoridad",
    "followup-uno",
    "followup-dos",
    "brief-llamada",
    "batch-nuevo-seguidor",
    "batch-comentario-recurso",
    "batch-link-fallido",
    "batch-conversacion-activa",
    "batch-respuesta-multisenal",
    "batch-tecnica-direccion",
    "batch-ruta-aceptada",
    "batch-dinero-espontaneo",
    "batch-llamada-aceptada",
    "batch-followup-uno",
    "batch-followup-dos",
    "batch-rechazo-skip",
    "batch-reserva-skip",
    "batch-salud-minoridad-skip",
    "batch-contexto-insuficiente",
    "batch-mixto-estado-independiente",
    "batch-contacto-duplicado",
    "trainology-entrevista-minima",
    "trainology-biomecanica-contextual",
    "trainology-programacion-individualizada",
    "trainology-dolor-prudente",
    "prospect-direccion-obligatoria",
    "prospect-pregunta-directa",
    "prospect-apertura-profunda",
    "prospect-aviso-interfaz",
    "prospect-lesion-alcance-tato",
    "prospect-huella-repetida",
}


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def relative(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT)).replace("\\", "/")


def read_utf8(path: Path, errors: list[str]) -> str:
    if not path.is_file():
        fail(errors, f"falta {relative(path)}")
        return ""
    try:
        raw = path.read_bytes()
        if b"\x00" in raw:
            fail(errors, f"byte nulo en {relative(path)}")
        return raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    except UnicodeDecodeError:
        fail(errors, f"UTF-8 inválido en {relative(path)}")
        return ""


def validate_frontmatter(text: str, errors: list[str]) -> None:
    match = re.match(r"\A---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        fail(errors, "SKILL.md no tiene frontmatter válido")
        return

    frontmatter = match.group(1)
    top_level = [
        line.split(":", 1)[0].strip()
        for line in frontmatter.splitlines()
        if ":" in line and not line.startswith((" ", "\t"))
    ]
    if top_level != ["name", "description", "license", "metadata"]:
        fail(errors, "SKILL.md debe declarar name, description, license y metadata en ese orden")

    checks = [
        (r"(?m)^name:\s*tato-calistenia\s*$", "nombre del skill inválido"),
        (r"(?m)^license:\s*Apache-2\.0\s*$", "licencia del skill inválida"),
        (r"(?m)^\s{2}author:\s*valka\s*$", "metadata.author inválido"),
        (r'(?m)^\s{2}version:\s*"3\.0"\s*$', "metadata.version inválido"),
    ]
    for pattern, message in checks:
        if not re.search(pattern, frontmatter):
            fail(errors, message)

    description_lines = [line for line in frontmatter.splitlines() if line.startswith("description:")]
    if len(description_lines) != 1:
        fail(errors, "description debe ocupar una sola línea física")
    else:
        description = description_lines[0].split(":", 1)[1].strip().strip('"')
        if len(description) > 250:
            fail(errors, "description supera 250 caracteres")
        if "Trigger:" not in description:
            fail(errors, "description no declara Trigger")

    body_words = len(text[match.end() :].split())
    if body_words > 700:
        fail(errors, f"SKILL.md supera 700 palabras ({body_words})")


def validate_references(skill_text: str, errors: list[str]) -> None:
    references = re.findall(r"`((?:references|assets)/[^`]+)`", skill_text)
    if not references:
        fail(errors, "SKILL.md no declara referencias locales")
        return
    for item in references:
        if not (SKILL_ROOT / item).is_file():
            fail(errors, f"referencia inexistente en SKILL.md: {item}")


def validate_calibration_contract(text: str, errors: list[str]) -> None:
    decisions = re.findall(r"(?m)^Decisión esperada:\s*$", text)
    if len(decisions) < 23:
        fail(errors, f"casos-calibracion.md tiene pocas decisiones comprobables ({len(decisions)})")

    forbidden_template_headers = [
        "Salida valida:",
        "Salida válida:",
        "Ritmo válido:",
        "Ritmos posibles:",
        "Preguntas de dirección posibles:",
    ]
    for marker in forbidden_template_headers:
        if marker in text:
            fail(errors, f"casos-calibracion.md conserva plantilla literal: {marker}")

    if OFFICIAL_CAL_URL not in text:
        fail(errors, "casos-calibracion.md no conserva la URL oficial en la decisión de agenda")


def validate_fixtures(path: Path, errors: list[str]) -> None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail(errors, f"forward-cases.json inválido: {exc}")
        return

    if data.get("version") != 3:
        fail(errors, "forward-cases.json debe usar version 3")

    rubric = data.get("rubric", {})
    expected_dimensions = [
        "fidelidad",
        "fase",
        "naturalidad",
        "posicionamiento",
        "seguridad",
    ]
    if rubric.get("dimensions") != expected_dimensions:
        fail(errors, "rúbrica forward incompleta o desordenada")
    if rubric.get("minimum_total") != 8:
        fail(errors, "rúbrica forward debe exigir 8/10")
    if rubric.get("required_full_scores") != ["fidelidad", "naturalidad", "seguridad"]:
        fail(errors, "rúbrica forward no exige fidelidad, naturalidad y seguridad completas")

    batch_rubric = data.get("batch_rubric", {})
    expected_batch_dimensions = [
        "elegibilidad",
        "prioridad",
        "continuidad",
        "mensaje",
        "seguridad",
    ]
    if batch_rubric.get("dimensions") != expected_batch_dimensions:
        fail(errors, "rúbrica outbound_batch incompleta o desordenada")
    if batch_rubric.get("max_per_dimension") != 2:
        fail(errors, "rúbrica outbound_batch debe puntuar 0 a 2")
    if batch_rubric.get("minimum_total") != 8:
        fail(errors, "rúbrica outbound_batch debe exigir 8/10")
    if batch_rubric.get("required_full_scores") != ["continuidad", "mensaje", "seguridad"]:
        fail(errors, "rúbrica outbound_batch no exige continuidad, mensaje y seguridad completas")

    cases = data.get("cases")
    if not isinstance(cases, list) or len(cases) < 50:
        fail(errors, "forward-cases.json debe contener al menos 50 casos")
        return

    seen: set[str] = set()
    batch_count = 0
    for index, case in enumerate(cases, start=1):
        if not isinstance(case, dict):
            fail(errors, f"fixture {index} no es un objeto")
            continue
        missing = REQUIRED_FIXTURE_FIELDS - case.keys()
        if missing:
            fail(errors, f"fixture {index} carece de {sorted(missing)}")
        case_id = case.get("id")
        if not isinstance(case_id, str) or not case_id:
            fail(errors, f"fixture {index} tiene id inválido")
        elif case_id in seen:
            fail(errors, f"fixture duplicado: {case_id}")
        else:
            seen.add(case_id)
        mode = case.get("mode")
        if mode not in {"prospect_dm", "outbound_batch", "call_brief"}:
            fail(errors, f"fixture {case_id} tiene modo inválido")
        if mode == "outbound_batch":
            batch_count += 1
            if not str(case_id).startswith("batch-"):
                fail(errors, f"fixture outbound_batch sin prefijo batch-: {case_id}")
        if case.get("phase") not in VALID_PHASES:
            fail(errors, f"fixture {case_id} tiene fase inválida")
        for key in ("required", "forbidden"):
            value = case.get(key)
            if not isinstance(value, list) or not value or not all(isinstance(item, str) for item in value):
                fail(errors, f"fixture {case_id} tiene {key} inválido")

        serialized = json.dumps(case, ensure_ascii=False)
        if re.search(r"(?i)Analisis_de_llamada|loom_transcripciones\.txt|Objeciones_Lead", serialized):
            fail(errors, f"fixture {case_id} referencia material crudo")
        if re.search(r"(?i)[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", serialized):
            fail(errors, f"fixture {case_id} parece contener un email privado")
        if re.search(r"(?<!\w)(?:\+?\d[\s().-]?){8,}(?!\w)", serialized):
            fail(errors, f"fixture {case_id} parece contener un teléfono o identificador numérico")

    missing_ids = REQUIRED_FORWARD_IDS - seen
    if missing_ids:
        fail(errors, f"faltan fixtures forward obligatorios: {sorted(missing_ids)}")
    if batch_count < 16:
        fail(errors, f"faltan casos outbound_batch: {batch_count}/16")


def validate_curation(path: Path, text: str, errors: list[str]) -> None:
    if not path.is_file() or not text:
        return

    cards = re.findall(r"(?ms)^### .+?\n(.*?)(?=^### |^## |\Z)", text)
    cards = [card for card in cards if re.search(r"(?m)^- `source`:", card)]
    if len(cards) < 10:
        fail(errors, f"criterio-fuentes-curadas.md tiene pocas fichas ({len(cards)})")

    required_patterns = {
        "source": r"(?m)^- `source`:",
        "lessons": r"(?m)^- `lessons`:",
        "domain": r"(?m)^- `domain`:",
        "status": r"(?m)^- `status`: `(candidate|approved|rejected|deferred)`",
        "reviewer": r"(?m)^- `reviewer`:",
        "reviewed_on": r"(?m)^- `reviewed_on`:",
        "Rescatar": r"(?m)^- \*\*Rescatar:\*\*",
        "Rechazar": r"(?m)^- \*\*Rechazar:\*\*",
        "Traducción Tato": r"(?m)^- \*\*Traducción Tato:\*\*",
        "Riesgo y límites": r"(?m)^- \*\*Riesgo y límites:\*\*",
    }
    for index, card in enumerate(cards, start=1):
        for label, pattern in required_patterns.items():
            if not re.search(pattern, card):
                fail(errors, f"ficha curada {index} carece de {label}")

    trainology = re.search(r"(?ms)^## Trainology\n(.*?)(?=^## |\Z)", text)
    if not trainology:
        fail(errors, "falta sección Trainology en criterio curado")
    else:
        statuses = re.findall(r"(?m)^- `status`: `([^`]+)`", trainology.group(1))
        reviewed_on = re.findall(r"(?m)^- `reviewed_on`: (.+)$", trainology.group(1))
        if len(statuses) != 4 or any(status != "approved" for status in statuses):
            fail(errors, "las cuatro fichas Trainology deben estar approved tras la autorización de Maxi")
        if len(reviewed_on) != 4 or any(value.strip() != "2026-08-31" for value in reviewed_on):
            fail(errors, "las cuatro fichas Trainology deben registrar reviewed_on 2026-08-31")


def validate_privacy(contents: dict[str, str], errors: list[str]) -> None:
    reference_names = [path.name for path in VALIDATED_FILES if path.parent == REFERENCES]
    for filename in reference_names:
        text = contents.get(filename, "")
        if re.search(r"(?m)^\s*\[?\d{1,2}:\d{2}(?::\d{2})?\]?\s", text):
            fail(errors, f"{filename} parece contener timestamps de transcripción")
        if re.search(r"(?i)Analisis_de_llamada|loom_transcripciones\.txt", text):
            fail(errors, f"{filename} referencia material crudo")
        if re.search(r"(?i)[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", text):
            fail(errors, f"{filename} parece contener un email privado")
        phone_text = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "", text)
        if re.search(r"(?<!\w)(?:\+?\d[\s().-]?){8,}(?!\w)", phone_text):
            fail(errors, f"{filename} parece contener un teléfono o identificador numérico")
        if re.search(r"(?i)C:[\\/]+Users[\\/]+[^\\/]+", text):
            fail(errors, f"{filename} parece contener una ruta personal")
        if re.search(r"(?im)^\s*(?:speaker|hablante)\s*\d*\s*:", text):
            fail(errors, f"{filename} parece contener turnos de una transcripción")


def validate_tracked_backups(errors: list[str]) -> None:
    try:
        result = subprocess.run(
            ["git", "ls-files", "*.bak"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        fail(errors, f"no se pudo comprobar backups trackeados: {exc}")
        return
    if result.returncode != 0:
        fail(errors, "git ls-files *.bak falló")
    elif result.stdout.strip():
        fail(errors, "hay backups *.bak todavía versionados")


def validate_no_loaded_output_templates(contents: dict[str, str], errors: list[str]) -> None:
    prospect_files = ["motor-agentico.md", "voz-escrita-tato.md", "operativa-dm.md"]
    forbidden_headers = [
        "Salida valida:",
        "Salida válida:",
        "Ritmo válido:",
        "Ritmos posibles:",
        "Preguntas de dirección posibles:",
        "Estructura interna, no plantilla:",
    ]
    for filename in prospect_files:
        text = contents.get(filename, "")
        for marker in forbidden_headers:
            if marker in text:
                fail(errors, f"{filename} contiene una plantilla de salida cargada: {marker}")


def validate_runtime() -> list[str]:
    errors: list[str] = []
    contents = {path.name: read_utf8(path, errors) for path in VALIDATED_FILES}

    skill_text = contents.get("SKILL.md", "")
    validate_frontmatter(skill_text, errors)
    validate_references(skill_text, errors)
    validate_calibration_contract(contents.get("casos-calibracion.md", ""), errors)
    validate_fixtures(ASSETS / "forward-cases.json", errors)
    validate_curation(
        REFERENCES / "criterio-fuentes-curadas.md",
        contents.get("criterio-fuentes-curadas.md", ""),
        errors,
    )
    validate_privacy(contents, errors)
    validate_tracked_backups(errors)
    validate_no_loaded_output_templates(contents, errors)

    for filename, markers in REQUIRED_MARKERS.items():
        text = contents.get(filename, "")
        for marker in markers:
            if marker not in text:
                fail(errors, f"falta marcador en {filename}: {marker}")

    normative = "\n".join(contents.get(path.name, "") for path in RUNTIME_FILES).lower()
    for phrase in FORBIDDEN_LEGACY:
        if phrase.lower() in normative:
            fail(errors, f"regla anterior presente: {phrase}")
    for phrase in FORBIDDEN_MANIPULATION:
        if phrase.lower() in normative:
            fail(errors, f"táctica manipulativa presente: {phrase}")
    for phrase in FORBIDDEN_PROACTIVE_ECONOMIC:
        if phrase.lower() in normative:
            fail(errors, f"filtro económico proactivo presente: {phrase}")

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
