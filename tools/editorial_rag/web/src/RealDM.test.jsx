import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import RealDM from './RealDM.jsx';

const response = (body, ok = true, status = 200) => ({ ok, status, json: async () => body });
const history = 'Prospecto: quiero fuerza\nTato: contáme\nProspecto: me cuesta subir';
async function setup(text = history) {
  const fetch = vi.fn().mockResolvedValue(response({ draft: 'salida ficticia?' }));
  vi.stubGlobal('fetch', fetch);
  const view = render(<RealDM token="fictional-token" />);
  fireEvent.change(screen.getByLabelText('Historial revisable'), { target: { value: text } });
  expect(fetch).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole('button', { name: 'Revisar conversación' }));
  return { fetch, ...view };
}
async function review() {
  await userEvent.click(screen.getByRole('checkbox', { name: /Revisé la conversación/ }));
  await userEvent.click(screen.getByRole('button', { name: 'Generar respuesta' }));
}
async function confirm() { await userEvent.click(screen.getByRole('button', { name: 'Confirmar una llamada' })); }
async function organize() {
  await userEvent.click(screen.getByRole('checkbox', { name: /Revisé los datos/ }));
  await userEvent.click(screen.getByRole('button', { name: 'Organizar con Codex' }));
  await confirm();
}
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('advanced connection invalidation', () => {
  it('rejects an old confirmation synchronously even when the new epoch is already connected', async () => {
    const { fetch, rerender } = await setup();
    const connection = { current: { epoch: 1, available: true, token: 'old' } };
    rerender(<RealDM token="old" connection={connection} connectionEpoch={1} />);
    await review();
    connection.current = { epoch: 2, available: true, token: 'fresh' };
    fireEvent.click(screen.getByRole('button', { name: 'Confirmar una llamada' }));
    expect(fetch).not.toHaveBeenCalled();
  });

  it.each(['success', 'failure'])('keeps reviewed history and suppresses late %s across shared epochs', async outcome => {
    const { fetch, rerender } = await setup();
    const connection = { current: { epoch: 1, available: true } };
    const lost = vi.fn();
    rerender(<RealDM token="old" connection={connection} connectionEpoch={1} onDisconnect={lost} />);
    let finish, fail;
    fetch.mockImplementationOnce(() => new Promise((yes, no) => { finish = yes; fail = no; }));
    await review(); await confirm();
    connection.current = { epoch: 2, available: false };
    // Ref changes synchronously, before React's invalidation effect.
    await act(async () => outcome === 'success' ? finish(response({ draft: 'obsolete result' })) : fail(new Error('secret sentinel')));
    expect(screen.queryByText('obsolete result')).not.toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(lost).not.toHaveBeenCalled();
    rerender(<RealDM token={null} connection={connection} connectionEpoch={2} onDisconnect={lost} />);
    expect(screen.getByText('me cuesta subir')).toBeVisible();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it('reports transport loss, not HTTP refusal, and preserves the input', async () => {
    const { fetch, rerender } = await setup();
    const lost = vi.fn();
    rerender(<RealDM token="old" onDisconnect={lost} />);
    fetch.mockResolvedValueOnce(response({}, false, 403));
    await review(); await confirm();
    expect(await screen.findByRole('alert')).toHaveTextContent('HTTP 403');
    expect(lost).not.toHaveBeenCalled();
    fetch.mockRejectedValueOnce(new Error('secret sentinel'));
    await userEvent.click(screen.getByRole('button', { name: 'Generar respuesta' }));
    await confirm();
    expect(lost).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('alert')).toHaveTextContent('No se pudo contactar');
    expect(screen.getByText('me cuesta subir')).toBeVisible();
    expect(fetch).toHaveBeenCalledTimes(2);
  });
});

describe('chat review with invented histories only', () => {
  it.each(['Hoy', '09:20'])('restores and drafts literal time-like message %s without false date context', async text => {
    const { fetch } = await setup(text + '\n\nProspecto: dato ficticio');
    await userEvent.click(screen.getByText(/Ver avisos separados/));
    await userEvent.click(screen.getByRole('button', { name: 'Restaurar como mensaje 1' }));
    await userEvent.selectOptions(screen.getByLabelText('Quién dijo el mensaje 1'), 'user');
    await review(); await confirm(); await screen.findByText('salida ficticia?');
    expect(JSON.parse(fetch.mock.calls[0][1].body).messages).toEqual([
      { role: 'user', text }, { role: 'user', text: 'dato ficticio' }]);
  });
  it('Spanish ManyChat export sends only active paragraphs and literal dates for organization', async () => {
    const raw = 'Todo el historial de canales\n\nPersona Inventada\n\nYo\n\n14 Jan 2025, 16:35\n'
      + 'La automatización Flujo ficticio se activó\nEtiqueta añadida: Prueba inventada\n'
      + 'La conversación fue movida de Abierta a Cerrada\nLa conversación fue asignada a Agente Ficticio\n'
      + 'Agente Ficticio ha pausado temporalmente las respuestas automáticas en esta conversación, puedes editar la pausa o reanudar la automatización en cualquier momento\n'
      + 'respondió a tu historia\nContenido no disponible\nLa historia expiró hace 12 horas\n\n'
      + 'quiero mejorar\n\nqué probaste?\n\nhttps://example.com/ficticio\n\n❤️\n\n3 Oct 2025, 09:20\notro intento';
    const { fetch } = await setup(raw);
    expect(screen.getAllByRole('combobox')).toHaveLength(4);
    expect(screen.getAllByRole('combobox').every(el => el.value === 'unknown')).toBe(true);
    expect(fetch).not.toHaveBeenCalled();
    fetch.mockImplementationOnce(async (_, options) => {
      const { blocks } = JSON.parse(options.body);
      expect(blocks.map(b => b.text)).toEqual(['quiero mejorar', 'qué probaste?', 'https://example.com/ficticio', 'otro intento']);
      expect(blocks.map(b => b.time_context)).toEqual(['14 Jan 2025, 16:35', '14 Jan 2025, 16:35', '14 Jan 2025, 16:35', '3 Oct 2025, 09:20']);
      expect(blocks.every(b => b.role === 'unknown')).toBe(true);
      expect(options.body).not.toMatch(/Persona Inventada|Agente Ficticio|Etiqueta|automatización|historia/);
      return response({ assignments: blocks.map(b => ({ id: b.id, role: 'unknown', uncertain: true })) });
    });
    await organize();
    await screen.findByText(/Organización recibida/);
    expect(fetch).toHaveBeenCalledTimes(1);
    await userEvent.click(screen.getByText(/Ver avisos separados/));
    expect(screen.getByText('Contenido no disponible')).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: 'Restaurar como mensaje 1' }));
    expect(screen.getAllByRole('combobox')).toHaveLength(5);
    expect(fetch).toHaveBeenCalledTimes(1);
  });
  it('local paragraphs need no manual splitting; roles are never guessed', async () => {
    const { fetch } = await setup('Monday 10:30\nAutomation paused\n\nquiero fuerza\n\nqué intentaste?');
    expect(screen.getByText('quiero fuerza')).toBeVisible();
    expect(screen.getByText('qué intentaste?')).toBeVisible();
    expect(screen.getAllByRole('combobox')).toHaveLength(2);
    expect(screen.getAllByRole('combobox').every(el => el.value === 'unknown')).toBe(true);
    expect(screen.getByRole('button', { name: 'Generar respuesta' })).toBeDisabled();
    expect(fetch).not.toHaveBeenCalled();
  });
  it.each(['Cancelar', 'Escape'])('Radix confirmation %s does not transmit and restores focus', async cancel => {
    const { fetch } = await setup();
    await review();
    expect(screen.getByRole('dialog')).toHaveTextContent('OpenAI/Codex');
    if (cancel === 'Escape') await userEvent.keyboard('{Escape}');
    else await userEvent.click(screen.getByRole('button', { name: cancel }));
    expect(fetch).not.toHaveBeenCalled();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Generar respuesta' })).toHaveFocus();
  });
  it('labelled import goes directly to separately confirmed draft and manual copy', async () => {
    const { fetch } = await setup();
    const copy = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: copy } });
    await review(); expect(fetch).not.toHaveBeenCalled(); await confirm();
    await screen.findByText('salida ficticia?');
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch.mock.calls[0][0]).toBe('/api/draft');
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ messages: [
      { role: 'user', text: 'quiero fuerza' }, { role: 'assistant', text: 'contáme' },
      { role: 'user', text: 'me cuesta subir' }], reviewed: true, consent: true });
    expect(fetch.mock.calls[0][1].headers['X-CSRF-Token']).toBe('fictional-token');
    expect(copy).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole('button', { name: 'Copiar DM' }));
    expect(copy).toHaveBeenCalledWith('salida ficticia?');
    expect(screen.getByRole('status')).toHaveTextContent('No se envió');
  });
  it('optional organization transmits only reviewed active blocks, retains uncertainty and never chains', async () => {
    const { fetch } = await setup('Instagram channel history\nPersona Ficticia\nYo\nMonday 10:30\nAutomation paused\n\nfuerza\n\ncontrol');
    fetch.mockImplementationOnce(async (_, options) => {
      const body = JSON.parse(options.body);
      expect(Object.keys(body).sort()).toEqual(['blocks', 'consent', 'reviewed']);
      expect(body.blocks.map(b => b.text)).toEqual(['fuerza', 'control']);
      expect(body.blocks.every(b => b.time_context === 'Monday 10:30' && b.role === 'unknown')).toBe(true);
      expect(options.body).not.toMatch(/Persona Ficticia|Automation paused/);
      return response({ assignments: body.blocks.map((b, i) => ({ id: b.id, role: i ? 'user' : 'assistant', uncertain: !!i })) });
    });
    await organize();
    await screen.findByText(/Organización recibida/);
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('button', { name: 'Generar respuesta' })).toBeDisabled();
    await userEvent.click(screen.getByRole('button', { name: 'Confirmar rol del mensaje 2' }));
    await review(); expect(fetch).toHaveBeenCalledTimes(1); await confirm();
    await screen.findByText('salida ficticia?');
    expect(fetch.mock.calls.map(([url]) => url)).toEqual(['/api/organize', '/api/draft']);
    expect(JSON.parse(fetch.mock.calls[1][1].body).messages[0].text).toBe('[Fecha/hora original: Monday 10:30]\nfuerza');
  });
  it.each(['clear', 'edit', 'unmount'])('late organization never revives state after %s', async action => {
    const { fetch, unmount } = await setup('fuerza\n\ncontrol');
    let finish, payload;
    fetch.mockImplementationOnce((_, options) => { payload = JSON.parse(options.body); return new Promise(resolve => { finish = resolve; }); });
    await organize();
    if (action === 'clear') await userEvent.click(screen.getByRole('button', { name: 'Limpiar conversación' }));
    if (action === 'edit') await userEvent.selectOptions(screen.getByLabelText('Quién dijo el mensaje 1'), 'user');
    if (action === 'unmount') unmount();
    await act(async () => finish(response({ assignments: payload.blocks.map(b => ({ id: b.id, role: 'assistant', uncertain: false })) })));
    expect(screen.queryByText(/Organización recibida/)).not.toBeInTheDocument();
    if (action === 'edit') expect(screen.getByLabelText('Quién dijo el mensaje 1')).toHaveValue('user');
    if (action === 'clear') expect(screen.getByLabelText('Historial revisable')).toHaveValue('');
  });
  it.each(['clear', 'edit', 'unmount'])('late draft never revives state after %s', async action => {
    const { fetch, unmount } = await setup();
    let finish;
    fetch.mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
    await review(); await confirm();
    if (action === 'clear') await userEvent.click(screen.getByRole('button', { name: 'Limpiar conversación' }));
    if (action === 'edit') await userEvent.selectOptions(screen.getByLabelText('Quién dijo el mensaje 1'), 'assistant');
    if (action === 'unmount') unmount();
    await act(async () => finish(response({ draft: 'resultado tardío ficticio' })));
    expect(screen.queryByText('resultado tardío ficticio')).not.toBeInTheDocument();
  });
  it.each([{}, { assignments: [] }, { assignments: [{ id: 'foreign', role: 'user', uncertain: false }] }])('rejects inconsistent organization atomically', async data => {
    const { fetch } = await setup('fuerza\n\ncontrol');
    fetch.mockResolvedValueOnce(response(data));
    await organize(); await screen.findByRole('alert');
    expect(screen.getAllByRole('combobox').every(el => el.value === 'unknown')).toBe(true);
    expect(fetch).toHaveBeenCalledTimes(1);
  });
  it.each([null, '', '   ', 12, {}])('rejects malformed drafts without retry %s', async draft => {
    const { fetch } = await setup(); fetch.mockResolvedValueOnce(response({ draft }));
    await review(); await confirm(); await screen.findByRole('alert');
    expect(screen.queryByRole('button', { name: 'Copiar DM' })).not.toBeInTheDocument();
    expect(fetch).toHaveBeenCalledTimes(1);
  });
  it('fixed errors, new confirmation on retry, literal HTML and clipboard failure', async () => {
    const { fetch } = await setup();
    fetch.mockResolvedValueOnce(response({ error: 'raw fictional diagnostic' }, false, 502))
      .mockResolvedValueOnce(response({ draft: '<b>ficticio</b>' }));
    await review(); await confirm(); await screen.findByRole('alert');
    expect(screen.queryByText(/raw fictional/)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Generar respuesta' }));
    expect(fetch).toHaveBeenCalledTimes(1); await confirm();
    expect((await screen.findByText('<b>ficticio</b>')).querySelector('b')).toBeNull();
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText: vi.fn().mockRejectedValue(new Error('raw clipboard')) } });
    await userEvent.click(screen.getByRole('button', { name: 'Copiar DM' }));
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('No se pudo copiar'));
  });
  it('limits preserve raw input and never use storage', async () => {
    const get = vi.spyOn(Storage.prototype, 'getItem'), set = vi.spyOn(Storage.prototype, 'setItem');
    const { fetch } = await setup('x'.repeat(4001));
    expect(screen.getByRole('alert')).toHaveTextContent('4.000');
    expect(screen.getByLabelText('Historial revisable')).toHaveValue('x'.repeat(4001));
    expect(fetch).not.toHaveBeenCalled(); expect(get).not.toHaveBeenCalled(); expect(set).not.toHaveBeenCalled();
  });
});
