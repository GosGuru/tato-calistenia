"""Offline CPU adapter; one short-lived Node process per batch, stdin only."""
import json
import math
import os
import shutil
import subprocess
import threading
from contextlib import suppress
from pathlib import Path

from tools.editorial_rag.model_setup import CACHE, SPEC, verify_cache


class EmbeddingError(RuntimeError):
    """Content-free embedding failure."""


def child_environment(source):
    allowed = {'systemroot', 'windir', 'path', 'pathext', 'temp', 'tmp'}
    return {key: value for key, value in source.items() if key.lower() in allowed}


def _text(value):
    if not isinstance(value, str) or not value or len(value) > SPEC['max_query_chars']:
        raise EmbeddingError('invalid_embedding_input')
    if any(0xD800 <= ord(c) <= 0xDFFF for c in value):
        raise EmbeddingError('invalid_embedding_input')


def _invoke(payload):
    process = None
    try:
        verify_cache()
        node = shutil.which('node')
        if not node:
            raise EmbeddingError('embedding_unavailable')
        script = Path(__file__).parent / 'embedding_node/embed.mjs'
        process = subprocess.Popen(
            [node, str(script.resolve())], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, env=child_environment(os.environ), shell=False,
        )
        assert process.stdin is not None and process.stdout is not None
        stdin, stdout = process.stdin, process.stdout
        output = bytearray()
        exceeded = threading.Event()

        def drain():
            while True:
                block = stdout.read(4096)
                if not block:
                    break
                if len(output) + len(block) > 1024 * 1024:
                    exceeded.set()
                    process.kill()
                    break
                output.extend(block)

        reader = threading.Thread(target=drain, daemon=True)
        reader.start()
        # A watchdog bounds stdin writes as well as inference and stdout collection.
        expired = threading.Event()

        def timeout():
            expired.set()
            process.kill()

        timer = threading.Timer(180, timeout)
        timer.start()
        try:
            stdin.write(json.dumps({**payload, 'model_path': str(CACHE)}, ensure_ascii=True).encode('utf-8'))
            stdin.close()
            code = process.wait(timeout=185)
            reader.join(timeout=5)
            if code or expired.is_set() or exceeded.is_set() or reader.is_alive():
                raise EmbeddingError('embedding_unavailable')
        finally:
            timer.cancel()
        return json.loads(output)
    except Exception:
        raise EmbeddingError('embedding_unavailable') from None
    finally:
        if process is not None:
            if process.poll() is None:
                process.kill()
                process.wait()
            for stream in (process.stdin, process.stdout):
                if stream:
                    # Cleanup must never replace the content-free public error.
                    with suppress(OSError, ValueError):
                        stream.close()


def _embed(mode, texts):
    response = _invoke({'mode': mode, 'texts': texts})
    try:
        if set(response) != {'type', 'vectors', 'chunks'} or response['type'] != 'embeddings':
            raise ValueError
        vectors = response['vectors']
        if not isinstance(vectors, list) or not 1 <= len(vectors) <= SPEC['max_chunks']:
            raise ValueError
        if type(response['chunks']) is not int or response['chunks'] != len(vectors):
            raise ValueError
        if mode == 'passage' and len(vectors) != len(texts):
            raise ValueError
        for vector in vectors:
            if not isinstance(vector, list) or len(vector) != SPEC['dimensions']:
                raise ValueError
            if any(type(x) not in (float, int) or not math.isfinite(x) for x in vector):
                raise ValueError
            if abs(math.sqrt(sum(x*x for x in vector)) - 1) > 1e-4:
                raise ValueError
        return vectors
    except Exception:
        raise EmbeddingError('invalid_embedding_output') from None


def embed_query(history):
    """Return one vector per lossless query chunk, never a truncated history."""
    _text(history)
    return _embed('query', [history])


def embed_passages(texts):
    """Return one vector per criterion; overlong token sequences are rejected."""
    if not isinstance(texts, (list, tuple)) or not 1 <= len(texts) <= SPEC['max_passages']:
        raise EmbeddingError('invalid_embedding_input')
    for text in texts:
        _text(text)
    return _embed('passage', list(texts))
