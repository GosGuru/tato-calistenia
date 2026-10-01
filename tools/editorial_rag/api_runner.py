"""Multi-provider LLM adapter supporting OpenAI-compatible APIs (DeepSeek, OpenRouter, Gemini, OpenCode)."""
import hashlib
import json
import os
import re
from contextlib import nullcontext
from typing import Any, Dict, List, Optional

import httpx
from pydantic import BaseModel, ConfigDict, Field, StrictStr

if __package__:
    from .codex_runner import CodexSessionRunner, _prompt
    from .raw_history import RawHistoryPacket
else:
    from codex_runner import CodexSessionRunner, _prompt
    from raw_history import RawHistoryPacket


class ApiRunnerError(RuntimeError):
    """User-facing API execution diagnostic."""


class ProviderConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')
    provider: StrictStr = 'codex'
    model: Optional[StrictStr] = None
    api_key: Optional[StrictStr] = None
    base_url: Optional[StrictStr] = None


PROVIDERS = {
    'codex': {
        'name': 'Codex Pro (CLI)',
        'type': 'cli',
        'default_model': 'chatgpt',
        'models': ['chatgpt'],
        'default_base_url': None,
        'env_key': None,
        'requires_key': False,
    },
    'deepseek': {
        'name': 'DeepSeek',
        'type': 'api',
        'default_model': 'deepseek-chat',
        'models': ['deepseek-chat', 'deepseek-reasoner', 'deepseek-flash', 'deepseek-v4-pro'],
        'default_base_url': 'https://api.deepseek.com',
        'env_key': 'DEEPSEEK_API_KEY',
        'requires_key': True,
    },
    'openrouter': {
        'name': 'OpenRouter',
        'type': 'api',
        'default_model': 'deepseek/deepseek-chat',
        'models': [
            'deepseek/deepseek-chat',
            'deepseek/deepseek-r1',
            'anthropic/claude-3.5-sonnet',
            'meta-llama/llama-3.3-70b-instruct',
            'google/gemini-2.5-pro',
            'openai/gpt-4o',
        ],
        'default_base_url': 'https://openrouter.ai/api/v1',
        'env_key': 'OPENROUTER_API_KEY',
        'requires_key': True,
    },
    'gemini': {
        'name': 'Google Gemini',
        'type': 'api',
        'default_model': 'gemini-2.5-flash',
        'models': ['gemini-2.5-flash', 'gemini-2.5-pro', 'gemini-2.0-flash'],
        'default_base_url': 'https://generativelanguage.googleapis.com/v1beta/openai',
        'env_key': 'GEMINI_API_KEY',
        'requires_key': True,
    },
    'opencode': {
        'name': 'OpenCode',
        'type': 'api',
        'default_model': 'gpt-6-luna',
        'models': ['gpt-6-luna', 'kimi-k2.6', 'glm-5.1', 'minimax-m2.7', 'deepseek-v4.1-flash', 'deepseek-r1'],
        'default_base_url': 'https://opencode.ai/zen/go/v1',
        'env_key': 'OPENCODE_API_KEY',
        'requires_key': True,
    },
    'openai': {
        'name': 'OpenAI Direct',
        'type': 'api',
        'default_model': 'gpt-4o',
        'models': ['gpt-4o', 'gpt-4o-mini', 'o3-mini'],
        'default_base_url': 'https://api.openai.com/v1',
        'env_key': 'OPENAI_API_KEY',
        'requires_key': True,
    },
}


def normalize_base_url(url: Optional[str]) -> str:
    """Normalize base URL by stripping whitespace, trailing slashes, and redundant /chat/completions."""
    if not url:
        return ''
    cleaned = url.strip()
    cleaned = re.sub(r'/chat/completions/?$', '', cleaned, flags=re.IGNORECASE)
    return cleaned.rstrip('/')


def normalize_model_name(provider: str, model: Optional[str]) -> str:
    """Normalize model identifier, mapping common marketing names or casing to exact API slugs."""
    if not model:
        return ''
    m = model.strip()
    if provider.lower() == 'deepseek':
        m_clean = m.lower().replace(' ', '-')
        if 'flash' in m_clean:
            return 'deepseek-flash'
        if 'pro' in m_clean or 'v4' in m_clean:
            return 'deepseek-v4-pro'
        if 'reason' in m_clean or 'r1' in m_clean:
            return 'deepseek-reasoner'
        if 'chat' in m_clean or 'v3' in m_clean:
            return 'deepseek-chat'
    return m


def get_available_models_info() -> Dict[str, Any]:
    providers_info = []
    for pid, info in PROVIDERS.items():
        env_key = info.get('env_key')
        has_env_key = bool(env_key and os.environ.get(env_key))
        providers_info.append({
            'id': pid,
            'name': info['name'],
            'type': info['type'],
            'default_model': info['default_model'],
            'models': info['models'],
            'default_base_url': info['default_base_url'],
            'has_env_key': has_env_key,
            'requires_key': info['requires_key'],
        })
    return {'providers': providers_info}


def extract_thinking_and_content(content: str) -> tuple[str, str]:
    """Extract <think>...</think> reasoning blocks and remaining content."""
    if not isinstance(content, str):
        return '', ''
    text = content.strip()
    thinking = ''
    if '<think>' in text:
        parts = text.split('<think>', 1)[1]
        if '</think>' in parts:
            thinking_raw, text = parts.split('</think>', 1)
            thinking = thinking_raw.strip()
        else:
            thinking = parts.strip()
            text = ''
    return text.strip(), thinking


def clean_model_output(content: str, is_json_expected: bool = False) -> str:
    """Clean model completion text, stripping <think> tags and markdown code blocks."""
    if not isinstance(content, str):
        return ''
    text, _ = extract_thinking_and_content(content)

    if is_json_expected:
        # Strip markdown code fences if present
        if text.startswith('```'):
            lines = text.splitlines()
            if lines and lines[0].startswith('```'):
                lines = lines[1:]
            if lines and lines[-1].strip() == '```':
                lines = lines[:-1]
            text = '\n'.join(lines).strip()

        # If there's an embedded JSON object, extract it and sanitize to closed schema
        if '{' in text and '}' in text:
            start = text.find('{')
            end = text.rfind('}') + 1
            candidate = text[start:end].strip()
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    msg_type = parsed.get('type')
                    if msg_type == 'needs_context' and 'question' in parsed:
                        if set(parsed.keys()) == {'type', 'question'}:
                            return candidate
                        return json.dumps({'type': 'needs_context', 'question': str(parsed['question']).strip()}, ensure_ascii=False, separators=(',', ':'))
                    dm_text = parsed.get('text') or parsed.get('dm') or parsed.get('message') or parsed.get('response')
                    if dm_text:
                        if set(parsed.keys()) == {'type', 'text'} and parsed.get('type') == 'dm':
                            return candidate
                        return json.dumps({'type': 'dm', 'text': str(dm_text).strip()}, ensure_ascii=False, separators=(',', ':'))
                    return candidate
            except Exception:
                pass

        # If plain text was returned instead of JSON, wrap as a DM
        if text.strip() and not text.startswith('{'):
            return json.dumps({'type': 'dm', 'text': text.strip()}, ensure_ascii=False, separators=(',', ':'))

    return text.strip()


def resolve_provider_settings(config: ProviderConfig) -> Dict[str, str]:
    provider = config.provider.lower().strip()
    info = PROVIDERS.get(provider)
    if not info:
        # Custom provider fallback
        base_url = normalize_base_url(config.base_url or 'https://api.openai.com/v1')
        model = normalize_model_name(provider, config.model or 'default')
        api_key = config.api_key or ''
        return {'provider': provider, 'base_url': base_url, 'model': model, 'api_key': api_key}

    base_url = normalize_base_url(config.base_url or info['default_base_url'] or '')
    model = normalize_model_name(provider, config.model or info['default_model'])
    api_key = config.api_key

    if not api_key and info['env_key']:
        api_key = os.environ.get(info['env_key'], '')

    if info['requires_key'] and not api_key:
        raise ApiRunnerError(
            f"Falta la clave de API para {info['name']}. "
            f"Configurala en el selector de modelos o en la variable de entorno {info['env_key']}."
        )

    return {
        'provider': provider,
        'base_url': base_url,
        'model': model,
        'api_key': api_key or '',
    }


def test_provider_connection(config: ProviderConfig, timeout: float = 15.0) -> Dict[str, Any]:
    """Perform a lightweight test request against the selected provider."""
    try:
        if config.provider == 'codex':
            import shutil
            import subprocess
            executable = shutil.which('codex')
            if not executable:
                return {'status': 'error', 'provider': 'codex', 'error': 'CLI de Codex no disponible en PATH.'}
            auth = subprocess.run([executable, 'login', 'status'], capture_output=True, text=True, timeout=10)
            if auth.returncode != 0 or 'Logged in using ChatGPT' not in (auth.stdout + auth.stderr):
                return {'status': 'error', 'provider': 'codex', 'error': 'No hay sesión activa de ChatGPT en Codex CLI.'}
            return {'status': 'ok', 'provider': 'codex', 'model': 'chatgpt', 'message': 'Conexión activa con Codex CLI.'}

        settings = resolve_provider_settings(config)
        endpoint = f"{settings['base_url']}/chat/completions"

        headers = {'Content-Type': 'application/json'}
        if settings['api_key']:
            headers['Authorization'] = f"Bearer {settings['api_key']}"

        if settings['provider'] == 'openrouter':
            headers['HTTP-Referer'] = 'http://127.0.0.1:8765'
            headers['X-Title'] = 'Tato Calistenia'

        if settings['provider'] == 'opencode':
            headers['x-opencode-session'] = 'tato-editorial-test'

        payload = {
            'model': settings['model'],
            'messages': [{'role': 'user', 'content': 'Responde únicamente con la palabra OK.'}],
            'max_tokens': 10,
            'temperature': 0.1,
        }

        with httpx.Client(timeout=timeout) as client:
            response = client.post(endpoint, headers=headers, json=payload)

        if response.status_code == 401 or response.status_code == 403:
            return {'status': 'error', 'provider': settings['provider'], 'error': 'API key inválida o permisos insuficientes.'}
        if response.status_code == 429:
            return {'status': 'error', 'provider': settings['provider'], 'error': 'Límite de tasa (rate limit) o saldo insuficiente.'}
        if response.status_code >= 400:
            try:
                err_body = response.json()
                detail = err_body.get('error', {}).get('message', response.text[:200])
            except Exception:
                detail = response.text[:200]
            return {'status': 'error', 'provider': settings['provider'], 'error': f"HTTP {response.status_code}: {detail}"}

        data = response.json()
        reply = data.get('choices', [{}])[0].get('message', {}).get('content', '').strip()
        return {
            'status': 'ok',
            'provider': settings['provider'],
            'model': settings['model'],
            'message': f"Conexión exitosa con {settings['provider']} ({settings['model']}). Respuesta: {reply[:30]}",
        }
    except ApiRunnerError as exc:
        return {'status': 'error', 'provider': config.provider, 'error': str(exc)}
    except httpx.TimeoutException:
        return {'status': 'error', 'provider': config.provider, 'error': 'Tiempo de espera agotado al conectar con el proveedor.'}
    except httpx.RequestError as exc:
        return {'status': 'error', 'provider': config.provider, 'error': f'Error de red al conectar: {str(exc)}'}
    except Exception as exc:
        return {'status': 'error', 'provider': config.provider, 'error': f'Fallo inesperado: {str(exc)}'}


class ApiSessionRunner:
    """Callable adapter sending prompts to OpenAI-compatible LLM endpoints."""

    def __init__(self, config: ProviderConfig, timeout: float = 120.0, diagnostics=None):
        self.config = config
        self.timeout = timeout
        self.diagnostics = diagnostics
        self.last_thinking = ''

    def stage(self, name: str):
        return self.diagnostics.stage(name) if self.diagnostics is not None else nullcontext()

    def outcome(self, name: str, outcome_name: str):
        if self.diagnostics is not None:
            self.diagnostics.outcome(name, outcome_name)

    def __call__(self, packet: Any) -> str:
        self.last_thinking = ''
        with self.stage('packet'):
            prompt = _prompt(packet)

        settings = resolve_provider_settings(self.config)
        endpoint = f"{settings['base_url']}/chat/completions"

        headers = {'Content-Type': 'application/json'}
        if settings['api_key']:
            headers['Authorization'] = f"Bearer {settings['api_key']}"

        if settings['provider'] == 'openrouter':
            headers['HTTP-Referer'] = 'http://127.0.0.1:8765'
            headers['X-Title'] = 'Tato Calistenia'

        if settings['provider'] == 'opencode':
            session_hash = hashlib.sha256(prompt[:300].encode('utf-8')).hexdigest()[:16]
            headers['x-opencode-session'] = f"tato-{session_hash}"

        is_json_expected = type(packet) is RawHistoryPacket
        payload: Dict[str, Any] = {
            'model': settings['model'],
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': 0.2,
        }

        with self.stage('exec'):
            if self.diagnostics is not None:
                self.diagnostics.attempt_exec()
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(endpoint, headers=headers, json=payload)
            except httpx.TimeoutException:
                self.outcome('exec', 'timeout')
                raise ApiRunnerError(f"Tiempo de espera agotado ({self.timeout}s) conectando a {settings['provider']}.")
            except httpx.RequestError as exc:
                self.outcome('exec', 'unavailable')
                raise ApiRunnerError(f"Error de conexión con {settings['provider']}: {str(exc)}")

            if response.status_code == 401 or response.status_code == 403:
                self.outcome('login', 'rejected')
                raise ApiRunnerError(f"API key inválida para {settings['provider']}.")
            if response.status_code == 429:
                self.outcome('exec', 'rejected')
                raise ApiRunnerError(f"Límite de tasa o cuota insuficiente en {settings['provider']}.")
            if response.status_code >= 400:
                self.outcome('exec', 'nonzero')
                try:
                    err_msg = response.json().get('error', {}).get('message', response.text[:200])
                except Exception:
                    err_msg = response.text[:200]
                raise ApiRunnerError(f"Error {response.status_code} de {settings['provider']}: {err_msg}")

        with self.stage('stream'):
            try:
                data = response.json()
                msg = data['choices'][0]['message']
                raw_content = msg.get('content') or ''
                reasoning = msg.get('reasoning_content') or msg.get('reasoning') or ''
            except (KeyError, IndexError, ValueError, TypeError):
                self.outcome('stream', 'invalid')
                raise ApiRunnerError('Respuesta malformada del proveedor.')

            extracted_text, think_tag = extract_thinking_and_content(raw_content)
            self.last_thinking = (reasoning or think_tag).strip()

            cleaned = clean_model_output(extracted_text, is_json_expected=is_json_expected)
            if not cleaned:
                self.outcome('stream', 'invalid')
                raise ApiRunnerError('El modelo devolvió una respuesta vacía.')

            self.outcome('stream', 'ok')
            return cleaned


def create_runner(config: Optional[ProviderConfig] = None, timeout: float = 120.0, diagnostics=None):
    """Factory creating either CodexSessionRunner or ApiSessionRunner."""
    if config is None or config.provider == 'codex':
        return CodexSessionRunner(timeout=timeout, diagnostics=diagnostics)
    return ApiSessionRunner(config, timeout=timeout, diagnostics=diagnostics)
