"""Deployment contract tests for the Linux (Railway) image and startup credentials.

Fictional owned resources only: every credential value is invented, every
transport is patched and nothing touches the network or a real account.
Structural Dockerfile checks read the stage text and never assert line numbers.
"""
import importlib
import io
import logging
import os
import re
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

# Both authorized unittest commands resolve namespace packages from the repo root.
from tools.editorial_rag import (  # pyright: ignore[reportMissingImports]
    local_web,
    model_setup,
    session_store,
)
from tools.editorial_rag.app_auth import (  # pyright: ignore[reportMissingImports]
    AppAuth,
)
from tools.editorial_rag.library_config import (  # pyright: ignore[reportMissingImports]
    PROJECT_URL,
    ConfigError,
    LibraryConfig,
)
from tools.editorial_rag.supabase_auth import (  # pyright: ignore[reportMissingImports]
    AuthError,
)

OWNER = '11111111-1111-4111-8111-111111111111'
CONFIG = LibraryConfig(1, PROJECT_URL, 'sb_publishable_test', OWNER)
PUBLISHABLE = 'sb_publishable_test'
PUBLIC_CONFIG = {'TATO_LIBRARY_PUBLISHABLE_KEY': PUBLISHABLE, 'TATO_LIBRARY_OWNER_ID': OWNER}
WINDOWS_DEFAULT_MODELS = Path('C:/Users/Maxim/AppData/Local/TatoEditorialRag/models')


def credential_environment(seed=None, email=None, login=None):
    """Environment mapping built from the module's own variable names."""
    values = dict(zip(local_web.ENV_CREDENTIAL_VARS, (seed, email, login), strict=True))
    chosen = {name: value for name, value in values.items() if value is not None}
    return {**PUBLIC_CONFIG, **chosen}


class ModelDirectoryTests(unittest.TestCase):
    """The single model-directory override; default behaviour is unchanged."""

    def test_cache_honours_the_environment_variable_and_falls_back_to_windows_default(self):
        revision_dir = Path(model_setup.SPEC['model']) / model_setup.SPEC['revision']
        self.assertEqual(model_setup.model_root({}), WINDOWS_DEFAULT_MODELS)
        self.assertEqual(model_setup.CACHE, WINDOWS_DEFAULT_MODELS / revision_dir)
        self.assertEqual(model_setup.model_root({'TATO_LIBRARY_MODEL_DIR': ''}), WINDOWS_DEFAULT_MODELS)
        self.assertEqual(model_setup.model_root({model_setup.ENV_MODEL_DIR: '/opt/tato/models'}),
                         Path('/opt/tato/models'))
        self.addCleanup(importlib.reload, model_setup)
        with patch.dict(os.environ, {model_setup.ENV_MODEL_DIR: '/opt/tato/models'}, clear=True):
            reloaded = importlib.reload(model_setup)
            self.assertEqual(reloaded.CACHE, Path('/opt/tato/models') / revision_dir)
        reloaded = importlib.reload(model_setup)
        self.assertEqual(reloaded.CACHE, WINDOWS_DEFAULT_MODELS / revision_dir)

    def test_verify_cache_still_fails_closed_on_missing_or_mismatched_assets(self):
        data = b'abc'
        # Git blob SHA-1 identity of b'abc', the same scheme the manifest uses
        # for its small metadata files; nothing security-sensitive depends on it.
        fabricated = {'path': 'config.json', 'size': len(data), 'hash_kind': 'git_blob_sha1',
                      'hash': 'f2ba8f84ab5c1bce84a7b441cb1959cfc7093b7f'}
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(model_setup, 'SPEC', {'files': [fabricated]}):
            root = Path(directory)
            with self.assertRaisesRegex(model_setup.SetupError, '^model_assets_unavailable$'):
                model_setup.verify_cache(root)
            (root / 'config.json').write_bytes(data)
            model_setup.verify_cache(root)
            (root / 'config.json').write_bytes(b'xyz')
            with self.assertRaisesRegex(model_setup.SetupError, '^model_assets_unavailable$'):
                model_setup.verify_cache(root)

    def test_setup_entrypoint_fails_loudly_with_a_fixed_message(self):
        stream = io.StringIO()
        with patch.object(model_setup, 'install_file', side_effect=model_setup.SetupError('model_setup_failed')), \
                redirect_stdout(stream):
            self.assertEqual(model_setup.main(), 1)
        self.assertEqual(stream.getvalue().strip(), '{"type":"error","code":"model_setup_failed"}')


class EnvSessionStoreTests(unittest.TestCase):
    """In-memory session equivalent; owned fictional values and no disk access."""

    def test_roundtrip_rotation_and_removal_in_memory(self):
        store = session_store.EnvSessionStore(CONFIG, 'fictional-seed-token')
        self.assertIs(store.config, CONFIG)
        self.assertEqual(store.load(), 'fictional-seed-token')
        self.assertTrue(store.save('fictional-rotated-token'))
        self.assertEqual(store.load(), 'fictional-rotated-token')
        self.assertTrue(store.clear())
        self.assertIsNone(store.load())

    def test_invalid_tokens_and_configs_fail_closed(self):
        with self.assertRaises(ValueError):
            session_store.EnvSessionStore(CONFIG, 'bad token with spaces')
        with self.assertRaises(ValueError):
            session_store.EnvSessionStore(object())  # pyright: ignore[reportArgumentType]
        store = session_store.EnvSessionStore(CONFIG)
        self.assertIsNone(store.load())
        self.assertFalse(store.save('bad token with spaces'))
        self.assertIsNone(store.load())
        self.assertTrue(store.save('fictional-kept-token'))
        self.assertEqual(store.load(), 'fictional-kept-token')

    def test_never_touches_disk(self):
        store = session_store.EnvSessionStore(CONFIG, 'fictional-seed-token')
        with patch('builtins.open', side_effect=AssertionError('disk access')), \
                patch('os.replace', side_effect=AssertionError('disk access')), \
                patch('os.fsync', side_effect=AssertionError('disk access')):
            self.assertEqual(store.load(), 'fictional-seed-token')
            self.assertTrue(store.save('fictional-rotated-token'))
            self.assertTrue(store.clear())


class ProductionAuthTests(unittest.TestCase):
    """production_auth() composes the deployment credential sets fail-closed."""

    def test_without_credentials_production_auth_stays_disconnected(self):
        for cloud in (True, False):
            with self.subTest(cloud=cloud), \
                    patch.dict(os.environ, dict(PUBLIC_CONFIG), clear=True), \
                    patch.object(local_web, 'is_cloud_env', return_value=cloud), \
                    patch('tools.editorial_rag.supabase_auth.refresh_session') as renew, \
                    patch('tools.editorial_rag.supabase_auth.sign_in_session') as signin:
                auth = local_web.production_auth()
            self.assertIsInstance(auth, AppAuth)
            self.assertFalse(auth.status()['connected'])
            renew.assert_not_called()
            signin.assert_not_called()

    def test_refresh_token_env_restores_connected_with_pinned_validation(self):
        seed_text = 'fictional-refresh-token-abc123'
        with patch.dict(os.environ, credential_environment(seed=seed_text), clear=True), \
                patch('tools.editorial_rag.supabase_auth.refresh_session',
                      return_value=('fictional-jwt', 'fictional-rotated')) as renew, \
                patch('tools.editorial_rag.app_auth._claims', return_value=OWNER), \
                patch('tools.editorial_rag.app_auth.read_library', return_value=()) as read:
            auth = local_web.production_auth()
            connected = auth.status()['connected']
        self.assertTrue(connected)
        renew.assert_called_once()
        self.assertEqual(renew.call_args.args[0], seed_text)
        config = renew.call_args.kwargs['config']
        self.assertEqual(config.project_url, PROJECT_URL)
        self.assertEqual(config.owner_id, OWNER)
        read.assert_called_once_with('fictional-jwt', config)

    def test_rejected_refresh_token_stays_disconnected_without_raising(self):
        seed_text = 'fictional-rejected-token-xyz'
        with patch.dict(os.environ, credential_environment(seed=seed_text), clear=True), \
                patch('tools.editorial_rag.supabase_auth.refresh_session',
                      side_effect=AuthError('Editorial authentication unavailable or rejected')) as renew, \
                patch('tools.editorial_rag.app_auth._claims', return_value=OWNER), \
                patch('tools.editorial_rag.app_auth.read_library', return_value=()) as read:
            auth = local_web.production_auth()
        self.assertIsInstance(auth, AppAuth)
        self.assertFalse(auth.status()['connected'])
        renew.assert_called_once()
        read.assert_not_called()

    def test_malformed_refresh_token_fails_closed_without_any_exchange(self):
        for seed_text in ('bad token with spaces', 'x' * 4097):
            with self.subTest(length=len(seed_text)), \
                    patch.dict(os.environ, credential_environment(seed=seed_text), clear=True), \
                    patch('tools.editorial_rag.supabase_auth.refresh_session') as renew:
                auth = local_web.production_auth()
            self.assertIsInstance(auth, AppAuth)
            self.assertFalse(auth.status()['connected'])
            renew.assert_not_called()

    def test_owner_mismatch_stays_disconnected(self):
        seed_text = 'fictional-refresh-token-abc123'
        with patch.dict(os.environ, credential_environment(seed=seed_text), clear=True), \
                patch('tools.editorial_rag.supabase_auth.refresh_session',
                      return_value=('fictional-jwt', 'fictional-rotated')), \
                patch('tools.editorial_rag.app_auth._claims', return_value='someone-else'), \
                patch('tools.editorial_rag.app_auth.read_library', return_value=()) as read:
            auth = local_web.production_auth()
        self.assertFalse(auth.status()['connected'])
        read.assert_not_called()

    def test_authenticated_read_failure_stays_disconnected(self):
        seed_text = 'fictional-refresh-token-abc123'
        with patch.dict(os.environ, credential_environment(seed=seed_text), clear=True), \
                patch('tools.editorial_rag.supabase_auth.refresh_session',
                      return_value=('fictional-jwt', 'fictional-rotated')), \
                patch('tools.editorial_rag.app_auth._claims', return_value=OWNER), \
                patch('tools.editorial_rag.app_auth.read_library', side_effect=ValueError('fictional')):
            auth = local_web.production_auth()
        self.assertFalse(auth.status()['connected'])

    def test_email_password_env_signs_in_once_at_startup(self):
        email = 'fictional-owner@example.invalid'
        login_text = 'fictional-owner-login-value'
        with patch.dict(os.environ, credential_environment(email=email, login=login_text), clear=True), \
                patch('tools.editorial_rag.supabase_auth.sign_in_session',
                      return_value=('fictional-jwt', 'fictional-rotated')) as signin, \
                patch('tools.editorial_rag.app_auth._claims', return_value=OWNER), \
                patch('tools.editorial_rag.app_auth.read_library', return_value=()) as read:
            auth = local_web.production_auth()
            connected = auth.status()['connected']
        self.assertTrue(connected)
        signin.assert_called_once()
        self.assertEqual(signin.call_args.args, (email, login_text))
        config = signin.call_args.kwargs['config']
        self.assertEqual(config.project_url, PROJECT_URL)
        read.assert_called_once_with('fictional-jwt', config)

    def test_refresh_token_takes_precedence_over_the_password_pair(self):
        seed_text = 'fictional-refresh-token-abc123'
        email = 'fictional-owner@example.invalid'
        login_text = 'fictional-owner-login-value'
        environment = credential_environment(seed=seed_text, email=email, login=login_text)
        with patch.dict(os.environ, environment, clear=True), \
                patch('tools.editorial_rag.supabase_auth.refresh_session',
                      return_value=('fictional-jwt', 'fictional-rotated')) as renew, \
                patch('tools.editorial_rag.supabase_auth.sign_in_session') as signin, \
                patch('tools.editorial_rag.app_auth._claims', return_value=OWNER), \
                patch('tools.editorial_rag.app_auth.read_library', return_value=()):
            auth = local_web.production_auth()
            connected = auth.status()['connected']
        self.assertTrue(connected)
        renew.assert_called_once()
        signin.assert_not_called()

    def test_incomplete_credential_set_keeps_todays_behaviour(self):
        email = 'fictional-owner@example.invalid'
        for values in ({'email': email}, {'login': 'fictional-owner-login-value'}):
            with self.subTest(present=sorted(values)), \
                    patch.dict(os.environ, credential_environment(**values), clear=True), \
                    patch.object(local_web, 'is_cloud_env', return_value=True), \
                    patch('tools.editorial_rag.supabase_auth.refresh_session') as renew, \
                    patch('tools.editorial_rag.supabase_auth.sign_in_session') as signin:
                auth = local_web.production_auth()
            self.assertIsInstance(auth, AppAuth)
            self.assertFalse(auth.status()['connected'])
            renew.assert_not_called()
            signin.assert_not_called()

    def test_no_credential_value_in_exception_messages_or_logs(self):
        seed_text = 'fictional-leak-refresh-987'
        email = 'fictional-leak-owner@example.invalid'
        login_text = 'fictional-leak-login-456'
        stream = io.StringIO()
        records = []

        class Capture(logging.Handler):
            def emit(self, record):
                records.append(self.format(record))

        handler = Capture()
        logger = logging.getLogger()
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        self.addCleanup(logger.removeHandler, handler)
        self.addCleanup(logger.setLevel, logging.WARNING)
        scenarios = (
            credential_environment(seed=seed_text),
            credential_environment(email=email, login=login_text),
        )
        # Leaky lower layers that embed a credential in their own error text must
        # still be swallowed at the boundary and never reach output or logs.
        failures = (Exception(seed_text), ConfigError(email), Exception(login_text))
        with redirect_stdout(stream), redirect_stderr(stream):
            for scenario, failure in zip(scenarios + scenarios[:1], failures, strict=True):
                with self.subTest(failure=type(failure).__name__), \
                        patch.dict(os.environ, scenario, clear=True), \
                        patch('tools.editorial_rag.supabase_auth.refresh_session', side_effect=failure), \
                        patch('tools.editorial_rag.supabase_auth.sign_in_session', side_effect=failure):
                    auth = local_web.production_auth()
                self.assertIsInstance(auth, AppAuth)
                self.assertFalse(auth.status()['connected'])
        captured = stream.getvalue() + '\n' + '\n'.join(records)
        for secret in (seed_text, email, login_text):
            self.assertNotIn(secret, captured)
        with self.assertRaises(ValueError) as caught:
            session_store.EnvSessionStore(CONFIG, 'bad token with spaces')
        self.assertNotIn('bad token', str(caught.exception))


class DockerfileTests(unittest.TestCase):
    """Structural, honest checks on the shipped runtime stage; no line numbers."""

    @classmethod
    def setUpClass(cls):
        cls.path = Path(__file__).resolve().parents[2] / 'Dockerfile'
        cls.text = cls.path.read_text(encoding='utf-8')
        cls.final = 'FROM ' + re.split(r'(?m)^FROM ', cls.text)[-1]

    def test_runtime_stage_is_the_glibc_python_image(self):
        self.assertTrue(self.final.startswith('FROM python:3.12-slim'))
        self.assertNotRegex(self.final, r'(?mi)^from\s+\S*alpine')
        # Only the compiled frontend assets cross from the discarded builder.
        for line in self.final.splitlines():
            if line.startswith('COPY --from=frontend-builder'):
                self.assertIn('web/dist', line)

    def test_runtime_stage_installs_a_pinned_official_node(self):
        self.assertRegex(self.final, r'(?m)^ARG NODE_VERSION=\d+\.\d+\.\d+$')
        self.assertIn('v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.gz', self.final)
        self.assertIn('sha256sum -c', self.final)
        self.assertRegex(self.final, r'tar -xzf \S+ -C /usr/local')
        self.assertNotRegex(self.final, r'COPY\s+--from=frontend-builder\s+\S*node_modules')

    def test_embedding_dependencies_are_installed_in_the_runtime_stage(self):
        self.assertRegex(self.final, r'(?m)^COPY \S*embedding_node/package\.json')
        self.assertRegex(self.final, r'(?m)^RUN npm ci')

    def test_model_directory_variable_is_set_in_the_runtime_stage(self):
        self.assertIn(model_setup.ENV_MODEL_DIR + '=', self.final)

    def test_model_setup_runs_at_build_after_the_variable(self):
        variable_at = self.final.find(model_setup.ENV_MODEL_DIR + '=')
        setup_at = self.final.find('tools.editorial_rag.model_setup')
        self.assertNotEqual(variable_at, -1)
        self.assertNotEqual(setup_at, -1)
        self.assertLess(variable_at, setup_at)
        self.assertRegex(self.final, r'(?m)^RUN python (\S+ )?-m tools\.editorial_rag\.model_setup')

    def test_local_node_modules_never_enter_the_build_context(self):
        ignore = (self.path.parent / '.dockerignore').read_text(encoding='utf-8')
        self.assertIn('tools/editorial_rag/embedding_node/node_modules', ignore.splitlines())


if __name__ == '__main__':
    unittest.main()
