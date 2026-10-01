import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ModelSelector, {
  getActiveProviderPayload,
  getSavedApiKeys,
  getSavedModelConfig,
  modelDisplayLabel,
  providerDisplayName,
  saveApiKey,
  saveModelConfig,
  sanitizeBaseUrl,
} from './ModelSelector.jsx';

describe('ModelSelector storage and label helpers', () => {
  beforeEach(() => {
    localStorage.clear();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  it('handles default model config when localStorage is empty', () => {
    expect(getSavedModelConfig()).toEqual({ provider: 'codex', model: 'chatgpt', baseUrl: '' });
  });

  it('saves and retrieves model config in localStorage', () => {
    saveModelConfig({ provider: 'deepseek', model: 'deepseek-chat' });
    expect(getSavedModelConfig()).toEqual({ provider: 'deepseek', model: 'deepseek-chat' });
  });

  it('saves and clears API keys in localStorage', () => {
    saveApiKey('deepseek', 'sk-test-key');
    expect(getSavedApiKeys()['deepseek']).toBe('sk-test-key');

    saveApiKey('deepseek', '');
    expect(getSavedApiKeys()['deepseek']).toBeUndefined();
  });

  it('returns clean provider payload for codex and custom APIs', () => {
    expect(getActiveProviderPayload({ provider: 'codex', model: 'chatgpt' })).toEqual({
      provider: 'codex',
      model: 'chatgpt',
    });

    saveApiKey('deepseek', 'sk-secret');
    expect(getActiveProviderPayload({ provider: 'deepseek', model: 'deepseek-chat' })).toEqual({
      provider: 'deepseek',
      model: 'deepseek-chat',
      api_key: 'sk-secret',
      base_url: undefined,
    });
  });

  it('sanitizes base URL by stripping /chat/completions and trailing slashes', () => {
    expect(sanitizeBaseUrl('https://opencode.ai/inference/openai/v1/chat/completions')).toBe('https://opencode.ai/inference/openai/v1');
    expect(sanitizeBaseUrl('https://opencode.ai/inference/openai/v1/chat/completions/')).toBe('https://opencode.ai/inference/openai/v1');
    expect(sanitizeBaseUrl('https://opencode.ai/inference/openai/v1/')).toBe('https://opencode.ai/inference/openai/v1');
    expect(sanitizeBaseUrl('https://opencode.ai/inference/openai/v1')).toBe('https://opencode.ai/inference/openai/v1');
    expect(sanitizeBaseUrl('')).toBe('');
    expect(sanitizeBaseUrl(null)).toBe('');
  });

  it('formats display labels accurately for various providers', () => {
    expect(modelDisplayLabel({ provider: 'codex', model: 'chatgpt' })).toBe('Codex');
    expect(modelDisplayLabel({ provider: 'deepseek', model: 'deepseek-chat' })).toBe('DeepSeek (V3)');
    expect(modelDisplayLabel({ provider: 'deepseek', model: 'deepseek-reasoner' })).toBe('DeepSeek (R1)');
    expect(modelDisplayLabel({ provider: 'deepseek', model: 'deepseek-flash' })).toBe('DeepSeek (Flash)');
    expect(modelDisplayLabel({ provider: 'deepseek', model: 'deepseek-v4-pro' })).toBe('DeepSeek (V4 Pro)');
    expect(modelDisplayLabel({ provider: 'openrouter', model: 'anthropic/claude-3.5-sonnet' })).toBe('OpenRouter (claude-3.5-sonnet)');
    expect(modelDisplayLabel({ provider: 'gemini', model: 'gemini-2.5-flash' })).toBe('Gemini (2.5-flash)');
    expect(modelDisplayLabel({ provider: 'opencode', model: 'gpt-6-luna' })).toBe('OpenCode (gpt-6-luna)');
    expect(modelDisplayLabel({ provider: 'opencode' })).toBe('OpenCode (gpt-6-luna)');
    expect(modelDisplayLabel({ provider: 'openai', model: 'gpt-4o' })).toBe('OpenAI (gpt-4o)');
  });

  it('returns full provider display name', () => {
    expect(providerDisplayName('codex')).toBe('Codex Pro (CLI)');
    expect(providerDisplayName('deepseek')).toBe('DeepSeek');
    expect(providerDisplayName('openrouter')).toBe('OpenRouter');
    expect(providerDisplayName('gemini')).toBe('Google Gemini');
    expect(providerDisplayName('opencode')).toBe('OpenCode');
  });
});

describe('ModelSelector UI interaction', () => {
  beforeEach(() => {
    localStorage.clear();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
  });

  it('renders default summary button with Codex', () => {
    render(<ModelSelector modelConfig={{ provider: 'codex', model: 'chatgpt' }} onModelChange={vi.fn()} token="tok" />);
    expect(screen.getByLabelText('Selector de modelos')).toBeInTheDocument();
    expect(screen.getByText('Codex')).toBeVisible();
  });

  it('opens panel, selects DeepSeek, enters API key, and applies changes', async () => {
    const onModelChange = vi.fn();
    render(<ModelSelector modelConfig={{ provider: 'codex', model: 'chatgpt' }} onModelChange={onModelChange} token="tok" />);

    const summary = screen.getByLabelText('Selector de modelos');
    fireEvent.click(summary);

    expect(screen.getByText('Selector de modelos')).toBeVisible();
    expect(screen.getByText('Elegí qué modelo y proveedor usar para generar los borradores de Instagram DM.')).toBeVisible();

    const deepseekBtn = screen.getByRole('button', { name: /DeepSeek/i });
    fireEvent.click(deepseekBtn);

    expect(screen.getByLabelText(/Clave de API \(DeepSeek\)/i)).toBeVisible();
    const keyInput = screen.getByPlaceholderText('sk-...');
    fireEvent.change(keyInput, { target: { value: 'sk-deepseek-12345' } });

    const applyBtn = screen.getByRole('button', { name: 'Guardar y usar' });
    await userEvent.click(applyBtn);

    expect(onModelChange).toHaveBeenCalledWith({
      provider: 'deepseek',
      model: 'deepseek-chat',
      baseUrl: 'https://api.deepseek.com',
    });
    expect(getSavedApiKeys()['deepseek']).toBe('sk-deepseek-12345');
  });

  it('tests provider connection with mocked fetch', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ status: 'ok', provider: 'deepseek', message: 'Conectado exitosamente con DeepSeek.' }),
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<ModelSelector modelConfig={{ provider: 'deepseek', model: 'deepseek-chat' }} onModelChange={vi.fn()} token="tok-123" />);

    const summary = screen.getByLabelText('Selector de modelos');
    fireEvent.click(summary);

    const testBtn = screen.getByRole('button', { name: /Probar conexión/i });
    await userEvent.click(testBtn);

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/models/test',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          'X-CSRF-Token': 'tok-123',
        }),
      })
    );

    expect(await screen.findByText('Conectado exitosamente con DeepSeek.')).toBeVisible();
  });

  it('configures OpenCode with cloud defaults, API key, and sanitizes /chat/completions from baseUrl', async () => {
    const onModelChange = vi.fn();
    render(<ModelSelector modelConfig={{ provider: 'codex', model: 'chatgpt' }} onModelChange={onModelChange} token="tok" />);

    const summary = screen.getByLabelText('Selector de modelos');
    fireEvent.click(summary);

    const opencodeBtn = screen.getByRole('button', { name: /OpenCode/i });
    fireEvent.click(opencodeBtn);

    expect(screen.getByLabelText(/Clave de API \(OpenCode\)/i)).toBeVisible();
    const keyInput = screen.getByPlaceholderText('sk-...');
    fireEvent.change(keyInput, { target: { value: 'sk-opencode-secret' } });

    const baseUrlInput = screen.getByLabelText(/Base URL/i);
    fireEvent.change(baseUrlInput, {
      target: { value: 'https://opencode.ai/inference/openai/v1/chat/completions' },
    });

    const applyBtn = screen.getByRole('button', { name: 'Guardar y usar' });
    await userEvent.click(applyBtn);

    expect(onModelChange).toHaveBeenCalledWith({
      provider: 'opencode',
      model: 'deepseek-v4.1-flash',
      baseUrl: 'https://opencode.ai/inference/openai/v1',
    });
    expect(getSavedApiKeys()['opencode']).toBe('sk-opencode-secret');
  });
});
