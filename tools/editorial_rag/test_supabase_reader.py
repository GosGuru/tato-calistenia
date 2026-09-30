"""Offline synthetic persistence boundary tests."""
import base64
import io
import json
import time
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit

from supabase_reader import MAX_BYTES, ReaderError, _NoRedirect, read_approved
from test_prototype import card

REF = 'cgoosfuwohjupcbwdaty'
BASE = 'https://' + REF + '.supabase.co'
OWNER = '11111111-1111-4111-8111-111111111111'
ENV = {'EDITORIAL_SUPABASE_URL': BASE, 'EDITORIAL_SUPABASE_PUBLISHABLE_KEY': 'sb_publishable_synthetic'}


def jwt(**changes):
    claims = {'iss': BASE + '/auth/v1', 'sub': OWNER, 'role': 'authenticated',
              'aud': 'authenticated', 'exp': int(time.time()) + 300}
    def part(value):
        return base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip('=')
    return part({'alg': 'ES256', 'typ': 'JWT'}) + '.' + part(claims | changes) + '.c2ln'


def row(**changes):
    return asdict(card()) | {'owner_id': OWNER, 'approval_id': 'approval-001'} | changes


class Response(io.BytesIO):
    url = ''
    status = 200
    headers = {'Content-Type': 'application/json'}
    def geturl(self):
        return self.url


class MigrationContractTests(unittest.TestCase):
    def test_one_shot_transaction_never_replaces_existing_objects(self):
        # Static guard only: this does not execute or validate PostgreSQL behavior.
        sql = Path(__file__).with_name('001_editorial_cards.sql').read_text(encoding='utf-8')
        statements = '\n'.join(line.split('--', 1)[0] for line in sql.splitlines()).lower().strip()
        self.assertTrue(statements.startswith('begin;'))
        self.assertTrue(statements.endswith('commit;'))
        self.assertNotIn('if not exists', statements)
        self.assertNotIn('or replace', statements)
        self.assertNotRegex(statements, r'\bdrop\s')
        for declaration in ('create table public.editorial_cards',
                            'create function public.editorial_invalidate_approval()',
                            'create trigger editorial_invalidate_approval'):
            self.assertIn(declaration, statements)


class ReaderTests(unittest.TestCase):
    def call(self, rows=None, token=None, env=None, **kwargs):
        seen = []
        def transport(request, timeout):
            seen.append((request, timeout))
            response = Response(json.dumps([row()] if rows is None else rows).encode())
            response.url = request.full_url
            return response
        with patch.dict('os.environ', ENV if env is None else env, clear=True):
            result = read_approved(jwt() if token is None else token,
                                   transport=transport, **kwargs)
        return result, seen

    def test_auth_filter_bounds_and_conversion(self):
        token = jwt()
        result, seen = self.call(token=token, limit=3)
        self.assertEqual(result, (card(),))
        request, timeout = seen[0]
        self.assertEqual(request.get_method(), 'GET')
        self.assertEqual(request.get_header('Authorization'), 'Bearer ' + token)
        self.assertEqual(request.get_header('Apikey'), ENV['EDITORIAL_SUPABASE_PUBLISHABLE_KEY'])
        query = parse_qs(urlsplit(request.full_url).query)
        self.assertEqual(query['status'], ['eq.approved'])
        self.assertEqual(query['owner_id'], ['eq.' + OWNER])
        self.assertEqual(query['limit'], ['3'])
        self.assertLessEqual(timeout, 10)

    def test_invalid_inputs_never_reach_transport(self):
        urls = [BASE + '/', BASE + ':443', BASE + '/rest/v1', BASE + '?x=1',
                BASE + '#fragment', BASE.replace('https:', 'http:'),
                BASE + '.evil.test', BASE.replace('https://', 'https://user@'),
                BASE.replace(REF, 'other'), ' ' + BASE, BASE + '\n',
                BASE.replace('https://', 'https://%63'), BASE + '\\evil']
        cases = [(jwt(), ENV | {'EDITORIAL_SUPABASE_URL': url}, {}) for url in urls]
        cases += [(token, ENV, {}) for token in ['', 'invalid', jwt(role='service_role'),
                  jwt(exp=0), jwt(iss='https://other/auth/v1'), jwt(sub='invalid'),
                  jwt(aud='anon'), jwt(exp=True)]]
        cases += [(jwt(), ENV, {'limit': value}) for value in [0, 51, True, '2']]
        cases += [(jwt(), ENV | {'EDITORIAL_SUPABASE_PUBLISHABLE_KEY': 'sb_secret_bad'}, {})]
        for token, env, kwargs in cases:
            with (self.subTest(token=token[:8], env_url=env.get('EDITORIAL_SUPABASE_URL')),
                  patch.dict('os.environ', env, clear=True), patch('socket.socket') as sock):
                transport = Mock()
                with self.assertRaises(ReaderError):
                    read_approved(token, transport=transport, **kwargs)
                transport.assert_not_called()
                sock.assert_not_called()

    def test_reject_every_invalid_card_and_duplicates(self):
        changes = [{'owner_id': '22222222-2222-4222-8222-222222222222'},
                   {'status': 'candidate'}, {'raw_quote': 'forbidden'}, {'sanitized': 1},
                   {'phase': 'other'}, {'approval_id': None}, {'provenance_id': '../raw'},
                   {'positive_voice': ''}, {'situation': 'x' * 2001}, {'gate': []}]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ReaderError):
                self.call(rows=[row(**change)])
        for rows in [[row(), row()], [row()]*4, {}, [None], [row() | {'card_id': None}]]:
            with self.assertRaises(ReaderError):
                self.call(rows=rows, limit=3)
        missing = row()
        del missing['gate']
        with self.assertRaises(ReaderError):
            self.call(rows=[missing])

    def test_real_transport_disables_proxies_redirects_and_bounds_read(self):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.status = 200
        response.headers = {'Content-Type': 'application/json'}
        response.read.return_value = b'[]'
        opener = Mock()
        def open_response(request, timeout):
            response.geturl.return_value = request.full_url
            self.assertEqual(timeout, 10)
            return response
        opener.open.side_effect = open_response
        with (patch.dict('os.environ', ENV, clear=True),
              patch('socket.socket', side_effect=AssertionError('network')),
              patch('supabase_reader.urllib.request.build_opener', return_value=opener) as build):
            self.assertEqual(read_approved(jwt()), ())
        handlers = build.call_args.args
        self.assertEqual(handlers[0].proxies, {})
        self.assertIsInstance(handlers[1], _NoRedirect)
        response.read.assert_called_once_with(MAX_BYTES + 1)
        with self.assertRaises(ValueError):
            handlers[1].redirect_request(None, None, 302, '', {}, 'https://evil.test')

    def test_sanitized_failure_traceback_drops_token_and_transport(self):
        token = jwt()
        for env, send in [({}, Mock()),
                          (ENV, Mock(return_value=Response(b'not json'))),
                          (ENV, Mock(side_effect=RuntimeError(token)))]:
            with self.subTest(env_valid=bool(env)), patch.dict('os.environ', env, clear=True):
                try:
                    read_approved(token, transport=send)
                except ReaderError as error:
                    self.assertIsNone(error.__context__)
                    self.assertIsNone(error.__cause__)
                    frames = []
                    trace = error.__traceback__
                    while trace is not None:
                        if trace.tb_frame.f_globals.get('__name__') == read_approved.__module__:
                            frames.append(trace.tb_frame)
                        trace = trace.tb_next
                    self.assertEqual([frame.f_code.co_name for frame in frames], ['read_approved'])
                    for frame in frames:
                        values = frame.f_locals
                        for name in ('jwt', 'transport', 'limit'):
                            self.assertNotIn(name, values)
                        for value in values.values():
                            self.assertNotIsInstance(value, BaseException)
                            self.assertIsNot(value, send)
                            if isinstance(value, str):
                                self.assertNotIn(token, value)
                else:
                    self.fail('Expected sanitized reader failure')

    def test_response_and_transport_fail_closed(self):
        for body, status, url in [(b'x' * (MAX_BYTES + 1), 200, None),
                                  (b'not json', 200, None), (b'[]', 401, None),
                                  (b'[]', 302, None), (b'[]', 200, 'https://evil.test')]:
            def transport(request, timeout, body=body, status=status, url=url):
                response = Response(body)
                response.status = status
                response.url = url or request.full_url
                return response
            with patch.dict('os.environ', ENV, clear=True), self.assertRaises(ReaderError):
                read_approved(jwt(), transport=transport)
        with patch.dict('os.environ', ENV, clear=True):
            with self.assertRaises(ReaderError) as caught:
                read_approved(jwt(), transport=Mock(side_effect=RuntimeError('SECRET')))
            self.assertIsNone(caught.exception.__context__)
            self.assertNotIn('SECRET', str(caught.exception))


if __name__ == '__main__':
    unittest.main()
