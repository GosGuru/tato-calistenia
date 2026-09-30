"""Fiction-only transport tests; subprocess is always mocked."""
import copy
import importlib
import io
import json
import os
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

FIXTURES = Path(os.environ['LOCALAPPDATA']) / 'TatoEditorialEval' / 'tmp'


class SmokeTests(unittest.TestCase):
    def setUp(self):
        self.smoke = importlib.import_module('tools.editorial_rag.evaluation.promptfoo_smoke')

    def test_import_and_check_are_inert(self):
        with patch('subprocess.run', side_effect=AssertionError('process')), \
                patch('socket.socket', side_effect=AssertionError('network')), \
                patch('tempfile.TemporaryDirectory', side_effect=AssertionError('write')), \
                patch.object(Path, 'mkdir', side_effect=AssertionError('write')):
            importlib.reload(self.smoke)
            with patch.object(self.smoke, 'check_runtime', return_value={}), redirect_stdout(io.StringIO()):
                self.assertEqual(self.smoke.main([]), 0)
                self.assertEqual(self.smoke.main(['--check']), 0)

    def test_fixed_bundle_binding_and_report_fidelity(self):
        bundle = self.smoke.prepare_bundle()
        self.assertEqual(len(bundle['outputs']), 5)
        self.assertFalse(bundle['config']['sharing'])
        rows = []
        for i, test in enumerate(bundle['config']['tests']):
            self.assertEqual(test['providerOutput'], bundle['outputs'][i])
            self.assertIn('MOCK_IMPORT_ONLY', test['providerOutput'])
            self.assertEqual(test['assert'], [{'type': 'is-json'}])
            # Model SDK report serialization without changing the raw response.
            reported_test = copy.deepcopy(test)
            reported_test['providerOutput'] = json.dumps(json.loads(test['providerOutput']), separators=(',', ':'))
            rows.append({'testIdx': i, 'testCase': reported_test, 'response': {'output': test['providerOutput']},
                         'prompt': {'raw': test['vars']['raw_prompt']}, 'success': True})
        report = {'results': {'results': rows, 'stats': {'successes': 5, 'failures': 0, 'errors': 0}}}
        self.smoke.validate_report(report, bundle)
        for mutation in ('order', 'output', 'count', 'prompt', 'failure', 'missing', 'malformed'):
            bad = copy.deepcopy(report)
            row = bad['results']['results'][0]
            if mutation == 'order':
                bad['results']['results'].reverse()
            if mutation == 'output':
                row['response']['output'] = '{}'
            if mutation == 'count':
                bad['results']['stats']['successes'] = 4
            if mutation == 'prompt':
                row['prompt']['raw'] = 'changed'
            if mutation == 'failure':
                row['success'] = False
            if mutation == 'missing':
                del row['testCase']['providerOutput']
            if mutation == 'malformed':
                row['testCase']['providerOutput'] = ''
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.smoke.validate_report(bad, bundle)

    def test_environment_is_minimal_and_owned(self):
        root = FIXTURES / 'not-created'
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'SECRET', 'HTTPS_PROXY': 'SECRET',
                                    'NODE_OPTIONS': 'SECRET', 'PYTHONPATH': 'SECRET'}):
            env = self.smoke.isolated_env(root)
        for key in ('OPENAI_API_KEY', 'HTTPS_PROXY', 'NODE_OPTIONS', 'PYTHONPATH'):
            self.assertNotIn(key, env)
        for key in ('HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA', 'TEMP', 'TMP',
                    'PROMPTFOO_CONFIG_DIR', 'PROMPTFOO_CACHE_PATH', 'XDG_CONFIG_HOME',
                    'XDG_CACHE_HOME', 'XDG_STATE_HOME'):
            self.assertTrue(Path(env[key]).is_relative_to(root))
        self.assertEqual(env['PYTHONDONTWRITEBYTECODE'], '1')

    def test_runtime_pins_fail_closed(self):
        with patch.object(self.smoke, 'file_hash', return_value='wrong'), self.assertRaises(ValueError):
            self.smoke.check_runtime(FIXTURES / 'not-created')

    def test_probe_shell_false_timeout_and_owned_cleanup(self):
        FIXTURES.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='unit-smoke-', dir=FIXTURES) as base:
            root = Path(base)
            runtime = {'base': root, 'node': root / 'node.exe', 'cli': root / 'entrypoint.js'}
            seen = []
            def fake_run(command, **kwargs):
                seen.append(kwargs['cwd'])
                self.assertFalse(kwargs['shell'])
                self.assertEqual(kwargs['timeout'], 120)
                self.assertEqual(command[-1], '--version')
                self.assertEqual(command[1], '--require')
                self.assertTrue(Path(kwargs['cwd']).is_relative_to(root / 'tmp'))
                return subprocess.CompletedProcess(command, 0, '0.123.1\n', self.markers())
            with patch.object(self.smoke, 'check_runtime', return_value=runtime), \
                    patch('subprocess.run', side_effect=fake_run):
                self.smoke.run_mode('probe', root)
            self.assertFalse(Path(seen[0]).exists())
            with patch.object(self.smoke, 'check_runtime', return_value=runtime), \
                    patch('subprocess.run', side_effect=subprocess.TimeoutExpired(['node'], 120,
                        output='PRIVATE_PAYLOAD', stderr='PRIVATE_PAYLOAD')), self.assertRaises(ValueError):
                self.smoke.run_mode('probe', root)
            self.assertEqual(list((root / 'tmp').iterdir()), [])

    @staticmethod
    def markers():
        return ('TATO_FENCE {"event":"startup","version":1}\n'
                'TATO_FENCE {"event":"exit","total":0,"forbidden":0,"counts":{}}\n')

    def test_mock_smoke_report_cleanup_and_fixed_flags(self):
        FIXTURES.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='unit-smoke-', dir=FIXTURES) as base:
            root = Path(base)
            runtime = {'base': root, 'node': root / 'node.exe', 'cli': root / 'entrypoint.js'}
            def fake_run(command, **kwargs):
                self.assertEqual(kwargs['timeout'], 180)
                self.assertFalse(kwargs['shell'])
                self.assertNotIn('--model-outputs', command)
                for flag in ('--no-write', '--no-cache', '--no-table', '--no-progress-bar', '--no-share'):
                    self.assertIn(flag, command)
                config = self.smoke.read_json(Path(command[command.index('--config') + 1]))
                self.assertFalse(config['sharing'])
                rows = [{'testIdx': i, 'testCase': item, 'success': True,
                         'response': {'output': item['providerOutput']},
                         'prompt': {'raw': item['vars']['raw_prompt']}}
                        for i, item in enumerate(config['tests'])]
                report = {'results': {'results': rows,
                                     'stats': {'successes': 5, 'failures': 0, 'errors': 0}}}
                Path(command[command.index('--output') + 1]).write_text(json.dumps(report), encoding='utf-8')
                return subprocess.CompletedProcess(command, 0, 'PRIVATE_PAYLOAD', self.markers())
            captured = io.StringIO()
            with patch.object(self.smoke, 'check_runtime', return_value=runtime), \
                    patch('subprocess.run', side_effect=fake_run) as run, redirect_stdout(captured):
                self.assertEqual(self.smoke.run_mode('smoke', root)['transport'], 'passed')
                run.assert_called_once()
            self.assertNotIn('PRIVATE_PAYLOAD', captured.getvalue())
            self.assertEqual(list((root / 'tmp').iterdir()), [])

    def test_report_reader_bounds_and_metadata_pins(self):
        FIXTURES.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='unit-smoke-', dir=FIXTURES) as base:
            path = Path(base) / 'report.json'
            path.write_text('x' * 20, encoding='utf-8')
            with patch.object(self.smoke, 'MAX_REPORT', 10), self.assertRaises(ValueError):
                self.smoke.read_json(path)
            with self.assertRaises(ValueError):
                self.smoke.read_json(path)
        for root, installed in (({'dependencies': {'promptfoo': '^0.123.1'}}, {'version': '0.123.1'}),
                                ({'dependencies': {'promptfoo': '0.123.1'}}, {'version': 'wrong'})):
            with patch.object(self.smoke, 'file_hash', side_effect=[self.smoke.NODE_SHA, self.smoke.LOCK_SHA]), \
                    patch.object(self.smoke, 'read_json', side_effect=[root, installed]), self.assertRaises(ValueError):
                self.smoke.check_runtime(FIXTURES / 'not-created')

    def test_failure_diagnostics_disclose_stage_not_payload(self):
        output = io.StringIO()
        with patch.object(self.smoke, 'run_mode', side_effect=ValueError('Report prompt mismatch')), \
                redirect_stdout(output):
            self.assertEqual(self.smoke.main(['--smoke']), 1)
        self.assertIn('Report prompt mismatch', output.getvalue())
        output = io.StringIO()
        with patch.object(self.smoke, 'run_mode', side_effect=ValueError('PRIVATE_PAYLOAD')), \
                redirect_stdout(output):
            self.assertEqual(self.smoke.main(['--smoke']), 1)
        self.assertNotIn('PRIVATE_PAYLOAD', output.getvalue())

    def test_missing_markers_and_forbidden_attempt_fail(self):
        for text in ('', 'PRIVATE_PAYLOAD', self.markers().replace('"forbidden":0', '"forbidden":1')):
            with self.assertRaises(ValueError):
                self.smoke.guard_evidence(text)

    def test_no_arbitrary_cli_or_private_input(self):
        with redirect_stdout(io.StringIO()), patch('sys.stderr', new=io.StringIO()):
            for args in (['--eval'], ['--file', 'private.json'], ['--smoke', '--probe-startup']):
                with self.assertRaises(SystemExit):
                    self.smoke.main(args)


if __name__ == '__main__':
    unittest.main()
