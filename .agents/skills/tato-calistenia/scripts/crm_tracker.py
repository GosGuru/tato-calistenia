#!/usr/bin/env python3
"""Private, idempotent event ledger and EOD report for Tato's setter workflow."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import tempfile
from collections import Counter
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from pathlib import Path
from typing import Any, Iterable


EVENT_TYPES = {
    "contact_started",
    "dm_drafted",
    "outbound_sent",
    "inbound_received",
    "followup_sent",
    "route_presented",
    "route_accepted",
    "call_invited",
    "calendar_sent",
    "booking_confirmed",
    "objection_observed",
    "disqualified",
    "operational_block",
}
ACTORS = {"maximo", "agent", "automation", "lead", "tato", "unknown"}
EVIDENCE_STATES = {"draft", "observed", "verified"}
PHASES = {"contexto", "destino", "brecha", "sentido", "disposicion", "ruta", "conversion"}
SUBSTATES = {
    "pendiente_aceptacion_ruta",
    "lista_para_llamada",
    "llamada_aceptada",
    "agenda_enviada",
    "reserva_confirmada",
}
QUALITIES = {"alta", "media", "baja", "sin_clasificar"}
COUNTABLE_EVIDENCE = {"observed", "verified"}
OUTBOUND_TYPES = {"outbound_sent", "followup_sent"}


def default_db_path() -> Path:
    override = os.environ.get("TATO_CRM_DB")
    if override:
        return Path(override).expanduser().resolve()
    root = Path(os.environ.get("LOCALAPPDATA", Path.home() / ".local" / "share"))
    return root / "TatoCalistenia" / "crm.sqlite3"


def connect(path: Path, readonly: bool = False) -> sqlite3.Connection:
    if readonly:
        db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
        db.row_factory = sqlite3.Row
        return db
    if path.exists():
        probe = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
        try:
            tables = {row[0] for row in probe.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            if tables and not {"leads", "events"}.issubset(tables):
                raise ValueError("Unknown CRM schema; no data was changed")
        finally:
            probe.close()
        if tables:
            # Existing schema needs no migration. Leave version and old events intact.
            db = sqlite3.connect(path)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys=ON")
            return db
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS leads (
            lead_key TEXT PRIMARY KEY,
            display_name TEXT,
            source_kind TEXT,
            source_ref TEXT,
            phase TEXT,
            conversion_substate TEXT,
            quality TEXT NOT NULL DEFAULT 'sin_clasificar',
            objection TEXT,
            next_action TEXT,
            next_action_at TEXT,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS events (
            event_id TEXT PRIMARY KEY,
            lead_key TEXT NOT NULL,
            event_type TEXT NOT NULL,
            occurred_at TEXT NOT NULL,
            actor TEXT NOT NULL,
            evidence_state TEXT NOT NULL,
            message_fingerprint TEXT,
            source_kind TEXT,
            source_ref TEXT,
            phase TEXT,
            conversion_substate TEXT,
            quality TEXT,
            objection TEXT,
            next_action TEXT,
            next_action_at TEXT,
            reason_code TEXT,
            recorded_at TEXT NOT NULL,
            FOREIGN KEY (lead_key) REFERENCES leads(lead_key)
        );
        CREATE INDEX IF NOT EXISTS idx_events_date ON events(occurred_at);
        CREATE INDEX IF NOT EXISTS idx_events_lead ON events(lead_key, occurred_at);
        """
    )
    db.execute("PRAGMA user_version=2")
    return db


def parse_datetime(value: str) -> str:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})", value.strip()):
        raise ValueError("occurred_at requires a complete ISO-8601 timestamp with UTC offset")
    candidate = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ValueError("occurred_at must be an ISO-8601 date-time") from exc
    if parsed.tzinfo is None or "T" not in candidate:
        raise ValueError("occurred_at requires a known time and explicit UTC offset")
    return parsed.astimezone(timezone.utc).isoformat()


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    result = " ".join(str(value).split()).strip()
    return result or None


def validate_event(raw: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "lead_key", "display_name", "event_type", "occurred_at", "actor", "evidence_state",
        "message_text", "message_fingerprint", "source_kind", "source_ref", "phase",
        "conversion_substate", "quality", "objection", "next_action", "next_action_at",
        "reason_code", "event_id",
    }
    if not isinstance(raw, dict) or any(not isinstance(value, str) for value in raw.values()):
        raise ValueError("event fields must be strings; omit unknown optional values")
    unknown = set(raw) - allowed
    if unknown:
        raise ValueError(f"unknown event fields: {', '.join(sorted(unknown))}")
    event = {key: raw.get(key) for key in allowed}
    event["lead_key"] = clean_text(event["lead_key"])
    if not event["lead_key"]:
        raise ValueError("lead_key is required")
    if event["event_type"] not in EVENT_TYPES:
        raise ValueError("invalid event_type")
    if event["actor"] not in ACTORS:
        raise ValueError("invalid actor")
    if event["evidence_state"] not in EVIDENCE_STATES:
        raise ValueError("invalid evidence_state")
    if event["event_type"] == "dm_drafted" and event["evidence_state"] != "draft":
        raise ValueError("dm_drafted requires evidence_state=draft")
    if event["event_type"] in OUTBOUND_TYPES and event["evidence_state"] == "draft":
        raise ValueError("sent events cannot use draft evidence")
    event["occurred_at"] = parse_datetime(str(event["occurred_at"] or ""))
    if event["next_action_at"]:
        event["next_action_at"] = parse_datetime(str(event["next_action_at"]))
    if "phase" in raw and event["phase"] not in PHASES:
        raise ValueError("invalid phase")
    if "conversion_substate" in raw and event["conversion_substate"] not in SUBSTATES:
        raise ValueError("invalid conversion_substate")
    event["quality"] = raw.get("quality", "sin_clasificar")
    if event["quality"] not in QUALITIES:
        raise ValueError("invalid quality")
    message_text = clean_text(event.pop("message_text", None))
    message_fingerprint = clean_text(event.get("message_fingerprint"))
    if message_text:
        message_fingerprint = hashlib.sha256(message_text.casefold().encode("utf-8")).hexdigest()
    event["message_fingerprint"] = message_fingerprint
    for key in (
        "display_name", "source_kind", "source_ref", "objection", "next_action", "reason_code"
    ):
        event[key] = clean_text(event.get(key))
    identity_type = "outbound_sent" if event["event_type"] in OUTBOUND_TYPES else event["event_type"]
    explicit_id = clean_text(event.get("event_id"))
    if "event_id" in raw and not explicit_id:
        raise ValueError("event_id cannot be blank")
    if identity_type in {"outbound_sent", "inbound_received", "dm_drafted"} and not (explicit_id or message_fingerprint):
        raise ValueError("message events require a stable event_id or message fingerprint")
    canonical = {"lead_key": event["lead_key"], "event_type": identity_type}
    if explicit_id:
        canonical["platform_event_id"] = explicit_id
    else:
        canonical.update(occurred_at=event["occurred_at"], message_fingerprint=message_fingerprint)
        if identity_type not in {"outbound_sent", "inbound_received", "dm_drafted"}:
            canonical.update(objection=event["objection"], reason_code=event["reason_code"])
    event["event_id"] = ("v2p:" if explicit_id else "v2f:") + hashlib.sha256(
        json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return event


def record_events(db: sqlite3.Connection, raw_events: Iterable[dict[str, Any]]) -> dict[str, int]:
    # Validate the whole batch before starting any mutation.
    events = [validate_event(raw) for raw in raw_events]
    inserted = duplicates = 0
    now = datetime.now(timezone.utc).isoformat()
    fields = ("event_id", "lead_key", "event_type", "occurred_at", "actor", "evidence_state",
              "message_fingerprint", "source_kind", "source_ref", "phase", "conversion_substate",
              "quality", "objection", "next_action", "next_action_at", "reason_code")
    with db:
        for event in events:
            db.execute("INSERT OR IGNORE INTO leads (lead_key,updated_at) VALUES (?,?)", (event["lead_key"], now))
            old = db.execute("SELECT * FROM events WHERE event_id=?", (event["event_id"],)).fetchone()
            if old:
                if old["occurred_at"] != event["occurred_at"] or old["message_fingerprint"] != event["message_fingerprint"]:
                    raise ValueError("Conflicting evidence for stable event_id; reconcile explicitly")
                evidence = "verified" if "verified" in (old["evidence_state"], event["evidence_state"]) else old["evidence_state"]
                kind = "followup_sent" if "followup_sent" in (old["event_type"], event["event_type"]) else old["event_type"]
                db.execute("UPDATE events SET evidence_state=?, event_type=? WHERE event_id=?", (evidence, kind, event["event_id"]))
                duplicates += 1
            else:
                db.execute(f"INSERT INTO events ({','.join(fields)},recorded_at) VALUES ({','.join('?' for _ in range(len(fields)+1))})",
                           (*[event[key] for key in fields], now))
                inserted += 1
            if event["display_name"]:
                db.execute("UPDATE leads SET display_name=? WHERE lead_key=?", (event["display_name"], event["lead_key"]))
        # Rebuild only touched leads, in occurrence order, never ingestion order.
        state_fields = ("source_kind", "source_ref", "phase", "conversion_substate", "quality", "objection", "next_action", "next_action_at")
        normalized, _ = normalized_events(db)
        for key in {event["lead_key"] for event in events}:
            state = dict.fromkeys(state_fields)
            state["quality"] = "sin_clasificar"
            rows = (row for row in normalized if row["lead_key"] == key)
            for row in rows:
                for field in state_fields:
                    if row[field] is not None and not (field == "quality" and row[field] == "sin_clasificar"):
                        state[field] = row[field]
            db.execute(f"UPDATE leads SET {','.join(field+'=?' for field in state_fields)},updated_at=? WHERE lead_key=?",
                       (*[state[field] for field in state_fields], now, key))
    return {"inserted": inserted, "duplicates": duplicates}


def load_json(source: str) -> list[dict[str, Any]]:
    text = sys.stdin.read() if source == "-" else Path(source).read_text(encoding="utf-8")
    data = json.loads(text)
    if isinstance(data, dict):
        return [data]
    if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
        raise ValueError("input must be one event object or a list of event objects")
    return data


def get_lead(db: sqlite3.Connection, lead_key: str) -> dict[str, Any]:
    lead = db.execute("SELECT * FROM leads WHERE lead_key=?", (lead_key,)).fetchone()
    events = db.execute(
        "SELECT * FROM events WHERE lead_key=? ORDER BY occurred_at DESC LIMIT 20", (lead_key,)
    ).fetchall()
    return {
        "lead": dict(lead) if lead else None,
        "recent_events": [dict(row) for row in events],
    }


def scalar(db: sqlite3.Connection, sql: str, params: tuple[Any, ...]) -> int:
    return int(db.execute(sql, params).fetchone()[0])


def normalized_events(db: sqlite3.Connection) -> tuple[list[dict[str, Any]], int]:
    """Collapse exact fallback identities on read; preserve distinct platform IDs."""
    grouped = {}
    unknown_dates = 0
    business_zone = ZoneInfo("America/Montevideo")
    for row in db.execute("SELECT * FROM events WHERE evidence_state IN ('observed','verified') ORDER BY recorded_at,event_id"):
        item = dict(row)
        try:
            item["instant"] = datetime.fromisoformat(parse_datetime(item["occurred_at"]))
        except ValueError:
            unknown_dates += 1
            continue
        item["day"] = item["instant"].astimezone(business_zone).date().isoformat()
        kind = "outbound_sent" if item["event_type"] in OUTBOUND_TYPES else item["event_type"]
        if item["event_id"].startswith("v2p:"):
            identity = ("platform", item["event_id"])
        elif kind in {"outbound_sent", "inbound_received"} and not item["message_fingerprint"]:
            # Never infer that two textless legacy messages were one bubble.
            identity = ("unresolved", item["event_id"])
        else:
            identity = (item["lead_key"], kind, item["instant"], item["message_fingerprint"],
                        item["objection"] if kind not in OUTBOUND_TYPES | {"inbound_received"} else None,
                        item["reason_code"] if kind not in OUTBOUND_TYPES | {"inbound_received"} else None)
        prior = grouped.get(identity)
        if prior is None:
            grouped[identity] = item
        else:
            if item["evidence_state"] == "verified":
                prior["evidence_state"] = "verified"
            if item["event_type"] == "followup_sent":
                prior["event_type"] = "followup_sent"
    rows = sorted(grouped.values(), key=lambda item: (item["instant"], item["event_id"]))
    return rows, unknown_dates


def eod_report(db: sqlite3.Connection, target_date: str) -> dict[str, Any]:
    date.fromisoformat(target_date)
    rows, unknown_dates = normalized_events(db)
    today = [item for item in rows if item["day"] == target_date]
    outbound = [item for item in today if item["event_type"] in OUTBOUND_TYPES]
    sent_unique = len({item["lead_key"] for item in outbound})
    outbound_bubbles = len(outbound)
    followups = len({item["lead_key"] for item in outbound if item["event_type"] == "followup_sent"})
    same_day, late = set(), set()
    previous_outbound = {}
    for item in rows:
        key = item["lead_key"]
        if item["event_type"] == "inbound_received" and item["day"] == target_date:
            prior = previous_outbound.get(key)
            if prior and prior["instant"] < item["instant"]:
                (same_day if prior["day"] == target_date else late).add(key)
        if item["event_type"] in OUTBOUND_TYPES:
            previous_outbound[key] = item
    # Categories are disjoint contacts; same-day response takes precedence.
    responded, late_responses = len(same_day), len(late - same_day)
    event_counts = {kind: len({item["lead_key"] for item in today if item["event_type"] == kind})
                    for kind in ("booking_confirmed", "disqualified", "operational_block")}
    touched = {item["lead_key"] for item in today if item["event_type"] in OUTBOUND_TYPES | {"inbound_received"}}
    historical_quality = {key: "sin_clasificar" for key in touched}
    for item in rows:
        if item["day"] <= target_date and item["lead_key"] in touched and item["quality"] not in (None, "sin_clasificar"):
            historical_quality[item["lead_key"]] = item["quality"]
    quality = {key: 0 for key in ("alta", "media", "baja", "sin_clasificar")}
    quality.update(Counter(historical_quality.values()))
    objection_contacts = {}
    for item in today:
        if item["event_type"] == "objection_observed":
            objection_contacts.setdefault(item["objection"] or "sin_clasificar", set()).add(item["lead_key"])
    objections = {key: len(value) for key, value in sorted(objection_contacts.items())}
    legacy = db.execute("PRAGMA user_version").fetchone()[0] != 2
    coverage = {"status": "partial", "timezone": "America/Montevideo", "legacy_reconciliation_required": legacy,
                "events_with_unknown_date": unknown_dates,
                "note": "Cobertura parcial: solo evidencia registrada; cero no demuestra ausencia de actividad externa."}
    quality_text = ", ".join(f"{key}: {quality[key]}" for key in ("alta", "media", "baja", "sin_clasificar"))
    objection_text = ", ".join(f"{key}: {value}" for key, value in objections.items()) or "Sin objeciones registradas"
    comments = (
        f"{coverage['note']} "
        f"Conciliación histórica requerida: {legacy}. Eventos sin fecha válida: {unknown_dates}. "
        f"Burbujas verificables: {outbound_bubbles}. Respuestas tardías: {late_responses}. "
        f"Reservas confirmadas: {event_counts['booking_confirmed']}. "
        f"Descartados: {event_counts['disqualified']}. Bloqueos operativos: {event_counts['operational_block']}."
    )
    return {
        "date": target_date,
        "coverage": coverage,
        "metrics": {
            "messages_sent_unique_contacts": sent_unique,
            "outbound_bubbles": outbound_bubbles,
            "responded_same_day_cohort": responded,
            "late_responses": late_responses,
            "followups_unique_contacts": followups,
            **event_counts,
        },
        "quality": quality,
        "objections": objections,
        "form": {
            "FECHA DE HOY": datetime.strptime(target_date, "%Y-%m-%d").strftime("%d/%m/%Y"),
            "¿Cuántos mensajes enviaste?": str(sent_unique),
            "¿Cuántos respondieron?": str(responded),
            "¿Cuántos seguimientos realizaste?": str(followups),
            "CALIDAD de los LEADS de hoy": quality_text,
            "Objeciones comunes por las cuales no agendas llamada": objection_text,
            "¿Cómo estás de energía hoy?": "Pendiente de Maxi",
            "Comentarios extras - referidos al setteo": comments,
            "extra… (cómo te sentiste hoy?)": "Pendiente de Maxi",
        },
    }


def print_form(report: dict[str, Any]) -> None:
    print(f"EOD {report['date']} — BORRADOR PARA REVISIÓN")
    for label, value in report["form"].items():
        print(f"\n{label}\n{value}")
    print("\nNo se envió ningún formulario.")


def self_test() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        db = connect(Path(tmp) / "test.sqlite3")
        try:
            events = [
                {"lead_key": "ana", "event_type": "outbound_sent", "occurred_at": "2026-09-03T10:00:00-03:00", "actor": "agent", "evidence_state": "verified", "message_text": "hola", "quality": "alta"},
                {"lead_key": "ana", "event_type": "outbound_sent", "occurred_at": "2026-09-03T10:00:00-03:00", "actor": "agent", "evidence_state": "verified", "message_text": "hola", "quality": "alta"},
                {"lead_key": "ana", "event_type": "inbound_received", "occurred_at": "2026-09-03T10:05:00-03:00", "actor": "lead", "evidence_state": "observed", "message_text": "buenas"},
                {"lead_key": "bruno", "event_type": "outbound_sent", "occurred_at": "2026-09-02T19:00:00-03:00", "actor": "maximo", "evidence_state": "observed", "message_text": "ayer"},
                {"lead_key": "bruno", "event_type": "inbound_received", "occurred_at": "2026-09-03T11:00:00-03:00", "actor": "lead", "evidence_state": "observed", "message_text": "hoy", "quality": "media"},
                {"lead_key": "carla", "event_type": "followup_sent", "occurred_at": "2026-09-03T12:00:00-03:00", "actor": "maximo", "evidence_state": "observed", "message_text": "seguimiento"},
                {"lead_key": "carla", "event_type": "objection_observed", "occurred_at": "2026-09-03T12:10:00-03:00", "actor": "lead", "evidence_state": "observed", "objection": "tiempo"},
                {"lead_key": "draft", "event_type": "dm_drafted", "occurred_at": "2026-09-03T13:00:00-03:00", "actor": "agent", "evidence_state": "draft", "message_text": "no cuenta"},
            ]
            result = record_events(db, events)
            assert result == {"inserted": 7, "duplicates": 1}, result
            report = eod_report(db, "2026-09-03")
            assert report["metrics"]["messages_sent_unique_contacts"] == 2, report
            assert report["metrics"]["outbound_bubbles"] == 2, report
            assert report["metrics"]["responded_same_day_cohort"] == 1, report
            assert report["metrics"]["late_responses"] == 1, report
            assert report["metrics"]["followups_unique_contacts"] == 1, report
            assert report["objections"] == {"tiempo": 1}, report
        finally:
            db.close()
    print("crm tracker self-test: ok")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=default_db_path())
    sub = parser.add_subparsers(dest="command", required=True)
    record = sub.add_parser("record")
    record.add_argument("--input", required=True)
    lead = sub.add_parser("lead")
    lead.add_argument("--lead-key", required=True)
    eod = sub.add_parser("eod")
    eod.add_argument("--date", default=datetime.now(ZoneInfo("America/Montevideo")).date().isoformat())
    eod.add_argument("--format", choices=("json", "form"), default="form")
    sub.add_parser("self-test")
    args = parser.parse_args()
    if args.command == "self-test":
        self_test()
        return 0
    db = connect(args.db, readonly=args.command in {"lead", "eod"})
    try:
        if args.command == "record":
            print(json.dumps(record_events(db, load_json(args.input)), ensure_ascii=False, indent=2))
        elif args.command == "lead":
            print(json.dumps(get_lead(db, args.lead_key), ensure_ascii=False, indent=2))
        elif args.command == "eod":
            report = eod_report(db, args.date)
            if args.format == "json":
                print(json.dumps(report, ensure_ascii=False, indent=2))
            else:
                print_form(report)
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, json.JSONDecodeError, OSError, sqlite3.Error, ZoneInfoNotFoundError) as exc:
        print(f"crm tracker error: {exc}", file=sys.stderr)
        raise SystemExit(2)
