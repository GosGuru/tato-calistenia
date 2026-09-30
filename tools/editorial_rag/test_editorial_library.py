import base64
import json
import time
import unittest
from dataclasses import replace
from urllib.parse import parse_qs, urlsplit

if __package__:
    from .editorial_criteria import fingerprint, parse_criterion
    from .editorial_library import LibraryError, ranklocal, read_library
    from .library_config import PROJECT_URL, LibraryConfig
    from .test_editorial_criteria import OWNER, VECTOR, row
else:
    from editorial_criteria import fingerprint, parse_criterion
    from editorial_library import LibraryError, ranklocal, read_library
    from library_config import PROJECT_URL, LibraryConfig
    from test_editorial_criteria import OWNER, VECTOR, row

def token(owner=OWNER):
    def encode(value):
        return base64.urlsafe_b64encode(json.dumps(value).encode()).decode().rstrip('=')
    return encode({'alg':'HS256'})+'.'+encode({'iss':PROJECT_URL+'/auth/v1','aud':'authenticated','role':'authenticated','sub':owner,'exp':int(time.time())+600})+'.synthetic'

class Response:
    status = 200
    headers = {'Content-Type':'application/json'}
    def __init__(self, request, rows):
        self.url = request.full_url
        self.body = json.dumps(rows).encode()
    def geturl(self): return self.url
    def read(self, limit): return self.body[:limit]
    def __enter__(self): return self
    def __exit__(self, *args): pass

class LibraryTests(unittest.TestCase):
    config = LibraryConfig(1, PROJECT_URL, 'sb_publishable_test', OWNER)
    def test_read_and_rank(self):
        def transport(request, timeout):
            self.assertEqual(request.method, 'GET')
            self.assertEqual(timeout, 10)
            self.assertEqual(urlsplit(request.full_url).path, '/rest/v1/editorial_runtime_library')
            self.assertEqual(parse_qs(urlsplit(request.full_url).query)['limit'], ['51'])
            self.assertIsNone(request.data)
            return Response(request, [row()])
        criteria = read_library(token(), self.config, transport=transport)
        self.assertEqual(criteria[0].approval_id, 'approval-fictional')
        result = ranklocal(criteria, [VECTOR, [-x for x in VECTOR]])
        self.assertEqual(result[0].rank, 1)
        self.assertEqual(result[0].similarity, 1.0)
        self.assertFalse(hasattr(result[0], 'confidence'))

    def test_reject_and_drop_errors(self):
        for rows in [[row()]*51, [row(),row()], [{**row(),'fingerprint':'bad'}]]:
            with self.assertRaises(LibraryError) as caught:
                read_library(token(), self.config, transport=lambda request, timeout, rows=rows: Response(request, rows))
            self.assertIsNone(caught.exception.__context__)
        with self.assertRaises(LibraryError):
            read_library(token('22222222-2222-4222-8222-222222222222'), self.config, transport=lambda *a,**k: self.fail('network'))
        criterion = parse_criterion(row(), OWNER)
        for vectors in [[], [[0]*384], [[float('inf')]*384], [VECTOR]*65]:
            with self.assertRaises(ValueError):
                ranklocal((criterion,), vectors)
        with self.assertRaises(ValueError):
            ranklocal((criterion,), [VECTOR], max_results=3)

    def test_http_boundaries(self):
        def transport_with(patch):
            def transport(request, timeout):
                response = Response(request, [row()])
                for key, value in patch.items():
                    setattr(response, key, value)
                return response
            return transport
        for patch in [{'status': 302}, {'url': 'https://other.invalid/'},
                      {'headers': {'Content-Type': 'text/plain'}},
                      {'body': b' ' * (2*1024*1024+1)},
                      {'body': b'[{"x":1,"x":2}]'}, {'body': b'{}'},
                      {'body': b'\xff'}, {'body': b'[NaN]'}]:
            with self.assertRaises(LibraryError):
                read_library(token(), self.config, transport=transport_with(patch))
        def failing(request, timeout):
            raise RuntimeError('synthetic transport secret')
        with self.assertRaises(LibraryError) as caught:
            read_library(token(), self.config, transport=failing)
        self.assertIsNone(caught.exception.__context__)
        self.assertIsNone(caught.exception.__cause__)
        self.assertNotIn('secret', str(caught.exception))

    def test_ties_chunk_max_and_no_threshold(self):
        first = parse_criterion(row(), OWNER)
        second_card = replace(first.card, card_id='another-fictional')
        second = replace(first, card=second_card, fingerprint=fingerprint(OWNER, second_card))
        ranked = ranklocal((first, second), [[-x for x in VECTOR]])
        self.assertEqual([item.criterion.card.card_id for item in ranked], ['another-fictional', 'fictional'])
        self.assertEqual(ranked[0].similarity, -1)
        self.assertEqual(ranklocal((first,), [[-x for x in VECTOR], VECTOR])[0].similarity, 1)
        self.assertEqual(ranklocal((), [VECTOR]), ())
