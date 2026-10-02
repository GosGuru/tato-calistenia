import { afterEach, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import AppAuth, { localRequest, connectionMessage } from './AppAuth.jsx';

it.each(['timeout', 'unavailable', 'rejected', 'nonzero', 'invalid', 'internal'])('uses only closed backend diagnostic %s, never response content', async outcome => {
  const headers = new Headers({ 'X-Tato-Diagnostics': '1', 'X-Tato-Exec-Outcome': outcome });
  const json = vi.fn().mockRejectedValue(new Error('secret sentinel'));
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 502, headers, json }));
  let failure;
  try { await localRequest('/api/raw-draft'); } catch (error) { failure = error; }
  expect(failure.category).toBe('http');
  expect(failure.diagnostic).toBe(outcome);
  expect(connectionMessage(failure)).not.toMatch(/secret sentinel|No se pudo contactar/);
  expect(json).not.toHaveBeenCalled();
});

it('does not classify unknown diagnostic text or an arbitrary 403 as expired CSRF', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 403,
    headers: new Headers({ 'X-Tato-Diagnostics': '1', 'X-Tato-Exec-Outcome': 'secret sentinel' }) }));
  let failure;
  try { await localRequest('/api/raw-draft'); } catch (error) { failure = error; }
  expect(failure.diagnostic).toBeUndefined();
  expect(connectionMessage(failure)).toContain('HTTP 403');
  expect(connectionMessage(failure)).not.toMatch(/secret sentinel|CSRF|vencido/);
});

const status = { connected: false, empty: false, count: 0, revision: 0 };
const response = body => ({ ok: true, json: async () => body });
let pendingPlans = [];
let unexpectedRequests = [];
let observedPlans = [];
function plannedAuth({ login, logout, metadataReads = 1 } = {}) {
  pendingPlans = [
    { url: '/api/auth/status', method: 'GET', result: response(status) },
    ...Array.from({ length: metadataReads }, () => ({
      url: '/api/auth/persistence', method: 'GET',
      result: { ok: false, status: 404 },
    })),
  ];
  if (login) pendingPlans.push({ url: '/api/auth/login', method: 'POST',
    body: { email: 'fictional@example.invalid', password: 'fictional-password' }, result: login });
  if (logout) pendingPlans.push({ url: '/api/auth/logout', method: 'POST', body: {}, result: logout });
  const fetch = vi.fn((url, options = {}) => {
    const method = options.method ?? 'GET';
    const index = pendingPlans.findIndex(plan => plan.url === url && plan.method === method);
    if (index < 0) {
      unexpectedRequests.push({ url, method });
      return Promise.reject(new Error('Unplanned fixture request'));
    }
    const [plan] = pendingPlans.splice(index, 1);
    observedPlans.push({ plan, options });
    return Promise.resolve(plan.result);
  });
  vi.stubGlobal('fetch', fetch);
  return fetch;
}
afterEach(() => {
  vi.unstubAllGlobals();
  const remaining = pendingPlans;
  const unexpected = unexpectedRequests;
  const observed = observedPlans;
  pendingPlans = []; unexpectedRequests = []; observedPlans = [];
  expect(remaining.map(({ url, method }) => ({ url, method }))).toEqual([]);
  expect(unexpected).toEqual([]);
  // Assert outside fetch: the production transport intentionally sanitizes rejections.
  for (const { plan, options } of observed) {
    expect(options).toEqual(expect.objectContaining({ cache: 'no-store', credentials: 'omit', redirect: 'error' }));
    if (plan.method === 'POST') {
      expect(options.headers).toEqual({ 'Content-Type': 'application/json', 'X-CSRF-Token': 'fictional' });
      expect(JSON.parse(options.body)).toEqual(plan.body);
    } else expect(options.body).toBeUndefined();
  }
});

it.each(['success', 'failure', 'malformed'])('settles the parent exactly once after child unmount on %s', async outcome => {
  let resolve, reject;
  plannedAuth({ logout: new Promise((yes, no) => { resolve = yes; reject = no; }) });
  const settle = vi.fn();
  const begin = vi.fn(() => settle);
  const view = render(<AppAuth token="fictional" onChange={begin} />);
  await userEvent.click(screen.getByText('Biblioteca'));
  await userEvent.click(screen.getByRole('button', { name: 'Desconectar' }));
  expect(begin).toHaveBeenCalledTimes(1);
  expect(settle).not.toHaveBeenCalled();
  view.unmount();
  await act(async () => outcome === 'failure' ? reject(new Error('fictional')) : resolve(response(outcome === 'malformed' ? {} : status)));
  expect(settle).toHaveBeenCalledTimes(1);
});

it('reports same-epoch transport loss to the parent even after Auth controls unmount', async () => {
  let reject;
  plannedAuth({ logout: new Promise((_, no) => { reject = no; }) });
  const settle = vi.fn();
  const lost = vi.fn();
  const connection = { current: { epoch: 1, available: true, token: 'fictional' } };
  const view = render(<AppAuth token="fictional" connection={connection} onChange={() => settle} onDisconnect={lost} />);
  await userEvent.click(screen.getByText('Biblioteca'));
  await userEvent.click(screen.getByRole('button', { name: 'Desconectar' }));
  view.unmount();
  await act(async () => reject(new Error('secret sentinel')));
  expect(settle).toHaveBeenCalledTimes(1);
  expect(lost).toHaveBeenCalledTimes(1);
});

it.each(['current', 'connection', 'auth', 'unmounted'])('disconnects only for current metadata transport loss: %s', async kind => {
  let reject;
  const fetch = plannedAuth();
  pendingPlans.find(plan => plan.url === '/api/auth/persistence').result = new Promise((_, no) => { reject = no; });
  const lost = vi.fn();
  const connection = { current: { epoch: 1, available: true, token: 'fictional' } };
  const authTransition = { current: { epoch: 1, pending: false } };
  const view = render(<AppAuth token="fictional" connection={connection} authTransition={authTransition} onDisconnect={lost} />);
  await userEvent.click(screen.getByText('Biblioteca'));
  await screen.findByText('Biblioteca desconectada.');
  if (kind === 'connection') connection.current.epoch += 1;
  if (kind === 'auth') authTransition.current.epoch += 1;
  if (kind === 'unmounted') view.unmount();
  await act(async () => reject(new TypeError('fictional transport')));
  expect(lost).toHaveBeenCalledTimes(kind === 'current' ? 1 : 0);
  expect(fetch).toHaveBeenCalledTimes(2);
  if (kind !== 'unmounted') expect(screen.getByText(/Persistencia sin verificar/)).toBeVisible();
});

it('is optional and requests only editorial credentials after opening', async () => {
  const fetch = plannedAuth();
  render(<AppAuth token="fictional" onChange={vi.fn()} />);
  expect(fetch).not.toHaveBeenCalled();
  expect(screen.getByText('Biblioteca').closest('details')).not.toHaveAttribute('open');
  await userEvent.click(screen.getByText('Biblioteca'));
  expect(await screen.findByText(/EDITORIAL SUPABASE/)).toBeVisible();
  expect(screen.getByText(/No uses/)).toHaveTextContent('ChatGPT');
  expect(fetch).toHaveBeenCalledWith('/api/auth/status', expect.objectContaining({ credentials: 'omit' }));
});

it('clears credentials on attempt and discards a late login after disconnect', async () => {
  let finish;
  const fetch = plannedAuth({
    login: new Promise(resolve => { finish = resolve; }),
    logout: response({ ...status, revision: 2 }),
    metadataReads: 2,
  });
  const change = vi.fn();
  render(<AppAuth token="fictional" onChange={change} />);
  await userEvent.click(screen.getByText('Biblioteca'));
  fireEvent.change(screen.getByLabelText('Email editorial'), { target: { value: 'fictional@example.invalid' } });
  fireEvent.change(screen.getByLabelText('Contraseña editorial'), { target: { value: 'fictional-password' } });
  await userEvent.click(screen.getByRole('button', { name: 'Conectar' }));
  expect(screen.getByLabelText('Email editorial')).toHaveValue('');
  expect(screen.getByLabelText('Contraseña editorial')).toHaveValue('');
  const loginCalls = fetch.mock.calls.filter(([url]) => url === '/api/auth/login');
  expect(loginCalls).toHaveLength(1);
  expect(JSON.parse(loginCalls[0][1].body)).toEqual({ email: 'fictional@example.invalid', password: 'fictional-password' });
  await userEvent.click(screen.getByRole('button', { name: 'Desconectar' }));
  await act(async () => finish(response({ connected: true, empty: false, count: 2, revision: 1 })));
  expect(screen.getByText('Biblioteca desconectada.')).toBeVisible();
  expect(change).toHaveBeenCalledTimes(2);
});

it.each(['Email editorial', 'Contraseña editorial'])('submits the login when Enter is pressed in the %s field', async label => {
  const fetch = plannedAuth({ login: response({ ...status, revision: 1 }), metadataReads: 2 });
  render(<AppAuth token="fictional" onChange={vi.fn()} />);
  await userEvent.click(screen.getByText('Biblioteca'));
  fireEvent.change(screen.getByLabelText('Email editorial'), { target: { value: 'fictional@example.invalid' } });
  fireEvent.change(screen.getByLabelText('Contraseña editorial'), { target: { value: 'fictional-password' } });
  await userEvent.type(screen.getByLabelText(label), '{Enter}');
  expect(fetch.mock.calls.filter(([url]) => url === '/api/auth/login')).toHaveLength(1);
});
