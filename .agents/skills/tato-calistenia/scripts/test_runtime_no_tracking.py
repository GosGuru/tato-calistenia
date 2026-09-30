#!/usr/bin/env python3
"""Structural regressions for the manual-only CRM boundary; no real DB access."""

import json
import unittest
from unittest.mock import patch

import validate_runtime as runtime


class ManualTrackingBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.contents = {path.name: path.read_text(encoding="utf-8")
                         for path in runtime.VALIDATED_FILES}

    def test_runtime_passes_without_legacy_tracker(self):
        with patch.object(runtime, "validate_crm_assets", side_effect=AssertionError("legacy tracker executed")):
            self.assertEqual(runtime.validate_runtime(), [])
        self.assertNotIn(runtime.CRM_TRACKER, runtime.VALIDATED_FILES)
        self.assertNotIn(runtime.ASSETS / "crm-event.schema.json", runtime.VALIDATED_FILES)

    def test_active_contract_disallows_bookkeeping(self):
        errors = []
        runtime.validate_no_automatic_tracking(self.contents, errors)
        self.assertEqual(errors, [])
        for name in ("SKILL.md", "motor-agentico.md", "operativa-dm.md", "operativa-maseteo.md"):
            self.assertIn("sin consultar ni escribir bases" if name != "SKILL.md" else
                          "no consultar ni escribir bases", self.contents[name])

    def test_reintroduced_tracker_commands_are_rejected(self):
        for command in ("lead", "ensure", "record", "eod"):
            with self.subTest(command=command):
                contents = dict(self.contents)
                contents["motor-agentico.md"] += f"\nEjecutar crm_tracker.py {command}"
                errors = []
                runtime.validate_no_automatic_tracking(contents, errors)
                self.assertTrue(errors)

    def test_reintroduced_draft_mandate_is_rejected(self):
        contents = dict(self.contents)
        contents["SKILL.md"] += "\nRegistrar `dm_drafted` antes de responder."
        errors = []
        runtime.validate_no_automatic_tracking(contents, errors)
        self.assertTrue(errors)

    def test_unconditional_tracking_load_is_rejected(self):
        contents = dict(self.contents)
        contents["motor-agentico.md"] = contents["motor-agentico.md"].replace(
            "Siempre cargar:", "Siempre cargar:\n- `tracking-eod.md`;")
        errors = []
        runtime.validate_no_automatic_tracking(contents, errors)
        self.assertTrue(errors)

    def test_eod_preserves_nine_fields_and_approval(self):
        text = self.contents["tracking-eod.md"]
        fields = text.split("## Nueve campos del cierre", 1)[1].split("## Cierre programado", 1)[0]
        numbered = [line for line in fields.splitlines() if line[:1].isdigit()]
        self.assertEqual(len(numbered), 9)
        for marker in ("pendientes de Maxi", "cobertura parcial", "sin consultar bases automáticamente",
                       "pendiente, no se convierte en cero", "No abrir, completar ni enviar Google Forms"):
            self.assertIn(marker, text)

    def test_forward_cases_cover_prospect_batch_and_eod(self):
        fixtures = json.loads((runtime.ASSETS / "forward-cases.json").read_text(encoding="utf-8"))
        cases = {case["id"]: case for case in fixtures["cases"]}
        for key, mode in (("prospect-sin-registro-automatico", "prospect_dm"),
                          ("batch-sin-registro-automatico", "outbound_batch"),
                          ("eod-sin-evidencia", "eod_review")):
            self.assertEqual(cases[key]["mode"], mode)
            self.assertTrue(cases[key]["forbidden"])


if __name__ == "__main__":
    unittest.main()
