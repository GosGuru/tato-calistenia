"""Opt-in one-shot loopback Auth check. Never imported by the setter."""
import contextlib
import getpass
import os
import queue
import secrets
import socket
import sys
import threading
import time
import warnings
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import cast
from urllib.parse import parse_qs

from .supabase_auth import configuration, sign_in
from .supabase_reader import MAX_CARDS, PROJECT_REF, read_approved

MAX_BODY = 16384
LIFETIME = 180
FAILURE = 'No se pudo completar la verificación.'


class LoginServer(HTTPServer):
    """Single serial request processor; no LAN binding or persistent sessions."""
    allow_reuse_address = False

    def __init__(self, *, lifetime: float = LIFETIME):
        self.deadline = time.monotonic() + min(lifetime, LIFETIME)
        self.done = threading.Event()
        self.success = False
        self.active = None
        self.attempts = 0
        self.nonce = secrets.token_urlsafe(32)
        super().__init__(('127.0.0.1', 0), LoginHandler)
        self.origin = f'http://127.0.0.1:{self.server_port}'
        self.timeout = 0.1

    def get_request(self):
        sock, address = super().get_request()
        self.active = sock
        sock.settimeout(max(0.001, min(2, self.deadline - time.monotonic())))
        return sock, address

    def handle_error(self, request, client_address):
        pass  # Never emit traceback, request path, headers or credentials.

    def stop(self):
        self.done.set()
        if self.active is not None:
            with contextlib.suppress(OSError):
                self.active.shutdown(socket.SHUT_RDWR)
            self.active.close()
        self.server_close()

    def run(self):
        watchdog = threading.Timer(max(0, self.deadline - time.monotonic()), self.stop)
        watchdog.daemon = True
        watchdog.start()
        try:
            while not self.done.is_set() and time.monotonic() < self.deadline:
                try:
                    self.handle_request()
                except (OSError, ValueError):
                    break
        finally:
            watchdog.cancel()
            self.stop()
            self.nonce = ''


class LoginHandler(BaseHTTPRequestHandler):
    @property
    def app(self):
        return cast(LoginServer, self.server)

    def log_message(self, format, *args):
        pass

    def send_error(self, code, message=None, explain=None):
        self.reply(code, FAILURE)

    def reply(self, status, content):
        self.close_connection = True
        body = ('<!doctype html><html lang="es"><meta charset="utf-8">'
                '<title>Verificación editorial</title>' + content + '</html>').encode('utf-8')
        self.send_response(status)
        for key, value in {
            'Content-Type': 'text/html; charset=utf-8',
            'Content-Length': str(len(body)), 'Connection': 'close',
            'Cache-Control': 'no-store', 'Pragma': 'no-cache',
            'Content-Security-Policy': "default-src 'none'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'",
            'X-Frame-Options': 'DENY', 'Referrer-Policy': 'no-referrer',
            'X-Content-Type-Options': 'nosniff',
        }.items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def valid(self, *, post=False):
        def values(name):
            return self.headers.get_all(name, [])
        origin = values('Origin')
        return (not self.app.done.is_set()
                and time.monotonic() < self.app.deadline
                and self.path == '/'
                and values('Host') == [self.app.origin.removeprefix('http://')]
                and (origin == [self.app.origin] if post else origin in ([], [self.app.origin]))
                and not values('Transfer-Encoding') and not values('Expect')
                and not values('Content-Encoding')
                and values('Sec-Fetch-Site') in ([], ['none'], ['same-origin']))

    def do_GET(self):
        if not self.valid() or self.headers.get_all('Content-Length', []) not in ([], ['0']):
            self.reply(400, FAILURE)
            return
        self.reply(200, '<h1>Verificar acceso editorial</h1>'
            '<p>Usá un usuario Auth dedicado, no tu cuenta del Dashboard.</p>'
            '<form method="post" action="/" autocomplete="off">'
            f'<input type="hidden" name="csrf" value="{self.app.nonce}">'
            '<label>Email <input name="email" type="email" maxlength="320" required autocomplete="off"></label>'
            '<label>Contraseña <input name="password" type="password" maxlength="4096" required autocomplete="off"></label>'
            '<button type="submit">Verificar</button></form>')

    def do_POST(self):
        if (not self.valid(post=True)
                or self.headers.get_all('Content-Type', []) != ['application/x-www-form-urlencoded']):
            self.reply(400, FAILURE)
            return
        lengths = self.headers.get_all('Content-Length', [])
        if (len(lengths) != 1 or len(lengths[0]) > 6
                or not lengths[0].isascii() or not lengths[0].isdigit()):
            self.reply(400, FAILURE)
            return
        try:
            size = int(lengths[0])
        except ValueError:
            self.reply(400, FAILURE)
            return
        if not 0 < size <= MAX_BODY:
            self.reply(413, FAILURE)
            return
        try:
            body = self.rfile.read(size)
            if len(body) != size:
                raise ValueError
            fields = parse_qs(body.decode('utf-8'), strict_parsing=True,
                              keep_blank_values=True, max_num_fields=3, errors='strict')
            del body
            if (set(fields) != {'csrf', 'email', 'password'}
                    or any(len(value) != 1 for value in fields.values())
                    or not secrets.compare_digest(fields['csrf'][0], self.app.nonce)):
                raise ValueError
        except Exception:
            self.reply(400, FAILURE)
            return
        self.app.attempts += 1
        # A daemon job allows the local listener/process to end at its deadline even
        # if the remote socket dribbles data indefinitely. No retries or persistence.
        result = queue.Queue(maxsize=1)
        job = threading.Thread(target=_check, args=(fields['email'][0], fields['password'][0], result), daemon=True)
        del fields
        job.start()
        try:
            count = result.get(timeout=max(0.001, self.app.deadline - time.monotonic()))
        except queue.Empty:
            count = None
        finished = count is not None or self.app.attempts >= 3
        try:
            self.reply(200 if count is not None else 400,
                       f'Acceso verificado. Fichas aprobadas devueltas: {count}.' if count is not None else FAILURE)
            if count is not None:
                self.app.success = True
        finally:
            if finished:
                self.app.done.set()


def _check(email, password, result):
    count = None
    try:
        token = sign_in(email, password)
        del email, password
        try:
            cards = read_approved(token, limit=MAX_CARDS)
            count = len(cards)
            del cards
        finally:
            del token
    except Exception:
        count = None  # Intentionally no logs: exceptions can contain credentials.
    result.put(count)


def main(argv=None):
    names = ('EDITORIAL_SUPABASE_URL', 'EDITORIAL_SUPABASE_PUBLISHABLE_KEY')
    previous = {name: os.environ.get(name) for name in names}
    try:
        if (sys.argv[1:] if argv is None else argv):
            raise ValueError
        expected = 'https://' + PROJECT_REF + '.supabase.co'
        if previous[names[0]] not in (None, expected):
            raise ValueError
        os.environ[names[0]] = expected
        if not previous[names[1]]:
            with warnings.catch_warnings():
                warnings.simplefilter('error', getpass.GetPassWarning)
                os.environ[names[1]] = getpass.getpass('Clave publishable del proyecto (oculta): ')
        configuration()
        with LoginServer() as server:
            print('Chequeo local temporal. Usá un navegador confiable sin extensiones; no guardes la contraseña.')
            # Only the fixed local origin is passed to the browser, never credentials.
            if not webbrowser.open(server.origin + '/', new=1):
                raise ValueError
            server.run()
            if not server.success:
                raise ValueError
        return 0
    except (Exception, KeyboardInterrupt):
        print(FAILURE, file=sys.stderr)
        return 1
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


if __name__ == '__main__':
    raise SystemExit(main())
