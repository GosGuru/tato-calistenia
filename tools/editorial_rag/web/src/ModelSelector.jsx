import { useEffect, useRef, useState } from 'react';
import { Bot, Check, Cpu, Eye, EyeOff, Key, Loader2, RefreshCw, Sparkles, X } from 'lucide-react';
import { localRequest } from './AppAuth.jsx';

export const DEFAULT_PROVIDERS = [
  {
    id: 'codex',
    name: 'Codex Pro (CLI)',
    badge: 'ChatGPT CLI',
    description: 'Usa tu suscripción de ChatGPT mediante la CLI de Codex en esta máquina.',
    requiresKey: false,
    models: ['chatgpt'],
    defaultModel: 'chatgpt',
    defaultBaseUrl: '',
  },
  {
    id: 'deepseek',
    name: 'DeepSeek',
    badge: 'API oficial',
    description: 'api.deepseek.com — Modelos DeepSeek-V3 y DeepSeek-R1 (razonamiento).',
    requiresKey: true,
    models: ['deepseek-chat', 'deepseek-reasoner'],
    defaultModel: 'deepseek-chat',
    defaultBaseUrl: 'https://api.deepseek.com',
  },
  {
    id: 'openrouter',
    name: 'OpenRouter',
    badge: 'Router global',
    description: 'openrouter.ai — Acceso unificado a Claude 3.5, Llama 3.3, Gemini, GPT-4o y DeepSeek.',
    requiresKey: true,
    models: [
      'deepseek/deepseek-chat',
      'deepseek/deepseek-r1',
      'anthropic/claude-3.5-sonnet',
      'meta-llama/llama-3.3-70b-instruct',
      'google/gemini-2.5-pro',
      'openai/gpt-4o',
    ],
    defaultModel: 'deepseek/deepseek-chat',
    defaultBaseUrl: 'https://openrouter.ai/api/v1',
  },
  {
    id: 'gemini',
    name: 'Google Gemini',
    badge: 'Google AI Studio',
    description: 'generativelanguage.googleapis.com — Gemini 2.5 Flash y Pro con tu API key de Google.',
    requiresKey: true,
    models: ['gemini-2.5-flash', 'gemini-2.5-pro', 'gemini-2.0-flash'],
    defaultModel: 'gemini-2.5-flash',
    defaultBaseUrl: 'https://generativelanguage.googleapis.com/v1beta/openai',
  },
  {
    id: 'opencode',
    name: 'OpenCode / Ollama',
    badge: 'Local / Proxy',
    description: 'Servidor local OpenAI-compatible (Ollama, vLLM, OpenCode) en tu máquina o red.',
    requiresKey: false,
    models: ['llama3.3', 'qwen2.5', 'deepseek-r1'],
    defaultModel: 'llama3.3',
    defaultBaseUrl: 'http://localhost:11434/v1',
  },
  {
    id: 'openai',
    name: 'OpenAI Direct',
    badge: 'OpenAI API',
    description: 'api.openai.com — GPT-4o, GPT-4o-mini y modelos o3 con API key oficial de OpenAI.',
    requiresKey: true,
    models: ['gpt-4o', 'gpt-4o-mini', 'o3-mini'],
    defaultModel: 'gpt-4o',
    defaultBaseUrl: 'https://api.openai.com/v1',
  },
];

export function getSavedModelConfig() {
  try {
    const raw = localStorage.getItem('tato_editorial_selected_model');
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed?.provider) return parsed;
    }
  } catch {}
  return { provider: 'codex', model: 'chatgpt', baseUrl: '' };
}

export function saveModelConfig(config) {
  try {
    localStorage.setItem('tato_editorial_selected_model', JSON.stringify(config));
  } catch {}
}

export function getSavedApiKeys() {
  try {
    return JSON.parse(localStorage.getItem('tato_editorial_api_keys') || '{}');
  } catch {
    return {};
  }
}

export function saveApiKey(provider, key) {
  try {
    const keys = getSavedApiKeys();
    if (key?.trim()) {
      keys[provider] = key.trim();
    } else {
      delete keys[provider];
    }
    localStorage.setItem('tato_editorial_api_keys', JSON.stringify(keys));
  } catch {}
}

export function getActiveProviderPayload(modelConfig) {
  if (!modelConfig || modelConfig.provider === 'codex') {
    return { provider: 'codex', model: 'chatgpt' };
  }
  const keys = getSavedApiKeys();
  const apiKey = keys[modelConfig.provider] || '';
  return {
    provider: modelConfig.provider,
    model: modelConfig.model,
    api_key: apiKey || undefined,
    base_url: modelConfig.baseUrl || undefined,
  };
}

export function modelDisplayLabel(modelConfig) {
  if (!modelConfig || modelConfig.provider === 'codex') return 'Codex';
  if (modelConfig.provider === 'deepseek') {
    return `DeepSeek (${modelConfig.model === 'deepseek-reasoner' ? 'R1' : 'V3'})`;
  }
  if (modelConfig.provider === 'openrouter') {
    const name = (modelConfig.model || '').split('/').pop() || 'V3';
    return `OpenRouter (${name})`;
  }
  if (modelConfig.provider === 'gemini') {
    return `Gemini (${(modelConfig.model || '').replace('gemini-', '')})`;
  }
  if (modelConfig.provider === 'opencode') {
    return `OpenCode (${modelConfig.model || 'Local'})`;
  }
  if (modelConfig.provider === 'openai') {
    return `OpenAI (${modelConfig.model || 'GPT-4o'})`;
  }
  return modelConfig.model || modelConfig.provider;
}

export function providerDisplayName(provider) {
  const p = DEFAULT_PROVIDERS.find(item => item.id === provider);
  return p ? p.name : provider;
}

export default function ModelSelector({ modelConfig, onModelChange, token, onDisconnect }) {
  const [open, setOpen] = useState(false);
  const [activeProvider, setActiveProvider] = useState(modelConfig?.provider || 'codex');
  const [selectedModel, setSelectedModel] = useState(modelConfig?.model || 'chatgpt');
  const [customModel, setCustomModel] = useState('');
  const [apiKey, setApiKey] = useState(() => {
    const keys = getSavedApiKeys();
    return keys[modelConfig?.provider || 'codex'] || '';
  });
  const [showKey, setShowKey] = useState(false);
  const [baseUrl, setBaseUrl] = useState(modelConfig?.baseUrl || '');
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [savedKeysMap, setSavedKeysMap] = useState(getSavedApiKeys);
  const [savedSuccess, setSavedSuccess] = useState(false);
  const detailsRef = useRef(null);

  function selectProvider(pid) {
    setActiveProvider(pid);
    const keys = getSavedApiKeys();
    setApiKey(keys[pid] || '');
    setCustomModel('');
    setTestResult(null);
    setSavedSuccess(false);
    const providerDef = DEFAULT_PROVIDERS.find(p => p.id === pid);
    if (modelConfig?.provider === pid) {
      setSelectedModel(modelConfig.model || providerDef?.defaultModel || '');
      setBaseUrl(modelConfig.baseUrl || providerDef?.defaultBaseUrl || '');
    } else {
      setSelectedModel(providerDef?.defaultModel || '');
      setBaseUrl(providerDef?.defaultBaseUrl || '');
    }
  }

  function handleToggle(isOpen) {
    setOpen(isOpen);
    if (isOpen) {
      setSavedKeysMap(getSavedApiKeys());
    }
  }

  const currentProviderDef = DEFAULT_PROVIDERS.find(p => p.id === activeProvider) || DEFAULT_PROVIDERS[0];
  const activeConfigProviderDef = DEFAULT_PROVIDERS.find(p => p.id === (modelConfig?.provider || 'codex')) || DEFAULT_PROVIDERS[0];

  const hasKey = !activeConfigProviderDef.requiresKey || !!savedKeysMap[activeConfigProviderDef.id];

  async function testConnection() {
    if (!token) return;
    setTesting(true);
    setTestResult(null);
    try {
      const finalModel = customModel.trim() || selectedModel || currentProviderDef.defaultModel;
      const res = await localRequest('/api/models/test', {
        method: 'POST',
        cache: 'no-store',
        credentials: 'omit',
        redirect: 'error',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': token },
        body: JSON.stringify({
          provider: activeProvider,
          model: finalModel,
          api_key: apiKey.trim() || undefined,
          base_url: baseUrl.trim() || undefined,
        }),
      });
      setTestResult(res);
    } catch (err) {
      if (err.category === 'transport') onDisconnect?.();
      setTestResult({
        status: 'error',
        error: err.diagnostic || err.message || 'Error al contactar el servidor local.',
      });
    } finally {
      setTesting(false);
    }
  }

  function handleApply() {
    const finalModel = customModel.trim() || selectedModel || currentProviderDef.defaultModel;
    if (currentProviderDef.requiresKey) {
      saveApiKey(activeProvider, apiKey.trim());
      setSavedKeysMap(getSavedApiKeys());
    }
    const newConfig = {
      provider: activeProvider,
      model: finalModel,
      baseUrl: baseUrl.trim() || undefined,
    };
    saveModelConfig(newConfig);
    onModelChange(newConfig);
    setSavedSuccess(true);
    setTimeout(() => {
      setSavedSuccess(false);
      setOpen(false);
      if (detailsRef.current) detailsRef.current.open = false;
    }, 400);
  }

  function handleClearKey() {
    saveApiKey(activeProvider, '');
    setApiKey('');
    setSavedKeysMap(getSavedApiKeys());
    setTestResult(null);
  }

  return (
    <details className="library-settings model-settings" ref={detailsRef} onToggle={e => handleToggle(e.currentTarget.open)}>
      <summary
        className="model-summary"
        aria-label="Selector de modelos"
        onClick={() => {
          const next = !open;
          setOpen(next);
          handleToggle(next);
        }}
      >
        <span className={`model-indicator ${hasKey ? 'ready' : 'needs-key'}`} aria-hidden="true" />
        <Cpu aria-hidden="true" />
        <span className="model-name-label">{modelDisplayLabel(modelConfig)}</span>
      </summary>

      {open && (
        <div className="library-body model-body" role="dialog" aria-label="Configurar modelos y proveedores">
        <div className="model-header">
          <div className="model-header-title">
            <Sparkles aria-hidden="true" />
            <h2>Selector de modelos</h2>
          </div>
          <button
            type="button"
            className="quiet close-btn"
            aria-label="Cerrar selector"
            onClick={() => {
              setOpen(false);
              if (detailsRef.current) detailsRef.current.open = false;
            }}
          >
            <X aria-hidden="true" />
          </button>
        </div>

        <p className="subtle">Elegí qué modelo y proveedor usar para generar los borradores de Instagram DM.</p>

        <section className="provider-grid" aria-label="Proveedores disponibles">
          {DEFAULT_PROVIDERS.map(p => {
            const isSelected = activeProvider === p.id;
            const isSavedActive = (modelConfig?.provider || 'codex') === p.id;
            const providerHasKey = !p.requiresKey || !!savedKeysMap[p.id];
            return (
              <button
                key={p.id}
                type="button"
                className={`provider-chip ${isSelected ? 'active' : ''} ${isSavedActive ? 'current-active' : ''}`}
                onClick={() => selectProvider(p.id)}
              >
                <span className="chip-name">{p.name}</span>
                <span className="chip-badge">{p.badge}</span>
                {providerHasKey && <span className="chip-check" title="Clave lista">✓</span>}
              </button>
            );
          })}
        </section>

        <div className="provider-details-card">
          <p className="provider-desc">{currentProviderDef.description}</p>

          <label htmlFor="model-select">Modelo a utilizar</label>
          <div className="model-quick-chips">
            {currentProviderDef.models.map(m => (
              <button
                key={m}
                type="button"
                className={`model-chip ${selectedModel === m && !customModel ? 'selected' : ''}`}
                onClick={() => {
                  setSelectedModel(m);
                  setCustomModel('');
                }}
              >
                {m}
              </button>
            ))}
          </div>

          <label htmlFor="custom-model">Otro modelo (ID manual opcional)</label>
          <input
            id="custom-model"
            type="text"
            placeholder={`Ej: ${currentProviderDef.defaultModel}`}
            value={customModel}
            onChange={e => setCustomModel(e.target.value)}
          />

          {currentProviderDef.requiresKey && (
            <div className="key-section">
              <label htmlFor="provider-api-key">
                Clave de API ({currentProviderDef.name})
                {savedKeysMap[activeProvider] && <span className="key-saved-badge">Guardada en este navegador</span>}
              </label>
              <div className="key-input-wrapper">
                <input
                  id="provider-api-key"
                  type={showKey ? 'text' : 'password'}
                  placeholder="sk-..."
                  autoComplete="off"
                  spellCheck={false}
                  value={apiKey}
                  onChange={e => setApiKey(e.target.value)}
                />
                <button
                  type="button"
                  className="quiet key-toggle"
                  onClick={() => setShowKey(!showKey)}
                  aria-label={showKey ? 'Ocultar clave' : 'Mostrar clave'}
                >
                  {showKey ? <EyeOff aria-hidden="true" /> : <Eye aria-hidden="true" />}
                </button>
              </div>
              <p className="privacy-note">
                Tu clave se almacena exclusivamente en tu navegador (localStorage). Nunca se sube a git ni a servidores de terceros.
              </p>
            </div>
          )}

          {activeProvider !== 'codex' && (
            <div className="base-url-section">
              <label htmlFor="custom-base-url">Base URL (opcional para proxies o local)</label>
              <input
                id="custom-base-url"
                type="text"
                placeholder={currentProviderDef.defaultBaseUrl || 'https://...'}
                value={baseUrl}
                onChange={e => setBaseUrl(e.target.value)}
              />
            </div>
          )}

          {testResult && (
            <div className={`test-feedback ${testResult.status === 'ok' ? 'success' : 'error'}`} role="status">
              {testResult.status === 'ok' ? (
                <>
                  <Check aria-hidden="true" />
                  <span>{testResult.message}</span>
                </>
              ) : (
                <>
                  <Bot aria-hidden="true" />
                  <span>{testResult.error}</span>
                </>
              )}
            </div>
          )}

          <div className="actions model-actions">
            <button
              type="button"
              className="quiet"
              disabled={testing || !token}
              onClick={testConnection}
            >
              {testing ? <Loader2 className="spinner" aria-hidden="true" /> : <RefreshCw aria-hidden="true" />}
              Probar conexión
            </button>

            {currentProviderDef.requiresKey && savedKeysMap[activeProvider] && (
              <button type="button" className="quiet destructive" onClick={handleClearKey}>
                Borrar clave
              </button>
            )}

            <button
              type="button"
              className="primary"
              disabled={savedSuccess}
              onClick={handleApply}
            >
              {savedSuccess ? 'Guardado ✓' : 'Guardar y usar'}
            </button>
          </div>
        </div>
      </div>
      )}
    </details>
  );
}
