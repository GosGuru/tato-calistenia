"""Opt-in, bounded PostgREST reads. No login, writes, persistence or runtime hook."""
import base64
import json
import os
import re
import time
import urllib.request
from dataclasses import fields
from urllib.parse import urlencode, urlsplit
from uuid import UUID

if __package__:
    from .prototype import Card
else:
    from prototype import Card

PROJECT_REF = 'cgoosfuwohjupcbwdaty'
MAX_BYTES = 524288
MAX_CARDS = 50
TIMEOUT = 10
CARD_FIELDS = tuple(field.name for field in fields(Card))
ROW_FIELDS = set(CARD_FIELDS) | {'owner_id', 'approval_id'}


class ReaderError(RuntimeError):
    """Fixed diagnostic, without tokens, URLs, response bodies or chained errors."""


def _json(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate field')
            result[key] = value
        return result
    try:
        return json.loads(data, object_pairs_hook=unique,
                          parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Constant')))
    except (ValueError, TypeError, UnicodeError):
        raise ValueError('Invalid JSON') from None


def _uuid(value):
    if type(value) is not str or str(UUID(value)) != value or UUID(value).int == 0:
        raise ValueError('Invalid owner')
    return value


def _claims(token, endpoint):
    if type(token) is not str or len(token) > 16384 or not re.fullmatch(
            r'[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+', token):
        raise ValueError('Invalid token')
    parts = token.split('.')
    header, claims = [_json(base64.b64decode(part + '=' * (-len(part) % 4),
                                            altchars=b'-_', validate=True))
                      for part in parts[:2]]
    if (type(header) is not dict or header.get('alg') not in {'HS256', 'RS256', 'ES256'}
            or type(claims) is not dict or claims.get('iss') != endpoint + '/auth/v1'
            or claims.get('role') != 'authenticated' or claims.get('aud') != 'authenticated'
            or type(claims.get('exp')) is not int or claims['exp'] <= time.time()
            or ('nbf' in claims and (type(claims['nbf']) is not int or claims['nbf'] > time.time()))):
        raise ValueError('Invalid claims')
    # This is only a preflight. Supabase must verify the signature and authorization.
    return _uuid(claims.get('sub'))


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Redirect rejected')


def _transport(request, timeout):
    # Never use ambient proxies; never forward credentials to redirects.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), _NoRedirect())
    return opener.open(request, timeout=timeout)


def _read(jwt, limit, transport):
    endpoint = os.environ.get('EDITORIAL_SUPABASE_URL')
    expected = 'https://' + PROJECT_REF + '.supabase.co'
    # Exact canonical origin rejects userinfo, ports, paths, whitespace and URL ambiguities.
    if endpoint != expected:
        raise ValueError('Wrong project origin')
    key = os.environ.get('EDITORIAL_SUPABASE_PUBLISHABLE_KEY', '')
    if not re.fullmatch(r'sb_publishable_[A-Za-z0-9_-]{1,256}', key):
        raise ValueError('Publishable key required')
    if type(limit) is not int or not 1 <= limit <= MAX_CARDS:
        raise ValueError('Invalid limit')
    owner = _claims(jwt, endpoint)
    query = urlencode({'select': ','.join(sorted(ROW_FIELDS)), 'status': 'eq.approved',
                       'owner_id': 'eq.' + owner, 'order': 'card_id.asc', 'limit': limit})
    url = endpoint + '/rest/v1/editorial_cards?' + query
    if urlsplit(url).scheme != 'https' or urlsplit(url).netloc != PROJECT_REF + '.supabase.co':
        raise ValueError('Invalid request origin')
    # Scheme and authority are validated above; caller cannot supply a request URL.
    request = urllib.request.Request(url, method='GET', headers={  # noqa: S310
        'apikey': key, 'Authorization': 'Bearer ' + jwt, 'Accept': 'application/json',
        'Accept-Encoding': 'identity'})
    with transport(request, timeout=TIMEOUT) as response:
        if (response.status != 200 or response.geturl() != url
                or response.headers.get('Content-Type', '').split(';')[0] != 'application/json'):
            raise ValueError('Rejected response')
        body = response.read(MAX_BYTES + 1)
    if type(body) is not bytes or len(body) > MAX_BYTES:
        raise ValueError('Oversized response')
    rows = _json(body)
    if type(rows) is not list or len(rows) > limit:
        raise ValueError('Invalid result count')
    cards, seen = [], set()
    for row in rows:
        if (type(row) is not dict or set(row) != ROW_FIELDS
                or row['owner_id'] != owner or row['status'] != 'approved'
                or type(row['approval_id']) is not str
                or not re.fullmatch(r'[a-z0-9][a-z0-9_-]{0,79}', row['approval_id'])):
            raise ValueError('Invalid row')
        for name in CARD_FIELDS:
            if name != 'sanitized' and (type(row[name]) is not str or len(row[name]) > 2000):
                raise ValueError('Invalid card field')
        card = Card(**{name: row[name] for name in CARD_FIELDS})
        if card.card_id in seen:
            raise ValueError('Duplicate card')
        seen.add(card.card_id)
        cards.append(card)
    return tuple(cards)


def read_approved(jwt, *, limit=20, transport=None):
    """Read approved owner cards; caller explicitly supplies a user access token.

    An injected transport is trusted test code, not a security boundary. The real
    transport uses TLS and server JWT validation; local claims are NOT verified.
    No pagination, retries, login, imports, logs or local credential storage.
    """
    try:
        return _read(jwt, limit, _transport if transport is None else transport)
    except Exception:
        # Drop all inputs: transports may retain requests; invalid limits may be secrets.
        del jwt, limit, transport
    # Outside the handler so sensitive exceptions are not chained or retained.
    raise ReaderError('Editorial read unavailable or rejected; no cards returned')
