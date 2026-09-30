"""Fixed fictional probe; all inference mocked."""
import contextlib
import io
import json
from dataclasses import asdict, replace
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.editorial_rag import synthetic_compare as cli
from tools.editorial_rag.prototype import retrieve


class SyntheticCompareTests(unittest.TestCase):
    def invoke(self, args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(args)
        return code, out.getvalue(), err.getvalue()

    def test_default_preview_never_constructs_runner(self):
        with patch.object(cli, 'CodexSessionRunner') as runner:
            code, out, err = self.invoke([])
        runner.assert_not_called()
        self.assertEqual(code, 0)
        self.assertEqual(err, '')
        for text in ('PREVIEW', 'synthetic', 'brecha', 'current', 'editorial', 'fixture eligibility'):
            self.assertIn(text, out)
        self.assertNotIn('DRAFT', out)

    def test_help_no_inference(self):
        with patch.object(cli, 'CodexSessionRunner') as runner:
            with contextlib.redirect_stdout(io.StringIO()) as out, self.assertRaises(SystemExit) as result:
                cli.main(['--help'])
        self.assertEqual(result.exception.code, 0)
        runner.assert_not_called()
        self.assertIn('synthetic', out.getvalue())
        self.assertIn('--run-codex', out.getvalue())

    def test_fixed_complete_rules_and_case(self):
        root = Path(__file__).resolve().parents[2]
        paths = (
            '.agents/skills/tato-calistenia/SKILL.md',
            '.agents/skills/tato-calistenia/references/motor-agentico.md',
            '.agents/skills/tato-calistenia/references/voz-escrita-tato.md',
            '.agents/skills/tato-calistenia/references/operativa-dm.md',
        )
        expected = '\n\n'.join((root / p).read_bytes().decode('utf-8') for p in paths)
        self.assertEqual(cli.load_rules(), expected)
        conversation, cards = cli.synthetic_case()
        self.assertEqual(conversation.phase, 'brecha')
        self.assertEqual([m.text for m in conversation.messages if m.role == 'user'],
                         ['fuerza', 'calistenia', 'las dominadas'])
        self.assertTrue(all(m.text.startswith('entiendo') for m in conversation.messages
                            if m.role == 'assistant'))
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0].status, 'approved')

    def test_observation_inference_case(self):
        conversation, cards = cli.synthetic_case(cli.CASE_OBSERVATION_INFERENCE)
        self.assertEqual(conversation.phase, 'brecha')
        self.assertEqual(conversation.gate, 'brecha_interpretation')
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0].card_id, 'separate_observation_from_inference')
        self.assertEqual(cards[0].gate, 'brecha_interpretation')
        self.assertEqual(cards[0].status, 'approved')
        current, editorial = cli.packets(conversation, cards, cli.load_rules())
        self.assertIsNone(current.guidance)
        self.assertIsNotNone(editorial.guidance)
        self.assertEqual(editorial.guidance.card_id, 'separate_observation_from_inference')

    def test_contexto_missing_evidence_case(self):
        conversation, cards = cli.synthetic_case(cli.CASE_CONTEXTO_MISSING_EVIDENCE)
        self.assertEqual(conversation.phase, 'contexto')
        self.assertEqual(conversation.gate, 'contexto_missing_evidence')
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0].card_id, 'ask_only_missing_evidence')
        self.assertEqual(cards[0].gate, 'contexto_missing_evidence')
        self.assertEqual(cards[0].status, 'approved')
        current, editorial = cli.packets(conversation, cards, cli.load_rules())
        self.assertIsNone(current.guidance)
        self.assertIsNotNone(editorial.guidance)
        self.assertEqual(editorial.guidance.card_id, 'ask_only_missing_evidence')

    def test_disposicion_without_pressure_case(self):
        conversation, cards = cli.synthetic_case(cli.CASE_DISPOSICION_WITHOUT_PRESSURE)
        self.assertEqual(conversation.phase, 'disposicion')
        self.assertEqual(conversation.gate, 'disposition_evidence')
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0].card_id, 'respond_without_pressure')
        self.assertEqual(cards[0].gate, 'disposition_evidence')
        self.assertEqual(cards[0].status, 'approved')
        current, editorial = cli.packets(conversation, cards, cli.load_rules())
        self.assertIsNone(current.guidance)
        self.assertIsNotNone(editorial.guidance)
        self.assertEqual(editorial.guidance.card_id, 'respond_without_pressure')




    def test_success_two_calls_one_compare_no_persistence(self):
        with patch.object(cli, 'CodexSessionRunner') as factory, \
             patch.object(cli, 'compare', wraps=cli.compare) as compare, \
             patch('pathlib.Path.write_text', side_effect=AssertionError('write')), \
             patch('pathlib.Path.write_bytes', side_effect=AssertionError('write')), \
             patch('builtins.open', side_effect=AssertionError('unexpected open')):
            factory.return_value.side_effect = ['synthetic first?', 'synthetic second?']
            code, out, err = self.invoke(['--run-codex'])
        self.assertEqual((code, err), (0, ''))
        compare.assert_called_once()
        self.assertEqual(factory.return_value.call_count, 2)
        a, b = [call.args[0] for call in factory.return_value.call_args_list]
        self.assertEqual((a.variant, b.variant), ('current', 'editorial'))
        self.assertEqual(a.current_rules, b.current_rules)
        self.assertEqual(a.current_rules, cli.load_rules())
        self.assertIsNone(a.guidance)
        self.assertIsNotNone(b.guidance)
        for text in ('REAL RUN', 'synthetic', 'CURRENT DRAFT', 'EDITORIAL DRAFT',
                     'synthetic first?', 'synthetic second?', 'signals'):
            self.assertIn(text, out)

    def test_failure_never_leaks_partial_draft_or_exception(self):
        for outcomes, calls in (([RuntimeError('raw detail')], 1),
                                (['first draft marker', RuntimeError('raw detail')], 2)):
            with self.subTest(calls=calls), patch.object(cli, 'CodexSessionRunner') as factory:
                factory.return_value.side_effect = outcomes
                code, out, err = self.invoke(['--run-codex'])
            self.assertNotEqual(code, 0)
            self.assertEqual(out, '')
            self.assertEqual(factory.return_value.call_count, calls)
            self.assertIn('failed', err)
            for forbidden in ('raw detail', 'first draft marker', 'Traceback'):
                self.assertNotIn(forbidden, out + err)

    def test_ruta_cases_history_retrieval_and_rules(self):
        root = Path(__file__).resolve().parents[2]
        extra = tuple('.agents/skills/tato-calistenia/references/' + name for name in
                      ('contexto-maestro.md', 'objeciones-agenda.md'))
        expected = '\n\n'.join((root / p).read_bytes().decode('utf-8')
                               for p in cli.RULE_PATHS + extra)
        for case, card_id, gate, move in (
            ('synthetic-ruta-help-to-gap', 'connect_help_to_concrete_gap',
             'route_fit_to_gap', 'relate_help_to_gap'),
            ('synthetic-ruta-concrete-doubt', 'resolve_concrete_doubt_first',
             'route_question_before_progress', 'answer_route_doubt'),
        ):
            with self.subTest(case=case):
                conversation, cards = cli.synthetic_case(case)
                self.assertEqual((conversation.phase, conversation.gate), ('ruta', gate))
                self.assertEqual((cards[0].card_id, cards[0].proposed_move), (card_id, move))
                self.assertEqual(cards[0].status, 'approved')
                self.assertTrue(cards[0].sanitized)
                users = ' '.join(m.text for m in conversation.messages if m.role == 'user')
                for evidence in ('dominadas con más control', 'me balanceo', 'turnos',
                                 'recibir correcciones', 'aplicarlas'):
                    self.assertIn(evidence, users)
                self.assertEqual(cli.load_rules(case), expected)
                current, editorial = cli.packets(conversation, cards, expected)
                self.assertEqual(current, replace(editorial, variant='current', guidance=None))
                self.assertEqual(editorial.guidance.card_id, card_id)
                for excluded in (replace(cards[0], phase='brecha'),
                                 replace(cards[0], gate='other_gate'),
                                 replace(cards[0], status='candidate')):
                    self.assertIsNone(cli.packets(conversation, (excluded,), expected)[1].guidance)
                with patch.object(cli, 'CodexSessionRunner') as runner:
                    code, out, err = self.invoke(['--case', case])
                runner.assert_not_called()
                self.assertEqual((code, err), (0, ''))
                metadata = json.loads(out.split('\n', 1)[1])
                self.assertEqual(metadata['rules_sources'], list(cli.RULE_PATHS + extra))
                self.assertEqual(metadata['rules_characters'], len(expected))
                self.assertIn('NOT production approval', metadata['fixture_status'])
                self.assertNotIn('DRAFT', out)
        help_history = cli.synthetic_case('synthetic-ruta-help-to-gap')[0].messages
        doubt = cli.synthetic_case('synthetic-ruta-concrete-doubt')[0]
        self.assertEqual(doubt.messages[:-2], help_history)
        self.assertIn('por video', doubt.messages[-2].text)
        self.assertIn('si me cambian el turno', doubt.messages[-1].text)
        self.assertIn('aceptación pendiente', doubt.situation)
        for case in (cli.CASE_ID, cli.CASE_OBSERVATION_INFERENCE,
                     cli.CASE_CONTEXTO_MISSING_EVIDENCE, cli.CASE_DISPOSICION_WITHOUT_PRESSURE):
            self.assertEqual(cli.load_rules(case), cli.load_rules())

    def test_ruta_exact_candidate_voice_packets(self):
        cases = (
            (cli.CASE_RUTA_HELP_TO_GAP, 'connect_help_to_concrete_gap', 'juli_structure',
             'route_fit_to_gap', 'confirmed_route_readiness', 'relate_help_to_gap',
             'Aplica cuando la evidencia permite presentar una ruta y hace falta explicar por qué una forma real de acompañamiento responde a la brecha concreta de esta persona. No aplica antes de conocer suficiente destino, brecha, realidad cotidiana y disposición, antes de resolver un freno activo o si la relación propuesta no está respaldada.',
             'Explicar con palabras cotidianas cómo una ayuda real responde a la brecha y a la capacidad o autonomía buscada, usando solo mecanismos pertinentes al caso. Cada frase debe aportar algo distinto. Elegir vocabulario según el contexto y la voz de Tato, sin perder precisión. Pedir una reacción con una pregunta natural y esperar antes de convertir. Separar el puente de la pregunta solo si mejora el ritmo; usar el nombre únicamente si consta y resulta natural.',
             'No recitar prestaciones, ofrecer una ruta intercambiable, prometer resultados o que cierto tiempo alcanza, ni presentar orden o adaptación como explicación suficiente por sí solos. No reformular una misma idea para alargar el mensaje, imponer aperturas o cierres fijos, prohibir palabras pertinentes al caso ni recortar explicaciones necesarias.'),
            (cli.CASE_RUTA_CONCRETE_DOUBT, 'resolve_concrete_doubt_first', 'de0a10_116',
             'route_question_before_progress', 'presented_contextual_route', 'answer_route_doubt',
             'Aplica cuando aparece una duda concreta sobre la ruta o la ayuda propuesta antes de que corresponda avanzar, y puede responderse dentro del alcance respaldado. No aplica para una urgencia, una necesidad fuera de alcance, un rechazo claro u otra excepción que exija frenar; tampoco autoriza a repetir el pitch o reiniciar fases ya resueltas.',
             'Atender primero la duda específica con claridad, respeto y palabras cotidianas; conservar el estado alcanzado y retomar solo el paso pendiente, si corresponde. Cada frase debe aportar algo distinto, sin reiterar la misma respuesta con otras palabras. Elegir vocabulario según el contexto y la voz de Tato, sin perder precisión. Cuando corresponda pedir una reacción, hacerlo con una pregunta natural. Separar el puente de la pregunta solo si mejora el ritmo; usar el nombre únicamente si consta y resulta natural.',
             'No esquivar la pregunta para acelerar la conversión, responder con una defensa genérica, repetir el pitch ni encadenar la aclaración con una invitación no habilitada. No imponer aperturas o cierres fijos, prohibir palabras pertinentes al caso, recortar explicaciones necesarias ni prometer resultados o que cierto tiempo alcanza.'),
        )
        for case, card_id, provenance, gate, previous, move, situation, positive, negative in cases:
            with self.subTest(case=case):
                conversation, cards = cli.synthetic_case(case)
                rules = cli.load_rules(case)
                current, editorial = cli.packets(conversation, cards, rules)
                self.assertEqual(asdict(editorial.guidance), {
                    'card_id': card_id, 'provenance_id': provenance,
                    'positive_voice': positive, 'negative_repetition': negative,
                })
                self.assertEqual(asdict(cards[0]), {
                    'card_id': card_id, 'provenance_id': provenance,
                    'status': 'approved', 'sanitized': True, 'phase': 'ruta', 'gate': gate,
                    'situation': situation, 'last_assistant_move': previous,
                    'proposed_move': move, 'positive_voice': positive,
                    'negative_repetition': negative,
                })
                self.assertIsNone(current.guidance)
                self.assertEqual(current.current_rules, rules)
                self.assertEqual(current, replace(editorial, variant='current', guidance=None))
                self.assertIsNone(retrieve((replace(cards[0], status='candidate'),), conversation))

    def test_ruta_pairs_buffer_and_fail_without_retry(self):
        for case in ('synthetic-ruta-help-to-gap', 'synthetic-ruta-concrete-doubt'):
            with self.subTest(case=case), patch.object(cli, 'CodexSessionRunner') as factory:
                def draft(packet):
                    self.assertEqual(sys_out.getvalue(), '')
                    return packet.variant + ' synthetic marker?'
                factory.return_value.side_effect = draft
                sys_out, err = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(sys_out), contextlib.redirect_stderr(err):
                    code = cli.main(['--case', case, '--run-codex'])
                self.assertEqual((code, err.getvalue()), (0, ''))
                factory.assert_called_once()
                self.assertEqual(factory.return_value.call_count, 2)
                a, b = [call.args[0] for call in factory.return_value.call_args_list]
                self.assertEqual(a, replace(b, variant='current', guidance=None))
                self.assertEqual(a.current_rules, cli.load_rules(case))
                self.assertIn('current synthetic marker?', sys_out.getvalue())
                self.assertIn('editorial synthetic marker?', sys_out.getvalue())
            for outcomes, calls in (([RuntimeError('raw detail')], 1),
                                    (['partial marker', RuntimeError('raw detail')], 2),
                                    ([''], 1), (['partial marker', '  '], 2)):
                with self.subTest(case=case, calls=calls, outcomes=outcomes), \
                     patch.object(cli, 'CodexSessionRunner') as factory:
                    factory.return_value.side_effect = outcomes
                    code, out, err = self.invoke(['--case', case, '--run-codex'])
                self.assertEqual(code, 1)
                self.assertEqual(out, '')
                self.assertEqual(err, 'Synthetic comparison failed; no drafts returned.\n')
                factory.assert_called_once()
                self.assertEqual(factory.return_value.call_count, calls)

    def test_no_input_or_output_path_flags(self):
        with patch.object(cli, 'CodexSessionRunner') as runner:
            for flag in ('--chat', '--file', '--output', '--rules'):
                with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    cli.main([flag, 'synthetic'])
        runner.assert_not_called()


if __name__ == '__main__':
    unittest.main()
