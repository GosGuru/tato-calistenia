"""Adapter contract tests; no model or subprocess is used."""

import io
import json
import math
import unittest
from unittest.mock import Mock, patch

import tools.editorial_rag.local_embedding as e  # pyright: ignore[reportMissingImports]


class EmbeddingTests(unittest.TestCase):
    def test_query_preserves_unicode(self):
        text = 'árbol\r\n🦊  ' * 10
        vector = [1.0] + [0.0]*383
        with patch.object(e, '_invoke', return_value={'type': 'embeddings', 'vectors': [vector], 'chunks': 1}) as run:
            self.assertEqual(e.embed_query(text), [vector])
            self.assertEqual(run.call_args.args[0], {'mode': 'query', 'texts': [text]})

    def test_rejects_invalid_input_before_process(self):
        with patch.object(e, '_invoke') as run:
            for value in ('', 'a'*24001, '\ud800', None):
                with self.assertRaises(e.EmbeddingError):
                    e.embed_query(value)
            for value in ([], ['a']*9, [''], 'text'):
                with self.assertRaises(e.EmbeddingError):
                    e.embed_passages(value)
            run.assert_not_called()

    def test_vector_validation(self):
        for vector in ([0.0]*384, [1.0]*384, [math.nan]*384, [True]+[0.0]*383, [1.0]):
            with (
                patch.object(e, '_invoke', return_value={'type': 'embeddings', 'vectors': [vector], 'chunks': 1}),
                self.assertRaises(e.EmbeddingError),
            ):
                e.embed_query('invented')

    def test_passages_count(self):
        with (
            patch.object(e, '_invoke', return_value={'type': 'embeddings', 'vectors': [[1.0]+[0.0]*383], 'chunks': 1}),
            self.assertRaises(e.EmbeddingError),
        ):
            e.embed_passages(['invented one', 'invented two'])

    def test_process_payload_is_stdin_only(self):
        class Buffer(io.BytesIO):
            def close(self):
                self.saved = self.getvalue()
                super().close()

        output = {'type': 'embeddings', 'vectors': [[1.0] + [0.0]*383], 'chunks': 1}
        process = Mock(stdin=Buffer(), stdout=io.BytesIO(json.dumps(output).encode()))
        process.wait.return_value = 0
        process.poll.return_value = 0
        with (
            patch.object(e, 'verify_cache'),
            patch.object(e.shutil, 'which', return_value='node.exe'),
            patch.object(e.subprocess, 'Popen', return_value=process) as spawn,
        ):
            self.assertEqual(e.embed_query('invented test'), output['vectors'])
        self.assertNotIn('invented test', str(spawn.call_args.args))
        self.assertEqual(json.loads(process.stdin.saved)['texts'], ['invented test'])
        self.assertFalse(spawn.call_args.kwargs['shell'])
        self.assertEqual(spawn.call_args.kwargs['stderr'], e.subprocess.DEVNULL)

    def test_broken_pipe_cleanup_keeps_error_fixed(self):
        process = Mock(stdout=io.BytesIO())
        process.stdin.write.side_effect = BrokenPipeError('synthetic diagnostic')
        process.stdin.close.side_effect = BrokenPipeError('synthetic diagnostic')
        process.poll.return_value = 1
        with (
            patch.object(e, 'verify_cache'),
            patch.object(e.shutil, 'which', return_value='node.exe'),
            patch.object(e.subprocess, 'Popen', return_value=process),
            self.assertRaisesRegex(e.EmbeddingError, '^embedding_unavailable$'),
        ):
            e.embed_query('invented test')

    def test_environment_allowlist(self):
        env = e.child_environment({'SystemRoot': 'C:/Windows', 'PATH': 'bin', 'OPENAI_API_KEY': 'synthetic', 'HTTPS_PROXY': 'synthetic', 'NODE_OPTIONS': 'synthetic'})
        self.assertEqual(env, {'SystemRoot': 'C:/Windows', 'PATH': 'bin'})
