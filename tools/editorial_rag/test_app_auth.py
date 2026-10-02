"""Memory-only authentication; all remote work is mocked."""
import unittest
from unittest.mock import Mock, patch

# Both authorized unittest commands resolve namespace packages from the repo root.
from tools.editorial_rag.app_auth import (
    AppAuth,  # pyright: ignore[reportMissingImports]
)
from tools.editorial_rag.library_config import (  # pyright: ignore[reportMissingImports]
    PROJECT_URL,
    ConfigError,
    LibraryConfig,
)

OWNER = '11111111-1111-4111-8111-111111111111'
CONFIG = LibraryConfig(1, PROJECT_URL, 'sb_publishable_test', OWNER)


class RememberedAuthTests(unittest.TestCase):
    def setUp(self):
        for name, value in [('load_config', CONFIG), ('sign_in', 'fictional-jwt')]:
            patcher = patch('tools.editorial_rag.app_auth.' + name, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch('socket.socket', side_effect=AssertionError('No network in auth tests'))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_restore_requires_authenticated_owner_read_and_rotates(self):
        store = Mock(config=CONFIG)
        store.load.return_value = 'fictional-refresh'
        store.save.return_value = True
        auth = AppAuth(store=store)
        with patch('tools.editorial_rag.supabase_auth.refresh_session', return_value=('fictional-jwt', 'fictional-rotated')), \
                patch('tools.editorial_rag.app_auth._claims', return_value=OWNER), \
                patch('tools.editorial_rag.app_auth.read_library', return_value=()) as read:
            self.assertTrue(auth.restore())
            read.assert_called_once_with('fictional-jwt', CONFIG)
            store.save.assert_called_once_with('fictional-rotated')
            self.assertTrue(auth.status()['connected'])
            self.assertTrue(auth.persistence()['remembered'])
        auth.logout()
        store.clear.assert_called()
        self.assertFalse(auth.persistence()['remembered'])

    def test_passive_status_is_nonblocking_during_restore_and_attempt_is_bounded(self):
        import threading
        from concurrent.futures import ThreadPoolExecutor
        store = Mock(config=CONFIG)
        store.load.return_value = 'fictional-refresh'
        store.save.return_value = True
        auth = AppAuth(store=store)
        entered, release = threading.Event(), threading.Event()
        def exchange(*args, **kwargs):
            entered.set()
            self.assertTrue(release.wait(3))
            return 'fictional-jwt', 'fictional-rotated'
        with patch('tools.editorial_rag.supabase_auth.refresh_session', side_effect=exchange) as renew, \
                patch('tools.editorial_rag.app_auth._claims', return_value=OWNER), \
                patch('tools.editorial_rag.app_auth.read_library', return_value=()), ThreadPoolExecutor(max_workers=2) as pool:
            pending = pool.submit(auth.restore)
            try:
                self.assertTrue(entered.wait(3))
                self.assertFalse(pool.submit(auth.status).result(timeout=1)['connected'])
                self.assertFalse(auth.restore())
                auth.logout()
            finally:
                release.set()
            self.assertFalse(pending.result(timeout=3))
            renew.assert_called_once()
        store.save.assert_not_called()

    def test_wrong_owner_and_failed_rls_never_save(self):
        for owner, failure in [('wrong-owner', None), (OWNER, ValueError('fictional'))]:
            store = Mock(config=CONFIG)
            store.load.return_value = 'fictional-refresh'
            auth = AppAuth(store=store)
            with patch('tools.editorial_rag.supabase_auth.refresh_session', return_value=('fictional-jwt', 'fictional-rotated')), \
                    patch('tools.editorial_rag.app_auth._claims', return_value=owner), \
                    patch('tools.editorial_rag.app_auth.read_library', side_effect=failure, return_value=()):
                self.assertFalse(auth.restore())
            self.assertFalse(auth.status()['connected'])
            store.save.assert_not_called()

    def test_expired_session_renews_only_on_snapshot_once_and_rotation_can_fail(self):
        store = Mock(config=CONFIG)
        store.load.return_value = 'fictional-refresh'
        store.save.return_value = True
        auth = AppAuth(store=store)
        with patch('tools.editorial_rag.supabase_auth.refresh_session', return_value=('fictional-jwt', 'fictional-rotated')) as renew, \
                patch('tools.editorial_rag.app_auth._claims', return_value=OWNER) as claims, \
                patch('tools.editorial_rag.app_auth.read_library', return_value=()):
            self.assertTrue(auth.restore())
            claims.side_effect = ValueError('fictional expiry')
            self.assertFalse(auth.status()['connected'])
            renew.assert_called_once()
            renew.side_effect = ValueError('fictional offline')
            auth.snapshot()
            auth.snapshot()
            self.assertEqual(renew.call_count, 2)
            self.assertFalse(auth.persistence()['remembered'])

    def test_logout_fences_restore_even_when_remote_returns_success(self):
        store = Mock(config=CONFIG)
        store.load.return_value = 'fictional-refresh'
        auth = AppAuth(store=store)
        with patch('tools.editorial_rag.supabase_auth.refresh_session', return_value=('fictional-jwt', 'fictional-rotated')), \
                patch('tools.editorial_rag.app_auth._claims', return_value=OWNER), \
                patch('tools.editorial_rag.app_auth.read_library', side_effect=lambda *args: (auth.logout() or ())):
            self.assertFalse(auth.restore())
        store.save.assert_not_called()
        self.assertFalse(auth.status()['connected'])

    def test_saving_failure_preserves_baseline_and_never_claims_remembered(self):
        store = Mock(config=CONFIG)
        store.save.return_value = False
        auth = AppAuth(store=store)
        with patch('tools.editorial_rag.supabase_auth.sign_in_session', return_value=('fictional-jwt', 'fictional-refresh')), \
                patch('tools.editorial_rag.app_auth._claims', return_value=OWNER), \
                patch('tools.editorial_rag.app_auth.read_library', return_value=()):
            self.assertTrue(auth.login('fictional@example.invalid', 'fictional'))
            self.assertTrue(auth.status()['connected'])
            self.assertEqual(auth.persistence(), {'enabled': True, 'remembered': False, 'problem': True})


class AppAuthTests(unittest.TestCase):
    def test_disconnected_status_is_lazy(self):
        with patch('tools.editorial_rag.app_auth.load_config') as load:
            auth = AppAuth()
            self.assertEqual(auth.status(), {'connected': False, 'empty': False, 'count': 0, 'revision': 0})
            load.assert_not_called()

    def test_connection_requires_authenticated_read_even_when_empty(self):
        with patch('tools.editorial_rag.app_auth.load_config', return_value=CONFIG), \
             patch('tools.editorial_rag.app_auth.sign_in', return_value='fictional-token') as login, \
             patch('tools.editorial_rag.app_auth._claims', return_value=OWNER), \
             patch('tools.editorial_rag.app_auth.read_library', return_value=()) as read:
            auth = AppAuth()
            self.assertTrue(auth.login('fictional@example.invalid', 'fictional-password'))
            self.assertEqual(auth.status(), {'connected': True, 'empty': True, 'count': 0, 'revision': 1})
            login.assert_called_once_with('fictional@example.invalid', 'fictional-password', config=CONFIG)
            read.assert_called_once_with('fictional-token', CONFIG)
            auth.logout()
            self.assertFalse(auth.status()['connected'])
            self.assertEqual(auth.status()['revision'], 2)

    def test_wrong_owner_and_failed_read_never_connect(self):
        for owner, failure in [('22222222-2222-4222-8222-222222222222', None), (OWNER, ValueError('fictional-secret'))]:
            with self.subTest(owner=owner), patch('tools.editorial_rag.app_auth.load_config', return_value=CONFIG), \
                 patch('tools.editorial_rag.app_auth.sign_in', return_value='fictional-token'), \
                 patch('tools.editorial_rag.app_auth._claims', return_value=owner), \
                 patch('tools.editorial_rag.app_auth.read_library', side_effect=failure, return_value=()):
                auth = AppAuth()
                self.assertFalse(auth.login('fictional@example.invalid', 'fictional-password'))
                self.assertFalse(auth.status()['connected'])

    def test_disconnect_invalidates_pending_login(self):
        with patch('tools.editorial_rag.app_auth.load_config', return_value=CONFIG), \
             patch('tools.editorial_rag.app_auth.sign_in', return_value='fictional-token'), \
             patch('tools.editorial_rag.app_auth._claims', return_value=OWNER):
            auth = AppAuth()
            with patch('tools.editorial_rag.app_auth.read_library', side_effect=lambda *args: (auth.logout() or ())):
                self.assertFalse(auth.login('fictional@example.invalid', 'fictional-password'))
            self.assertFalse(auth.status()['connected'])

    def test_concurrent_login_is_rejected_and_missing_config_is_baseline(self):
        auth = AppAuth()
        with patch('tools.editorial_rag.app_auth.load_config', side_effect=ValueError('fictional secret')):
            self.assertFalse(auth.login('fictional@example.invalid', 'fictional-password'))
        self.assertFalse(auth.status()['connected'])
        def sign_in(*args, **kwargs):
            self.assertFalse(auth.login('other@example.invalid', 'fictional-password'))
            return 'fictional-token'
        with patch('tools.editorial_rag.app_auth.load_config', return_value=CONFIG), \
             patch('tools.editorial_rag.app_auth.sign_in', side_effect=sign_in) as login, \
             patch('tools.editorial_rag.app_auth._claims', return_value=OWNER), \
             patch('tools.editorial_rag.app_auth.read_library', return_value=()):
            self.assertTrue(auth.login('fictional@example.invalid', 'fictional-password'))
            login.assert_called_once()
            self.assertEqual(auth.status()['revision'], 2)

    def test_expiry_does_not_change_explicit_revision(self):
        with patch('tools.editorial_rag.app_auth.load_config', return_value=CONFIG), \
             patch('tools.editorial_rag.app_auth.sign_in', return_value='fictional-token'), \
             patch('tools.editorial_rag.app_auth._claims', return_value=OWNER) as claims, \
             patch('tools.editorial_rag.app_auth.read_library', return_value=()):
            auth = AppAuth()
            self.assertTrue(auth.login('fictional@example.invalid', 'fictional-password'))
            claims.side_effect = ValueError('expired')
            self.assertFalse(auth.status()['connected'])
            self.assertEqual(auth.status()['revision'], 1)
            self.assertEqual(auth.snapshot()[1], 'expired')


class InjectedConfigSourceTests(unittest.TestCase):
    """A managed deployment injects the bounded public configuration explicitly."""

    def setUp(self):
        for name, value in [('sign_in', 'fictional-jwt')]:
            patcher = patch('tools.editorial_rag.app_auth.' + name, return_value=value)
            patcher.start()
            self.addCleanup(patcher.stop)
        patcher = patch('socket.socket', side_effect=AssertionError('No network in auth tests'))
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_injected_source_replaces_the_missing_local_file(self):
        source = Mock(return_value=CONFIG)
        auth = AppAuth(config_source=source)
        with patch('tools.editorial_rag.app_auth._claims', return_value=OWNER), \
                patch('tools.editorial_rag.app_auth.read_library', return_value=()):
            self.assertTrue(auth.login('fictional@example.invalid', 'fictional-password'))
            self.assertTrue(auth.status()['connected'])
        source.assert_called_once_with()

    def test_failing_injected_source_fails_closed(self):
        auth = AppAuth(config_source=Mock(side_effect=ConfigError('unavailable')))
        self.assertFalse(auth.login('fictional@example.invalid', 'fictional-password'))
        self.assertFalse(auth.status()['connected'])
