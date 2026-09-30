"""Offline password-login and manual check contracts; synthetic credentials only."""
import io
import json
import os
import sys
import unittest
import warnings
from pathlib import Path
from unittest.mock import Mock, patch

# Resolve legacy fixture imports for the dotted command, then restore the search path.
with patch.object(sys, 'path', [str(Path(__file__).resolve().parent), *sys.path]):
    import check_connection as cli
    import supabase_auth as auth
    from library_config import LibraryConfig
    from test_supabase_reader import BASE, ENV, OWNER, Response, jwt, row


class AuthTests(unittest.TestCase):
    def transport(self, body=None, status=200, content_type='application/json', url=None):
        def send(request, timeout):
            response = Response(json.dumps(body).encode() if not isinstance(body, bytes) else body)
            response.status = status
            response.headers = {'Content-Type': content_type}
            response.url = request.full_url if url is None else url
            return response
        return Mock(side_effect=send)

    def test_explicit_session_exchange_and_rotation_are_fixed_origin_and_bounded(self):
        config = LibraryConfig(1, BASE, 'sb_publishable_test', OWNER)
        token = jwt()
        for refresh in (False, True):
            send = self.transport({'access_token': token, 'refresh_token': 'fictional-rotated'})
            if refresh:
                result = auth.refresh_session('fictional-old', config=config, transport=send)
            else:
                result = auth.sign_in_session('fictional@example.invalid', 'fictional', config=config, transport=send)
            self.assertEqual(result, (token, 'fictional-rotated'))
            request = send.call_args.args[0]
            self.assertEqual(request.full_url, BASE + '/auth/v1/token?grant_type=' + ('refresh_token' if refresh else 'password'))
            self.assertEqual(json.loads(request.data), {'refresh_token': 'fictional-old'} if refresh else
                             {'email': 'fictional@example.invalid', 'password': 'fictional'})
        for value in ('', None, 'x' * 4097, 'bad\nrefresh'):
            send = self.transport({'access_token': token, 'refresh_token': value})
            with self.assertRaises(auth.AuthError):
                auth.refresh_session('fictional-old', config=config, transport=send)

    def test_password_post_returns_only_access_token_without_persistence(self):
        token = jwt()
        send = self.transport({'access_token': token, 'refresh_token': 'NEVER-STORE'})
        with (patch.dict(os.environ, ENV, clear=True), patch('builtins.open', side_effect=AssertionError),
              patch('socket.socket', side_effect=AssertionError)):
            before = dict(os.environ)
            self.assertEqual(auth.sign_in('synthetic@example.invalid', 'PASSWORD', transport=send), token)
            self.assertEqual(dict(os.environ), before)
        request = send.call_args.args[0]
        self.assertEqual(request.full_url, BASE + '/auth/v1/token?grant_type=password')
        self.assertEqual(request.get_method(), 'POST')
        self.assertEqual(json.loads(request.data), {'email': 'synthetic@example.invalid', 'password': 'PASSWORD'})
        self.assertEqual(request.get_header('Apikey'), ENV['EDITORIAL_SUPABASE_PUBLISHABLE_KEY'])
        self.assertEqual(send.call_args.kwargs['timeout'], 10)

    def test_trusted_public_config_is_optional_without_environment_mutation(self):
        config = LibraryConfig(1, BASE, 'sb_publishable_test', OWNER)
        send = self.transport({'access_token': jwt()})
        with patch.dict(os.environ, {}, clear=True):
            token = auth.sign_in('synthetic@example.invalid', 'PASSWORD', config=config, transport=send)
            self.assertTrue(token)
            self.assertEqual(dict(os.environ), {})
        self.assertEqual(send.call_args.args[0].get_header('Apikey'), 'sb_publishable_test')
        for invalid in ({}, 'fictional-secret'):
            send.reset_mock()
            with self.assertRaises(auth.AuthError):
                auth.sign_in('synthetic@example.invalid', 'PASSWORD', config=invalid, transport=send)
            send.assert_not_called()

    def test_invalid_configuration_never_sends(self):
        for env in [ENV | {'EDITORIAL_SUPABASE_URL': value} for value in
                    [BASE + '/', BASE + ':443', 'http://example.invalid', BASE + '.evil', BASE + '?x=1']
                    ] + [ENV | {'EDITORIAL_SUPABASE_PUBLISHABLE_KEY': 'sb_secret_bad'}]:
            with patch.dict(os.environ, env, clear=True):
                send = Mock()
                with self.assertRaises(auth.AuthError):
                    auth.sign_in('synthetic@example.invalid', 'PASSWORD', transport=send)
                send.assert_not_called()

    def test_response_rejection_and_redaction(self):
        cases = [self.transport({'access_token': jwt(role='service_role')}),
                 self.transport({'access_token': jwt(exp=0)}),
                 self.transport({'access_token': jwt(iss='wrong')}),
                 self.transport({'error': 'PASSWORD'}), self.transport(b'not json'),
                 self.transport(b'x' * (auth.MAX_BYTES + 1)),
                 self.transport({}, status=401), self.transport({}, status=302),
                 self.transport({}, content_type='text/html'),
                 self.transport({}, url='https://example.invalid'),
                 self.transport(b'{"access_token":1,"access_token":2}'),
                 Mock(side_effect=RuntimeError('PASSWORD JWT EMAIL SERVER'))]
        for send in cases:
            with patch.dict(os.environ, ENV, clear=True), self.assertRaises(auth.AuthError) as caught:
                auth.sign_in('synthetic@example.invalid', 'PASSWORD', transport=send)
            self.assertIsNone(caught.exception.__context__)
            self.assertEqual(str(caught.exception), 'Editorial authentication unavailable or rejected')

    def test_sanitized_failure_traceback_drops_credentials_and_transport(self):
        email, password, token = 'trace@example.invalid', 'TRACE-PASSWORD', jwt(exp=0)
        for env, send in [
                ({}, Mock()),
                (ENV, self.transport({'access_token': token})),
                (ENV, Mock(side_effect=RuntimeError(email + password + token)))]:
            with self.subTest(env_valid=bool(env)), patch.dict(os.environ, env, clear=True):
                try:
                    auth.sign_in(email, password, transport=send)
                except auth.AuthError as error:
                    self.assertIsNone(error.__context__)
                    self.assertIsNone(error.__cause__)
                    frames = []
                    trace = error.__traceback__
                    while trace is not None:
                        if trace.tb_frame.f_globals.get('__name__') == auth.__name__:
                            frames.append(trace.tb_frame)
                        trace = trace.tb_next
                    self.assertEqual([frame.f_code.co_name for frame in frames], ['sign_in'])
                    for frame in frames:
                        values = frame.f_locals
                        for name in ('email', 'password', 'transport'):
                            self.assertNotIn(name, values)
                        for value in values.values():
                            self.assertNotIsInstance(value, BaseException)
                            self.assertIsNot(value, send)
                            if isinstance(value, str):
                                for secret in (email, password, token):
                                    self.assertNotIn(secret, value)
                else:
                    self.fail('Expected sanitized authentication failure')

    def test_real_transport_bounds_disables_proxies_and_redirects(self):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.status = 200
        response.headers = {'Content-Type': 'application/json'}
        response.geturl.return_value = BASE + '/auth/v1/token?grant_type=password'
        response.read.return_value = json.dumps({'access_token': jwt()}).encode()
        opener = Mock()
        opener.open.return_value = response
        with (patch.dict(os.environ, ENV, clear=True), patch('socket.socket', side_effect=AssertionError),
              patch('supabase_reader.urllib.request.build_opener', return_value=opener) as build):
            auth.sign_in('synthetic@example.invalid', 'PASSWORD')
        self.assertEqual(build.call_args.args[0].proxies, {})
        with self.assertRaises(ValueError):
            build.call_args.args[1].redirect_request(None, None, 302, '', {}, 'https://example.invalid')
        response.read.assert_called_once_with(auth.MAX_BYTES + 1)


class ConnectionTests(unittest.TestCase):
    def test_end_to_end_post_then_read_only_get_and_count(self):
        requests = []
        token = jwt()
        def send(request, timeout):
            requests.append(request)
            body = {'access_token': token, 'refresh_token': 'NEVER-STORE'} if len(requests) == 1 else [row()]
            response = Response(json.dumps(body).encode())
            response.url = request.full_url
            return response
        output = io.StringIO()
        with (patch.dict(os.environ, ENV, clear=True), patch('builtins.input', return_value='synthetic@example.invalid'),
              patch('check_connection.getpass.getpass', return_value='PASSWORD'),
              patch('supabase_reader._transport', side_effect=send),
              patch('builtins.open', side_effect=AssertionError), patch('socket.socket', side_effect=AssertionError),
              patch('sys.stdout', output)):
            self.assertEqual(cli.main([]), 0)
        self.assertEqual(output.getvalue(), 'Connection successful; approved cards returned: 1\n')
        self.assertEqual([r.get_method() for r in requests], ['POST', 'GET'])
        self.assertIn('status=eq.approved', requests[1].full_url)
        self.assertEqual(requests[1].get_header('Authorization'), 'Bearer ' + token)

    def test_cli_failure_redaction_interrupt_and_no_echo_fallback(self):
        for failure in [RuntimeError('EMAIL PASSWORD JWT SERVER'), KeyboardInterrupt(), EOFError(),
                        getpass_warning()]:
            output, errors = io.StringIO(), io.StringIO()
            with (patch.dict(os.environ, ENV, clear=True), patch('builtins.input', return_value='synthetic@example.invalid'),
                  patch('check_connection.getpass.getpass', side_effect=failure),
                  patch('check_connection.sign_in') as sign_in,
                  patch('sys.stdout', output), patch('sys.stderr', errors)):
                self.assertEqual(cli.main([]), 1)
            sign_in.assert_not_called()
            self.assertEqual(output.getvalue(), '')
            self.assertEqual(errors.getvalue(), 'Connection check unavailable or rejected.\n')

    def test_cli_auth_and_reader_errors_never_print_context(self):
        for failing in ['check_connection.sign_in', 'check_connection.read_approved']:
            output, errors = io.StringIO(), io.StringIO()
            with (patch.dict(os.environ, ENV, clear=True),
                  patch('builtins.input', return_value='synthetic@example.invalid'),
                  patch('check_connection.getpass.getpass', return_value='PASSWORD'),
                  patch('check_connection.sign_in', return_value=jwt()),
                  patch('check_connection.read_approved', return_value=()),
                  patch(failing, side_effect=RuntimeError('EMAIL PASSWORD JWT SERVER')),
                  patch('sys.stdout', output), patch('sys.stderr', errors)):
                self.assertEqual(cli.main([]), 1)
            self.assertEqual(output.getvalue(), '')
            self.assertEqual(errors.getvalue(), 'Connection check unavailable or rejected.\n')

    def test_cli_empty_read_is_success(self):
        output = io.StringIO()
        with (patch.dict(os.environ, ENV, clear=True),
              patch('builtins.input', return_value='synthetic@example.invalid'),
              patch('check_connection.getpass.getpass', return_value='PASSWORD'),
              patch('check_connection.sign_in', return_value=jwt()),
              patch('check_connection.read_approved', return_value=()),
              patch('sys.stdout', output)):
            self.assertEqual(cli.main([]), 0)
        self.assertEqual(output.getvalue(), 'Connection successful; approved cards returned: 0\n')

    def test_cli_invalid_config_or_arguments_before_prompt(self):
        for args, env in [(['PASSWORD'], ENV), ([], ENV | {'EDITORIAL_SUPABASE_URL': BASE + '/'})]:
            with (patch.dict(os.environ, env, clear=True), patch('builtins.input') as prompt,
                  patch('sys.stderr', io.StringIO()), patch('socket.socket') as sock):
                self.assertEqual(cli.main(args), 1)
            prompt.assert_not_called()
            sock.assert_not_called()


def getpass_warning():
    def fallback(*args, **kwargs):
        import getpass
        warnings.warn('SECRET fallback', getpass.GetPassWarning, stacklevel=2)
        raise AssertionError('Must not reach echoing input')
    return fallback
