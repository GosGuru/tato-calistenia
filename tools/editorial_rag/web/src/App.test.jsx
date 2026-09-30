import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, waitFor, act, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from './App.jsx';

const context = {
  csrf_token: 'synthetic-token', phase: 'brecha', model: 'unknown', effort: 'unknown',
  messages: [{ role: 'assistant', text: 'qué movimiento querés mejorar?' },
    { role: 'user', text: 'las dominadas' }],
  guidance: { positive_voice: 'Criterio sintético, no plantilla.', negative_repetition: 'No repetir aperturas.' },
};
const bootstrap = { app: 'tato-local', protocol: 1, csrf_token: 'synthetic-token', model: 'unknown', effort: 'unknown' };
const signals = { exact_previous: false, same_opening: false, shared_trigrams: 0, guidance_trigrams: 0 };
const pair = (mode = 'simulated') => ({
  mode, label: mode === 'simulated' ? 'Demo simulada · borradores manuales' : 'Codex · caso sintético',
  drafts: { current: 'primer borrador sintético?', editorial: 'segundo borrador sintético?' },
  signals: { current: signals, editorial: signals },
});
const response = (body, ok = true, status = 200) => ({ ok, status, json: async () => body });
async function openApp() {
  // Every test gets independent primary bootstrap; synthetic mocks remain unchanged.
  const original = globalThis.fetch;
  globalThis.fetch = (url, options) => url === '/api/bootstrap'
    ? Promise.resolve(response(bootstrap)) : original(url, options);
  render(<App />);
  await userEvent.click(screen.getByRole('tab', { name: 'Comparador sintético' }));
  await screen.findByText('las dominadas');
}
afterEach(() => vi.unstubAllGlobals());

const deferred = () => {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
};
const libraryStatus = { connected: false, empty: false, count: 0, revision: 20 };
const rawEnvelope = text => ({ result: { type: 'dm', text }, retrieval: { status: 'off', count: 0 }, revision: 40 });
const rawButton = () => screen.getByRole('button', { name: 'Generar borrador' });
const paste = () => fireEvent.change(screen.getByLabelText('Historial completo'), { target: { value: 'fictional history only' } });
async function authFixture() {
  const auth = deferred();
  const old = deferred();
  const fetch = vi.fn(url => {
    if (url === '/api/bootstrap') return Promise.resolve(response(bootstrap));
    if (url === '/api/auth/status') return Promise.resolve(response(libraryStatus));
    if (url === '/api/raw-draft') return old.promise;
    return auth.promise;
  });
  vi.stubGlobal('fetch', fetch);
  const view = render(<App />);
  paste();
  await waitFor(() => expect(rawButton()).toBeEnabled());
  await userEvent.click(screen.getByText('Biblioteca'));
  await screen.findByText('Biblioteca desconectada.');
  return { auth, old, fetch, view, rawCalls: () => fetch.mock.calls.filter(([url]) => url === '/api/raw-draft') };
}
async function beginAuth(operation) {
  if (operation === 'Conectar') {
    fireEvent.change(screen.getByLabelText('Email editorial'), { target: { value: 'fictional@example.invalid' } });
    fireEvent.change(screen.getByLabelText('Contraseña editorial'), { target: { value: 'fictional-only' } });
  }
  await userEvent.click(screen.getByRole('button', { name: operation }));
}

describe('persistence transport isolation', () => {
  it.each(['transport', '404', 'http', 'json', 'envelope', 'reconnect', 'auth'])('handles metadata-only %s without replay or input loss', async kind => {
    const metadata = deferred();
    let metadataReads = 0;
    let nonce = 'synthetic-token';
    const fetch = vi.fn((url, options = {}) => {
      if (url === '/api/bootstrap') return Promise.resolve(response({ ...bootstrap, csrf_token: nonce }));
      if (url === '/api/auth/status' || url === '/api/auth/logout') return Promise.resolve(response(libraryStatus));
      if (url === '/api/auth/persistence') return ++metadataReads === 1 ? metadata.promise : Promise.resolve(response({}, false, 404));
      if (url === '/api/raw-draft' && options.method === 'POST') return Promise.resolve(response(rawEnvelope('fresh fictional result')));
      throw new Error('Unplanned fixture request');
    });
    vi.stubGlobal('fetch', fetch);
    render(<App />); paste();
    await waitFor(() => expect(rawButton()).toBeEnabled());
    await userEvent.click(screen.getByText('Biblioteca'));
    await screen.findByText('Biblioteca desconectada.');
    if (kind === 'reconnect') {
      nonce = 'fresh';
      await userEvent.click(screen.getByRole('button', { name: 'Reconectar' }));
      await waitFor(() => expect(rawButton()).toBeEnabled());
    }
    if (kind === 'auth') await beginAuth('Desconectar');
    await act(async () => {
      if (['transport', 'reconnect', 'auth'].includes(kind)) metadata.reject(new TypeError('fictional transport'));
      else if (kind === 'json') metadata.resolve({ ok: true, json: async () => { throw new SyntaxError('fictional invalid JSON'); } });
      else metadata.resolve(kind === 'envelope' ? response({}) : response({}, false, kind === '404' ? 404 : 503));
    });
    expect(screen.getByLabelText('Historial completo')).toHaveValue('fictional history only');
    expect(fetch.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(kind === 'auth' ? 1 : 0);
    if (kind === 'transport') {
      expect(rawButton()).toBeDisabled();
      expect(screen.getByRole('alert')).toHaveTextContent('No se pudo contactar');
      fireEvent.click(rawButton());
      expect(fetch.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(0);
      nonce = 'fresh';
      await userEvent.click(screen.getByRole('button', { name: 'Reconectar' }));
      await waitFor(() => expect(rawButton()).toBeEnabled());
      expect(fetch.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(0);
      await userEvent.click(rawButton());
      await screen.findByText('fresh fictional result');
      expect(fetch.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(1);
      expect(fetch.mock.calls.find(([url]) => url === '/api/raw-draft')[1].headers['X-CSRF-Token']).toBe('fresh');
    } else {
      expect(rawButton()).toBeEnabled();
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    }
  });
});

describe('remembered library presentation', () => {
  it.each([404, 'saved', 'unsaved'])('shows only verified session and persistence state for %s', async mode => {
    const fetch = vi.fn(async url => {
      if (url === '/api/bootstrap') return response(bootstrap);
      if (url === '/api/auth/status') return response({ connected: true, empty: false, count: 2, revision: 1 });
      if (url === '/api/auth/persistence') return mode === 404 ? response({}, false, 404)
        : response({ enabled: true, remembered: mode === 'saved', problem: mode === 'unsaved' });
      throw new Error('Unexpected fictional request');
    });
    vi.stubGlobal('fetch', fetch);
    render(<App />);
    expect(screen.getByText('Sin verificar')).toBeVisible();
    await userEvent.click(screen.getByText('Biblioteca'));
    expect(await screen.findByText('2 criterios disponibles')).toBeVisible();
    expect(screen.queryByLabelText('Email editorial')).not.toBeInTheDocument();
    expect(await screen.findByText(mode === 404 ? /Persistencia no activada/ : mode === 'saved' ? /Sesión recordada/ : /No se pudo guardar/)).toBeVisible();
    expect(screen.getByText('2 disponibles')).toBeVisible();
    expect(fetch.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(0);
  });
});

describe('workspace presentation contract', () => {
  it('mobile navigation traps focus, closes with Escape and preserves input without POST', async () => {
    vi.stubGlobal('innerWidth', 390);
    const fetch = vi.fn(async () => response(bootstrap)); vi.stubGlobal('fetch', fetch);
    render(<App />); paste();
    const toggle = screen.getByRole('button', { name: 'Alternar navegación' });
    await userEvent.click(toggle);
    expect(screen.getByRole('dialog')).toHaveTextContent('Navegación');
    await userEvent.tab();
    expect(screen.getByRole('dialog')).toContainElement(document.activeElement);
    expect(document.head.querySelector('style')).toBeNull();
    await userEvent.keyboard('{Escape}');
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(toggle).toHaveFocus();
    expect(screen.getByLabelText('Historial completo')).toHaveValue('fictional history only');
    expect(fetch.mock.calls.filter(([, o]) => o?.method === 'POST')).toHaveLength(0);
  });
  it('closing the library clears credentials without remounting the conversation', async () => {
    const fetch = vi.fn(async url => response(url === '/api/bootstrap' ? bootstrap : libraryStatus));
    vi.stubGlobal('fetch', fetch);
    render(<App />); paste();
    await userEvent.click(screen.getByText('Biblioteca'));
    const input = screen.getByLabelText('Historial completo');
    fireEvent.change(screen.getByLabelText('Email editorial'), { target: { value: 'fixture@example.invalid' } });
    fireEvent.change(screen.getByLabelText('Contraseña editorial'), { target: { value: 'fictional-only' } });
    await userEvent.click(screen.getByRole('button', { name: 'Cerrar biblioteca' }));
    expect(screen.getByLabelText('Historial completo')).toBe(input);
    await userEvent.click(screen.getByText('Biblioteca'));
    expect(screen.getByLabelText('Email editorial')).toHaveValue('');
    expect(screen.getByLabelText('Contraseña editorial')).toHaveValue('');
    expect(screen.queryByText(/criterios disponibles$/)).not.toBeInTheDocument();
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
    expect(fetch.mock.calls.filter(([, o]) => o?.method === 'POST')).toHaveLength(0);
  });
  it('collapses navigation without storage, preserves raw input through the secondary library panel', async () => {
    const fetch = vi.fn(async url => response(url === '/api/bootstrap' ? bootstrap : { connected: true, empty: false, count: 2, revision: 1 }));
    vi.stubGlobal('fetch', fetch);
    const storage = vi.spyOn(Storage.prototype, 'setItem');
    const cookie = vi.spyOn(document, 'cookie', 'set');
    render(<App />); paste();
    await waitFor(() => expect(rawButton()).toBeEnabled());
    await userEvent.click(screen.getByRole('button', { name: 'Alternar navegación' }));
    expect(document.querySelector('[data-slot="sidebar"]')).toHaveAttribute('data-state', 'collapsed');
    await userEvent.click(screen.getByRole('button', { name: 'Alternar navegación' }));
    await userEvent.click(screen.getByText('Biblioteca'));
    expect(await screen.findByText('2 criterios disponibles')).toBeVisible();
    await userEvent.click(screen.getByText('Criterios y fuentes'));
    expect(screen.getByText(/Seleccionar o aprobar criterios no está disponible/)).toBeVisible();
    expect(screen.queryByLabelText('Email editorial')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Historial completo')).toHaveValue('fictional history only');
    await userEvent.click(screen.getByText('Biblioteca'));
    expect(screen.getByLabelText('Historial completo')).toHaveValue('fictional history only');
    expect(fetch.mock.calls.filter(([, o]) => o?.method === 'POST')).toHaveLength(0);
    expect(storage).not.toHaveBeenCalled(); storage.mockRestore();
    expect(cookie).not.toHaveBeenCalled(); cookie.mockRestore();
  });
});

describe('verifier recovery regressions', () => {
  it.each(['TypeError', 'AbortError', 'SyntaxError'])('classifies body-read %s after headers without replay', async kind => {
    const connected = { connected: true, empty: false, count: 2, revision: 1 };
    const fetch = vi.fn(url => {
      if (url === '/api/bootstrap') return Promise.resolve(response(bootstrap));
      if (url === '/api/auth/status') return Promise.resolve(response(connected));
      if (url === '/api/auth/persistence') return Promise.resolve(response({}, false, 404));
      return Promise.resolve({ ok: true, json: async () => {
        if (kind === 'AbortError') throw new DOMException('secret sentinel', 'AbortError');
        throw kind === 'TypeError' ? new TypeError('secret sentinel') : new SyntaxError('secret sentinel');
      } });
    });
    vi.stubGlobal('fetch', fetch);
    render(<App />); paste();
    await waitFor(() => expect(rawButton()).toBeEnabled());
    await userEvent.click(screen.getByText('Biblioteca'));
    await screen.findByText(/Biblioteca conectada\./);
    await userEvent.click(rawButton());
    if (kind === 'SyntaxError') {
      expect(await screen.findByRole('alert')).toHaveTextContent('formato esperado');
      expect(rawButton()).toBeEnabled();
      expect(screen.getByText(/Biblioteca conectada\./)).toBeVisible();
    } else {
      await waitFor(() => expect(rawButton()).toBeDisabled());
      expect(screen.queryByText(/Biblioteca conectada\./)).not.toBeInTheDocument();
      expect(screen.getByRole('alert')).toHaveTextContent('No se pudo contactar');
    }
    expect(screen.getByLabelText('Historial completo')).toHaveValue('fictional history only');
    expect(document.body).not.toHaveTextContent('secret sentinel');
    expect(fetch.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(1);
  });

  it.each([['Conectar', false], ['Conectar', true], ['Desconectar', false], ['Desconectar', true]])('discards status before %s settlement, remount=%s', async (operation, remount) => {
    const login = deferred(), oldStatus = deferred();
    let reads = 0, settled = false;
    const connected = { connected: true, empty: false, count: 2, revision: 1 };
    const initial = operation === 'Conectar' ? libraryStatus : connected;
    const final = operation === 'Conectar' ? connected : libraryStatus;
    const fetch = vi.fn(url => {
      if (url === '/api/bootstrap') return Promise.resolve(response(bootstrap));
      if (url === '/api/auth/login' || url === '/api/auth/logout') return login.promise;
      if (url === '/api/auth/status') {
        reads += 1;
        if (reads === 2) return oldStatus.promise;
        return Promise.resolve(response(settled ? final : initial));
      }
      return Promise.resolve(response(rawEnvelope('fictional fresh')));
    });
    vi.stubGlobal('fetch', fetch);
    render(<App />); paste();
    await waitFor(() => expect(rawButton()).toBeEnabled());
    await userEvent.click(screen.getByText('Biblioteca'));
    await screen.findByText(initial.connected ? /Biblioteca conectada\./ : 'Biblioteca desconectada.');
    await beginAuth(operation);
    if (remount) {
      await userEvent.click(screen.getByRole('tab', { name: 'Revisión avanzada' }));
      await userEvent.click(screen.getByRole('tab', { name: 'Responder conversación' }));
      paste();
    } else await userEvent.click(screen.getByText('Biblioteca'));
    await userEvent.click(screen.getByText('Biblioteca'));
    expect(rawButton()).toBeDisabled();
    settled = true;
    await act(async () => login.resolve(response(final)));
    await act(async () => oldStatus.resolve(response(initial)));
    expect(await screen.findByText(final.connected ? /Biblioteca conectada\./ : 'Biblioteca desconectada.')).toBeVisible();
    expect(rawButton()).toBeEnabled();
    expect(fetch.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(1);
  });

  it.each(['resolve', 'reject'])('reloads comparator context for the recovered epoch despite old %s without a POST', async outcome => {
    const old = deferred();
    let contexts = 0;
    const fetch = vi.fn(url => {
      if (url === '/api/bootstrap') return Promise.resolve(response({ ...bootstrap, csrf_token: 'fresh' }));
      if (url === '/api/auth/status') return Promise.resolve(response(libraryStatus));
      if (url === '/api/context') return ++contexts === 1 ? old.promise : Promise.resolve(response(context));
      throw new Error('unexpected POST');
    });
    vi.stubGlobal('fetch', fetch);
    render(<App />);
    await waitFor(() => expect(screen.getByRole('button', { name: 'Reconectar' })).toBeEnabled());
    await userEvent.click(screen.getByRole('tab', { name: 'Comparador sintético' }));
    await waitFor(() => expect(contexts).toBe(1));
    await userEvent.click(screen.getByRole('button', { name: 'Reconectar' }));
    await act(async () => outcome === 'resolve' ? old.resolve(response({ ...context, messages: [{ role: 'user', text: 'obsolete context' }] })) : old.reject(new TypeError('secret sentinel')));
    expect(await screen.findByText('las dominadas')).toBeVisible();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(screen.queryByText('obsolete context')).not.toBeInTheDocument();
    expect(contexts).toBe(2);
    expect(screen.getByRole('tab', { name: 'Comparador sintético' })).toHaveAttribute('aria-selected', 'true');
    expect(fetch.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(0);
  });
});

describe('connection recovery', () => {
  it.each(['http403', 'http502', 'json', 'envelope'])('distinguishes %s from transport failure without losing the nonce', async kind => {
    const fetch = vi.fn(url => {
      if (url === '/api/bootstrap') return Promise.resolve(response(bootstrap));
      if (kind === 'json') return Promise.resolve({ ok: true, json: async () => { throw new Error('secret sentinel'); } });
      if (kind === 'envelope') return Promise.resolve(response({ secret: 'secret sentinel' }));
      return Promise.resolve(response({}, false, kind === 'http403' ? 403 : 502));
    });
    vi.stubGlobal('fetch', fetch);
    render(<App />); paste();
    await waitFor(() => expect(rawButton()).toBeEnabled());
    await userEvent.click(rawButton());
    expect(await screen.findByRole('alert')).toHaveTextContent(kind.startsWith('http') ? `HTTP ${kind.slice(4)}` : 'formato esperado');
    expect(screen.getByRole('alert')).not.toHaveTextContent(/secret sentinel|CSRF|modelo|No se pudo contactar/);
    expect(rawButton()).toBeEnabled();
    expect(fetch.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(1);
  });

  it.each(['success', 'failure'])('suppresses late %s after explicit reconnect while keeping history', async outcome => {
    const old = deferred();
    let nonce = 'first';
    const fetch = vi.fn(url => {
      if (url === '/api/bootstrap') return Promise.resolve(response({ ...bootstrap, csrf_token: nonce }));
      if (url === '/api/auth/status') return Promise.resolve(response(libraryStatus));
      return old.promise;
    });
    vi.stubGlobal('fetch', fetch);
    render(<App />); paste();
    await waitFor(() => expect(rawButton()).toBeEnabled());
    await userEvent.click(rawButton());
    nonce = 'fresh';
    await userEvent.click(screen.getByRole('button', { name: 'Reconectar' }));
    await act(async () => outcome === 'success' ? old.resolve(response(rawEnvelope('obsolete result'))) : old.reject(new Error('secret sentinel')));
    expect(screen.queryByText('obsolete result')).not.toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Historial completo')).toHaveValue('fictional history only');
    expect(rawButton()).toBeEnabled();
    expect(fetch.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(1);
  });

  it('invalidates cached library connection and accepts current status without replaying credentials', async () => {
    let connected = true;
    const fetch = vi.fn(url => {
      if (url === '/api/bootstrap') return Promise.resolve(response(bootstrap));
      if (url === '/api/auth/status') return Promise.resolve(response({ connected, empty: false, count: connected ? 2 : 0, revision: 0 }));
      if (url === '/api/auth/persistence') return Promise.resolve(response({}, false, 404));
      return Promise.reject(new Error('secret sentinel'));
    });
    vi.stubGlobal('fetch', fetch);
    render(<App />); paste();
    await waitFor(() => expect(rawButton()).toBeEnabled());
    await userEvent.click(screen.getByText('Biblioteca'));
    expect(await screen.findByText(/Biblioteca conectada\./)).toBeVisible();
    expect(screen.queryByLabelText('Contraseña editorial')).not.toBeInTheDocument();
    await userEvent.click(rawButton());
    await waitFor(() => expect(rawButton()).toBeDisabled());
    expect(screen.queryByText(/Biblioteca conectada\./)).not.toBeInTheDocument();
    expect(screen.getByLabelText('Contraseña editorial')).toHaveValue('');
    connected = false;
    await userEvent.click(screen.getByRole('button', { name: 'Reconectar' }));
    expect(await screen.findByText('Biblioteca desconectada.')).toBeVisible();
    expect(fetch.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(1);
  });

  it('validates bootstrap identity and never waits for status before allowing baseline', async () => {
    let valid = false;
    const pending = deferred();
    const fetch = vi.fn(url => url === '/api/bootstrap'
      ? Promise.resolve(response({ ...bootstrap, app: valid ? 'tato-local' : 'foreign' })) : pending.promise);
    vi.stubGlobal('fetch', fetch);
    render(<App />); paste();
    expect(await screen.findByRole('alert')).toHaveTextContent('formato esperado');
    expect(rawButton()).toBeDisabled();
    expect(fetch).toHaveBeenCalledTimes(1);
    valid = true;
    await userEvent.click(screen.getByRole('button', { name: 'Reconectar' }));
    await waitFor(() => expect(rawButton()).toBeEnabled());
    expect(fetch.mock.calls.map(([url]) => url)).toEqual(['/api/bootstrap', '/api/bootstrap', '/api/auth/status']);
    await act(async () => pending.resolve(response(libraryStatus)));
  });

  it('comparator uses fresh parent nonce rather than cached context nonce', async () => {
    let nonce = 'first';
    const fetch = vi.fn(url => {
      if (url === '/api/bootstrap') return Promise.resolve(response({ ...bootstrap, csrf_token: nonce }));
      if (url === '/api/context') return Promise.resolve(response(context));
      if (url === '/api/auth/status') return Promise.resolve(response(libraryStatus));
      return Promise.resolve(response(pair()));
    });
    vi.stubGlobal('fetch', fetch);
    render(<App />);
    await userEvent.click(screen.getByRole('tab', { name: 'Comparador sintético' }));
    await screen.findByText('las dominadas');
    nonce = 'fresh';
    await userEvent.click(screen.getByRole('button', { name: 'Reconectar' }));
    await userEvent.click(screen.getByRole('button', { name: 'Ver demo simulada' }));
    expect(fetch.mock.calls.filter(([, options]) => options?.method === 'POST')[0][1].headers['X-CSRF-Token']).toBe('fresh');
  });

  it('preserves paste, reconnects with a fresh nonce and never replays generation', async () => {
    let nonce = 'old';
    const fetch = vi.fn(url => {
      if (url === '/api/bootstrap') return Promise.resolve(response({ ...bootstrap, csrf_token: nonce }));
      if (url === '/api/auth/status') return Promise.resolve(response(libraryStatus));
      return Promise.reject(new TypeError('synthetic transport failure'));
    });
    vi.stubGlobal('fetch', fetch);
    render(<App />);
    paste();
    await waitFor(() => expect(rawButton()).toBeEnabled());
    await userEvent.click(rawButton());
    await waitFor(() => expect(rawButton()).toBeDisabled());
    expect(screen.getByLabelText('Historial completo')).toHaveValue('fictional history only');
    nonce = 'fresh';
    await userEvent.click(screen.getByRole('button', { name: 'Reconectar' }));
    await waitFor(() => expect(rawButton()).toBeEnabled());
    expect(fetch.mock.calls.filter(([, options]) => options?.method === 'POST')).toHaveLength(1);
    await userEvent.click(rawButton());
    expect(fetch.mock.calls.filter(([, options]) => options?.method === 'POST')[1][1].headers['X-CSRF-Token']).toBe('fresh');
  });
});

describe('explicit auth transition barrier', () => {
  it.each(['Conectar', 'Desconectar'])('%s pending blocks generation and settles to one fresh call', async operation => {
    const { auth, old, rawCalls } = await authFixture();
    await beginAuth(operation);
    fireEvent.click(rawButton());
    expect(rawCalls()).toHaveLength(0);
    expect(rawButton()).toBeDisabled();
    await act(async () => auth.resolve(response(libraryStatus)));
    expect(screen.getByLabelText('Historial completo')).toHaveValue('fictional history only');
    expect(rawButton()).toBeEnabled();
    await userEvent.click(rawButton());
    await act(async () => old.resolve(response(rawEnvelope('fresh after transition'))));
    expect(screen.getByText('fresh after transition')).toBeVisible();
    expect(rawCalls()).toHaveLength(1);
  });

  it.each(['success', 'failure'])('closing settings preserves pending barrier through %s', async outcome => {
    const { auth, rawCalls } = await authFixture();
    await beginAuth('Desconectar');
    await userEvent.click(screen.getByText('Biblioteca'));
    fireEvent.click(rawButton());
    expect(rawCalls()).toHaveLength(0);
    expect(rawButton()).toBeDisabled();
    await act(async () => outcome === 'failure' ? auth.reject(new Error('fictional')) : auth.resolve(response(libraryStatus)));
    if (outcome === 'failure') {
      expect(rawButton()).toBeDisabled();
      expect(screen.getByRole('alert')).toHaveTextContent('No se pudo contactar');
      await userEvent.click(screen.getByRole('button', { name: 'Reconectar' }));
      await waitFor(() => expect(rawButton()).toBeEnabled());
    } else {
      expect(rawButton()).toBeEnabled();
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    }
  });

  it.each(['success', 'failure'])('settles after settings unmount/navigation on %s', async outcome => {
    const { auth, old, rawCalls } = await authFixture();
    await beginAuth('Desconectar');
    await userEvent.click(screen.getByRole('tab', { name: 'Revisión avanzada' }));
    await userEvent.click(screen.getByRole('tab', { name: 'Responder conversación' }));
    paste();
    fireEvent.click(rawButton());
    expect(rawCalls()).toHaveLength(0);
    expect(rawButton()).toBeDisabled();
    await act(async () => outcome === 'failure' ? auth.reject(new Error('fictional')) : auth.resolve(response(libraryStatus)));
    if (outcome === 'failure') {
      expect(rawButton()).toBeDisabled();
      await userEvent.click(screen.getByRole('button', { name: 'Reconectar' }));
      await waitFor(() => expect(rawButton()).toBeEnabled());
    }
    expect(rawButton()).toBeEnabled();
    await userEvent.click(rawButton());
    await act(async () => old.resolve(response(rawEnvelope('fresh after navigation'))));
    expect(screen.getByText('fresh after navigation')).toBeVisible();
    expect(rawCalls()).toHaveLength(1);
  });

  it.each(['success', 'error', '409'])('discards old %s after auth settles, then allows fresh generation', async outcome => {
    const { auth, old, fetch, rawCalls } = await authFixture();
    await userEvent.click(rawButton());
    await beginAuth('Desconectar');
    await act(async () => auth.resolve(response(libraryStatus)));
    await act(async () => {
      if (outcome === 'error') old.reject(new Error('fictional'));
      else old.resolve(outcome === '409' ? response({}, false, 409) : response(rawEnvelope('obsolete draft')));
    });
    expect(screen.queryByText('obsolete draft')).not.toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    fetch.mockResolvedValueOnce(response(rawEnvelope('fresh replacement')));
    await userEvent.click(rawButton());
    expect(await screen.findByText('fresh replacement')).toBeVisible();
    expect(rawCalls()).toHaveLength(2);
  });

  it.each(['login-first', 'logout-first'])('keeps overlapping operations gated until both settle: %s', async order => {
    const { auth: login, fetch, rawCalls } = await authFixture();
    await beginAuth('Conectar');
    const logout = deferred();
    fetch.mockImplementationOnce(() => logout.promise);
    await beginAuth('Desconectar');
    const first = order === 'login-first' ? login : logout;
    const last = order === 'login-first' ? logout : login;
    await act(async () => first.resolve(response(libraryStatus)));
    expect(rawButton()).toBeDisabled();
    fireEvent.click(rawButton());
    expect(rawCalls()).toHaveLength(0);
    await act(async () => last.resolve(response(libraryStatus)));
    expect(rawButton()).toBeEnabled();
    expect(screen.getByText('Biblioteca desconectada.')).toBeVisible();
  });

  it.each(['draft', 'error'])('clears existing %s on start and leaves no result on HTTP rejection', async kind => {
    const { auth, old } = await authFixture();
    await userEvent.click(rawButton());
    await act(async () => kind === 'error' ? old.resolve(response({}, false, 502)) : old.resolve(response(rawEnvelope('old visible draft'))));
    if (kind === 'error') expect(screen.getByRole('alert')).toBeVisible();
    else expect(screen.getByText('old visible draft')).toBeVisible();
    await beginAuth('Desconectar');
    expect(screen.queryByText('old visible draft')).not.toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    await act(async () => auth.resolve(response({}, false, 401)));
    expect(screen.queryByText('old visible draft')).not.toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Historial completo')).toHaveValue('fictional history only');
    expect(rawButton()).toBeEnabled();
  });

  it('status-only pending GET does not block baseline', async () => {
    const { fetch, old, rawCalls } = await authFixture();
    const status = deferred();
    fetch.mockImplementation(url => {
      if (url === '/api/auth/status') return status.promise;
      if (url === '/api/auth/persistence') return Promise.resolve(response({}, false, 404));
      if (url === '/api/raw-draft') return old.promise;
      throw new Error('Unexpected fictional request');
    });
    await userEvent.click(screen.getByRole('button', { name: 'Consultar estado' }));
    expect(rawButton()).toBeEnabled();
    await userEvent.click(rawButton());
    await act(async () => old.resolve(response(rawEnvelope('baseline'))));
    expect(screen.getByText('baseline')).toBeVisible();
    expect(rawCalls()).toHaveLength(1);
    await act(async () => status.reject(new Error('fictional')));
    expect(rawButton()).toBeDisabled();
    expect(screen.queryByText('baseline')).not.toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('No se pudo contactar');
  });

  it.each(['success', 'failure'])('parent unmount is safe with late auth %s', async outcome => {
    const { auth, view, rawCalls } = await authFixture();
    await beginAuth('Desconectar');
    view.unmount();
    await act(async () => outcome === 'failure' ? auth.reject(new Error('fictional')) : auth.resolve(response(libraryStatus)));
    expect(screen.queryByRole('main')).not.toBeInTheDocument();
    expect(rawCalls()).toHaveLength(0);
  });
});

describe('primera pantalla local', () => {
  it('opens a focused primary shell without laboratory branding or a technical footer', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(bootstrap)));
    render(<App />);
    expect(screen.getByRole('heading', { name: 'Responder conversación', exact: true })).toBeVisible();
    expect(screen.getByRole('main').closest('[data-workspace="raw"]')).not.toBeNull();
    expect(screen.getByText('Pegá el historial. Recibí el próximo DM.')).toBeVisible();
    expect(screen.queryByText(/EXPERIMENTO LOCAL|Laboratorio editorial|Revisión humana/)).not.toBeInTheDocument();
    expect(screen.queryByRole('contentinfo')).not.toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'Revisión avanzada' })).toBeVisible();
    expect(screen.getByRole('tab', { name: 'Comparador sintético' })).toBeVisible();
    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalledTimes(1));
  });
  it.each(['resolve', 'reject', 'conflict'])('ignores stale synthetic %s after navigating away and back, then accepts a fresh pair', async outcome => {
    let finish, reject;
    const fetch = vi.fn().mockResolvedValueOnce(response(context))
      .mockImplementationOnce(() => new Promise((resolve, fail) => { finish = resolve; reject = fail; }))
      .mockResolvedValueOnce(response(pair()));
    vi.stubGlobal('fetch', fetch);
    await openApp();
    await userEvent.click(screen.getByRole('button', { name: 'Ver demo simulada' }));
    await userEvent.click(screen.getByRole('tab', { name: 'Responder conversación' }));
    await userEvent.click(screen.getByRole('tab', { name: 'Comparador sintético' }));
    await act(async () => {
      if (outcome === 'reject') reject(new Error('fictional failure'));
      else finish(outcome === 'conflict' ? response({}, false, 409) : response(pair()));
    });
    expect(screen.queryByText('primer borrador sintético?')).not.toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Ver demo simulada' }));
    await screen.findByText('segundo borrador sintético?');
    expect(fetch).toHaveBeenCalledTimes(3);
  });
  it('abre historial real sin inferencia y cambiar de modo borra el texto', async () => {
    const fetch = vi.fn(url => Promise.resolve(response(url === '/api/bootstrap' ? bootstrap : context)));
    vi.stubGlobal('fetch', fetch);
    render(<App />);
    await userEvent.type(screen.getByRole('textbox'), 'Prospecto: hola ficticio');
    await userEvent.click(screen.getByRole('tab', { name: 'Comparador sintético' }));
    await screen.findByText('las dominadas');
    await userEvent.click(screen.getByRole('tab', { name: 'Responder conversación' }));
    expect(screen.getByRole('textbox')).toHaveValue('');
    expect(fetch).toHaveBeenCalledTimes(2);
  });
  it('carga solo contexto y no ofrece entrada arbitraria', async () => {
    const fetch = vi.fn().mockResolvedValue(response(context));
    vi.stubGlobal('fetch', fetch);
    await openApp();
    expect(screen.getByRole('heading', { name: 'Tato · Laboratorio editorial' })).toBeVisible();
    expect(screen.getByRole('main').closest('[data-workspace="raw"]')).toBeNull();
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch.mock.calls[0][0]).toBe('/api/context');
    expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
    expect(screen.getByText(/no son puntajes de calidad/i)).toBeVisible();
  });

  it('muestra demo manual, sin consentimiento ni llamada real, y limpia sin red', async () => {
    const fetch = vi.fn().mockResolvedValueOnce(response(context)).mockResolvedValueOnce(response(pair()));
    vi.stubGlobal('fetch', fetch);
    await openApp();
    await userEvent.click(screen.getByRole('button', { name: 'Ver demo simulada' }));
    await screen.findByText('primer borrador sintético?');
    expect(screen.getByText('Demo simulada · borradores manuales')).toBeVisible();
    expect(fetch.mock.calls[1][0]).toBe('/api/demo');
    await userEvent.click(screen.getByRole('button', { name: 'Limpiar resultados' }));
    expect(screen.queryByText('primer borrador sintético?')).not.toBeInTheDocument();
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it.each(['Cancelar', 'Escape'])('actualiza el estado tras demo, apertura y %s sin generar', async cancel => {
    const fetch = vi.fn().mockResolvedValueOnce(response(context)).mockResolvedValueOnce(response(pair()));
    vi.stubGlobal('fetch', fetch);
    await openApp();
    await userEvent.click(screen.getByRole('button', { name: 'Ver demo simulada' }));
    await screen.findByText('primer borrador sintético?');
    expect(screen.getByRole('status')).toHaveTextContent('Par completo disponible');
    await userEvent.click(screen.getByRole('button', { name: 'Generar con Codex Pro' }));
    expect(screen.queryByText('primer borrador sintético?')).not.toBeInTheDocument();
    expect(screen.queryByText('segundo borrador sintético?')).not.toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('Sin borradores. Confirmación pendiente; no se inició una nueva llamada.');
    if (cancel === 'Escape') await userEvent.keyboard('{Escape}');
    else await userEvent.click(screen.getByRole('button', { name: 'Cancelar' }));
    expect(screen.getByRole('status')).toHaveTextContent('Confirmación cancelada. Sin borradores; no se inició una nueva llamada.');
    expect(screen.queryByText('primer borrador sintético?')).not.toBeInTheDocument();
    expect(screen.queryByText('segundo borrador sintético?')).not.toBeInTheDocument();
    expect(fetch.mock.calls.map(([url]) => url)).toEqual(['/api/context', '/api/demo']);
  });

  it('exige confirmación nueva y deshabilita duplicados durante las dos llamadas', async () => {
    let finish;
    const fetch = vi.fn().mockResolvedValueOnce(response(context))
      .mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
    vi.stubGlobal('fetch', fetch);
    await openApp();
    await userEvent.click(screen.getByRole('button', { name: 'Generar con Codex Pro' }));
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/dos llamadas a Codex/i)).toBeVisible();
    expect(screen.getByText(/OpenAI/)).toBeVisible();
    expect(screen.getByRole('button', { name: 'Confirmar dos llamadas' })).toBeDisabled();
    await userEvent.click(screen.getByRole('checkbox'));
    await userEvent.click(screen.getByRole('button', { name: 'Confirmar dos llamadas' }));
    expect(screen.getByRole('button', { name: 'Ver demo simulada' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Generar con Codex Pro' })).toBeDisabled();
    expect(screen.getByText(/Generando el par completo/)).toBeVisible();
    expect(fetch.mock.calls[1][0]).toBe('/api/generate');
    const options = fetch.mock.calls[1][1];
    expect(JSON.parse(options.body)).toEqual({ consent: true });
    expect(options.headers['X-CSRF-Token']).toBe(context.csrf_token);
    finish(response(pair('codex')));
    await screen.findByText('segundo borrador sintético?');
    expect(screen.getByText('Codex · caso sintético')).toBeVisible();
    expect(screen.getByRole('button', { name: 'Generar con Codex Pro' })).toBeEnabled();
  });

  it('cancelar no genera y un fallo limpia resultados sin detalles crudos ni reintento', async () => {
    const fetch = vi.fn().mockResolvedValueOnce(response(context))
      .mockResolvedValueOnce(response(pair()))
      .mockResolvedValueOnce(response({ error: 'RAW-SYNTHETIC', drafts: { current: 'partial' } }, false, 502));
    vi.stubGlobal('fetch', fetch);
    await openApp();
    await userEvent.click(screen.getByRole('button', { name: 'Generar con Codex Pro' }));
    await userEvent.click(screen.getByRole('button', { name: 'Cancelar' }));
    expect(fetch).toHaveBeenCalledTimes(1);
    await userEvent.click(screen.getByRole('button', { name: 'Ver demo simulada' }));
    await screen.findByText('primer borrador sintético?');
    await userEvent.click(screen.getByRole('button', { name: 'Ver demo simulada' }));
    await screen.findByRole('alert');
    expect(screen.queryByText('primer borrador sintético?')).not.toBeInTheDocument();
    expect(screen.queryByText(/RAW-SYNTHETIC|partial/)).not.toBeInTheDocument();
    expect(fetch).toHaveBeenCalledTimes(3);
  });

  it('rechaza una respuesta incompleta aunque HTTP indique éxito', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValueOnce(response(context))
      .mockResolvedValueOnce(response({ ...pair(), drafts: { current: 'partial' } })));
    await openApp();
    await userEvent.click(screen.getByRole('button', { name: 'Ver demo simulada' }));
    await screen.findByRole('alert');
    expect(screen.queryByText('partial')).not.toBeInTheDocument();
  });

  it('borra resultados al iniciar otro pedido y muestra conflicto sin reintentar', async () => {
    let finish;
    const fetch = vi.fn().mockResolvedValueOnce(response(context)).mockResolvedValueOnce(response(pair()))
      .mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
    vi.stubGlobal('fetch', fetch);
    await openApp();
    await userEvent.click(screen.getByRole('button', { name: 'Ver demo simulada' }));
    await screen.findByText('primer borrador sintético?');
    await userEvent.click(screen.getByRole('button', { name: 'Ver demo simulada' }));
    expect(screen.queryByText('primer borrador sintético?')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Limpiar resultados' })).toBeDisabled();
    finish(response({}, false, 409));
    expect(await screen.findByRole('alert')).toHaveTextContent('Ya hay una comparación en curso');
    expect(fetch).toHaveBeenCalledTimes(3);
  });

  it('Escape cancela, devuelve foco y cada apertura exige otro consentimiento', async () => {
    const fetch = vi.fn().mockResolvedValueOnce(response(context));
    vi.stubGlobal('fetch', fetch);
    await openApp();
    const generate = screen.getByRole('button', { name: 'Generar con Codex Pro' });
    await userEvent.click(generate);
    expect(screen.getByRole('checkbox')).toHaveFocus();
    await userEvent.click(screen.getByRole('checkbox'));
    await userEvent.keyboard('{Escape}');
    expect(generate).toHaveFocus();
    await userEvent.click(generate);
    expect(screen.getByRole('checkbox')).not.toBeChecked();
    expect(screen.getByRole('button', { name: 'Confirmar dos llamadas' })).toBeDisabled();
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it('fallo de contexto deja acciones deshabilitadas y no reintenta', async () => {
    const fetch = vi.fn(url => url === '/api/bootstrap' ? Promise.resolve(response(bootstrap))
      : Promise.reject(new Error('RAW-SYNTHETIC')));
    vi.stubGlobal('fetch', fetch);
    render(<App />);
    await userEvent.click(screen.getByRole('tab', { name: 'Comparador sintético' }));
    await waitFor(() => expect(screen.getAllByRole('alert').length).toBeGreaterThan(0));
    expect(screen.getByRole('button', { name: 'Ver demo simulada' })).toBeDisabled();
    expect(screen.queryByText('RAW-SYNTHETIC')).not.toBeInTheDocument();
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it.each(['resolve', 'reject', 'conflict'])('raw navigation discards stale %s without synthetic dependency', async outcome => {
    let finish, reject;
    const fetch = vi.fn().mockResolvedValueOnce(response(bootstrap))
      .mockImplementationOnce(() => new Promise((resolve, fail) => { finish = resolve; reject = fail; }));
    vi.stubGlobal('fetch', fetch);
    render(<App />);
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'texto totalmente inventado' } });
    await waitFor(() => expect(rawButton()).toBeEnabled());
    await userEvent.click(rawButton());
    await userEvent.click(screen.getByRole('tab', { name: 'Revisión avanzada' }));
    await userEvent.click(screen.getByRole('tab', { name: 'Responder conversación' }));
    await act(async () => {
      if (outcome === 'reject') reject(new Error('invented diagnostic'));
      else finish(outcome === 'conflict' ? response({}, false, 409) : response({ result: { type: 'dm', text: 'resultado ficticio obsoleto' }, retrieval: { status: 'off', count: 0 }, revision: 0 }));
    });
    expect(screen.getByRole('textbox')).toHaveValue('');
    expect(screen.queryByText('resultado ficticio obsoleto')).not.toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(fetch.mock.calls.map(([url]) => url)).toEqual(['/api/bootstrap', '/api/raw-draft']);
  });

  it('opening optional library settings preserves history and never generates', async () => {
    const fetch = vi.fn(async url => response(url === '/api/bootstrap' ? bootstrap
      : { connected: false, empty: false, count: 0, revision: 0 }));
    vi.stubGlobal('fetch', fetch);
    render(<App />);
    await userEvent.type(screen.getByRole('textbox', { name: 'Historial completo' }), 'fictional unchanged history');
    await userEvent.click(screen.getByText('Biblioteca'));
    expect(await screen.findByText('Biblioteca desconectada.')).toBeVisible();
    expect(screen.getByRole('textbox', { name: 'Historial completo' })).toHaveValue('fictional unchanged history');
    expect(fetch.mock.calls.map(([url]) => url)).toEqual(['/api/bootstrap', '/api/auth/persistence', '/api/auth/status']);
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('primary bootstrap works when synthetic context fails and leaves advanced review optional', async () => {
    const fetch = vi.fn(async url => url === '/api/bootstrap' ? response(bootstrap) : response({}, false, 503));
    vi.stubGlobal('fetch', fetch);
    render(<App />);
    await userEvent.type(screen.getByRole('textbox'), 'historial totalmente inventado');
    expect(rawButton()).toBeEnabled();
    expect(fetch.mock.calls.map(([url]) => url)).toEqual(['/api/bootstrap']);
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('tab', { name: 'Comparador sintético' }));
    await screen.findByRole('alert');
    await userEvent.click(screen.getByRole('tab', { name: 'Responder conversación' }));
    await userEvent.type(screen.getByRole('textbox'), 'otro historial inventado');
    expect(rawButton()).toBeEnabled();
    await userEvent.click(screen.getByRole('tab', { name: 'Revisión avanzada' }));
    expect(screen.getByRole('main').closest('[data-workspace="raw"]')).toBeNull();
    expect(screen.getByRole('heading', { name: 'Revisión avanzada', exact: true })).toBeVisible();
    expect(screen.getByRole('button', { name: 'Revisar conversación' })).toBeVisible();
  });
});
