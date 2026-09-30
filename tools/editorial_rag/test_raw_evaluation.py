"""Offline contracts only. Outputs below are unit fakes, never model evidence."""
import builtins
import copy
import hashlib
import io
import json
import unittest
from contextlib import ExitStack, redirect_stdout
from dataclasses import replace
from pathlib import Path
from typing import Any
from unittest.mock import patch

from . import raw_evaluation as evaluation
from .raw_history import parse_raw_result, raw_prompt
from .real_history import RULE_PATHS, load_real_rules


class RawEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.guard = ExitStack()
        self.addCleanup(self.guard.close)
        for target in (
            'socket.socket', 'socket.create_connection', 'subprocess.Popen',
            'subprocess.run', 'os.system', 'os.remove', 'os.unlink', 'os.rename',
            'os.replace', 'os.mkdir', 'os.rmdir',
            'tools.editorial_rag.codex_runner.CodexSessionRunner.__call__',
        ):
            self.guard.enter_context(patch(target, side_effect=AssertionError('Forbidden side effect')))
        self.cases, self.expectations, self.manifest = evaluation.load_bank()

    def records(self) -> list[dict[str, Any]]:
        return [evaluation.result_record(case, json.dumps({'type': 'dm', 'text': 'unit fake?'}))
                for case in self.cases]

    def test_complete_sources_exact_payload_and_unknown_metadata(self):
        self.assertTrue(4 <= len(self.cases) <= 6)
        self.assertEqual([s['path'] for s in self.manifest['sources']], list(RULE_PATHS))
        root = Path(__file__).resolve().parents[2]
        for source in self.manifest['sources']:
            raw = (root / source['path']).read_bytes()
            self.assertEqual(source['sha256'], hashlib.sha256(raw).hexdigest())
            self.assertEqual(source['bytes'], len(raw))
        rules = load_real_rules()
        for case, entry in zip(self.cases, self.manifest['cases'], strict=True):
            self.assertEqual(case.packet.current_rules, rules)
            self.assertEqual(case.packet.guidance, ())
            self.assertEqual(case.prompt, raw_prompt(case.packet))
            self.assertEqual(case.fingerprint, hashlib.sha256(case.prompt.encode('utf-8')).hexdigest())
            self.assertEqual(entry['fingerprint'], case.fingerprint)
        self.assertEqual(self.manifest['guidance'], 'off')
        self.assertEqual(self.manifest['model'], 'unknown')
        self.assertEqual(self.manifest['effort'], 'unknown')
        self.assertNotIn('history', json.dumps(self.manifest))

    def test_build_cases_preserves_raw_text_and_excludes_expectations(self):
        history = '  fictional export\r\nrepeat\rrepeat\t🪁\n'
        inputs = [{'id': 'fiction-' + str(n), 'history': history} for n in range(4)]
        cases = evaluation.build_cases(inputs, 'complete test rules')
        for case in cases:
            self.assertEqual(case.packet.history, history)
            self.assertEqual(json.loads(case.prompt.split('UNTRUSTED RAW HISTORY JSON\n')[1]),
                             {'history': history})
        altered = copy.deepcopy(self.expectations)
        altered[0]['criteria'] = ['EVALUATOR_ONLY_SENTINEL']
        bundle = evaluation.export_bundle(self.cases, altered, self.records())
        self.assertNotIn('EVALUATOR_ONLY_SENTINEL', json.dumps(bundle['config']))
        self.assertIn('EVALUATOR_ONLY_SENTINEL', json.dumps(bundle['expectations']))

    def test_inputs_reject_extra_metadata_bad_ids_duplicates_and_bad_history(self):
        inputs = [{'id': case.id, 'history': case.packet.history} for case in self.cases]
        for key, value in (('phase', 'ruta'), ('expected', 'answer'), ('guidance', []),
                           ('id', '../case'), ('id', 1), ('history', ' '), ('history', '\ud800')):
            bad = copy.deepcopy(inputs)
            bad[0][key] = value
            with self.subTest(key=key, value=repr(value)), self.assertRaises(ValueError):
                evaluation.build_cases(bad, 'rules')
        for bad in ([], inputs[:3], inputs * 2, [inputs[0]] * 4, None):
            with self.assertRaises(ValueError):
                evaluation.build_cases(bad, 'rules')

    def test_expectations_require_matching_order_ids_types_and_criteria(self):
        for bad in (self.expectations[::-1], self.expectations[:-1],
                    self.expectations + [self.expectations[0]], None):
            with self.assertRaises(ValueError):
                evaluation.export_bundle(self.cases, bad, self.records())
        for key, value in (('type', 'other'), ('criteria', []), ('criteria', [' ']),
                           ('criteria', [1]), ('extra', True)):
            bad = copy.deepcopy(self.expectations)
            bad[0][key] = value
            with self.assertRaises(ValueError):
                evaluation.export_bundle(self.cases, bad, self.records())

    def test_results_are_ordered_json_strings_using_actual_parser(self):
        records = self.records()
        records[-1] = evaluation.result_record(
            self.cases[-1], '{"type":"needs_context","question":"unit fake clarification?"}')
        bundle = evaluation.export_bundle(self.cases, self.expectations, records)
        self.assertEqual(bundle['outputs'], [record['output'] for record in records])
        self.assertEqual(json.loads(json.dumps(bundle['outputs'])), bundle['outputs'])
        self.assertTrue(all(type(output) is str for output in bundle['outputs']))
        self.assertEqual(parse_raw_result(bundle['outputs'][-1])['type'], 'needs_context')
        self.assertEqual(bundle['config']['prompts'], ['{{raw_prompt}}'])
        self.assertEqual(len(bundle['config']['providers']), 1)
        self.assertTrue(bundle['config']['providers'][0].endswith('/no_inference_provider.py'))
        for case, test in zip(self.cases, bundle['config']['tests'], strict=True):
            self.assertEqual(test['description'], case.id)
            self.assertEqual(test['vars'], {'raw_prompt': case.prompt})
            self.assertEqual(test['providerOutput'], records[self.cases.index(case)]['output'])
        self.assertNotIn('score', json.dumps(bundle))

    def test_export_rejects_record_identity_order_fingerprint_and_schema(self):
        records = self.records()
        for bad in (records[::-1], records[:-1], records + [records[0]], None):
            with self.assertRaises(ValueError):
                evaluation.export_bundle(self.cases, self.expectations, bad)
        for key, value in (('id', 'wrong'), ('fingerprint', '0' * 64), ('extra', True),
                           ('output', ''), ('output', None),
                               ('output', {'type': 'dm', 'text': 'fake'}),
                           ('output', '{"type":"dm","text":"fake","text":"duplicate"}'),
                           ('output', '{"type":"dm","text":"fake","extra":true}'),
                           ('output', '{"type":"needs_context","text":"wrong"}'),
                           ('output', '```json\n{}\n```'), ('output', '{"type":"dm","text":" "}')):
            bad = copy.deepcopy(records)
            bad[0][key] = value
            with self.subTest(key=key, value=repr(value)), self.assertRaises(ValueError):
                evaluation.export_bundle(self.cases, self.expectations, bad)

    def test_changed_payload_or_tampered_case_invalidates_records(self):
        inputs = [{'id': case.id, 'history': case.packet.history} for case in self.cases]
        for changed in (evaluation.build_cases(inputs, 'different rules'),
                        (replace(self.cases[0], prompt='tampered'),) + self.cases[1:],
                        (replace(self.cases[0], fingerprint='0' * 64),) + self.cases[1:]):
            with self.assertRaises(ValueError):
                evaluation.export_bundle(changed, self.expectations, self.records())
        inputs[0]['history'] += '\nfictional added turn'
        with self.assertRaises(ValueError):
            evaluation.export_bundle(evaluation.build_cases(inputs, load_real_rules()),
                                     self.expectations, self.records())

    def test_default_and_check_deny_writes_and_only_print_manifest(self):
        original_open, original_io_open = builtins.open, io.open

        def read_only(original):
            def guarded(file, mode='r', *args, **kwargs):
                if any(flag in mode for flag in 'wax+'):
                    raise AssertionError('Unexpected write')
                return original(file, mode, *args, **kwargs)
            return guarded

        with patch('builtins.open', side_effect=read_only(original_open)), \
                patch('io.open', side_effect=read_only(original_io_open)), \
                patch('os.open', side_effect=AssertionError('Unexpected low-level open')), \
                patch('pathlib.Path.mkdir', side_effect=AssertionError('Unexpected mkdir')):
            for args in ([], ['--check']):
                output = io.StringIO()
                with redirect_stdout(output):
                    self.assertEqual(evaluation.main(args), 0)
                self.assertEqual(json.loads(output.getvalue()), self.manifest)

    def test_pure_helpers_do_not_read_or_write_files(self):
        inputs = [{'id': c.id, 'history': c.packet.history} for c in self.cases]
        rules = self.cases[0].packet.current_rules
        with patch('builtins.open', side_effect=AssertionError('Unexpected file access')), \
                patch('io.open', side_effect=AssertionError('Unexpected file access')), \
                patch('os.open', side_effect=AssertionError('Unexpected file access')):
            cases = evaluation.build_cases(inputs, rules)
            records = [evaluation.result_record(c, '{"type":"dm","text":"unit fake?"}')
                       for c in cases]
            self.assertEqual(len(evaluation.export_bundle(cases, self.expectations, records)['outputs']),
                             len(cases))

    def test_invalid_bank_prints_no_partial_manifest_or_content(self):
        output = io.StringIO()
        with patch.object(evaluation, 'load_bank', side_effect=ValueError('private sentinel')), \
                redirect_stdout(output):
            self.assertEqual(evaluation.main(['--check']), 1)
        self.assertEqual(output.getvalue(), 'Invalid offline bank\n')

    def test_rule_snapshot_mismatch_fails_closed(self):
        with patch.object(evaluation, 'load_real_rules', return_value='changed during read'), \
                self.assertRaises(ValueError):
            evaluation.load_bank()

    def test_strict_json_rejects_duplicate_keys(self):
        with patch.object(Path, 'read_bytes', return_value=b'[{"id":"a","id":"b"}]'), \
                self.assertRaises(ValueError):
            evaluation.read_json(Path('unused'))

    def test_stub_always_denies_inference(self):
        from .evaluation.no_inference_provider import call_api
        for prompt in ('anything', '', None):
            with self.assertRaisesRegex(RuntimeError, 'Inference disabled'):
                call_api(prompt, {}, {})


if __name__ == '__main__':
    unittest.main()
