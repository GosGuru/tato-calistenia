#!/usr/bin/env python3
"""Structural checks for the declared forward-review contract, not DM quality."""

import copy
import json
import unittest
from unittest.mock import Mock

import validate_runtime as runtime


class DirectionContractTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(
            (runtime.ASSETS / "forward-cases.json").read_text(encoding="utf-8")
        )
        self.data["rubric"]["required_full_scores"] = [
            "fidelidad",
            "fase",
            "naturalidad",
            "seguridad",
        ]
        self.data["rubric"]["required_gates"] = ["intencion"]
        self.data["rubric"]["gate_criteria"] = {
            "intencion": "La respuesta cambia una decisión pendiente desde la evidencia del caso."
        }

    def validate(self, data=None):
        source = Mock()
        source.read_text.return_value = json.dumps(self.data if data is None else data)
        errors = []
        runtime.validate_fixtures(source, errors)
        return errors

    def test_declared_contract_is_valid(self):
        self.assertEqual(self.validate(), [])

    def test_phase_cannot_be_compensated_by_other_scores(self):
        self.data["rubric"]["required_full_scores"].remove("fase")
        self.assertTrue(any("fase" in error for error in self.validate()))

    def test_intention_gate_is_required(self):
        self.data["rubric"].pop("required_gates")
        self.assertTrue(any("intención" in error for error in self.validate()))

    def test_intention_criterion_must_be_declared(self):
        for criteria in ({}, {"intencion": " "}, {"intencion": []}, None):
            with self.subTest(criteria=criteria):
                data = copy.deepcopy(self.data)
                data["rubric"]["gate_criteria"] = criteria
                self.assertTrue(
                    any("criterio" in error for error in self.validate(data))
                )

    def test_listening_pairs_are_required(self):
        for case_id in (
            "prospect-meta-numerica-ambigua",
            "prospect-meta-numerica-explicada",
            "prospect-rutina-sin-voluntad",
            "prospect-voluntad-proceso-confirmada",
            "prospect-objecion-postagenda",
            "prospect-rechazo-postagenda",
            "prospect-seleccion-no-reserva",
            "prospect-nacionalidad-no-proxy",
            "prospect-imposibilidad-postreserva",
            "prospect-emergencia-postagenda",
            "prospect-objecion-resuelta-retoma",
        ):
            with self.subTest(case_id=case_id):
                data = copy.deepcopy(self.data)
                data["cases"] = [
                    case for case in data["cases"] if case["id"] != case_id
                ]
                self.assertTrue(any(case_id in error for error in self.validate(data)))

    def test_precedence_and_modes_are_declared(self):
        text = (runtime.REFERENCES / "motor-agentico.md").read_text(encoding="utf-8")
        errors = []
        runtime.validate_decision_contract(text, errors)
        self.assertEqual(errors, [])
        for old, new in (
            ("`eod_review`, ", ""),
            ("3. Bloqueo operativo", "8. Bloqueo operativo"),
        ):
            with self.subTest(old=old):
                errors = []
                runtime.validate_decision_contract(text.replace(old, new), errors)
                self.assertTrue(errors)

    def test_human_voice_boundary_pairs_are_required(self):
        for case_id in (
            'voz-reentrada-fechada',
            'voz-continuidad-inmediata',
            'voz-auditoria-habilitada',
            'voz-auditoria-no-habilitada',
            'voz-cierre-negativo-demora',
            'voz-seguridad-demora',
            'voz-llamada-ya-aceptada',
            'voz-fecha-no-disponible',
        ):
            with self.subTest(case_id=case_id):
                data = copy.deepcopy(self.data)
                data["cases"] = [case for case in data["cases"] if case["id"] != case_id]
                self.assertTrue(any(case_id in error for error in self.validate(data)))

    def test_naturalness_criteria_require_nonblank_text(self):
        keys = ("continuidad", "directividad", "proporcionalidad", "sin_gestion_ficticia")
        for container in (None, [], "criterios"):
            with self.subTest(container=container):
                data = copy.deepcopy(self.data)
                data["rubric"]["naturalness_criteria"] = container
                self.assertTrue(any("naturalidad" in e for e in self.validate(data)))
        data = copy.deepcopy(self.data)
        data["rubric"].pop("naturalness_criteria", None)
        self.assertTrue(any("naturalidad" in e for e in self.validate(data)))
        for key in keys:
            for value in (None, [], True, " "):
                with self.subTest(key=key, value=value):
                    data = copy.deepcopy(self.data)
                    criteria = data["rubric"].setdefault(
                        "naturalness_criteria", dict.fromkeys(keys, "Semantic criterion")
                    )
                    if value is None:
                        criteria.pop(key, None)
                    else:
                        criteria[key] = value
                    self.assertTrue(any(key in e for e in self.validate(data)))

    def test_composition_contrasts_are_required(self):
        for case_id in (
            "voz-composicion-puente-util",
            "voz-composicion-directa-suficiente",
            "voz-composicion-apertura-significativa",
            "voz-composicion-gestion-no-acordada",
        ):
            with self.subTest(case_id=case_id):
                data = copy.deepcopy(self.data)
                data["cases"] = [c for c in data["cases"] if c["id"] != case_id]
                self.assertTrue(any(case_id in e for e in self.validate(data)))

    def test_direct_and_bridge_declarations_coexist_without_dm_templates(self):
        cases = {case["id"]: case for case in self.data["cases"]}
        for case_id in ("voz-composicion-puente-util", "voz-composicion-directa-suficiente"):
            with self.subTest(case_id=case_id):
                self.assertIn(case_id, cases)
                if case_id in cases:
                    self.assertEqual(cases[case_id]["mode"], "prospect_dm")
                    self.assertEqual(set(cases[case_id]), runtime.REQUIRED_FIXTURE_FIELDS)
        self.assertEqual(self.validate(), [])

    def test_output_summary_keeps_contextual_composition(self):
        text = (runtime.REFERENCES / "motor-agentico.md").read_text(encoding="utf-8")
        summary = next(
            line for line in text.splitlines()
            if line.startswith("- `contexto` a `disposicion`:")
        )
        for declaration in (
            "cuando ayude",
            "sin prefacio obligatorio",
            "una pregunta directa puede bastar",
            "reconocimiento proporcional ante una apertura significativa",
            "una sola pregunta sustantiva de dirección",
        ):
            with self.subTest(declaration=declaration):
                self.assertIn(declaration, summary)
        self.assertIn("los cierres excepcionales permanecen sin pregunta", text)

    def test_question_hard_fail_preserves_social_reentry_exception(self):
        text = (runtime.REFERENCES / "casos-calibracion.md").read_text(encoding="utf-8")
        hard_fails = text.split("## Hard fails\n", 1)[1].split("## ", 1)[0]
        self.assertNotIn("- más de una pregunta;", hard_fails)
        for declaration in (
            "más de una pregunta sustantiva",
            "saludo social de reentrada",
            "según `voz-escrita-tato.md`",
            "no cuenta como segunda pregunta de calificación",
            "sin repetir saludos ni reiniciar la fase",
            "cierres excepcionales sin pregunta",
        ):
            with self.subTest(declaration=declaration):
                self.assertIn(declaration, hard_fails)

    def test_direction_case_is_required(self):
        case_id = "prospect-impulso-no-estricto"
        self.data["cases"] = [
            case for case in self.data["cases"] if case["id"] != case_id
        ]
        self.assertTrue(any(case_id in error for error in self.validate()))


if __name__ == "__main__":
    unittest.main()
