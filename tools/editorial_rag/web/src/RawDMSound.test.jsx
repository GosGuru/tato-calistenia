import { StrictMode } from 'react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';
import RawDM from './RawDM.jsx';

const dm = { type: 'dm', text: 'respuesta ficticia del simulador' };
const envelope = (result = dm) => ({ result, revision: 0, retrieval: { status: 'off', count: 0 } });
const input = () => screen.getByRole('textbox', { name: 'Historial completo' });
const click = () => fireEvent.click(screen.getByRole('button', { name: 'Generar borrador' }));
const enter = () => fireEvent.keyDown(input(), { key: 'Enter' });
const paste = (value = 'historial ficticio 🧭\nsegunda línea') => fireEvent.change(input(), { target: { value } });
let context, audioConstructor, fetchMock, finish, nodes;
beforeEach(() => {
  nodes = [];
  context = { state: 'running', currentTime: 0, destination: {}, resume: vi.fn(() => Promise.resolve()), close: vi.fn(() => Promise.resolve()),
    createOscillator: vi.fn(() => { const node = { frequency: { setValueAtTime: vi.fn() }, connect: vi.fn(), disconnect: vi.fn(), start: vi.fn(), stop: vi.fn() }; nodes.push(node); return node; }),
    createGain: vi.fn(() => ({ gain: { setValueAtTime: vi.fn(), linearRampToValueAtTime: vi.fn(), exponentialRampToValueAtTime: vi.fn() }, connect: vi.fn(), disconnect: vi.fn() })) };
  audioConstructor = vi.fn(function () { return context; });
  vi.stubGlobal('AudioContext', audioConstructor);
  fetchMock = vi.fn(() => new Promise(resolve => { finish = body => resolve({ ok: true, status: 200, json: async () => body }); }));
  vi.stubGlobal('fetch', fetchMock);
  Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: vi.fn().mockResolvedValue() } });
});
afterEach(() => vi.unstubAllGlobals());
const complete = async (body = envelope()) => { await act(async () => finish(body)); };

it.each(['click', 'Enter', 'StrictMode'])('arms synchronously on %s and sounds only once for one accepted DM', async gesture => {
  const ui = <RawDM token="fictional" />;
  const view = render(gesture === 'StrictMode' ? <StrictMode>{ui}</StrictMode> : ui);
  expect(audioConstructor).not.toHaveBeenCalled(); paste();
  expect(audioConstructor).not.toHaveBeenCalled();
  context.state = 'suspended';
  fetchMock.mockImplementationOnce(() => {
    expect(context.resume).toHaveBeenCalledTimes(1);
    return new Promise(resolve => { finish = body => resolve({ ok: true, status: 200, json: async () => body }); });
  });
  if (gesture === 'Enter') enter(); else click();
  expect(audioConstructor).toHaveBeenCalledTimes(1);
  expect(context.createOscillator).not.toHaveBeenCalled();
  expect(fetchMock).toHaveBeenCalledTimes(1);
  expect(fetchMock.mock.calls[0][0]).toBe('/api/raw-draft');
  expect(fetchMock.mock.calls[0][1].method).toBe('POST');
  expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({ history: 'historial ficticio 🧭\nsegunda línea', consent: true });
  expect(input()).toHaveValue('');
  expect(screen.getByRole('region', { name: 'Historial enviado completo' })).toHaveTextContent('historial ficticio 🧭');
  context.state = 'running'; await complete();
  expect(screen.getByText(dm.text)).toBeVisible();
  expect(context.createOscillator).toHaveBeenCalledTimes(2);
  view.rerender(gesture === 'StrictMode' ? <StrictMode>{ui}</StrictMode> : <RawDM token="fictional" />);
  await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Copiar DM' })));
  await complete(); fireEvent.scroll(input());
  expect(context.createOscillator).toHaveBeenCalledTimes(2);
  expect(fetchMock).toHaveBeenCalledTimes(1);
  view.unmount(); expect(context.close).toHaveBeenCalledTimes(1);
});

it.each(['empty', 'invalid', 'long', 'token', 'inactive', 'unavailable', 'auth', 'repeat', 'shift', 'ime'])('never arms or posts for %s guard', guard => {
  render(<RawDM token={guard === 'token' ? '' : 'fictional'} active={guard !== 'inactive'} connection={{ current: { available: guard !== 'unavailable', epoch: 0 } }} authTransition={{ current: { pending: guard === 'auth', epoch: 0 } }} />);
  const guardedInputs = { empty: ' ', invalid: '\u0001', long: 'a'.repeat(24001) };
  paste(guardedInputs[guard] ?? 'fictional');
  if (guard === 'ime') fireEvent.compositionStart(input());
  fireEvent.keyDown(input(), { key: 'Enter', repeat: guard === 'repeat', shiftKey: guard === 'shift' });
  expect(audioConstructor).not.toHaveBeenCalled(); expect(fetchMock).not.toHaveBeenCalled();
});

it('does not rearm while busy even after clear and new paste', async () => {
  render(<RawDM token="fictional" />); paste(); click();
  fireEvent.click(screen.getByRole('button', { name: 'Limpiar' })); paste(); enter(); click();
  expect(audioConstructor).toHaveBeenCalledTimes(1); expect(fetchMock).toHaveBeenCalledTimes(1);
  await complete(); expect(context.createOscillator).not.toHaveBeenCalled();
});

it.each(['needs_context', 'malformed', 'error', 'connection', 'auth', 'revision', 'inactive', 'unmount'])('never sounds for %s outcome', async outcome => {
  const connection = { current: { available: true, epoch: 0 } };
  const authTransition = { current: { pending: false, epoch: 0 } };
  const props = { token: 'fictional', connection, authTransition };
  if (outcome === 'error') fetchMock.mockRejectedValueOnce(new Error('fictional rejection'));
  const view = render(<RawDM {...props} />); paste(); click();
  if (outcome === 'connection') connection.current.epoch++;
  if (outcome === 'auth') authTransition.current.epoch++;
  if (outcome === 'revision') view.rerender(<RawDM {...props} authRevision={1} />);
  if (outcome === 'inactive') view.rerender(<RawDM {...props} active={false} />);
  if (outcome === 'unmount') view.unmount();
  if (outcome === 'error') await act(async () => {});
  else {
    const outcomes = { needs_context: envelope({ type: 'needs_context', question: 'dato ficticio pendiente?' }), malformed: envelope({ ...dm, extra: true }) };
    await complete(outcomes[outcome] ?? envelope());
  }
  expect(context.createOscillator).not.toHaveBeenCalled(); expect(fetchMock).toHaveBeenCalledTimes(1);
  if (outcome === 'error' || outcome === 'malformed') expect(screen.getByRole('alert')).toBeVisible();
});

it.each(['unsupported', 'constructor', 'resume', 'node', 'suspended'])('keeps one POST and visible DM despite %s audio', async failure => {
  if (failure === 'unsupported') vi.stubGlobal('AudioContext', undefined);
  if (failure === 'constructor') audioConstructor.mockImplementation(function () { throw new Error('fictional'); });
  if (failure === 'resume') { context.state = 'suspended'; context.resume.mockRejectedValue(new Error('fictional')); }
  if (failure === 'node') context.createGain.mockImplementation(() => { throw new Error('fictional'); });
  let resumed;
  if (failure === 'suspended') { context.state = 'suspended'; context.resume.mockImplementation(() => new Promise(resolve => { resumed = resolve; })); }
  render(<RawDM token="fictional" />); paste(); click(); await complete();
  expect(screen.getByText(dm.text)).toBeVisible(); expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledTimes(1);
  if (resumed) { context.state = 'running'; await act(async () => resumed()); expect(context.createOscillator).not.toHaveBeenCalled(); }
});
