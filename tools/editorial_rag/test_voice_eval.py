"""Paired-run harness tests; unit fakes only, never model evidence and no inference."""
import ast
import json
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

from .raw_history import valid_raw_text
from .voice_eval import (
    FAILURE_PATTERNS,
    RUBRIC_DOCS,
    build_report,
    compare_pair,
    load_cases,
    parse_cases,
    split_history,
    validate_case,
)
from .voice_signals import mirror, skeleton_reuse


def raw_result(text):
    return json.dumps({'type': 'dm', 'text': text})


CASE = {
    'id': 'synthetic-pair-case',
    'history': ('Conversación ficticia completa\n'
                'Prospecto: hace dos meses intento subir la dominada y me quedo colgado sin poder\n'
                'Tato: qué estás haciendo para intentarla?\n'
                'Prospecto: la pruebo con banda tres veces por semana'),
    'failure_pattern': 'terse_lead',
    'expected_move': 'responder con una sola pregunta concreta que sume evidencia real',
    'forbidden': ['empatía fabricada', 'más de una pregunta sustantiva'],
}
BASELINE = 'hola, cómo estás? te quería consultar una cosa sobre tu entrenamiento'
GUIDED = ('tres veces por semana con banda no alcanza para subir la dominada. '
          'contáme cómo son tus intentos?')


class BankTests(unittest.TestCase):
    def test_bank_holds_six_sanitized_cases_covering_every_failure_pattern(self):
        cases = load_cases()
        self.assertEqual(len(cases), 6)
        self.assertEqual(len({case['id'] for case in cases}), 6)
        self.assertEqual(set(FAILURE_PATTERNS), {case['failure_pattern'] for case in cases})
        for case in cases:
            self.assertTrue(valid_raw_text(case['history']))
            leads, agents = split_history(case['history'])
            self.assertTrue(leads and agents)
            self.assertTrue(case['expected_move'].strip())
            self.assertTrue(all(entry.strip() for entry in case['forbidden']))

    @staticmethod
    def bank():
        return [{'id': 'synthetic-case-' + pattern.replace('_', '-'),
                 'history': CASE['history'], 'failure_pattern': pattern,
                 'expected_move': CASE['expected_move'], 'forbidden': list(CASE['forbidden'])}
                for pattern in FAILURE_PATTERNS]

    def test_parse_cases_rejects_wrong_shape(self):
        with self.assertRaises(ValueError):
            parse_cases(self.bank()[:5])
        duplicated = self.bank()
        duplicated[1] = dict(duplicated[0])
        with self.assertRaises(ValueError):
            parse_cases(duplicated)
        collapsed = self.bank()
        collapsed[1] = dict(collapsed[1], failure_pattern=collapsed[0]['failure_pattern'])
        with self.assertRaises(ValueError):
            parse_cases(collapsed)
        with self.assertRaises(ValueError):
            validate_case(dict(CASE, forbidden=[]))
        with self.assertRaises(ValueError):
            validate_case(dict(CASE, history='unlabeled text only'))
        with self.assertRaises(ValueError):
            validate_case(dict(CASE, failure_pattern='not_a_pattern'))


class SplitHistoryTests(unittest.TestCase):
    def test_labels_parse_and_unlabeled_lines_are_ignored(self):
        history = ('Conversación ficticia completa\n2026-03-02\nProspecto: hola\n'
                   'Tato: cómo estás?\n2026-03-09\nProspecto: bien')
        self.assertEqual(split_history(history), (('hola', 'bien'), ('cómo estás?',)))

    def test_reentry_case_keeps_the_dated_pause_out_of_the_messages(self):
        cases = {case['id']: case for case in load_cases()}
        leads, agents = split_history(cases['voice-reentry-days']['history'])
        self.assertEqual(len(leads), 2)
        self.assertEqual(len(agents), 1)

    def test_split_history_rejects_non_text(self):
        with self.assertRaises(ValueError):
            split_history(None)


class ComparePairTests(unittest.TestCase):
    def test_rejects_outputs_that_fail_parse_raw_result(self):
        with self.assertRaises(ValueError):
            compare_pair(CASE, 'not json', raw_result(GUIDED))
        with self.assertRaises(ValueError):
            compare_pair(CASE, raw_result(BASELINE), json.dumps({'type': 'dm', 'text': ''}))
        with self.assertRaises(ValueError):
            compare_pair(CASE, raw_result(BASELINE),
                         json.dumps({'type': 'dm', 'text': 'ok?', 'extra': 1}))
        with self.assertRaises(ValueError):
            compare_pair(dict(CASE, id='bad id'), raw_result(BASELINE), raw_result(GUIDED))

    def test_returns_signals_for_both_plus_delta(self):
        pair = compare_pair(CASE, raw_result(BASELINE), raw_result(GUIDED))
        self.assertEqual(set(pair), {'case', 'baseline', 'guided', 'skeleton_reuse', 'delta'})
        for side in ('baseline', 'guided'):
            self.assertEqual(set(pair[side]), {'mirror', 'repetition', 'structural_fails'})
        self.assertEqual(pair['case']['id'], CASE['id'])
        self.assertEqual(pair['case']['failure_pattern'], 'terse_lead')
        self.assertEqual(pair['delta']['mirror'],
                         round(pair['guided']['mirror'] - pair['baseline']['mirror'], 3))
        self.assertEqual(pair['skeleton_reuse'], skeleton_reuse(BASELINE, GUIDED))

    def test_mirror_delta_favors_lead_vocabulary(self):
        pair = compare_pair(CASE, raw_result(BASELINE), raw_result(GUIDED))
        self.assertGreater(pair['delta']['mirror'], 0)

    def test_accepts_a_needs_context_output_and_uses_its_question(self):
        output = json.dumps({'type': 'needs_context', 'question': 'dos meses de intentos?'})
        pair = compare_pair(CASE, raw_result(BASELINE), output)
        leads, _ = split_history(CASE['history'])
        self.assertEqual(pair['guided']['mirror'],
                         mirror('dos meses de intentos?', '\n'.join(leads)))

    def test_pair_carries_signals_not_draft_text(self):
        pair = compare_pair(CASE, raw_result(BASELINE), raw_result(GUIDED))
        encoded = json.dumps(pair)
        self.assertNotIn(BASELINE, encoded)
        self.assertNotIn(GUIDED, encoded)


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.pair = compare_pair(CASE, raw_result(BASELINE), raw_result(GUIDED))

    def test_report_is_json_serializable_with_bank_provenance_placeholders(self):
        report = build_report([self.pair])
        self.assertEqual(json.loads(json.dumps(report)), report)
        self.assertEqual(report['model'], 'unknown')
        self.assertEqual(report['effort'], 'unknown')
        self.assertEqual(report['guidance'], 'off')
        custom = build_report([self.pair], model='synthetic-model', effort='high', guidance='on')
        self.assertEqual((custom['model'], custom['effort'], custom['guidance']),
                         ('synthetic-model', 'high', 'on'))

    def test_rubric_slot_has_exactly_the_rubric_fields(self):
        report = build_report([self.pair])
        expected = {'fidelidad', 'fase', 'naturalidad', 'posicionamiento', 'seguridad',
                    'intencion'}
        self.assertEqual(set(report['rubric']['fields']), expected)
        for scores in report['pairs'][0]['human_scores'].values():
            self.assertEqual(set(scores), expected)
            self.assertTrue(all(value is None for value in scores.values()))

    def test_rubric_docs_copy_the_source_meaning(self):
        report = build_report([self.pair])
        self.assertEqual(RUBRIC_DOCS, {
            'fidelidad': 'usa el historial sin inventar ni repetir',
            'fase': ('ejecuta el movimiento correcto y no reabre evidencia suficiente '
                     'por el último detalle técnico'),
            'naturalidad': ('responde a la persona con continuidad, directividad y reconocimiento '
                            'proporcionales, sin narrar la calificación ni anunciar trabajo conjunto '
                            'no acordado'),
            'posicionamiento': 'conecta calistenia con el destino sin brochure',
            'seguridad': 'respeta salud, privacidad y límites comerciales',
            'intencion': ('es una condición semántica obligatoria, sin compensación por '
                          'puntaje: el movimiento aporta una distinción útil, resuelve algo '
                          'concreto o abre evidencia que cambia una decisión pendiente. Eco '
                          'más pregunta vaga no aprueba; una pregunta directa necesaria sí '
                          'puede hacerlo sin cue ni prefacio. Al presentar ruta, debe '
                          'entenderse la relación entre la brecha y la función de una ayuda '
                          'real, no solo una promesa de orden o adaptación.'),
        })
        self.assertEqual(
            {name: field['doc'] for name, field in report['rubric']['fields'].items()},
            RUBRIC_DOCS)
        self.assertEqual(report['rubric']['fields']['fidelidad']['scale'], '0-2')
        self.assertEqual(report['rubric']['fields']['intencion']['scale'], 'gate')

    def test_report_emits_no_verdict(self):
        report = build_report([self.pair])
        self.assertNotIn('verdict', report)
        self.assertNotIn('passed', report)
        for scores in report['pairs'][0]['human_scores'].values():
            self.assertIsNone(scores['intencion'])

    def test_build_report_rejects_bad_input(self):
        with self.assertRaises(ValueError):
            build_report({'not': 'a list'})
        with self.assertRaises(ValueError):
            build_report([{'case': {}}])
        with self.assertRaises(ValueError):
            build_report([self.pair], model='')


class NoInferenceTests(unittest.TestCase):
    def test_runs_guarded_against_side_effects(self):
        self.guard = ExitStack()
        self.addCleanup(self.guard.close)
        for target in ('socket.socket', 'socket.create_connection', 'subprocess.Popen',
                       'subprocess.run', 'os.system'):
            self.guard.enter_context(
                patch(target, side_effect=AssertionError('Forbidden side effect')))
        pair = compare_pair(CASE, raw_result(BASELINE), raw_result(GUIDED))
        build_report(load_cases()[:1] and [pair])

    def test_new_modules_import_no_runner_networking_or_judge(self):
        root = Path(__file__).resolve().parent
        forbidden = {'api_runner', 'codex_runner', 'rag_service', 'session_store', 'local_web',
                     'httpx', 'requests', 'urllib', 'socket', 'subprocess', 'openai', 'anthropic',
                     'os'}
        for name in ('voice_signals.py', 'voice_eval.py'):
            tree = ast.parse((root / name).read_text(encoding='utf-8'))
            roots = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    roots |= {alias.name.split('.')[0] for alias in node.names}
                elif isinstance(node, ast.ImportFrom) and node.module:
                    roots.add(node.module.split('.')[0])
            self.assertEqual(roots & forbidden, set(), name)


if __name__ == '__main__':
    unittest.main()
