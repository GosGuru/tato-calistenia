"""Gobernanza estructural de solo lectura; no aprueba ni aplica reglas."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
BASE = ".agents/skills/tato-calistenia/"
SOURCES = BASE + "assets/source-governance.json"
LEDGER = BASE + "assets/feedback-ledger.json"
OWNERS = {
    "skill": BASE + "SKILL.md",
    **{
        domain: BASE + "references/" + name + ".md"
        for domain, name in {
            "motor": "motor-agentico",
            "voz": "voz-escrita-tato",
            "contexto": "contexto-maestro",
            "objeciones": "objeciones-agenda",
            "maseteo": "operativa-maseteo",
            "tracking": "tracking-eod",
            "biblioteca": "biblioteca-tecnica-tato",
            "feedback": "feedback-controlado",
            "operativa": "operativa-dm",
            "handoff": "handoff-llamada",
        }.items()
    },
}
RECORD_FIELDS = {
    "id",
    "status",
    "kind",
    "owner",
    "principle",
    "scope",
    "exception",
    "replaces",
    "contrast",
    "change_case",
    "no_change_case",
    "previous",
    "replacement",
    "approval",
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def shape(value, keys):
    require(type(value) is dict and set(value) == set(keys), "campos inválidos")


def text(value):
    require(type(value) is str and bool(value.strip()), "texto inválido")


def identifier(value):
    text(value)
    require(re.fullmatch(r"[a-z][a-z0-9-]*", value) is not None, "ID inválido")


def safe_file(value):
    text(value)
    require(not any(c in value for c in ("\\", ":", "\x00")), "ruta inválida")
    parts = value.split("/")
    require(all(p not in ("", ".", "..") for p in parts), "ruta no canónica")
    path = ROOT
    for part in parts:
        path = path / part
        require(not path.is_symlink(), "symlink no permitido")
    require(path.resolve().is_relative_to(ROOT.resolve()), "escape de repositorio")
    require(path.is_file(), "archivo inexistente")
    return path


def load_json(path):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "clave JSON duplicada")
            result[key] = value
        return result

    def constant(_value):
        raise ValueError("constante JSON inválida")

    try:
        result = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=pairs,
            parse_constant=constant,
        )
    except (OSError, ValueError) as exc:
        raise ValueError("JSON ilegible o inválido") from exc
    require(type(result) is dict, "raíz JSON inválida")
    return result


def source_contract(data):
    shape(data, ("version", "owners", "summaries", "sources"))
    require(type(data["version"]) is int and data["version"] == 1, "versión inválida")
    require(data["owners"] == OWNERS, "dueños canónicos inválidos")
    for owner in OWNERS.values():
        safe_file(owner)
    summaries = data["summaries"]
    require(type(summaries) is list, "resúmenes inválidos")
    seen = set()
    for summary in summaries:
        shape(summary, ("path", "role"))
        safe_file(summary["path"])
        require(summary["role"] == "summary", "documentación no normativa")
        require(summary["path"] not in seen, "resumen duplicado")
        require(summary["path"] not in OWNERS.values(), "dueño no es resumen")
        seen.add(summary["path"])
    require(
        {
            "AGENTS.md",
            "README.md",
            "docs/sdd/call-first-dm.md",
            "docs/source-audit-status.md",
        }
        <= seen,
        "faltan resúmenes",
    )
    require(
        type(data["sources"]) is list and bool(data["sources"]), "fuentes inválidas"
    )
    seen = set()
    for source in data["sources"]:
        shape(source, ("id", "status", "translated_refs"))
        identifier(source["id"])
        require(source["id"] not in seen, "fuente duplicada")
        seen.add(source["id"])
        require(
            type(source["status"]) is str
            and source["status"]
            in {"approved", "historical", "pending", "candidate", "rejected"},
            "estado de fuente inválido",
        )
        refs = source["translated_refs"]
        require(type(refs) is list, "traducciones inválidas")
        for ref in refs:
            text(ref)
            require(ref in OWNERS.values(), "traducción sin dueño")
            safe_file(ref)
        require(len(refs) == len(set(refs)), "traducción duplicada")
        require(
            bool(refs) == (source["status"] == "approved"),
            "solo aprobación traducida tiene referencias activas",
        )


def ledger_contract(data, fixtures):
    shape(data, ("version", "records"))
    require(type(data["version"]) is int and data["version"] == 1, "versión inválida")
    require(type(data["records"]) is list, "registros inválidos")
    records = {}
    for record in data["records"]:
        shape(record, RECORD_FIELDS)
        identifier(record["id"])
        require(record["id"] not in records, "registro duplicado")
        records[record["id"]] = record
        for key in (
            "status",
            "kind",
            "owner",
            "principle",
            "scope",
            "exception",
            "replaces",
            "contrast",
            "change_case",
            "no_change_case",
        ):
            text(record[key])
        require(
            record["status"]
            in {"candidate", "rejected", "approved", "applied", "reverted"},
            "estado inválido",
        )
        require(
            record["kind"] in {"local_edit", "style", "general_rule"}, "clase inválida"
        )
        require(record["owner"] in OWNERS.values(), "dueño inválido")
        require(record["kind"] != "local_edit", "edición local no se persiste")
        for key in ("change_case", "no_change_case"):
            require(record[key] in fixtures, "fixture inexistente")
        require(
            record["change_case"] != record["no_change_case"],
            "contraste necesita dos fixtures",
        )
        for key in ("previous", "replacement"):
            if record[key] is not None:
                identifier(record[key])
        approval = record["approval"]
        if approval is not None:
            shape(approval, ("by", "decision", "principle"))
            require(
                approval
                == {
                    "by": "user",
                    "decision": "explicit",
                    "principle": record["principle"],
                },
                "aprobación no corresponde al principio exacto",
            )
        promoted = record["status"] in {"approved", "applied", "reverted"}
        require(
            (approval is not None) == promoted,
            "aprobación requerida solo en estados promovidos",
        )
    for key, record in records.items():
        for link, reciprocal in (
            ("previous", "replacement"),
            ("replacement", "previous"),
        ):
            target = record[link]
            if target is not None:
                require(target in records and target != key, "enlace inválido")
                require(records[target][reciprocal] == key, "enlace no recíproco")
                require(
                    records[target]["owner"] == record["owner"],
                    "reemplazo entre dueños",
                )
        seen = set()
        cursor = key
        while cursor is not None:
            require(cursor not in seen, "ciclo de reemplazo")
            seen.add(cursor)
            require(cursor in records, "enlace inexistente")
            cursor = records[cursor]["replacement"]


def validate(sources, ledger, fixtures):
    errors = []
    for label, check in (
        ("sources", lambda: source_contract(sources)),
        ("ledger", lambda: ledger_contract(ledger, fixtures)),
    ):
        try:
            check()
        except (ValueError, OSError, RuntimeError) as exc:
            errors.append(f"{label}: {exc}")
    return errors


def validate_repository():
    try:
        sources = load_json(safe_file(SOURCES))
        ledger = load_json(safe_file(LEDGER))
        cases = load_json(safe_file(BASE + "assets/forward-cases.json"))["cases"]
        require(type(cases) is list, "fixtures inválidos")
        ids = []
        for case in cases:
            require(type(case) is dict and "id" in case, "fixture inválido")
            identifier(case["id"])
            ids.append(case["id"])
        require(len(ids) == len(set(ids)), "fixture duplicado")
        require(
            {
                "feedback-local",
                "feedback-no-copy",
                "feedback-style",
                "feedback-approved",
                "feedback-conflict",
                "feedback-no-change",
            }
            <= set(ids),
            "faltan fixtures de feedback",
        )
        return validate(sources, ledger, set(ids))
    except (ValueError, OSError, RuntimeError, KeyError) as exc:
        return [f"governance: {exc}"]


def main():
    import argparse

    argparse.ArgumentParser(description=__doc__).parse_args()
    errors = validate_repository()
    for error in errors:
        print(error)
    if not errors:
        print(
            "gobernanza válida; no demuestra aprobación humana ni aplicación semántica"
        )
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
