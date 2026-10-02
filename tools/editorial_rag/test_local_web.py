"""Synthetic-only HTTP contracts; the Codex factory is always mocked."""
import asyncio
import json
import re
import subprocess
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

# Namespace packages resolve from the repo root used by both unittest commands.
# The editor's file-local search root does not include that invocation root.
from . import codex_runner as runner_module
from . import local_web as web
from .synthetic_compare import synthetic_case
from .test_codex_runner import (
    DESCRIPTION_WARNINGS,
    stream,
    success,
    warning_event,
)


class ForegroundTests(unittest.TestCase):
    def test_launcher_checks_existing_files_and_runs_synchronously(self):
        script = (web.Path(__file__).parent / 'start_app.cmd').read_text(encoding='utf-8')
        self.assertIn('cd /d "%~dp0..\\.."', script)
        self.assertIn('if not exist "tools\\editorial_rag\\.venv\\Scripts\\python.exe" goto missing', script)
        self.assertIn('if not exist "tools\\editorial_rag\\web\\dist\\index.html" goto missing', script)
        self.assertIn('"tools\\editorial_rag\\.venv\\Scripts\\python.exe" -B -m tools.editorial_rag.local_web', script)
        self.assertIn('pause', script)
        for forbidden in ('start ', 'taskkill', 'pip ', 'npm ', 'schtasks', 'powershell', 'goto restart'):
            self.assertNotIn(forbidden, script.lower())

    def test_reserved_socket_is_passed_and_closed(self):
        with patch.object(web, 'socket') as sockets, patch.object(web, 'os') as os_module, \
                patch.object(web, 'DIST') as dist, patch('uvicorn.Config') as config, \
                patch('uvicorn.Server') as server, patch.object(web, 'create_app'), \
                    patch.object(web, 'production_auth'):
            os_module.name = 'nt'
            dist.__truediv__.return_value.is_file.return_value = True
            reserved = sockets.socket.return_value

            def foreground(*, sockets):
                self.assertEqual(sockets, [reserved])
                reserved.close.assert_not_called()
            server.return_value.run.side_effect = foreground
            self.assertEqual(web.main(), 0)
            reserved.setsockopt.assert_called_once_with(sockets.SOL_SOCKET, sockets.SO_EXCLUSIVEADDRUSE, 1)
            reserved.bind.assert_called_once_with(('127.0.0.1', 8765))
            server.return_value.run.assert_called_once_with(sockets=[reserved])
            reserved.close.assert_called_once()
            self.assertFalse(config.call_args.kwargs['access_log'])

    def test_refused_or_occupied_socket_fails_without_server(self):
        for failure in (PermissionError(), OSError()):
            with patch.object(web, 'socket') as sockets, patch.object(web, 'DIST') as dist, \
                    patch('uvicorn.Server') as server:
                dist.__truediv__.return_value.is_file.return_value = True
                sockets.socket.return_value.bind.side_effect = failure
                self.assertEqual(web.main(), 1)
                server.assert_not_called()
                sockets.socket.return_value.close.assert_called_once()

    def test_missing_build_does_not_bind(self):
        with patch.object(web, 'socket') as sockets, patch.object(web, 'DIST') as dist:
            dist.__truediv__.return_value.is_file.return_value = False
            self.assertEqual(web.main(), 1)
            sockets.socket.assert_not_called()


class LocalWebTests(unittest.TestCase):
    def setUp(self):
        self.factory = patch.object(web, 'CodexSessionRunner').start()
        self.addCleanup(patch.stopall)
        self.client = TestClient(web.create_app(), base_url=web.ORIGIN)
        self.addCleanup(self.client.close)
        self.token = self.client.get('/api/context').json()['csrf_token']
        self.headers = {'Origin': web.ORIGIN, 'X-CSRF-Token': self.token}

    def post(self, body=None, headers=None, path='/api/generate'):
        return self.client.post(path, json={'consent': True} if body is None else body,
                                headers=self.headers if headers is None else headers)

    def draft(self, **changes):
        return self.post({'history': 'Prospecto: quiero fuerza', 'reviewed': True,
                          'consent': True} | changes, path='/api/draft')

    def test_complete_primary_composition_with_two_fictional_criteria(self):
        from pathlib import Path

        from .real_history import RULE_PATHS
        from .test_app_auth import CONFIG, OWNER
        from .test_rag_service import VECTOR, criterion

        rows = (criterion('fictional-a'), criterion('fictional-b'))
        history = '  Ficción completa\r\nrepetido\r\nrepetido\t🪁\r'
        final = {'type': 'dm', 'text': 'salida enteramente ficticia?'}
        self.factory.side_effect = runner_module.CodexSessionRunner
        with patch('tools.editorial_rag.app_auth.load_config', return_value=CONFIG), \
                patch('tools.editorial_rag.app_auth.sign_in', return_value='secret-token-sentinel'), \
                patch('tools.editorial_rag.app_auth._claims', return_value=OWNER), \
                patch('tools.editorial_rag.app_auth.read_library', return_value=rows), \
                patch('tools.editorial_rag.rag_service.read_library', return_value=rows), \
                patch('tools.editorial_rag.rag_service.embed_query', return_value=[VECTOR]) as embed, \
                patch.object(runner_module.shutil, 'which', return_value='/fictional/codex'), \
                patch.object(runner_module.subprocess, 'run', side_effect=[
                    subprocess.CompletedProcess([], 0, 'Logged in using ChatGPT', ''),
                    subprocess.CompletedProcess([], 0, success(json.dumps(final)), 'secret-stderr-sentinel'),
                ]) as run:
            self.assertEqual(self.post({'email': 'fictional@example.invalid', 'password': 'fictional'}, path='/api/auth/login').status_code, 200)
            response = self.post({'history': history, 'consent': True}, path='/api/raw-draft')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['result'], final)
        self.assertEqual(set(response.json()), {'result', 'retrieval', 'revision'})
        self.assertEqual(response.json()['retrieval'], {'status': 'supplied', 'count': 2})
        self.assertEqual(run.call_count, 2)
        self.assertEqual(sum('status' in call.args[0] for call in run.call_args_list), 1)
        self.assertEqual(sum('exec' in call.args[0] for call in run.call_args_list), 1)
        prompt = run.call_args.kwargs['input']
        self.assertEqual(json.loads(prompt.split('UNTRUSTED RAW HISTORY JSON\n')[1]), {'history': history})
        guidance = json.loads(prompt.split('CONDITIONAL GUIDANCE JSON\n')[1].split('\nUNTRUSTED RAW HISTORY JSON')[0])
        self.assertEqual(len(guidance), 2)
        self.assertEqual(len(RULE_PATHS), 7)
        for path in RULE_PATHS:
            self.assertIn((Path(__file__).resolve().parents[2] / path).read_bytes().decode('utf-8'), prompt)
        self.assertNotIn('secret-token-sentinel', prompt)
        self.assertNotIn(OWNER, prompt)
        embed.assert_called_once_with(history)
        self.assertEqual(response.headers['x-tato-exec-attempts'], '1')
        for stage in ('retrieval', 'rules', 'packet', 'login', 'exec', 'stream', 'raw-result'):
            self.assertEqual(response.headers[f'x-tato-{stage}-outcome'], 'ok')
            self.assertGreaterEqual(float(response.headers[f'x-tato-{stage}-ms']), 0)
        self.assertNotIn('secret-', str(response.headers))
        self.assertFalse(web._FLIGHT.locked())

    def test_primary_diagnostics_fail_closed_and_release_shared_lock(self):
        self.factory.side_effect = runner_module.CodexSessionRunner
        cases = [
            ('nonzero', subprocess.CompletedProcess([], 1, 'secret-sentinel', 'secret-sentinel'), 'exec', 'nonzero'),
            ('timeout', subprocess.TimeoutExpired(['secret-sentinel'], 1, output='secret-sentinel'), 'exec', 'timeout'),
            ('forbidden', subprocess.CompletedProcess([], 0, stream({'type': 'item.started', 'item': {'type': 'command_execution'}}), ''), 'stream', 'invalid'),
            ('incomplete', subprocess.CompletedProcess([], 0, stream({'type': 'turn.started'}), ''), 'stream', 'invalid'),
            ('malformed', subprocess.CompletedProcess([], 0, 'secret-sentinel', ''), 'stream', 'invalid'),
            ('raw', subprocess.CompletedProcess([], 0, success('{"type":"dm","text":"secret-sentinel","extra":1}'), ''), 'raw-result', 'invalid'),
        ]
        for label, result, stage, outcome in cases:
            with self.subTest(case=label), \
                    patch.object(runner_module.shutil, 'which', return_value='/fictional/codex'), \
                    patch.object(runner_module.subprocess, 'run', side_effect=[
                        subprocess.CompletedProcess([], 0, 'Logged in using ChatGPT', ''), result]) as run:
                response = self.post({'history': 'fictional history', 'consent': True}, path='/api/raw-draft')
                self.assertEqual(response.status_code, 502)
                self.assertEqual(response.json(), {'error': web.DRAFT_FAILURE})
                self.assertEqual(response.headers['x-tato-exec-attempts'], '1')
                self.assertEqual(response.headers[f'x-tato-{stage}-outcome'], outcome)
                self.assertNotIn('secret-sentinel', str(response.headers) + response.text)
                self.assertEqual(run.call_count, 2)
                self.assertFalse(web._FLIGHT.locked())

    def test_raw_bootstrap_independent_and_single_typed_call(self):
        from tools.editorial_rag.raw_history import (  # pyright: ignore[reportMissingImports]
            RawHistoryPacket,
        )
        from tools.editorial_rag.real_history import (  # pyright: ignore[reportMissingImports]
            load_real_rules,
        )

        with patch.object(web, 'synthetic_case', side_effect=ValueError('invented failure')), \
                patch.object(web, 'load_real_rules', side_effect=ValueError('invented failure')), \
                patch.object(web, 'retrieve', side_effect=ValueError('invented failure')), \
                patch.object(web.AppAuth, 'status', side_effect=ValueError('invented failure')):
            bootstrap = self.client.get('/api/bootstrap')
            self.assertEqual(bootstrap.status_code, 200)
            self.assertEqual(bootstrap.json(), {'app': 'tato-local', 'protocol': 1, 'csrf_token': self.token, 'model': 'unknown', 'effort': 'unknown'})
        self.factory.assert_not_called()
        history = '  Autor ficticio\r\nrepetido\r\nrepetido\t🪁\r'
        for output in ({'type': 'dm', 'text': 'salida ficticia?'},
                       {'type': 'needs_context', 'question': 'quién escribió la última línea?'}):
            self.factory.return_value.reset_mock()
            self.factory.return_value.return_value = json.dumps(output)
            response = self.post({'history': history, 'consent': True}, path='/api/raw-draft')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {'result': output, 'retrieval': {'status': 'off', 'count': 0}, 'revision': 0})
            self.factory.return_value.assert_called_once()
            packet = self.factory.return_value.call_args.args[0]
            self.assertIs(type(packet), RawHistoryPacket)
            self.assertEqual(packet.history, history)
            self.assertEqual(packet.current_rules, load_real_rules())
            self.assertIs(packet.consent, True)

    def test_persistence_metadata_is_optional_lazy_and_contains_no_credentials(self):
        with patch('tools.editorial_rag.app_auth.load_config', side_effect=AssertionError('No real config')):
            response = self.client.get('/api/auth/persistence')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'enabled': False, 'remembered': False, 'problem': False})
        self.assertEqual(response.headers['cache-control'], 'no-store')
        self.factory.assert_not_called()

    def test_auth_routes_strict_protected_and_bounded(self):
        self.assertEqual(self.client.get('/api/auth/status').json(),
                         {'connected': False, 'empty': False, 'count': 0, 'revision': 0})
        for body in ({}, {'email': 1, 'password': 'fictional'},
                     {'email': 'fictional@example.invalid', 'password': 'x', 'jwt': 'bad'}):
            self.assertEqual(self.post(body, path='/api/auth/login').status_code, 422)
        for path in ('/api/auth/login', '/api/auth/logout'):
            self.assertEqual(self.post({}, headers={}, path=path).status_code, 403)
        with patch.object(web.AppAuth, 'login', return_value=False) as login:
            response = self.post({'email': 'fictional@example.invalid', 'password': 'x' * 4096}, path='/api/auth/login')
            self.assertEqual(response.status_code, 401)
            login.assert_called_once()
        self.assertEqual(self.post({}, path='/api/auth/logout').status_code, 200)
        self.assertEqual(self.client.get('/api/auth/status').json()['revision'], 1)
        self.assertEqual(self.client.get('/api/auth/status').headers['cache-control'], 'no-store')
        self.factory.assert_not_called()

    def test_disconnect_during_raw_call_drops_late_success_and_error(self):
        for output in ('{\"type\":\"dm\",\"text\":\"fictional stale\"}', ValueError('fictional secret')):
            def run(packet, output=output):
                self.assertTrue(web._FLIGHT.locked())
                self.assertEqual(self.post({}, path='/api/auth/logout').status_code, 200)
                if isinstance(output, Exception):
                    raise output
                return output
            self.factory.return_value.side_effect = run
            response = self.post({'history': 'fictional', 'consent': True}, path='/api/raw-draft')
            self.assertEqual(response.status_code, 409)
            self.assertNotIn('fictional', response.text)
            self.assertFalse(web._FLIGHT.locked())

    def test_retrieval_and_embedding_share_process_flight(self):
        def retrieve(auth, history):
            self.assertTrue(web._FLIGHT.locked())
            self.assertEqual(history, 'fictional')
            self.assertEqual(self.draft().status_code, 409)
            return 0, (), {'status': 'unavailable', 'count': 0}
        self.factory.return_value.return_value = '{\"type\":\"dm\",\"text\":\"fictional draft\"}'
        with patch.object(web, 'retrieve', side_effect=retrieve):
            response = self.post({'history': 'fictional', 'consent': True}, path='/api/raw-draft')
        self.assertEqual(response.json()['retrieval'], {'status': 'unavailable', 'count': 0})
        self.factory.return_value.assert_called_once()

    def test_connected_criteria_and_expiry_during_generation(self):
        from tools.editorial_rag.test_app_auth import (  # pyright: ignore[reportMissingImports]
            CONFIG,
            OWNER,
        )
        from tools.editorial_rag.test_rag_service import (  # pyright: ignore[reportMissingImports]
            VECTOR,
            criterion,
        )
        with patch('tools.editorial_rag.app_auth.load_config', return_value=CONFIG), \
             patch('tools.editorial_rag.app_auth.sign_in', return_value='fictional-token'), \
             patch('tools.editorial_rag.app_auth._claims', return_value=OWNER) as claims, \
             patch('tools.editorial_rag.app_auth.read_library', return_value=(criterion(),)), \
             patch('tools.editorial_rag.rag_service.read_library', return_value=(criterion(),)) as read, \
             patch('tools.editorial_rag.rag_service.embed_query', return_value=[VECTOR]) as embed:
            login = self.post({'email': 'fictional@example.invalid', 'password': 'fictional'}, path='/api/auth/login')
            self.assertEqual(login.status_code, 200)
            def run(packet):
                self.assertEqual(packet.history, 'fictional full history')
                self.assertEqual(len(packet.guidance), 1)
                self.assertNotIn('fictional-token', repr(packet))
                self.assertNotIn(OWNER, repr(packet))
                self.assertNotIn('embedding', repr(packet))
                return '{"type":"dm","text":"fictional draft"}'
            self.factory.return_value.side_effect = run
            body = {'history': 'fictional full history', 'consent': True}
            response = self.post(body, path='/api/raw-draft')
            self.assertEqual(response.json()['retrieval'], {'status': 'supplied', 'count': 1})
            self.factory.return_value.assert_called_once()
            read.assert_called_once_with('fictional-token', CONFIG)
            embed.assert_called_once_with(body['history'])
            def expire(packet):
                claims.side_effect = ValueError('fictional-expired')
                return '{"type":"dm","text":"fictional stale"}'
            self.factory.return_value.side_effect = expire
            self.assertEqual(self.post(body, path='/api/raw-draft').status_code, 409)
            # A fresh click after natural expiry is a deliberate baseline, not a stale result.
            self.factory.return_value.side_effect = None
            self.factory.return_value.return_value = '{"type":"dm","text":"fictional fresh baseline"}'
            response = self.post(body, path='/api/raw-draft')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['retrieval'], {'status': 'expired', 'count': 0})
            self.assertEqual(self.factory.return_value.call_args.args[0].guidance, ())

    def test_raw_strict_schema_limits_and_fixed_errors(self):
        body = {'history': 'texto inventado', 'consent': True}
        invalid = [{}, body | {'reviewed': True}, body | {'current_rules': 'x'},
                   body | {'messages': []}, {'history': 'x'}, {'consent': True}]
        invalid += [body | {'consent': v} for v in (False, 1, 'true', None)]
        invalid += [body | {'history': v} for v in ('', ' ', 1, [], None, '\ud800', 'x\x00', 'x' * 24001)]
        for value in invalid:
            result = self.client.post('/api/raw-draft', content=json.dumps(value),
                                      headers=self.headers | {'Content-Type': 'application/json'})
            self.assertEqual(result.status_code, 422)
            self.assertEqual(result.json(), {'error': web.INVALID})
        self.factory.assert_not_called()
        self.factory.return_value.return_value = '{"type":"dm","text":"salida ficticia"}'
        result = self.client.post('/api/raw-draft', content=json.dumps(body | {'history': '🪁' * 24000}),
                                  headers=self.headers | {'Content-Type': 'application/json'})
        self.assertEqual(result.status_code, 200)
        self.factory.reset_mock()
        result = self.client.post('/api/raw-draft', content=iter([b'x' * 150001, b'x' * 150000]),
                                  headers=self.headers | {'Content-Type': 'application/json'})
        self.assertEqual(result.status_code, 413)
        self.factory.assert_not_called()
        for value in ('raw invented diagnostic', '{"type":"dm","text":"partial","extra":1}',
                      '{"type":"needs_context","text":"not a DM"}', RuntimeError('invented internal detail')):
            self.factory.return_value.reset_mock()
            self.factory.return_value.side_effect = value if isinstance(value, Exception) else None
            self.factory.return_value.return_value = value
            result = self.post(body, path='/api/raw-draft')
            self.assertEqual(result.status_code, 502)
            self.assertEqual(result.json(), {'error': web.DRAFT_FAILURE})
            self.factory.return_value.assert_called_once()
            self.assertFalse(web._FLIGHT.locked())

    def test_raw_rule_failure_before_runner_and_bootstrap_security(self):
        with patch.object(web, 'load_real_rules', side_effect=RuntimeError('invented failure')):
            result = self.post({'history': 'inventado', 'consent': True}, path='/api/raw-draft')
        self.assertEqual(result.status_code, 502)
        self.assertEqual(result.json(), {'error': web.DRAFT_FAILURE})
        self.assertEqual(result.headers['x-tato-rules-outcome'], 'internal')
        self.assertEqual(result.headers['x-tato-exec-attempts'], '0')
        self.assertFalse(web._FLIGHT.locked())
        for headers in ({'Host': 'evil.test'}, {'Origin': 'null'}):
            self.assertEqual(self.client.get('/api/bootstrap', headers=headers).status_code, 403)
        self.assertEqual(self.client.get('/api/bootstrap').headers['cache-control'], 'no-store')
        self.factory.assert_not_called()

    def test_raw_security_and_shared_flight(self):
        body = {'history': 'inventado', 'consent': True}
        for headers in ({}, self.headers | {'Origin': 'null'}, self.headers | {'Host': 'evil.test'},
                        self.headers | {'X-CSRF-Token': 'wrong'}):
            self.assertEqual(self.post(body, headers=headers, path='/api/raw-draft').status_code, 403)
        for content, content_type, status in [(b'{', 'application/json', 422),
                                              (b'\xff', 'application/json', 422),
                                              (b'{}', 'text/plain', 415)]:
            result = self.client.post('/api/raw-draft', content=content,
                                      headers=self.headers | {'Content-Type': content_type})
            self.assertEqual(result.status_code, status)
            self.assertEqual(result.headers['cache-control'], 'no-store')
        with web._FLIGHT:
            self.assertEqual(self.post(body, path='/api/raw-draft').status_code, 409)
        self.factory.assert_not_called()
        def runner(packet):
            self.assertTrue(web._FLIGHT.locked())
            self.assertEqual(self.draft().status_code, 409)
            self.assertEqual(self.post().status_code, 409)
            self.assertEqual(self.post({}, path='/api/demo').status_code, 409)
            self.assertEqual(self.post(body, path='/api/raw-draft').status_code, 409)
            return '{"type":"dm","text":"salida inventada"}'
        self.factory.return_value.side_effect = runner
        self.assertEqual(self.post(body, path='/api/raw-draft').status_code, 200)
        self.assertFalse(web._FLIGHT.locked())
        self.factory.return_value.assert_called_once()

    def test_real_rejects_before_runner_and_never_echoes(self):
        valid = {'history': 'Prospecto: texto ficticio', 'reviewed': True, 'consent': True}
        bodies = [{k: v for k, v in valid.items() if k != missing} for missing in valid]
        bodies += [valid | {key: value} for key in ('reviewed', 'consent')
                   for value in (False, 1, 'true', None, [], {})]
        bodies += [valid | {'history': value} for value in ('', 'Nombre: secreto', 1, [], 'Prospecto: ' + 'x' * 4001)]
        bodies += [valid | {key: 'override'} for key in ('current_rules', 'phase', 'guidance')]
        for body in bodies:
            response = self.post(body, path='/api/draft')
            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.json(), {'error': web.INVALID})
            self.assertEqual(response.headers['cache-control'], 'no-store')
        self.factory.assert_not_called()

    def test_structured_reviewed_messages(self):
        messages = [{'role': 'user', 'text': 'Horario: 18:30\nhttps://example.com/a:b'}]
        body = {'messages': messages, 'reviewed': True, 'consent': True}
        self.factory.return_value.return_value = 'salida ficticia'
        self.assertEqual(self.post(body, path='/api/draft').status_code, 200)
        self.assertEqual(vars(self.factory.return_value.call_args.args[0].messages[0]), messages[0])
        self.factory.reset_mock()
        invalid = [body | {'history': 'Prospecto: hola'}, body | {'history': None},
                   body | {'extra': True}, {'reviewed': True, 'consent': True}]
        invalid += [body | {key: value} for key in ('reviewed', 'consent')
                    for value in (False, 1, 'true', None)]
        invalid += [body | {'messages': value} for value in (None, {}, [], 'texto',
                    [{'role': role, 'text': 'hola'} for role in ('', 'system')],
                    [{'text': 'hola'}], [{'role': 'user', 'text': 1}],
                    [{'role': 'user', 'text': ' '}], [{'role': 'user', 'text': 'x', 'id': 'x'}],
                    [{'role': 'user', 'text': '😀' * 4001}],
                    [{'role': 'user', 'text': 'x'}] * 101,
                    [{'role': 'user', 'text': '😀' * 4000}] * 7)]
        for value in invalid:
            result = self.post(value, path='/api/draft')
            self.assertEqual(result.status_code, 422)
            self.assertEqual(result.json(), {'error': web.INVALID})
        self.factory.assert_not_called()

    def test_real_boundary_before_runner(self):
        for headers in ({}, self.headers | {'Origin': 'null'}, self.headers | {'Host': 'evil.test'},
                        self.headers | {'X-CSRF-Token': 'wrong'}):
            self.assertEqual(self.post({}, headers=headers, path='/api/draft').status_code, 403)
        for content, expected in [(b'{', 422), (b'\xff', 422), (b'x' * 300001, 413)]:
            result = self.client.post('/api/draft', content=content,
                                     headers=self.headers | {'Content-Type': 'application/json'})
            self.assertEqual(result.status_code, expected)
            self.assertEqual(result.headers['cache-control'], 'no-store')
        self.factory.assert_not_called()

    def test_real_large_unicode_body_and_limits(self):
        self.factory.return_value.return_value = 'salida ficticia'
        history = '\n'.join('Prospecto: ' + '😀' * 3900 for _ in range(6))
        self.assertEqual(self.draft(history=history).status_code, 200)
        self.factory.reset_mock()
        for history in ('Prospecto: a\n' * 101, 'Prospecto: ' + 'x' * 24001):
            self.assertEqual(self.draft(history=history).status_code, 422)
        self.factory.assert_not_called()
        response = self.client.post('/api/draft', content=iter([b'x' * 150001, b'y' * 150000]),
                                    headers=self.headers | {'Content-Type': 'application/json'})
        self.assertEqual(response.status_code, 413)
        self.factory.assert_not_called()

    def test_real_rule_failure_is_fixed_before_runner(self):
        with patch.object(web, 'load_real_rules', side_effect=RuntimeError('fictional internal detail')):
            response = self.draft()
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {'error': web.DRAFT_FAILURE})
        self.factory.assert_not_called()

    def test_real_single_call_server_rules_and_no_history_response(self):
        from tools.editorial_rag.real_history import (  # pyright: ignore[reportMissingImports]
            RealPacket,
            load_real_rules,
        )

        self.factory.return_value.return_value = 'qué querés mejorar?'
        response = self.draft()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'draft': 'qué querés mejorar?'})
        self.factory.return_value.assert_called_once()
        packet = self.factory.return_value.call_args.args[0]
        self.assertIs(type(packet), RealPacket)
        self.assertEqual(packet.current_rules, load_real_rules())
        self.assertNotIn('quiero fuerza', response.text)

    def test_real_failures_fixed_no_retry_and_lock_released(self):
        for value in ('', '   ', None, {}, RuntimeError('raw fictional input')):
            self.factory.return_value.reset_mock()
            self.factory.return_value.side_effect = value if isinstance(value, Exception) else None
            self.factory.return_value.return_value = value
            response = self.draft()
            self.assertEqual(response.status_code, 502)
            self.assertEqual(response.json(), {'error': web.DRAFT_FAILURE})
            self.factory.return_value.assert_called_once()
        self.factory.return_value.side_effect = None
        self.factory.return_value.return_value = 'salida ficticia'
        self.assertEqual(self.draft().status_code, 200)

    def test_real_shares_synthetic_single_flight(self):
        entered, release = threading.Event(), threading.Event()
        def runner(packet):
            entered.set()
            if not release.wait(5):
                raise RuntimeError('test timeout')
            return 'salida ficticia'
        self.factory.return_value.side_effect = runner
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(self.draft)
            try:
                self.assertTrue(entered.wait(5))
                self.assertEqual(self.draft().status_code, 409)
                self.assertEqual(self.post().status_code, 409)
                self.assertEqual(self.post({}, path='/api/demo').status_code, 409)
            finally:
                release.set()
            self.assertEqual(pending.result(timeout=5).status_code, 200)
        self.factory.assert_called_once()

    def test_organization_closed_consent_and_output(self):
        from tools.editorial_rag.test_organization import (  # pyright: ignore[reportMissingImports]
            blocks,
        )

        body = {'blocks': blocks(), 'reviewed': True, 'consent': True}
        invalid = [body | {key: value} for key in ('reviewed', 'consent')
                   for value in (False, 1, 'true', None)]
        invalid += [body | {'extra': True}, body | {'blocks': []},
                    body | {'blocks': blocks() * 2}]
        for value in invalid:
            self.assertEqual(self.post(value, path='/api/organize').status_code, 422)
        self.factory.assert_not_called()
        self.factory.return_value.return_value = ('{"assignments":['
            '{"id":"m-1","role":"assistant","uncertain":false},'
            '{"id":"m-2","role":"user","uncertain":true}]}')
        result = self.post(body, path='/api/organize')
        self.assertEqual(result.status_code, 200)
        self.assertEqual(len(result.json()['assignments']), 2)
        self.factory.return_value.assert_called_once()
        self.factory.return_value.reset_mock()
        self.factory.return_value.return_value = 'raw fictional invalid result'
        result = self.post(body, path='/api/organize')
        self.assertEqual(result.status_code, 502)
        self.assertEqual(result.json(), {'error': web.ORGANIZATION_FAILURE})
        self.factory.return_value.assert_called_once()
        with web._FLIGHT:
            self.assertEqual(self.post(body, path='/api/organize').status_code, 409)
        for headers in ({}, self.headers | {'Origin': 'null'}, self.headers | {'Host': 'evil.test'}):
            self.assertEqual(self.post(body, headers=headers, path='/api/organize').status_code, 403)

    def test_organization_limits_before_runner(self):
        from tools.editorial_rag.test_organization import (  # pyright: ignore[reportMissingImports]
            blocks,
        )

        body = {'blocks': blocks(), 'reviewed': True, 'consent': True}
        for values in ([blocks()[0] | {'text': 'x' * 4001}],
                       [blocks()[0] | {'time_context': 'x' * 201}],
                       [blocks()[0] | {'id': f'm-{i}', 'text': 'x' * 4000} for i in range(7)],
                       [blocks()[0] | {'id': f'm-{i}'} for i in range(101)],
                       [blocks()[0] | {'rewrite': True}]):
            self.assertEqual(self.post(body | {'blocks': values}, path='/api/organize').status_code, 422)
        result = self.client.post('/api/organize', content=iter([b'x' * 150001, b'y' * 150000]),
                                 headers=self.headers | {'Content-Type': 'application/json'})
        self.assertEqual(result.status_code, 413)
        self.factory.assert_not_called()

    def test_organization_holds_shared_lock_and_failure_releases_it(self):
        from tools.editorial_rag.test_organization import (  # pyright: ignore[reportMissingImports]
            blocks,
        )

        body = {'blocks': blocks(), 'reviewed': True, 'consent': True}
        entered, release = threading.Event(), threading.Event()
        def runner(packet):
            entered.set()
            if not release.wait(5):
                raise RuntimeError('test timeout')
            raise RuntimeError('raw fictional failure')
        self.factory.return_value.side_effect = runner
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(self.post, body, None, '/api/organize')
            try:
                self.assertTrue(entered.wait(5))
                self.assertEqual(self.draft().status_code, 409)
                self.assertEqual(self.post().status_code, 409)
                self.assertEqual(self.post({}, path='/api/demo').status_code, 409)
            finally:
                release.set()
            result = pending.result(timeout=5)
        self.assertEqual(result.status_code, 502)
        self.assertEqual(result.json(), {'error': web.ORGANIZATION_FAILURE})
        self.factory.return_value.assert_called_once()
        self.assertFalse(web._FLIGHT.locked())

    def test_context_is_fixed_and_never_constructs_runner(self):
        data = self.client.get('/api/context').json()
        self.assertEqual(data['messages'], [vars(m) for m in synthetic_case()[0].messages])
        self.assertEqual(data['phase'], 'brecha')
        self.assertEqual(data['model'], 'unknown')
        self.assertEqual(data['effort'], 'unknown')
        self.assertNotIn('drafts', data)
        self.assertIn('positive_voice', data['guidance'])
        self.factory.assert_not_called()

    def test_host_origin_token_and_missing_host_rejected(self):
        for headers in ({'Host': 'evil.test'}, {'Host': 'localhost:8765'},
                        {'Host': '127.0.0.1'}, {'Host': web.HOST + '.evil'},
                        {'Origin': 'https://evil.test'}):
            with self.subTest(headers=headers):
                self.assertEqual(self.client.get('/api/context', headers=headers).status_code, 403)
        # TestClient synthesizes Host when absent; test the raw ASGI boundary.
        downstream, send = AsyncMock(), AsyncMock()
        asyncio.run(web.LocalBoundary(downstream)(
            {'type': 'http', 'method': 'GET', 'headers': []}, AsyncMock(), send))
        self.assertEqual(send.call_args_list[0].args[0]['status'], 403)
        downstream.assert_not_called()
        for headers in ({}, {'Origin': web.ORIGIN}, {'X-CSRF-Token': self.token},
                        self.headers | {'Origin': 'null'},
                        self.headers | {'Origin': web.ORIGIN + '/'},
                        self.headers | {'X-CSRF-Token': 'wrong'}):
            self.assertEqual(self.post(headers=headers).status_code, 403)
        duplicate = list(self.headers.items()) + [('Host', web.HOST), ('Host', 'evil.test')]
        self.assertEqual(self.post(headers=duplicate).status_code, 403)
        self.factory.assert_not_called()

    def test_consent_exact_schema_and_redacted_validation(self):
        for body in ({}, {'consent': False}, {'consent': 1}, {'consent': 'true'},
                     {'consent': True, 'input': 'SYNTHETIC-REJECTED'},
                     {'consent': True, 'command': 'not permitted'}):
            response = self.post(body)
            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.json(), {'error': web.INVALID})
        response = self.client.post('/api/generate', content='{"consent":',
                                    headers=self.headers | {'Content-Type': 'application/json'})
        self.assertEqual(response.status_code, 422)
        self.factory.assert_not_called()

    def test_content_type_and_bounded_body(self):
        for content, content_type, expected in [('consent=true', 'text/plain', 415),
                                                ('x' * 257, 'application/json', 413)]:
            response = self.client.post('/api/generate', content=content,
                                        headers=self.headers | {'Content-Type': content_type})
            self.assertEqual(response.status_code, expected)
        self.factory.assert_not_called()

    def test_demo_is_manual_and_never_calls_codex(self):
        response = self.client.post('/api/demo', json={}, headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['mode'], 'simulated')
        self.assertIn('manual', response.json()['label'])
        self.assertEqual(set(response.json()['drafts']), {'current', 'editorial'})
        self.factory.assert_not_called()

    def test_success_two_calls_same_rules_complete_pair(self):
        self.factory.return_value.side_effect = ['primer borrador sintético?', 'segundo borrador sintético?']
        response = self.post()
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['mode'], 'codex')
        self.assertEqual(data['drafts']['current'], 'primer borrador sintético?')
        self.assertEqual(data['drafts']['editorial'], 'segundo borrador sintético?')
        self.assertEqual(self.factory.return_value.call_count, 2)
        first, second = [call.args[0] for call in self.factory.return_value.call_args_list]
        self.assertEqual((first.variant, second.variant), ('current', 'editorial'))
        self.assertEqual(first.current_rules, second.current_rules)
        self.assertIsNone(first.guidance)
        self.assertIsNotNone(second.guidance)
        self.assertIn('shared_trigrams', data['signals']['current'])
        self.assertNotIn('drafts', self.client.get('/api/context').json())

    def test_description_warnings_through_real_parser_deliver_complete_pair(self):
        self.factory.side_effect = runner_module.CodexSessionRunner
        drafts = ['primer borrador sintético?', 'segundo borrador sintético?']
        results = []
        for message, draft in zip(DESCRIPTION_WARNINGS, drafts, strict=True):
            results.extend([
                subprocess.CompletedProcess([], 0, 'Logged in using ChatGPT', ''),
                subprocess.CompletedProcess([], 0,
                    stream(warning_event(message)) + '\n' + success(draft), ''),
            ])
        with patch.object(runner_module.shutil, 'which', return_value='/synthetic/codex'), \
             patch.object(runner_module.subprocess, 'run', side_effect=results) as run:
            response = self.post()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['drafts'], dict(zip(('current', 'editorial'), drafts, strict=True)))
        self.assertEqual(run.call_count, 4)
        self.assertEqual(sum('exec' in call.args[0] for call in run.call_args_list), 2)
        self.assertNotIn('Skill descriptions', response.text)

    def test_failure_redacted_no_partial_and_lock_released(self):
        for results in ([RuntimeError('raw synthetic failure')],
                        ['partial synthetic draft', RuntimeError('raw synthetic failure')],
                        ['partial synthetic draft', '']):
            self.factory.return_value.side_effect = results
            response = self.post()
            self.assertEqual(response.status_code, 502)
            self.assertEqual(response.json(), {'error': web.FAILURE})
            self.assertNotIn('partial', response.text)
            self.assertNotIn('raw synthetic', response.text)
        self.factory.return_value.side_effect = ['uno?', 'dos?']
        self.assertEqual(self.post().status_code, 200)

    def test_busy_request_excluded_while_context_remains_available(self):
        entered, release = threading.Event(), threading.Event()
        def runner(packet):
            entered.set()
            if not release.wait(5):
                raise RuntimeError('test release timed out')
            return 'salida sintética?'
        self.factory.return_value.side_effect = runner
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(self.post)
            try:
                self.assertTrue(entered.wait(5))
                self.assertEqual(self.post().status_code, 409)
                self.assertEqual(self.draft().status_code, 409)
                self.assertEqual(self.client.post('/api/demo', json={}, headers=self.headers).status_code, 409)
                self.assertEqual(self.client.get('/api/context').status_code, 200)
            finally:
                release.set()
            self.assertEqual(pending.result(timeout=5).status_code, 200)
        self.assertEqual(self.factory.return_value.call_count, 2)

    def test_demo_requires_same_security_and_accepts_no_inputs(self):
        self.assertEqual(self.client.post('/api/demo', json={}).status_code, 403)
        response = self.client.post('/api/demo', json={'chat': 'synthetic'}, headers=self.headers)
        self.assertEqual(response.status_code, 422)
        self.factory.assert_not_called()

    def test_chunked_body_limit_without_content_length(self):
        response = self.client.post('/api/generate', content=iter([b'x' * 130, b'y' * 130]),
                                    headers=self.headers | {'Content-Type': 'application/json'})
        self.assertEqual(response.status_code, 413)
        self.factory.assert_not_called()

    def test_launch_is_fixed_loopback_without_logs_or_proxy_trust(self):
        with patch.object(web, 'socket') as sockets, patch('uvicorn.Server') as server, \
                patch('uvicorn.Config') as config, patch.object(web, 'production_auth', return_value=web.AppAuth()):
            self.assertEqual(web.main(), 0)
        options = config.call_args.kwargs
        sockets.socket.return_value.bind.assert_called_once_with(('127.0.0.1', 8765))
        server.return_value.run.assert_called_once_with(sockets=[sockets.socket.return_value])
        self.assertEqual(options['workers'], 1)
        self.assertFalse(options['access_log'])
        self.assertFalse(options['proxy_headers'])
        self.assertIsNone(options['log_config'])
        self.assertEqual(options['log_level'], 'critical')
        self.factory.assert_not_called()

    def test_compiled_assets_are_same_origin_and_source_maps_unavailable(self):
        if not (web.DIST / 'index.html').is_file():
            self.skipTest('Build the frontend to verify compiled assets')
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        paths = re.findall(r'(?:src|href)="([^"]+)"', response.text)
        self.assertTrue(paths)
        for path in paths:
            self.assertTrue(path.startswith('/assets/'))
            asset = self.client.get(path)
            self.assertEqual(asset.status_code, 200)
            self.assertEqual(asset.headers['cache-control'], 'no-store')
            self.assertEqual(self.client.get(path + '.map').status_code, 404)
        self.assertEqual(self.client.get('/', headers={'Host': 'evil.test'}).status_code, 403)
        self.factory.assert_not_called()

    def test_asset_directory_resolving_outside_dist_is_rejected_before_read(self):
        outside = web.DIST.parent / 'synthetic-outside'
        original_resolve = type(web.DIST).resolve
        def redirected(path, *args, **kwargs):
            if path == web.DIST / 'assets':
                return outside
            if path.parent == web.DIST / 'assets':
                return outside / path.name
            return original_resolve(path, *args, **kwargs)
        with patch('pathlib.Path.resolve', autospec=True, side_effect=redirected), \
             patch('pathlib.Path.is_file', return_value=True), \
             patch('pathlib.Path.read_bytes', return_value=b'synthetic file') as read:
            self.assertEqual(self.client.get('/assets/foreign.js').status_code, 404)
        read.assert_not_called()

    def test_security_headers_and_no_repository_exposure(self):
        for path in ('/api/context', '/docs', '/openapi.json', '/README.md', '/src/App.jsx',
                     '/assets/../../README.md', '/assets/%2e%2e%2flocal_web.py', '/assets/missing.js'):
            response = self.client.get(path)
            if path != '/api/context':
                self.assertEqual(response.status_code, 404)
            self.assertEqual(response.headers['cache-control'], 'no-store')
            self.assertEqual(response.headers['referrer-policy'], 'no-referrer')
            self.assertEqual(response.headers['x-content-type-options'], 'nosniff')
            self.assertEqual(response.headers['x-frame-options'], 'DENY')
            self.assertIn("default-src 'none'", response.headers['content-security-policy'])
            self.assertNotIn('set-cookie', response.headers)
            self.assertNotIn('access-control-allow-origin', response.headers)
        denied = self.post(headers={})
        self.assertEqual(denied.headers['cache-control'], 'no-store')
        self.factory.assert_not_called()

    def test_models_info_endpoint(self):
        response = self.client.get('/api/models')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('providers', data)
        providers = [p['id'] for p in data['providers']]
        self.assertIn('deepseek', providers)
        self.assertIn('openrouter', providers)
        self.assertIn('gemini', providers)

    def test_models_test_endpoint_mocked(self):
        with patch('tools.editorial_rag.api_runner.httpx.Client') as mock_client_cls:
            from unittest.mock import MagicMock
            mock_client = MagicMock()
            mock_client_cls.return_value.__enter__.return_value = mock_client
            mock_res = MagicMock()
            mock_res.status_code = 200
            mock_res.json.return_value = {'choices': [{'message': {'content': 'OK'}}]}
            mock_client.post.return_value = mock_res
            response = self.post({'provider': 'deepseek', 'api_key': 'sk-test'}, path='/api/models/test')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['status'], 'ok')

    def test_raw_draft_with_provider_config(self):
        with patch('tools.editorial_rag.local_web.create_runner') as mock_create:
            from unittest.mock import MagicMock
            mock_runner = MagicMock()
            mock_runner.return_value = '{"type":"dm","text":"hola con deepseek"}'
            mock_create.return_value = mock_runner
            response = self.post({
                'history': 'Lead: hola\nTato: buenas',
                'consent': True,
                'provider_config': {'provider': 'deepseek', 'api_key': 'sk-test'}
            }, path='/api/raw-draft')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['result'], {'type': 'dm', 'text': 'hola con deepseek'})
            mock_create.assert_called_once()


class CloudAuthTests(unittest.TestCase):
    """A managed deployment injects the bounded public configuration explicitly."""

    def test_cloud_injects_the_explicit_env_source(self):
        with patch.object(web, 'is_cloud_env', return_value=True), \
                patch('tools.editorial_rag.library_config.env_config') as source, \
                patch.object(web, 'AppAuth') as auth_class:
            web.production_auth()
        auth_class.assert_called_once_with(config_source=source)

    def test_off_cloud_keeps_the_local_file_source(self):
        with patch.object(web, 'is_cloud_env', return_value=False), \
                patch.object(web, 'os') as os_module, \
                patch('tools.editorial_rag.library_config.env_config') as source:
            os_module.name = 'posix'
            auth = web.production_auth()
        source.assert_not_called()
        self.assertIsInstance(auth, web.AppAuth)


if __name__ == '__main__':
    unittest.main()
