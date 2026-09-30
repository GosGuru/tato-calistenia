"""Pruebas sintéticas; no ejecutan modelos ni guardan respuestas."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

import dm_guard as guard

ROOT = Path(__file__).resolve().parent


def payload(text="qué querés mejorar?", closure="active", accepted=False):
    return {"version": 1, "text": text, "closure": closure, "call_accepted": accepted}


class GuardTests(unittest.TestCase):
    def check(self, data):
        return guard.evaluate(data)

    def test_active(self):
        self.assertEqual(self.check(payload())[0], 0)
        for text in ("seguimos", "qué buscás? seguimos", "uno? dos?"):
            with self.subTest(text=text):
                self.assertEqual(self.check(payload(text))[0], 1)

    def test_each_terminal_reason(self):
        reasons = {
            "minor",
            "rejection",
            "investment_impossible",
            "incompatibility",
            "safety",
            "followup_limit",
            "booking_confirmed",
        }
        self.assertEqual(guard.TERMINAL, reasons)
        for reason in reasons:
            with self.subTest(reason=reason):
                self.assertEqual(self.check(payload("gracias", reason))[0], 0)
                self.assertEqual(self.check(payload("seguimos?", reason))[0], 1)

    def test_schema(self):
        invalid = [None, [], {}, 1]
        for key, values in {
            "version": [True, 1.0, 2, "1"],
            "text": [None, 3, [], "", "  ", "x" * 4097],
            "closure": [None, [], "terminal", "unknown"],
            "call_accepted": [0, 1, "true", None],
        }.items():
            for value in values:
                data = payload()
                data[key] = value
                invalid.append(data)
        invalid += [dict(payload(), extra=True)]
        for key in payload():
            data = payload()
            del data[key]
            invalid.append(data)
        for data in invalid:
            with self.subTest(data_type=type(data).__name__):
                self.assertEqual(self.check(data)[0], 2)

    def test_punctuation(self):
        for text in (
            "¿seguimos?",
            "¡hola! seguimos?",
            "```seguimos?```",
            "~~~\nseguimos?",
            "dato: seguimos?",
        ):
            self.assertEqual(self.check(payload(text))[0], 1)

    def test_agenda(self):
        good = guard.AGENDA + "\nelegí día y hora, me avisás?"
        self.assertEqual(self.check(payload(good, accepted=True))[0], 0)
        self.assertEqual(self.check(payload(good))[0], 1)
        for link in (
            guard.AGENDA + "/",
            guard.AGENDA + "?x=1",
            "http://cal.com/tato-ramon/reunion-auditoria",
            "https://cal.com/otra",
            "cal.com/tato-ramon/reunion-auditoria",
        ):
            self.assertEqual(
                self.check(payload(link + "\nseguimos?", accepted=True))[0], 1
            )
        self.assertEqual(self.check(payload("acá " + good, accepted=True))[0], 1)
        self.assertEqual(
            self.check(payload(guard.AGENDA, "booking_confirmed", True))[0], 3
        )

    def test_price_not_repetitions(self):
        for text in ("300 repeticiones, seguimos?", "1300 repeticiones, seguimos?"):
            self.assertEqual(self.check(payload(text))[0], 0)
        for price in ("USD 300", "300 USD", "$300", "300 dólares", "US$ 300.00"):
            self.assertEqual(self.check(payload(price + ", seguimos?"))[0], 1)

    def test_manual_resources(self):
        for link in ("https://example.org/guia", "www.example.org", "example.org/guia"):
            code, result = self.check(payload(link + "\nte llegó?"))
            self.assertEqual(code, 3)
            self.assertEqual(result["status"], "manual_review")

    def test_envelope_no_echo(self):
        for data in (payload(), payload("SYNTHETIC_PRIVATE: seguimos?"), None):
            _, result = self.check(data)
            self.assertTrue(result["semantic_review_required"])
            self.assertEqual(result["enforcement"], "manual_shadow")
            self.assertNotIn("SYNTHETIC_PRIVATE", json.dumps(result))

    def test_cli_fail_closed_and_no_outputs(self):
        before = sorted(p.name for p in ROOT.iterdir())
        inputs = [
            b"{",
            b"[]",
            b"\xff",
            b" " * 16385,
            b'{"version":NaN}',
            b'{"version":1,"version":1}',
            b"[" * 1200,
            json.dumps(payload()).encode(),
        ]
        for raw in inputs:
            run = subprocess.run(
                [sys.executable, "-B", str(ROOT / "dm_guard.py")],
                input=raw,
                capture_output=True,
                check=False,
            )
            result = json.loads(run.stdout)
            self.assertEqual(run.stderr, b"")
            self.assertTrue(result["semantic_review_required"])
            self.assertEqual(run.returncode, 0 if raw == inputs[-1] else 2)
        self.assertEqual(before, sorted(p.name for p in ROOT.iterdir()))

    def test_stability_pack_structure_only(self):
        pack = json.loads((ROOT / "stability_cases.json").read_text(encoding="utf-8"))
        self.assertEqual(set(pack), {"version", "execution", "pairs"})
        self.assertEqual(pack["version"], 1)
        self.assertEqual(pack["execution"], "manual_only_no_model_results")
        self.assertTrue(4 <= len(pack["pairs"]) <= 6)
        ids = set()
        for pair in pack["pairs"]:
            self.assertEqual(
                set(pair), {"id", "a", "b", "expectation", "counterexample"}
            )
            for value in pair.values():
                self.assertIsInstance(value, str)
                self.assertTrue(value.strip())
            self.assertNotIn(pair["id"], ids)
            ids.add(pair["id"])


if __name__ == "__main__":
    unittest.main()
