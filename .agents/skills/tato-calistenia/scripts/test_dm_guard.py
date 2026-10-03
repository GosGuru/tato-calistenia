#!/usr/bin/env python3
"""
test_dm_guard.py — Tests for dm_guard.py.

Runs via subprocess with synthetic JSON inputs.
No private data, no network, no file persistence.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
import unittest
from pathlib import Path

SCRIPT = Path(__file__).parent / "dm_guard.py"

# ── Helper ────────────────────────────────────────────────────────────────────

_BASE_STATE = {
    "call_accepted": False,
    "followup_count": 0,
    "explicit_rejection": False,
    "movement": "prospect",
    "closure_reason": None,
}


def _run(payload: dict) -> tuple[int, dict]:
    raw = json.dumps(payload, ensure_ascii=False).encode()
    proc = subprocess.run(
        [sys.executable, "-B", str(SCRIPT)],
        input=raw,
        capture_output=True,
    )
    try:
        out = json.loads(proc.stdout.decode("utf-8"))
    except json.JSONDecodeError:
        out = {"_raw": proc.stdout.decode("utf-8", errors="replace")}
    return proc.returncode, out


def _state(**overrides) -> dict:
    return {**_BASE_STATE, **overrides}


def _ok_payload(dm: str, **state_overrides) -> dict:
    return {"mode": "prospect_dm", "dm": dm, "state": _state(**state_overrides)}


# ── RED: tests written before implementation; now GREEN ───────────────────────


class TestInputErrors(unittest.TestCase):
    """Malformed inputs must fail closed with exit code 2."""

    def test_empty_input(self):
        proc = subprocess.run(
            [sys.executable, "-B", str(SCRIPT)],
            input=b"",
            capture_output=True,
        )
        self.assertEqual(proc.returncode, 2)

    def test_not_json(self):
        proc = subprocess.run(
            [sys.executable, "-B", str(SCRIPT)],
            input=b"not json at all",
            capture_output=True,
        )
        self.assertEqual(proc.returncode, 2)

    def test_unsupported_mode(self):
        code, out = _run({"mode": "eod_review", "dm": "ok?", "state": _state()})
        self.assertEqual(code, 2)
        self.assertFalse(out.get("mechanical_pass", True))

    def test_unknown_top_level_field(self):
        payload = {**_ok_payload("hola?"), "secret_flag": True}
        code, _ = _run(payload)
        self.assertEqual(code, 2)

    def test_dm_too_long(self):
        code, _ = _run(_ok_payload("x" * 2001))
        self.assertEqual(code, 2)

    def test_state_missing_field(self):
        bad_state = {k: v for k, v in _BASE_STATE.items() if k != "followup_count"}
        code, _ = _run({"mode": "prospect_dm", "dm": "ok?", "state": bad_state})
        self.assertEqual(code, 2)

    def test_state_bad_type(self):
        code, _ = _run(
            {"mode": "prospect_dm", "dm": "ok?", "state": _state(followup_count="zero")}
        )
        self.assertEqual(code, 2)

    def test_state_unknown_movement(self):
        code, _ = _run(_ok_payload("ok?", movement="spin"))
        self.assertEqual(code, 2)

    def test_state_negative_followup(self):
        code, _ = _run(_ok_payload("ok?", followup_count=-1))
        self.assertEqual(code, 2)

    def test_resource_url_not_https(self):
        payload = {
            **_ok_payload("ok?"),
            "allowed_resource_urls": ["http://insecure.example.com/video"],
        }
        code, _ = _run(payload)
        self.assertEqual(code, 2)

    def test_oversized_input(self):
        """Input larger than 16 384 bytes must be rejected."""
        raw = json.dumps({"mode": "prospect_dm", "dm": "a" * 100, "state": _BASE_STATE}).encode()
        # Pad to exceed limit
        padded = raw + b" " * (16_385 - len(raw) + 1)
        proc = subprocess.run(
            [sys.executable, "-B", str(SCRIPT)],
            input=padded,
            capture_output=True,
        )
        self.assertEqual(proc.returncode, 2)


class TestPassingDMs(unittest.TestCase):
    """Well-formed DMs that should pass all mechanical checks."""

    def test_simple_prospect_dm(self):
        code, out = _run(_ok_payload("qué te llevó a escribirme?"))
        self.assertEqual(code, 0)
        self.assertTrue(out["mechanical_pass"])
        self.assertTrue(out["semantic_review_required"])

    def test_dm_with_name(self):
        code, out = _run(_ok_payload("Lucas, qué objetivo tenés en mente?"))
        self.assertEqual(code, 0)
        self.assertTrue(out["mechanical_pass"])

    def test_300_reps_not_flagged(self):
        """300 reps / dominadas must not trigger the internal-price check."""
        code, out = _run(_ok_payload("y hoy podés hacer 300 reps sin problema?"))
        self.assertEqual(code, 0)
        self.assertTrue(out["mechanical_pass"])
        self.assertTrue(out["checks"].get("no_internal_price"))

    def test_300_dominadas_not_flagged(self):
        code, out = _run(_ok_payload("si llegás a 300 dominadas ya estás en otro nivel?"))
        self.assertEqual(code, 0)
        self.assertTrue(out["mechanical_pass"])

    def test_agenda_url_with_accepted_call(self):
        code, out = _run(
            _ok_payload(
                "agendá acá\nhttps://cal.com/tato-ramon/reunion-auditoria\ncuándo te queda mejor?",
                call_accepted=True,
                movement="agenda",
            )
        )
        self.assertEqual(code, 0)
        self.assertTrue(out["mechanical_pass"])

    def test_resource_url_in_approved_list(self):
        """An approved resource URL should not fail the agenda_url check."""
        payload = {
            "mode": "prospect_dm",
            "dm": "mirá este video\nhttps://drive.google.com/file/d/EXAMPLE/view\nqué te parece?",
            "state": _state(movement="resource"),
            "allowed_resource_urls": ["https://drive.google.com/file/d/EXAMPLE/view"],
        }
        code, out = _run(payload)
        self.assertEqual(code, 0)
        self.assertTrue(out["mechanical_pass"])

    def test_closure_no_question_ok(self):
        """Confirmed reservation: no question required."""
        code, out = _run(
            _ok_payload(
                "genial, te espero en la reunión",
                movement="closure",
                closure_reason="reservation_confirmed",
            )
        )
        self.assertEqual(code, 0)
        self.assertTrue(out["mechanical_pass"])


class TestFailingDMs(unittest.TestCase):
    """DMs that should fail specific mechanical checks."""

    def test_empty_dm(self):
        code, out = _run(_ok_payload("   "))
        self.assertEqual(code, 1)
        self.assertFalse(out["mechanical_pass"])
        self.assertFalse(out["checks"]["nonempty"])

    def test_opening_question_mark(self):
        code, out = _run(_ok_payload("¿qué hacés hoy?"))
        self.assertEqual(code, 1)
        self.assertFalse(out["checks"]["no_opening_punctuation"])

    def test_opening_exclamation(self):
        code, out = _run(_ok_payload("¡hola! cómo estás?"))
        self.assertEqual(code, 1)
        self.assertFalse(out["checks"]["no_opening_punctuation"])

    def test_two_questions(self):
        code, out = _run(_ok_payload("cómo estás? y qué hacés?"))
        self.assertEqual(code, 1)
        self.assertFalse(out["checks"]["question_count"])

    def test_no_question_active_conversation(self):
        """Active conversation without a question is a violation."""
        code, out = _run(_ok_payload("bien, me alegra saberlo"))
        self.assertEqual(code, 1)
        self.assertFalse(out["checks"]["question_count"])

    def test_code_fence(self):
        code, out = _run(_ok_payload("mirá esto\n```python\nprint('hola')\n```\nqué ves?"))
        self.assertEqual(code, 1)
        self.assertFalse(out["checks"]["no_code_fence"])

    def test_bare_colon_in_prose(self):
        code, out = _run(_ok_payload("mi método: transformar tu cuerpo. qué buscás?"))
        self.assertEqual(code, 1)
        self.assertFalse(out["checks"]["no_bare_colon"])

    def test_colon_in_url_allowed(self):
        """Colon inside https:// URL must not trigger bare-colon check."""
        code, out = _run(
            _ok_payload(
                "agendá acá\nhttps://cal.com/tato-ramon/reunion-auditoria\ncuándo te queda mejor?",
                call_accepted=True,
                movement="agenda",
            )
        )
        self.assertTrue(out["checks"]["no_bare_colon"])

    def test_usd_300_flagged(self):
        code, out = _run(_ok_payload("el programa sale USD 300 en total. qué te parece?"))
        self.assertEqual(code, 1)
        self.assertFalse(out["checks"]["no_internal_price"])

    def test_dollar_300_flagged(self):
        code, out = _run(_ok_payload("son $300 para empezar. qué decidís?"))
        self.assertEqual(code, 1)
        self.assertFalse(out["checks"]["no_internal_price"])

    def test_300_dolares_flagged(self):
        code, out = _run(_ok_payload("el costo es 300 dólares. te interesa?"))
        self.assertEqual(code, 1)
        self.assertFalse(out["checks"]["no_internal_price"])

    def test_agenda_url_without_accepted_call(self):
        code, out = _run(
            _ok_payload(
                "agendá acá\nhttps://cal.com/tato-ramon/reunion-auditoria\ncuándo podés?",
                call_accepted=False,
                movement="agenda",
            )
        )
        self.assertEqual(code, 1)
        self.assertFalse(out["checks"]["agenda_url"])

    def test_agenda_movement_missing_url(self):
        code, out = _run(
            _ok_payload(
                "agendamos para mañana. te va bien?",
                call_accepted=True,
                movement="agenda",
            )
        )
        self.assertEqual(code, 1)
        self.assertFalse(out["checks"]["agenda_movement"])

    def test_agenda_movement_missing_question(self):
        code, out = _run(
            _ok_payload(
                "https://cal.com/tato-ramon/reunion-auditoria elegí el turno.",
                call_accepted=True,
                movement="agenda",
            )
        )
        self.assertEqual(code, 1)
        self.assertFalse(out["checks"]["agenda_movement"])

    def test_followup_cap_exceeded(self):
        code, out = _run(_ok_payload("ey, cómo vas con eso?", followup_count=2))
        self.assertEqual(code, 1)
        self.assertFalse(out["checks"]["followup_cap"])

    def test_explicit_rejection_blocked(self):
        code, out = _run(_ok_payload("dale, seguimos en contacto?", explicit_rejection=True))
        self.assertEqual(code, 1)
        self.assertFalse(out["checks"]["followup_cap"])

    def test_unapproved_url(self):
        """An https:// URL not in allowed_resource_urls and not the agenda URL fails."""
        code, out = _run(
            _ok_payload(
                "mirá este video https://example.com/random. qué pensás?",
                call_accepted=False,
            )
        )
        self.assertEqual(code, 1)
        self.assertFalse(out["checks"]["agenda_url"])

    def test_semantic_review_always_required(self):
        """Even on a full mechanical pass, semantic_review_required must be True."""
        code, out = _run(_ok_payload("qué objetivo tenés?"))
        self.assertEqual(code, 0)
        self.assertTrue(out.get("semantic_review_required"))


class TestContrastCases(unittest.TestCase):
    """Pairs that verify boundary distinctions."""

    def test_300_reps_vs_usd_300(self):
        """300 reps passes; USD 300 fails."""
        code_reps, _ = _run(_ok_payload("podés hacer 300 reps ya?"))
        code_usd, _ = _run(_ok_payload("el programa vale USD 300, te suma?"))
        self.assertEqual(code_reps, 0)
        self.assertEqual(code_usd, 1)

    def test_followup_cap_closure_exempt(self):
        """Closure movement with followup_count >= cap should still pass."""
        code, out = _run(
            _ok_payload(
                "cerramos por ahora",
                followup_count=3,
                movement="closure",
                closure_reason="followup_limit",
            )
        )
        self.assertTrue(out["checks"]["followup_cap"])

    def test_agenda_with_vs_without_accepted(self):
        dm = "agendá acá\nhttps://cal.com/tato-ramon/reunion-auditoria\ncuándo te queda mejor?"
        code_yes, _ = _run(_ok_payload(dm, call_accepted=True, movement="agenda"))
        code_no, _ = _run(_ok_payload(dm, call_accepted=False, movement="agenda"))
        self.assertEqual(code_yes, 0)
        self.assertEqual(code_no, 1)

    def test_resource_approved_vs_unapproved(self):
        resource_url = "https://drive.google.com/file/d/EXAMPLE/view"
        dm = f"mirá esto\n{resource_url}\nqué te parece?"
        payload_ok = {
            "mode": "prospect_dm",
            "dm": dm,
            "state": _state(movement="resource"),
            "allowed_resource_urls": [resource_url],
        }
        payload_fail = {
            "mode": "prospect_dm",
            "dm": dm,
            "state": _state(movement="resource"),
            "allowed_resource_urls": [],
        }
        code_ok, _ = _run(payload_ok)
        code_fail, _ = _run(payload_fail)
        self.assertEqual(code_ok, 0)
        self.assertEqual(code_fail, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
