"""Synthetic, network-free integrity tests."""
import email.message
import hashlib
import io
import json
import tempfile
import unittest
import urllib.error
import urllib.request
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from tools.editorial_rag import (  # pyright: ignore[reportMissingImports]
    model_setup as m,
)


def git_blob_sha1(data):
    """Git blob SHA-1 identity of data; the manifest's small metadata scheme."""
    return hashlib.new('sha1', b'blob ' + str(len(data)).encode('ascii') + b'\0' + data,
                       usedforsecurity=False).hexdigest()


class SetupTests(unittest.TestCase):
    def spec(self, data=b'abc'):
        return {'path': 'config.json', 'size': len(data), 'hash_kind': 'git_blob_sha1',
                'hash': git_blob_sha1(data)}

    def test_git_blob_not_plain_sha1(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'config.json'
            p.write_bytes(b'abc')
            self.assertTrue(m.valid_file(p, self.spec()))
            p.write_bytes(b'xyz')
            self.assertFalse(m.valid_file(p, self.spec()))

    def test_download_verified_and_reused(self):
        with tempfile.TemporaryDirectory() as d, \
                patch.object(m, 'open_download', return_value=io.BytesIO(b'abc')) as fetch:
            self.assertEqual(m.install_file(Path(d), self.spec()), 3)
            self.assertEqual(m.install_file(Path(d), self.spec()), 0)
            self.assertEqual(fetch.call_count, 1)

    def test_bad_download_not_published(self):
        for content in (b'ab', b'abcd', b'xyz'):
            with self.subTest(content=content), tempfile.TemporaryDirectory() as d, \
                    patch.object(m, 'open_download', return_value=io.BytesIO(content)), \
                    patch.object(m, 'RETRY_BACKOFF', (0, 0)):
                self.assertRaisesRegex(m.SetupError, '^model_setup_failed$',
                                       m.install_file, Path(d), self.spec())
                self.assertEqual(list(Path(d).iterdir()), [])

    def test_manifest_pinned(self):
        self.assertEqual(sum(f['size'] for f in m.SPEC['files']), 135392183)
        self.assertEqual(m.SPEC['dimensions'], 384)
        self.assertEqual(m.SPEC['revision'], '3acb1fa45c83e69002b1641b37f3cccc132cdd63')


class FailureDetailTests(unittest.TestCase):
    """Failures name the asset and the check on stderr, never a URL or token."""

    def spec(self, data=b'abc'):
        return {'path': 'config.json', 'size': len(data), 'hash_kind': 'git_blob_sha1',
                'hash': git_blob_sha1(data)}

    def expect_failed_install(self, directory):
        with patch.object(m, 'RETRY_BACKOFF', (0, 0)), \
                self.assertRaisesRegex(m.SetupError, '^model_setup_failed$'):
            m.install_file(Path(directory), self.spec())

    def expect_failed_verify(self, directory):
        with self.assertRaisesRegex(m.SetupError, '^model_assets_unavailable$'):
            m.verify_cache(Path(directory))

    def record(self, directory, work):
        """Run work(directory); return (stdout, stderr) and prove nothing sensitive leaks."""
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            work(directory)
        captured = (out.getvalue(), err.getvalue())
        for stream in captured:
            self.assertNotIn('://', stream)  # no URL and no redirect target
            self.assertNotIn(directory, stream)  # no filesystem location
            self.assertNotIn(m.DEFAULT_MODEL_DIR.as_posix(), stream)
            self.assertNotIn(str(m.DEFAULT_MODEL_DIR), stream)
        return captured

    def detail_line(self, err):
        lines = [json.loads(line) for line in err.splitlines() if line.strip()]
        self.assertTrue(lines, 'expected a diagnostic line on stderr')
        return lines[-1]

    def test_size_and_hash_mismatches_name_the_asset_and_the_check(self):
        cases = ((b'ab', 'size_mismatch'), (b'abcd', 'size_overflow'), (b'xyz', 'hash_mismatch'))
        for content, check in cases:
            streams = [io.BytesIO(content) for _ in range(m.DOWNLOAD_ATTEMPTS)]
            with self.subTest(content=content), tempfile.TemporaryDirectory() as d, \
                    patch.object(m, 'RETRY_BACKOFF', (0, 0)), \
                    patch.object(m, 'open_download', side_effect=streams):
                out, err = self.record(d, self.expect_failed_install)
            line = self.detail_line(err)
            self.assertEqual(line['type'], 'setup_detail')
            self.assertEqual(line['asset'], 'config.json')
            self.assertEqual(line['check'], check)

    def test_http_failures_report_the_status_without_the_request_url(self):
        marker = 'fictional-token-987'
        failure = urllib.error.HTTPError(
            'https://example.invalid/x?' + marker, 429, 'Too Many', email.message.Message(), None)
        with tempfile.TemporaryDirectory() as d, \
                patch.object(m, 'RETRY_BACKOFF', (0, 0)), \
                patch.object(m, 'open_download', side_effect=failure):
            out, err = self.record(d, self.expect_failed_install)
        self.assertNotIn(marker, err)
        line = self.detail_line(err)
        self.assertEqual(line['asset'], 'config.json')
        self.assertEqual(line['check'], 'download_http_error')
        self.assertEqual(line['http_status'], 429)

    def test_transient_failure_is_retried_and_every_attempt_is_verified(self):
        attempts = [TimeoutError(), io.BytesIO(b'xyz'), io.BytesIO(b'abc')]
        with tempfile.TemporaryDirectory() as d, \
                patch.object(m, 'RETRY_BACKOFF', (0, 0)), \
                patch.object(m, 'open_download', side_effect=attempts) as fetch:
            self.assertEqual(m.install_file(Path(d), self.spec()), 3)
            self.assertEqual(fetch.call_count, 3)
            self.assertTrue(m.valid_file(Path(d) / 'config.json', self.spec()))

    def test_persistent_failure_fails_closed_after_the_bounded_attempts(self):
        with tempfile.TemporaryDirectory() as d, \
                patch.object(m, 'RETRY_BACKOFF', (0, 0)), \
                patch.object(m, 'open_download', side_effect=TimeoutError()) as fetch:
            out, err = self.record(d, self.expect_failed_install)
            self.assertEqual(list(Path(d).iterdir()), [])
            self.assertEqual(fetch.call_count, m.DOWNLOAD_ATTEMPTS)
        line = self.detail_line(err)
        self.assertEqual(line['asset'], 'config.json')
        self.assertEqual(line['check'], 'download_timeout')
        self.assertEqual(line['attempts'], m.DOWNLOAD_ATTEMPTS)

    def test_existing_invalid_asset_is_named_and_never_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            target = Path(d) / 'config.json'
            target.write_bytes(b'xyz')
            out, err = self.record(d, self.expect_failed_install)
            self.assertEqual(target.read_bytes(), b'xyz')
        line = self.detail_line(err)
        self.assertEqual(line['asset'], 'config.json')
        self.assertEqual(line['check'], 'existing_asset_invalid')

    def test_redirect_rejection_is_content_free(self):
        request = urllib.request.Request('https://example.invalid/a')
        handler = m.TLSRedirect()
        with self.assertRaises(m.UnsafeRedirect):
            handler.redirect_request(request, io.BytesIO(), 302, 'Found',
                                     email.message.Message(), 'http://example.invalid/x')

    def test_verify_cache_names_the_asset_and_the_check(self):
        data = b'abc'
        fabricated = {'path': 'config.json', 'size': len(data), 'hash_kind': 'git_blob_sha1',
                      'hash': git_blob_sha1(b'xyz')}
        with tempfile.TemporaryDirectory() as d, patch.object(m, 'SPEC', {'files': [fabricated]}):
            out, err = self.record(d, self.expect_failed_verify)
            (Path(d) / 'config.json').write_bytes(data)
        line = self.detail_line(err)
        self.assertEqual(line['asset'], 'config.json')
        self.assertEqual(line['check'], 'missing')

    def test_entrypoint_stdout_stays_the_fixed_error_while_stderr_explains(self):
        out, err = io.StringIO(), io.StringIO()
        with patch.object(m, 'install_file', side_effect=m.SetupError('model_setup_failed')), \
                redirect_stdout(out), redirect_stderr(err):
            self.assertEqual(m.main(), 1)
        self.assertEqual(out.getvalue().strip(), '{"type":"error","code":"model_setup_failed"}')
        line = self.detail_line(err.getvalue())
        self.assertEqual(line['check'], 'unclassified_error')
        self.assertEqual(line['error'], 'SetupError')


if __name__ == '__main__':
    unittest.main()
