"""Fixed-origin password and refresh exchanges; no storage or automatic retries."""
import json
import os
import re
import urllib.request

if __package__:
    from . import supabase_reader as reader
else:
    import supabase_reader as reader

MAX_BYTES = 65536


def sign_in_session(email, password, *, config, transport=None):
    """Explicit server-only session exchange; never return either token to the UI."""
    try:
        return _sign_in(email, password, reader._transport if transport is None else transport, config, session=True)
    except Exception:
        del email, password, config, transport
    raise AuthError('Editorial authentication unavailable or rejected')


def refresh_session(token, *, config, transport=None):
    """One bounded exchange, with sanitized errors and no retry."""
    try:
        return _sign_in(None, None, reader._transport if transport is None else transport, config,
                        session=True, refresh=token)
    except Exception:
        del token, config, transport
    raise AuthError('Editorial authentication unavailable or rejected')


def _valid_refresh(token):
    return (type(token) is str and 1 <= len(token) <= 4096
            and all(33 <= ord(char) <= 126 for char in token))


class AuthError(RuntimeError):
    """Fixed diagnostic without server content or credential context."""


def configuration():
    """Validate the exact project before prompting or transmitting credentials."""
    endpoint = os.environ.get('EDITORIAL_SUPABASE_URL')
    key = os.environ.get('EDITORIAL_SUPABASE_PUBLISHABLE_KEY', '')
    if (endpoint != 'https://' + reader.PROJECT_REF + '.supabase.co'
            or not re.fullmatch(r'sb_publishable_[A-Za-z0-9_-]{1,256}', key)):
        raise AuthError('Editorial authentication unavailable or rejected')
    return endpoint, key


def _sign_in(email, password, transport, config, session=False, refresh=None):
    if config is None:
        endpoint, key = configuration()
    else:
        if __package__:
            from .library_config import LibraryConfig
        else:
            from library_config import LibraryConfig
        if type(config) is not LibraryConfig:
            raise ValueError('Validated configuration required')
        config.__post_init__()
        endpoint, key = config.project_url, config.publishable_key
    if refresh is not None:
        if not _valid_refresh(refresh):
            raise ValueError('Invalid credentials')
        payload, grant = {'refresh_token': refresh}, 'refresh_token'
    else:
        if (type(email) is not str or not 1 <= len(email) <= 320 or '@' not in email
                or any(char.isspace() or ord(char) < 32 for char in email)
                or type(password) is not str or not 1 <= len(password) <= 4096):
            raise ValueError('Invalid credentials')
        payload, grant = {'email': email, 'password': password}, 'password'
    url = endpoint + '/auth/v1/token?grant_type=' + grant
    # configuration() binds this URL to one exact HTTPS origin and fixed path.
    request = urllib.request.Request(url, method='POST',  # noqa: S310
        data=json.dumps(payload).encode('utf-8'),
        headers={'apikey': key, 'Content-Type': 'application/json',
                 'Accept': 'application/json', 'Accept-Encoding': 'identity'})
    with transport(request, timeout=reader.TIMEOUT) as response:
        if (response.status != 200 or response.geturl() != url
                or response.headers.get('Content-Type', '').split(';')[0] != 'application/json'):
            raise ValueError('Rejected response')
        body = response.read(MAX_BYTES + 1)
    if type(body) is not bytes or len(body) > MAX_BYTES:
        raise ValueError('Oversized response')
    result = reader._json(body)
    if type(result) is not dict:
        raise ValueError('Invalid response')
    token = result.get('access_token')
    reader._claims(token, endpoint)
    if session:
        refresh_token = result.get('refresh_token')
        if not _valid_refresh(refresh_token):
            raise ValueError('Invalid response')
        return token, refresh_token
    return token


def sign_in(email, password, *, transport=None, config=None):
    """Return only an in-memory access JWT; discard refresh token and user data.

    Local claims are a preflight, NOT signature verification. The authenticated
    reader request must follow; Supabase verifies signature and authorization.
    Injected transport is trusted test code. Never log inputs or returned tokens.
    """
    try:
        return _sign_in(email, password, reader._transport if transport is None else transport, config)
    except Exception:
        # Drop arguments, including transports that may retain requests or exceptions.
        del email, password, transport, config
    # Outside the handler so sensitive exceptions are not chained or retained.
    raise AuthError('Editorial authentication unavailable or rejected')
