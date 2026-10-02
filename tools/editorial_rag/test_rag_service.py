"""Retrieval is advisory and never an extra provider generation."""
import inspect
import unittest
from dataclasses import replace
from unittest.mock import Mock, patch

from tools.editorial_rag.editorial_criteria import (  # pyright: ignore[reportMissingImports]
    MODEL_METADATA,
    Criterion,
    EmbeddingRecord,
    fingerprint,
)
from tools.editorial_rag.editorial_library import (  # pyright: ignore[reportMissingImports]
    ranklocal,
)
from tools.editorial_rag.library_config import (  # pyright: ignore[reportMissingImports]
    PROJECT_URL,
    LibraryConfig,
)
from tools.editorial_rag.prototype import Card  # pyright: ignore[reportMissingImports]
from tools.editorial_rag.rag_service import (  # pyright: ignore[reportMissingImports]
    GUIDANCE_FIELDS,
    retrieve,
)
from tools.editorial_rag.real_history import (  # pyright: ignore[reportMissingImports]
    DEFAULT_GUIDANCE,
    MAX_GUIDANCE,
)

OWNER = '11111111-1111-4111-8111-111111111111'
CONFIG = LibraryConfig(1, PROJECT_URL, 'sb_publishable_test', OWNER)
VECTOR = (1.0,) + (0.0,) * 383


def criterion(identity='fictional-one', owner=OWNER):
    card = Card(identity, 'fictional-provenance', 'approved', True, 'ruta', 'fictional-gate',
                'fictional situation', 'fictional-last', 'fictional-next',
                'fictional positive', 'fictional negative')
    return Criterion(owner, card, 'fictional-approval', fingerprint(owner, card),
                     EmbeddingRecord(**MODEL_METADATA, vector=VECTOR))


class RetrievalTests(unittest.TestCase):
    def test_fresh_local_ranking_supplies_only_the_ceiling_of_content_records(self):
        auth = Mock()
        auth.snapshot.return_value = (1, 'connected', 'fictional-token', CONFIG)
        history = 'complete fictional history'
        rows = tuple(criterion('fictional-' + letter) for letter in 'abcdefghi')
        with patch('tools.editorial_rag.rag_service.read_library', side_effect=[rows, ()]) as read, \
             patch('tools.editorial_rag.rag_service.embed_query', return_value=[VECTOR]) as embed:
            revision, guidance, status = retrieve(auth, history)
            self.assertEqual(revision, 1)
            self.assertEqual(status, {'status': 'supplied', 'count': 8})
            self.assertEqual(len(guidance), 8)
            self.assertEqual(set(guidance[0]), set(GUIDANCE_FIELDS))
            self.assertNotIn('fictional-provenance', repr(guidance))
            read.assert_called_with('fictional-token', CONFIG)
            embed.assert_called_once_with(history)
            self.assertEqual(retrieve(auth, history)[1:], ((), {'status': 'empty', 'count': 0}))
            self.assertEqual(read.call_count, 2)
            embed.assert_called_once()

    def test_request_size_is_the_ceiling_while_the_library_default_stays_pinned(self):
        auth = Mock()
        auth.snapshot.return_value = (1, 'connected', 'fictional-token', CONFIG)
        rows = tuple(criterion('fictional-' + letter) for letter in 'abcdefghi')
        with patch('tools.editorial_rag.rag_service.read_library', return_value=rows), \
             patch('tools.editorial_rag.rag_service.embed_query', return_value=[VECTOR]), \
             patch('tools.editorial_rag.rag_service.ranklocal', wraps=ranklocal) as rank:
            revision, guidance, status = retrieve(auth, 'complete fictional history')
        self.assertEqual(revision, 1)
        self.assertEqual(status, {'status': 'supplied', 'count': 8})
        self.assertEqual(len(guidance), 8)
        self.assertEqual(rank.call_args.kwargs['max_results'], MAX_GUIDANCE)
        self.assertEqual(inspect.signature(ranklocal).parameters['max_results'].default, DEFAULT_GUIDANCE)
        self.assertEqual(DEFAULT_GUIDANCE, 2)
        self.assertEqual(MAX_GUIDANCE, 8)

    def test_stale_revoked_and_wrong_owner_never_embed_or_supply(self):
        stale, revoked = criterion(), criterion()
        object.__setattr__(stale, 'card', replace(stale.card, situation='changed fictional situation'))
        object.__setattr__(revoked, 'card', replace(revoked.card, status='rejected'))
        wrong = criterion(owner='22222222-2222-4222-8222-222222222222')
        auth = Mock()
        auth.snapshot.return_value = (1, 'connected', 'fictional-token', CONFIG)
        for row in (stale, revoked, wrong):
            with patch('tools.editorial_rag.rag_service.read_library', return_value=(row,)), \
                 patch('tools.editorial_rag.rag_service.embed_query') as embed:
                self.assertEqual(retrieve(auth, 'fictional')[1:], ((), {'status': 'unavailable', 'count': 0}))
                embed.assert_not_called()

    def test_query_text_and_vectors_never_enter_http_requests(self):
        from tools.editorial_rag.editorial_library import (  # pyright: ignore[reportMissingImports]
            read_library,
        )
        from tools.editorial_rag.test_editorial_library import (  # pyright: ignore[reportMissingImports]
            Response,
            row,
            token,
        )
        auth = Mock()
        auth.snapshot.return_value = (1, 'connected', token(), CONFIG)
        history = 'fictional-history-never-in-http'
        def transport(request, timeout):
            self.assertEqual(request.get_method(), 'GET')
            self.assertIsNone(request.data)
            self.assertNotIn(history, request.full_url + repr(request.headers))
            self.assertNotIn('embedding=eq.', request.full_url)
            self.assertNotIn('query', request.headers)
            return Response(request, [row()])
        with patch('tools.editorial_rag.rag_service.read_library',
                   side_effect=lambda jwt, config: read_library(jwt, config, transport=transport)), \
             patch('tools.editorial_rag.rag_service.embed_query', return_value=[VECTOR]):
            self.assertEqual(retrieve(auth, history)[2], {'status': 'supplied', 'count': 1})

    def test_unrenderable_guidance_is_unavailable_not_a_generation_failure(self):
        item = criterion()
        card = replace(item.card, situation='fictional\x01condition')
        item = replace(item, card=card, fingerprint=fingerprint(OWNER, card))
        auth = Mock()
        auth.snapshot.return_value = (1, 'connected', 'fictional-token', CONFIG)
        with patch('tools.editorial_rag.rag_service.read_library', return_value=(item,)), \
             patch('tools.editorial_rag.rag_service.embed_query', return_value=[VECTOR]):
            self.assertEqual(retrieve(auth, 'fictional')[1:], ((), {'status': 'unavailable', 'count': 0}))

    def test_embedding_failure_supplies_nothing_without_retry(self):
        auth = Mock()
        auth.snapshot.return_value = (1, 'connected', 'fictional-token', CONFIG)
        with patch('tools.editorial_rag.rag_service.read_library', return_value=(criterion(),)), \
             patch('tools.editorial_rag.rag_service.embed_query', side_effect=ValueError('fictional secret')) as embed:
            self.assertEqual(retrieve(auth, 'fictional')[1:], ((), {'status': 'unavailable', 'count': 0}))
            embed.assert_called_once()

    def test_off_does_not_read_or_embed(self):
        auth = Mock()
        auth.snapshot.return_value = (0, 'off', None, None)
        with patch('tools.editorial_rag.rag_service.read_library') as read, patch('tools.editorial_rag.rag_service.embed_query') as embed:
            self.assertEqual(retrieve(auth, 'fictional history'), (0, (), {'status': 'off', 'count': 0}))
            read.assert_not_called()
            embed.assert_not_called()

    def test_empty_and_failure_are_explicit_baselines(self):
        auth = Mock()
        auth.snapshot.return_value = (1, 'connected', 'fictional-token', Mock())
        for rows, failure, status in [((), None, 'empty'), (None, ValueError('fictional-secret'), 'unavailable')]:
            with self.subTest(status=status), patch('tools.editorial_rag.rag_service.read_library', return_value=rows, side_effect=failure) as read, patch('tools.editorial_rag.rag_service.embed_query') as embed:
                self.assertEqual(retrieve(auth, 'fictional history'), (1, (), {'status': status, 'count': 0}))
                self.assertEqual(len(read.call_args.args), 2)
                self.assertNotIn('fictional history', str(read.call_args))
                embed.assert_not_called()
