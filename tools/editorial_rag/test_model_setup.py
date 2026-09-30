"""Synthetic, network-free integrity tests."""
import hashlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tools.editorial_rag import model_setup as m


class SetupTests(unittest.TestCase):
    def spec(self, data=b'abc'):
        return {'path': 'config.json', 'size': len(data), 'hash_kind': 'git_blob_sha1',
                'hash': hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()}

    def test_git_blob_not_plain_sha1(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)/'config.json'
            p.write_bytes(b'abc')
            self.assertTrue(m.valid_file(p, self.spec()))
            p.write_bytes(b'xyz')
            self.assertFalse(m.valid_file(p, self.spec()))

    def test_download_verified_and_reused(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.object(m, 'open_download', return_value=io.BytesIO(b'abc')) as fetch:
                self.assertEqual(m.install_file(Path(d), self.spec()), 3)
                self.assertEqual(m.install_file(Path(d), self.spec()), 0)
                self.assertEqual(fetch.call_count, 1)

    def test_bad_download_not_published(self):
        for content in (b'ab', b'abcd', b'xyz'):
            with self.subTest(content=content), tempfile.TemporaryDirectory() as d:
                with patch.object(m, 'open_download', return_value=io.BytesIO(content)):
                    with self.assertRaisesRegex(m.SetupError, '^model_setup_failed$'):
                        m.install_file(Path(d), self.spec())
                self.assertEqual(list(Path(d).iterdir()), [])

    def test_manifest_pinned(self):
        self.assertEqual(sum(f['size'] for f in m.SPEC['files']), 135392183)
        self.assertEqual(m.SPEC['dimensions'], 384)
        self.assertEqual(m.SPEC['revision'], '3acb1fa45c83e69002b1641b37f3cccc132cdd63')
