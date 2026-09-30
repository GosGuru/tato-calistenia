"""Owned fictional resources only; never construct a production store."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from . import session_store as module
from .test_app_auth import CONFIG


class SessionStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='tato-fictional-')
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'session.bin'
        # A reversible test codec, never used by production composition.
        self.protect = lambda data: b'fictional-cipher:' + data[::-1]
        self.unprotect = lambda data: data.removeprefix(b'fictional-cipher:')[::-1]
        self.store = module.SessionStore(self.path, CONFIG, protect=self.protect, unprotect=self.unprotect)

    def test_roundtrip_rotation_and_removal(self):
        self.assertIsNone(self.store.load())
        self.assertTrue(self.store.save('fictional-refresh-one'))
        self.assertNotIn(b'fictional-refresh-one', self.path.read_bytes())
        self.assertEqual(self.store.load(), 'fictional-refresh-one')
        self.assertTrue(self.store.save('fictional-refresh-two'))
        self.assertEqual(self.store.load(), 'fictional-refresh-two')
        self.assertTrue(self.store.clear())
        self.assertIsNone(self.store.load())

    def test_invalid_tokens_and_corrupt_oversized_files_fail_closed(self):
        for token in ('', 'x' * 4097, 'bad\nvalue', None):
            self.assertFalse(self.store.save(token))
            self.assertFalse(self.path.exists())
        for data in (b'garbage', b'x' * 32769):
            self.path.write_bytes(data)
            self.assertIsNone(self.store.load())

    def test_wrong_owner_project_version_and_extra_fields_fail_closed(self):
        import json
        payload = {'version': 1, 'project': CONFIG.project_url, 'owner': CONFIG.owner_id, 'refresh': 'fictional'}
        for change in ({'owner': 'other'}, {'project': 'https://example.invalid'}, {'version': True}, {'email': 'fictional@example.invalid'}):
            self.path.write_bytes(self.protect(json.dumps(payload | change).encode()))
            self.assertIsNone(self.store.load())

    def test_failed_atomic_rotation_preserves_previous_ciphertext(self):
        self.assertTrue(self.store.save('fictional-old'))
        with patch.object(module.os, 'replace', side_effect=OSError('fictional')):
            self.assertFalse(self.store.save('fictional-new'))
        self.assertEqual(self.store.load(), 'fictional-old')
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_encryption_and_read_failures_are_sanitized(self):
        self.store.protect = lambda _: (_ for _ in ()).throw(ValueError('fictional secret'))
        self.assertFalse(self.store.save('fictional'))
        self.path.write_bytes(b'fictional')
        self.store.unprotect = self.store.protect
        self.assertIsNone(self.store.load())

    @unittest.skipUnless(os.name == 'nt', 'Windows DPAPI only')
    def test_real_current_user_dpapi_only_with_fictional_temp_token(self):
        store = module.SessionStore(self.path, CONFIG)
        self.assertTrue(store.save('fictional-only-dpapi-token'))
        self.assertNotIn(b'fictional-only-dpapi-token', self.path.read_bytes())
        self.assertEqual(store.load(), 'fictional-only-dpapi-token')
        self.assertTrue(store.clear())
