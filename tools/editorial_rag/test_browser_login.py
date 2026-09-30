"""Synthetic tests: real loopback HTTP, mocked Auth and reader only."""
import contextlib
import http.client
import io
import os
import re
import socket
import threading
import time
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

import tools.editorial_rag.browser_login as ui


class BrowserTests(unittest.TestCase):
    def setUp(self):
        self.auth = patch.object(ui, 'sign_in', return_value='synthetic-token').start()
        self.reader = patch.object(ui, 'read_approved', return_value=()).start()
        self.server = ui.LoginServer(lifetime=3)
        self.thread = threading.Thread(target=self.server.run)
        self.thread.start()
        self.addCleanup(patch.stopall)
        self.addCleanup(self.close)

    def close(self):
        self.server.stop()
        self.thread.join(4)
        self.assertFalse(self.thread.is_alive())

    def request(self, method='GET', path='/', body=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=2)
        started = time.monotonic()
        phase = 'request'
        try:
            conn.request(method, path, body, headers or {})
            phase = 'getresponse'
            response = conn.getresponse()
            phase = 'read_response'
            return response.status, dict(response.getheaders()), response.read().decode()
        except Exception as exc:
            now = time.monotonic()
            exc.add_note(f'HTTP phase={phase}; elapsed={now - started:.6f}s; '
                         f'server_remaining={self.server.deadline - now:.6f}s')
            raise
        finally:
            conn.close()

    def form(self):
        status, headers, body = self.request()
        self.assertEqual(status, 200)
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertIn("frame-ancestors 'none'", headers['Content-Security-Policy'])
        match = re.search(r'name="csrf" value="([^"]+)"', body)
        assert match is not None
        return match[1]

    def post(self, **overrides):
        fields = {'csrf': self.form(), 'email': 'synthetic@example.invalid',
                  'password': 'synthetic-password'}
        fields.update(overrides)
        return self.request('POST', '/', urlencode(fields), {
            'Origin': self.server.origin, 'Content-Type': 'application/x-www-form-urlencoded'})

    def test_success_zero_and_shutdown_no_secrets_or_logs(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            status, _, body = self.post()
        self.assertEqual(status, 200)
        self.assertIn('0', body)
        for secret in ('synthetic@example.invalid', 'synthetic-password', 'synthetic-token'):
            self.assertNotIn(secret, body + output.getvalue())
        self.assertEqual(output.getvalue(), '')
        self.auth.assert_called_once_with('synthetic@example.invalid', 'synthetic-password')
        self.reader.assert_called_once_with('synthetic-token', limit=50)
        self.thread.join(2)
        self.assertFalse(self.thread.is_alive())

    def raw_post(self, body, extra=(), length=None):
        headers = [f'Host: 127.0.0.1:{self.server.server_port}',
                   f'Origin: {self.server.origin}',
                   'Content-Type: application/x-www-form-urlencoded',
                   f'Content-Length: {len(body) if length is None else length}', *extra]
        with socket.create_connection(('127.0.0.1', self.server.server_port), timeout=2) as conn:
            conn.sendall(('POST / HTTP/1.1\r\n' + '\r\n'.join(headers) + '\r\n\r\n').encode() + body)
            conn.shutdown(socket.SHUT_WR)
            response = http.client.HTTPResponse(conn)
            response.begin()
            return response.status, response.read().decode()

    def test_duplicate_headers_fields_and_malformed_bodies(self):
        valid = urlencode({'csrf': self.server.nonce, 'email': 'synthetic@example.invalid',
                           'password': 'synthetic-password'}).encode()
        cases = [(valid, (f'Host: 127.0.0.1:{self.server.server_port}',), None),
                 (valid, (f'Origin: {self.server.origin}',), None),
                 (valid, (f'Content-Length: {len(valid)}',), None)]
        cases += [(valid + b'&' + field + b'=duplicate', (), None)
                  for field in (b'csrf', b'email', b'password')]
        cases += [(valid, (), length) for length in ('-1', 'abc', '1.5', '0000001')]
        cases += [(valid + suffix, (), None) for suffix in (b'\xff', b'%FF')]
        cases += [(valid[:-3], (), len(valid))]
        for body, extra, length in cases:
            with self.subTest(extra=extra, length=length, size=len(body)):
                status, response = self.raw_post(body, extra, length)
                self.assertGreaterEqual(status, 400)
                self.assertIn(ui.FAILURE, response)
                self.assertNotIn('synthetic-password', response)
        self.auth.assert_not_called()
        self.assertEqual(self.server.attempts, 0)

    def test_stalled_auth_job_cannot_extend_deadline(self):
        self.close()
        release = threading.Event()
        entered = threading.Event()
        finished = threading.Event()

        def stalled(*args):
            entered.set()
            try:
                release.wait(2)
                raise ValueError('synthetic-password')
            finally:
                finished.set()

        self.auth.side_effect = stalled
        self.server = ui.LoginServer(lifetime=0.3)
        self.thread = threading.Thread(target=self.server.run)
        self.thread.start()
        try:
            with contextlib.suppress(OSError, http.client.HTTPException):
                self.post()
            self.assertTrue(entered.is_set())
            self.thread.join(1)
            self.assertFalse(self.thread.is_alive())
            self.assertFalse(self.server.success)
        finally:
            release.set()
            self.assertTrue(finished.wait(1))

    @contextlib.contextmanager
    def boundary_case(self, label):
        started = time.monotonic()
        remaining = self.server.deadline - started
        with self.subTest(case=label):
            try:
                yield
            except Exception as exc:
                now = time.monotonic()
                exc.add_note(f'fixture={label}; elapsed={now - started:.6f}s; '
                             f'server_remaining_start={remaining:.6f}s; '
                             f'server_remaining={self.server.deadline - now:.6f}s')
                raise

    def test_reject_boundaries(self):
        for label, method, path, body, headers in [
            ('invalid_host', 'GET', '/', None, {'Host': 'evil.invalid'}),
            ('invalid_origin', 'GET', '/', None, {'Origin': 'http://evil.invalid'}),
            ('unknown_path', 'GET', '/other', None, {}),
            ('unsupported_method', 'PUT', '/', '', {}),
            ('invalid_content_type', 'POST', '/', '', {'Origin': self.server.origin,
                'Content-Type': 'text/plain'}),
            ('missing_origin', 'POST', '/', '', {'Content-Type': 'application/x-www-form-urlencoded'}),
            ('oversized_body', 'POST', '/', 'x' * (ui.MAX_BODY + 1), {'Origin': self.server.origin,
                'Content-Type': 'application/x-www-form-urlencoded'}),
        ]:
            with self.boundary_case(label):
                self.assertGreaterEqual(self.request(method, path, body, headers)[0], 400)
        with self.boundary_case('invalid_csrf'):
            self.assertGreaterEqual(self.post(csrf='wrong')[0], 400)
        self.auth.assert_not_called()

    def test_failures_are_generic_and_attempts_bounded(self):
        self.auth.side_effect = ValueError('synthetic-password')
        for _ in range(3):
            status, _, body = self.post()
            self.assertEqual(status, 400)
            self.assertNotIn('synthetic-password', body)
        self.thread.join(2)
        self.assertFalse(self.thread.is_alive())

    def test_reader_failure_does_not_report_success(self):
        self.reader.side_effect = ValueError('synthetic-token')
        status, _, body = self.post()
        self.assertEqual(status, 400)
        self.assertNotIn('synthetic-token', body)

    def test_stalled_headers_cannot_extend_deadline(self):
        self.close()
        self.server = ui.LoginServer(lifetime=0.2)
        self.thread = threading.Thread(target=self.server.run)
        self.thread.start()
        with socket.create_connection(('127.0.0.1', self.server.server_port), timeout=1) as conn:
            conn.sendall(b'GET / HTTP/1.1\r\nHost: ')
            self.thread.join(1)
            self.assertFalse(self.thread.is_alive())

    def test_deadline(self):
        self.close()
        self.server = ui.LoginServer(lifetime=0.15)
        self.thread = threading.Thread(target=self.server.run)
        self.thread.start()
        self.thread.join(1)
        self.assertFalse(self.thread.is_alive())


class PromptTests(unittest.TestCase):
    def test_main_real_server_outcomes(self):
        real_server = ui.LoginServer
        for outcome in ('timeout', 'rejected', 'reader_failure', 'cancelled', 'interrupt', 'success', 'send_failure'):
            with self.subTest(outcome=outcome):
                server = real_server(lifetime=0.2)
                errors = io.StringIO()
                clients = []
                def browser(*args, outcome=outcome, server=server, clients=clients, **kwargs):
                    if outcome == 'cancelled':
                        return False
                    if outcome == 'interrupt':
                        raise KeyboardInterrupt
                    if outcome != 'timeout':
                        def submit():
                            for _ in range(3 if outcome == 'rejected' else 1):
                                conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=1)
                                try:
                                    conn.request('POST', '/', urlencode({'csrf': server.nonce,
                                        'email': 'synthetic@example.invalid', 'password': 'synthetic-password'}),
                                        {'Origin': server.origin, 'Content-Type': 'application/x-www-form-urlencoded'})
                                    conn.getresponse().read()
                                except (OSError, http.client.HTTPException):
                                    pass
                                finally:
                                    conn.close()
                        client = threading.Thread(target=submit)
                        clients.append(client)
                        client.start()
                    return True
                with patch.dict(os.environ, {'EDITORIAL_SUPABASE_PUBLISHABLE_KEY': 'sb_publishable_synthetic'}, clear=True), \
                        patch.object(ui, 'LoginServer', return_value=server), \
                        patch.object(ui.webbrowser, 'open', side_effect=browser), \
                        patch.object(ui, 'sign_in', side_effect=ValueError('synthetic-password') if outcome == 'rejected' else None,
                                     return_value='synthetic-token'), \
                        patch.object(ui, 'read_approved', side_effect=ValueError('synthetic-token') if outcome == 'reader_failure' else None,
                                     return_value=()), \
                        contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(errors), \
                        contextlib.ExitStack() as stack:
                    if outcome == 'send_failure':
                        stack.enter_context(patch.object(ui.LoginHandler, 'reply', side_effect=OSError('synthetic-password')))
                    result = ui.main([])
                    for client in clients:
                        client.join(2)
                        self.assertFalse(client.is_alive())
                self.assertEqual(result, 0 if outcome == 'success' else 1)
                self.assertEqual(errors.getvalue(), '' if outcome == 'success' else ui.FAILURE + '\n')

    def test_hidden_prompt_and_fixed_origin_without_network(self):
        with patch.dict(os.environ, {}, clear=True), \
                patch.object(ui.getpass, 'getpass', return_value='sb_publishable_synthetic') as prompt, \
                patch.object(ui, 'LoginServer') as server, \
                patch.object(ui.webbrowser, 'open', return_value=True), \
                contextlib.redirect_stdout(io.StringIO()):
            server.return_value.__enter__.return_value.success = True
            self.assertEqual(ui.main([]), 0)
            prompt.assert_called_once()
            server.return_value.__enter__.return_value.run.assert_called_once()
            self.assertNotIn('EDITORIAL_SUPABASE_PUBLISHABLE_KEY', os.environ)

    def test_no_echo_fallback_no_browser_or_server(self):
        with patch.dict(os.environ, {}, clear=True), \
                patch.object(ui.getpass, 'getpass', side_effect=ui.getpass.GetPassWarning), \
                patch.object(ui, 'LoginServer') as server, \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(ui.main([]), 1)
            server.assert_not_called()

    def test_arguments_and_wrong_project_fail_before_prompt(self):
        for args, endpoint in [(['forbidden'], None), ([], 'https://other.invalid')]:
            env = {} if endpoint is None else {'EDITORIAL_SUPABASE_URL': endpoint}
            with patch.dict(os.environ, env, clear=True), \
                    patch.object(ui.getpass, 'getpass') as prompt, \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(ui.main(args), 1)
                prompt.assert_not_called()


if __name__ == '__main__':
    unittest.main()
