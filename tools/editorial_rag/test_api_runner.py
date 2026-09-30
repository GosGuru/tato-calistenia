"""Tests for multi-provider API runner adapter."""
import json
import os
import unittest
from unittest.mock import MagicMock, patch

from tools.editorial_rag.api_runner import (
    ApiRunnerError,
    ApiSessionRunner,
    ProviderConfig,
    clean_model_output,
    create_runner,
    get_available_models_info,
    resolve_provider_settings,
    test_provider_connection,
)
from tools.editorial_rag.codex_runner import CodexSessionRunner
from tools.editorial_rag.raw_history import RawHistoryPacket


class CleanModelOutputTests(unittest.TestCase):
    def test_plain_text_preserved(self):
        self.assertEqual(clean_model_output("hola cómo estás?"), "hola cómo estás?")

    def test_think_tag_stripped(self):
        output = "<think>Let's consider the lead's problem.</think>Hola, qué tal?"
        self.assertEqual(clean_model_output(output), "Hola, qué tal?")

    def test_unclosed_think_returns_empty(self):
        output = "<think>Incomplete reasoning without end"
        self.assertEqual(clean_model_output(output), "")

    def test_markdown_code_fences_stripped_for_json(self):
        output = "```json\n{\"type\":\"dm\",\"text\":\"salida\"}\n```"
        self.assertEqual(clean_model_output(output, is_json_expected=True), '{"type":"dm","text":"salida"}')

    def test_markdown_code_fences_without_lang(self):
        output = "```\n{\"type\":\"dm\",\"text\":\"salida\"}\n```"
        self.assertEqual(clean_model_output(output, is_json_expected=True), '{"type":"dm","text":"salida"}')

    def test_extract_outer_json_when_surrounded_by_text(self):
        output = "Aquí está tu respuesta:\n{\"type\":\"dm\",\"text\":\"salida\"}\nEspero te sirva."
        self.assertEqual(clean_model_output(output, is_json_expected=True), '{"type":"dm","text":"salida"}')


class ProviderSettingsTests(unittest.TestCase):
    def test_codex_defaults(self):
        cfg = ProviderConfig(provider='codex')
        settings = resolve_provider_settings(cfg)
        self.assertEqual(settings['provider'], 'codex')
        self.assertEqual(settings['model'], 'chatgpt')

    def test_deepseek_requires_key(self):
        cfg = ProviderConfig(provider='deepseek')
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ApiRunnerError):
                resolve_provider_settings(cfg)

    def test_deepseek_reads_from_config(self):
        cfg = ProviderConfig(provider='deepseek', api_key='sk-test-123')
        settings = resolve_provider_settings(cfg)
        self.assertEqual(settings['api_key'], 'sk-test-123')
        self.assertEqual(settings['base_url'], 'https://api.deepseek.com')
        self.assertEqual(settings['model'], 'deepseek-chat')

    def test_deepseek_reads_from_env(self):
        cfg = ProviderConfig(provider='deepseek')
        with patch.dict(os.environ, {'DEEPSEEK_API_KEY': 'sk-env-456'}):
            settings = resolve_provider_settings(cfg)
            self.assertEqual(settings['api_key'], 'sk-env-456')

    def test_openrouter_settings(self):
        cfg = ProviderConfig(provider='openrouter', api_key='sk-or-test', model='anthropic/claude-3.5-sonnet')
        settings = resolve_provider_settings(cfg)
        self.assertEqual(settings['base_url'], 'https://openrouter.ai/api/v1')
        self.assertEqual(settings['model'], 'anthropic/claude-3.5-sonnet')

    def test_gemini_settings(self):
        cfg = ProviderConfig(provider='gemini', api_key='AIzaSyTest')
        settings = resolve_provider_settings(cfg)
        self.assertEqual(settings['base_url'], 'https://generativelanguage.googleapis.com/v1beta/openai')
        self.assertEqual(settings['model'], 'gemini-2.5-flash')

    def test_opencode_local_requires_no_key(self):
        cfg = ProviderConfig(provider='opencode')
        settings = resolve_provider_settings(cfg)
        self.assertEqual(settings['base_url'], 'http://localhost:11434/v1')
        self.assertEqual(settings['model'], 'llama3.3')
        self.assertEqual(settings['api_key'], '')

    def test_custom_provider(self):
        cfg = ProviderConfig(provider='custom_corp', base_url='http://internal.ai/v1', model='corp-llm', api_key='k')
        settings = resolve_provider_settings(cfg)
        self.assertEqual(settings['base_url'], 'http://internal.ai/v1')
        self.assertEqual(settings['model'], 'corp-llm')


class FactoryTests(unittest.TestCase):
    def test_create_runner_codex(self):
        runner = create_runner(None)
        self.assertIsInstance(runner, CodexSessionRunner)
        runner2 = create_runner(ProviderConfig(provider='codex'))
        self.assertIsInstance(runner2, CodexSessionRunner)

    def test_create_runner_api(self):
        runner = create_runner(ProviderConfig(provider='deepseek', api_key='k'))
        self.assertIsInstance(runner, ApiSessionRunner)


class ApiSessionRunnerMockTests(unittest.TestCase):
    @patch('httpx.Client.post')
    def test_successful_raw_call(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'choices': [{
                'message': {'content': '{"type":"dm","text":"hola qué tal?"}'}
            }]
        }
        mock_post.return_value = mock_response

        cfg = ProviderConfig(provider='deepseek', api_key='sk-test')
        runner = ApiSessionRunner(cfg)
        packet = RawHistoryPacket('Lead: hola\nTato: buenas', 'rules', True)
        result = runner(packet)
        self.assertEqual(result, '{"type":"dm","text":"hola qué tal?"}')

    @patch('httpx.Client.post')
    def test_auth_error_handling(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_post.return_value = mock_response

        cfg = ProviderConfig(provider='deepseek', api_key='sk-bad')
        runner = ApiSessionRunner(cfg)
        packet = RawHistoryPacket('Lead: hola', 'rules', True)
        with self.assertRaises(ApiRunnerError) as ctx:
            runner(packet)
        self.assertIn('API key inválida', str(ctx.exception))


class AvailableModelsInfoTests(unittest.TestCase):
    def test_get_available_models_info(self):
        info = get_available_models_info()
        self.assertIn('providers', info)
        provider_ids = [p['id'] for p in info['providers']]
        for expected in ('codex', 'deepseek', 'openrouter', 'gemini', 'opencode', 'openai'):
            self.assertIn(expected, provider_ids)


if __name__ == '__main__':
    unittest.main()
