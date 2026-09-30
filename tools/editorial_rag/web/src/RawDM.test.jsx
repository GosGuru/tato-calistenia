import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import RawDM from './RawDM.jsx';

const response = (body, status = 200) => ({ ok: status === 200, status,
  json: async () => status === 200 ? { result: body, retrieval: { status: 'off', count: 0 }, revision: 0 } : body });
const dm = { type: 'dm', text: 'salida completamente inventada?' };
const input = () => screen.getByRole('textbox', { name: 'Historial completo' });
const send = () => screen.getByRole('button', { name: 'Generar borrador' });
afterEach(() => vi.unstubAllGlobals());

describe('compact presentation', () => {
  it('shows only an honest compact loader until the complete reply arrives', async () => {
    let finish;
    vi.stubGlobal('fetch', vi.fn(() => new Promise(resolve => { finish = resolve; })));
    render(<RawDM token="fictional" />);
    fireEvent.change(input(), { target: { value: 'ficticio' } });
    fireEvent.click(send());
    expect(screen.getByRole('status')).toHaveTextContent('Preparando el próximo DM');
    expect(screen.getByRole('status')).toHaveTextContent('Este historial se usa para preparar una respuesta. No se envía a Instagram.');
    expect(input()).toHaveValue('');
    expect(screen.getByRole('region', { name: 'Historial enviado completo' })).toHaveTextContent('ficticio');
    expect(document.querySelector('.generation-mark')).not.toBeNull();
    expect(screen.queryByRole('region', { name: 'Borrador completo' })).not.toBeInTheDocument();
    expect(screen.queryByText('Privacidad y límites')).not.toBeInTheDocument();
    await act(async () => finish(response(dm)));
    expect(screen.getByRole('button', { name: 'Copiar DM' }).querySelector('svg')).not.toBeNull();
  });
});

describe('editorial composition', () => {
  it('keeps only entry and actions inside the rounded surface, with visible adjacent informed captions', () => {
    vi.stubGlobal('fetch', vi.fn());
    render(<RawDM token="fictional" />);
    const surface = input().closest('.raw-input-panel');
    expect(surface).toContainElement(send());
    expect(surface).not.toContainElement(screen.getByText(/Al generar, autorizás/));
    expect(screen.queryByText(/quitá datos sensibles/)).not.toBeInTheDocument();
    expect(surface).not.toContainElement(screen.getByText(/24.000 caracteres Unicode/));
    expect(input()).toHaveAttribute('rows', '2');
    expect(screen.queryByText('Historial preparado')).not.toBeInTheDocument();
    const caption = surface.nextElementSibling;
    expect(caption).toContainElement(screen.getByText(/Al generar, autorizás/));
    expect(caption).toBeVisible();
    expect(send()).toHaveAttribute('aria-describedby', 'raw-disclosure');
  });
  it('starts with one composer, no empty draft panel, and preserves its node through disclosures', () => {
    const fetch = vi.fn(); vi.stubGlobal('fetch', fetch);
    render(<RawDM token="fictional" />);
    const history = input();
    expect(screen.getByRole('heading', { name: 'Qué conversación preparamos?' })).toBeVisible();
    expect(screen.getByRole('region', { name: 'Historial preparado' })).toBeVisible();
    expect(screen.queryByRole('region', { name: 'Borrador' })).not.toBeInTheDocument();
    fireEvent.change(history, { target: { value: 'ficticio 🧭' } });
    expect(screen.queryByText('Privacidad y límites')).not.toBeInTheDocument();
    expect(screen.queryByText('Criterios y fuentes')).not.toBeInTheDocument();
    expect(input()).toBe(history);
    expect(history).toHaveValue('ficticio 🧭');
    expect(send()).toBeEnabled();
    expect(screen.queryByRole('button', { name: 'Copiar DM' })).not.toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
  });
});

describe('conversational result structure', () => {
  it.each(['dm', 'needs_context', 'error'])('moves the submitted history above %s and keeps it editable', async kind => {
    const fetch = vi.fn().mockResolvedValue(kind === 'error' ? response({}, 502)
      : response(kind === 'dm' ? dm : { type: 'needs_context', question: 'Qué falta en el ejemplo?' }));
    vi.stubGlobal('fetch', fetch);
    render(<RawDM token="fictional" />);
    const history = input();
    const raw = 'Ficticio 🧭\nrepetido\nrepetido';
    fireEvent.change(history, { target: { value: raw } });
    await act(async () => fireEvent.click(send()));
    const result = screen.getByRole('region', { name: 'Borrador' });
    const submitted = screen.getByRole('region', { name: 'Historial enviado para preparar el DM' });
    expect(submitted).toHaveClass('response-enter-up');
    expect(submitted.compareDocumentPosition(result) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(result.compareDocumentPosition(history) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(input()).toBe(history);
    expect(history).toHaveValue('');
    expect(screen.getByRole('region', { name: 'Historial enviado completo' }).textContent).toBe(raw);
    expect(screen.queryByRole('heading', { name: 'Qué conversación preparamos?' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Copiar DM' }) !== null).toBe(kind === 'dm');
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ history: raw, consent: true });
    fireEvent.click(screen.getByRole('button', { name: 'Editar historial' }));
    expect(screen.queryByRole('region', { name: 'Borrador' })).not.toBeInTheDocument();
    expect(input()).toBe(history);
    expect(history).toHaveValue(raw);
    expect(fetch).toHaveBeenCalledTimes(1);
  });
});

describe('RAW keyboard guards', () => {
  it('ignores IME, legacy composition and repeats, then posts the exact Unicode history once', async () => {
    let finish;
    const fetch = vi.fn(() => new Promise(resolve => { finish = resolve; }));
    vi.stubGlobal('fetch', fetch);
    render(<RawDM token="fictional" />);
    const raw = '  ficticio 🪁\nrepetido\nrepetido\t';
    fireEvent.change(input(), { target: { value: raw } });
    for (const options of [{ isComposing: true }, { keyCode: 229 }, { repeat: true }]) {
      fireEvent.keyDown(input(), { key: 'Enter', ...options });
    }
    expect(fetch).not.toHaveBeenCalled();
    fireEvent.keyDown(input(), { key: 'Enter' });
    fireEvent.keyDown(input(), { key: 'Enter' });
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ history: raw, consent: true });
    await act(async () => finish(response(dm)));
    expect(input()).toHaveValue('');
    expect(screen.getByRole('region', { name: 'Historial enviado completo' }).textContent).toBe(raw);
  });
  it.each(['empty', 'invalid', 'auth', 'disconnected'])('does not post Enter while %s', state => {
    const fetch = vi.fn(); vi.stubGlobal('fetch', fetch);
    render(<RawDM token="fictional" authTransition={{ current: { pending: state === 'auth', epoch: 0 } }}
      connection={{ current: { available: state !== 'disconnected', epoch: 0, token: 'fictional' } }} />);
    const values = { empty: '', invalid: '\u0000', auth: 'ficticio', disconnected: 'ficticio' };
    fireEvent.change(input(), { target: { value: values[state] } });
    fireEvent.keyDown(input(), { key: 'Enter' });
    expect(fetch).not.toHaveBeenCalled();
  });
});

describe('synchronous connection guard', () => {
  it('rejects stale rendered nonce immediately and uses current parent nonce after recovery', async () => {
    const fetch = vi.fn().mockResolvedValue(response(dm));
    vi.stubGlobal('fetch', fetch);
    const connection = { current: { epoch: 0, available: true, token: 'old' } };
    render(<RawDM token="old" connection={connection} />);
    fireEvent.change(input(), { target: { value: 'fictional history' } });
    connection.current = { epoch: 1, available: false, token: null };
    fireEvent.click(send());
    expect(fetch).not.toHaveBeenCalled();
    connection.current = { epoch: 2, available: true, token: 'fresh' };
    await act(async () => fireEvent.click(send()));
    expect(fetch).toHaveBeenCalledTimes(1);
    expect(fetch.mock.calls[0][1].headers['X-CSRF-Token']).toBe('fresh');
  });
});

describe('synchronous parent auth guard', () => {
  it('blocks the handler before React renders the pending state', async () => {
    const fetch = vi.fn();
    vi.stubGlobal('fetch', fetch);
    const authTransition = { current: { epoch: 0, pending: 0 } };
    render(<RawDM token="fictional" authTransition={authTransition} />);
    fireEvent.change(input(), { target: { value: 'fictional history' } });
    expect(send()).toBeEnabled();
    // Parent begin callback updates this synchronously, before the next render.
    authTransition.current.pending = 1;
    authTransition.current.epoch += 1;
    fireEvent.click(send());
    expect(fetch).not.toHaveBeenCalled();
  });

  it.each(['success', 'error', '409'])('synchronous epoch discards late %s before the invalidation effect', async outcome => {
    let finish, fail;
    vi.stubGlobal('fetch', vi.fn(() => new Promise((resolve, reject) => { finish = resolve; fail = reject; })));
    const authTransition = { current: { epoch: 0, pending: 0 } };
    render(<RawDM token="fictional" authTransition={authTransition} />);
    fireEvent.change(input(), { target: { value: 'fictional history' } });
    fireEvent.click(send());
    authTransition.current.epoch += 2;
    await act(async () => outcome === 'error' ? fail(new Error('fictional')) : finish(response(dm, outcome === '409' ? 409 : 200)));
    expect(screen.queryByText(dm.text)).not.toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(screen.queryByText(/Solicitud terminada/)).not.toBeInTheDocument();
  });
});

describe('composer disabled-state boundary', () => {
  it.each(['empty', 'loading', 'disconnected'])('keeps editable input and disclosure undimmed while Generate is %s', async state => {
    let finish;
    const fetch = vi.fn(() => new Promise(resolve => { finish = resolve; }));
    vi.stubGlobal('fetch', fetch);
    render(<RawDM token={state === 'disconnected' ? null : 'fictional'} />);
    if (state !== 'empty') fireEvent.change(input(), { target: { value: 'historial ficticio' } });
    if (state === 'loading') fireEvent.click(send());
    expect(send()).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Limpiar' })).toBeEnabled();
    fireEvent.click(send());
    expect(input()).toBeEnabled();
    const disclosure = screen.getByText(/Al generar, autorizás/);
    expect(disclosure).toBeVisible();
    // jsdom does not execute Tailwind's nested CSS. Protect the ancestor styling
    // contract here; the independent Chrome harness checks computed opacity.
    for (const element of [input(), disclosure]) {
      for (let ancestor = element; ancestor; ancestor = ancestor.parentElement) {
        expect(ancestor.className).not.toMatch(/(?:^|\s)\S*has-disabled:opacity-/);
      }
    }
    expect(fetch).toHaveBeenCalledTimes(state === 'loading' ? 1 : 0);
    if (finish) await act(async () => finish(response(dm)));
  });
});

describe('safe static presentation', () => {
  it('does not let an older clipboard success overwrite the latest failure', async () => {
    let finish;
    const writeText = vi.fn().mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }))
      .mockRejectedValueOnce(new Error('fictional'));
    vi.stubGlobal('navigator', { clipboard: { writeText } });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(dm)));
    render(<RawDM token="fictional" />);
    fireEvent.change(input(), { target: { value: 'ficticio' } });
    await act(async () => fireEvent.click(send()));
    fireEvent.click(screen.getByRole('button', { name: 'Copiar DM' }));
    await act(async () => fireEvent.click(screen.getByRole('button', { name: 'Copiar DM' })));
    await act(async () => finish());
    expect(screen.queryByText('DM copiado. No se envió.')).not.toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('No se pudo copiar');
  });
  it.each(['resolve', 'reject'])('ignores late clipboard %s after a parent Auth transition', async outcome => {
    let finish, fail;
    const writeText = vi.fn(() => new Promise((resolve, reject) => { finish = resolve; fail = reject; }));
    vi.stubGlobal('navigator', { clipboard: { writeText } });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response(dm)));
    const authTransition = { current: { epoch: 1, pending: 0 } };
    const view = render(<RawDM token="fictional" authRevision={1} authTransition={authTransition} />);
    fireEvent.change(input(), { target: { value: 'historial ficticio' } });
    await act(async () => fireEvent.click(send()));
    fireEvent.click(screen.getByRole('button', { name: 'Copiar DM' }));
    authTransition.current = { epoch: 2, pending: 1 };
    view.rerender(<RawDM token="fictional" authRevision={2} authTransition={authTransition} />);
    await act(async () => outcome === 'resolve' ? finish() : fail(new Error('fixture')));
    expect(screen.queryByText('DM copiado. No se envió.')).not.toBeInTheDocument();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    expect(input()).toHaveValue('');
    expect(screen.getByRole('region', { name: 'Historial enviado completo' })).toHaveTextContent('historial ficticio');
  });
  it('renders Markdown without images, active links or HTML and copies the original', async () => {
    const text = '**fuerza ficticia**\nsegunda línea\n<img src="https://example.invalid/private">\n![remoto](https://example.invalid/image)\n[enlace](javascript:alert(1))';
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal('navigator', { clipboard: { writeText } });
    const fetch = vi.fn().mockResolvedValue(response({ type: 'dm', text }));
    vi.stubGlobal('fetch', fetch);
    render(<RawDM token="fictional" />);
    fireEvent.change(input(), { target: { value: 'historial ficticio' } });
    await act(async () => fireEvent.click(send()));
    expect(screen.getByText('fuerza ficticia').tagName).toBe('STRONG');
    expect(document.querySelector('img, iframe, a[href], script')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: 'Copiar DM' }));
    expect(writeText).toHaveBeenCalledWith(text);
    expect(input()).toHaveValue('');
    expect(screen.getByRole('region', { name: 'Historial enviado completo' })).toHaveTextContent('historial ficticio');
    expect(fetch).toHaveBeenCalledTimes(1);
  });
  it('Shift Enter adds a newline and Enter moves the exact history out of the input', async () => {
    const fetch = vi.fn().mockResolvedValue(response(dm)); vi.stubGlobal('fetch', fetch);
    const view = render(<RawDM token="fictional" />);
    await userEvent.type(input(), 'ficticio{Shift>}{Enter}{/Shift}otra línea');
    expect(input()).toHaveValue('ficticio\notra línea');
    expect(fetch).not.toHaveBeenCalled();
    expect(document.querySelector('input[type="file"]')).toBeNull();
    await userEvent.type(input(), '{Enter}');
    expect(input()).toHaveValue('');
    expect(screen.getByRole('region', { name: 'Historial enviado completo' }).textContent).toBe('ficticio\notra línea');
    view.unmount(); render(<RawDM token="fictional" />);
    expect(input()).toHaveValue(''); expect(fetch).toHaveBeenCalledTimes(1);
  });
});

describe('pegado directo', () => {
  it('keeps concise consent and limits visible without a new popup or main-chat disclosure blocks', () => {
    const fetch = vi.fn(); vi.stubGlobal('fetch', fetch);
    render(<RawDM token="fictional" />);
    const notice = screen.getByText(/Al generar, autorizás/);
    expect(notice).toBeVisible();
    expect(notice).toHaveTextContent('una llamada a OpenAI con el historial completo');
    expect(notice).toHaveTextContent('No se envía a Instagram');
    expect(send()).toHaveAttribute('aria-describedby', notice.id);
    expect(screen.queryByText('Privacidad y límites')).not.toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });
  it('does not transmit before a click and sends exact text once without checkbox or dialog', async () => {
    let finish;
    const fetch = vi.fn(() => new Promise(resolve => { finish = resolve; }));
    vi.stubGlobal('fetch', fetch);
    render(<RawDM token="fictional-token" />);
    const history = '  Export inventado\nrepetido\nrepetido\t🪁\n';
    fireEvent.change(input(), { target: { value: history } });
    expect(fetch).not.toHaveBeenCalled();
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
    expect(screen.getByText(/Al generar, autorizás/)).toHaveTextContent('OpenAI');
    await userEvent.dblClick(send());
    expect(fetch).toHaveBeenCalledTimes(1);
    const [url, options] = fetch.mock.calls[0];
    expect(url).toBe('/api/raw-draft');
    expect(JSON.parse(options.body)).toEqual({ history, consent: true });
    expect(options.headers['X-CSRF-Token']).toBe('fictional-token');
    expect(options.cache).toBe('no-store');
    expect(options.credentials).toBe('omit');
    expect(send()).toBeDisabled();
    await act(async () => finish(response(dm)));
    expect(screen.getByText(dm.text)).toBeVisible();
    expect(screen.getByRole('button', { name: 'Copiar DM' })).toBeEnabled();
  });

  it('auth changes discard drafts without losing pasted history', async () => {
    let finish;
    vi.stubGlobal('fetch', vi.fn(() => new Promise(resolve => { finish = resolve; })));
    const view = render(<RawDM token="fictional" authRevision={0} />);
    fireEvent.change(input(), { target: { value: 'fictional unchanged history' } });
    await userEvent.click(send());
    view.rerender(<RawDM token="fictional" authRevision={1} />);
    await act(async () => finish(response(dm)));
    expect(input()).toHaveValue('');
    expect(screen.getByRole('region', { name: 'Historial enviado completo' })).toHaveTextContent('fictional unchanged history');
    expect(screen.queryByText(dm.text)).not.toBeInTheDocument();
  });

  it.each([
    ['off', 0, 'Biblioteca desconectada'], ['empty', 0, 'Biblioteca consultada sin criterios disponibles'],
    ['expired', 0, 'Sesión editorial vencida'], ['unavailable', 0, 'Biblioteca o búsqueda local no disponible'],
    ['supplied', 2, '2 criterios aportados, no necesariamente aplicados'],
  ])('passes truthful retrieval status %s to secondary settings', async (status, count) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({
      result: dm, retrieval: { status, count }, revision: 4,
    }) }));
    const onRetrieval = vi.fn();
    render(<RawDM token="fictional" onRetrieval={onRetrieval} />);
    fireEvent.change(input(), { target: { value: 'fictional history' } });
    await userEvent.click(send());
    expect(await screen.findByText(dm.text)).toBeVisible();
    expect(onRetrieval).toHaveBeenCalledExactlyOnceWith({ status, count });
  });

  it.each([
    { result: dm, retrieval: { status: 'supplied', count: 0 }, revision: 0 },
    { result: dm, retrieval: { status: 'off', count: 1 }, revision: 0 },
    { result: dm, retrieval: { status: 'supplied', count: 3 }, revision: 0 },
    { result: dm, retrieval: { status: 'applied', count: 1 }, revision: 0 },
    { result: dm, retrieval: { status: 'off', count: 0 }, revision: -1 },
    { result: dm, retrieval: { status: 'off', count: 0, jwt: 'fictional' }, revision: 0 },
    { result: dm, retrieval: { status: 'off', count: 0 }, revision: 0, extra: true },
    dm,
  ])('fails closed on malformed envelope', async body => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => body }));
    render(<RawDM token="fictional" />);
    fireEvent.change(input(), { target: { value: 'fictional history' } });
    await userEvent.click(send());
    expect(await screen.findByRole('alert')).toHaveTextContent('No se pudo generar');
    expect(screen.queryByText(dm.text)).not.toBeInTheDocument();
  });

  it('shows needs_context only as operator clarification, never a copyable DM', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(response({ type: 'needs_context', question: 'quién escribió la última línea ficticia?' })));
    render(<RawDM token="fictional" />);
    fireEvent.change(input(), { target: { value: 'fragmento ficticio ambiguo' } });
    await userEvent.click(send());
    expect(await screen.findByText('quién escribió la última línea ficticia?')).toBeVisible();
    expect(screen.getByText('Falta contexto para preparar el DM')).toBeVisible();
    expect(screen.getByRole('status')).not.toHaveTextContent('Borrador disponible');
    expect(screen.getByRole('status')).toHaveTextContent('Falta contexto. No se generó un DM.');
    expect(screen.queryByRole('button', { name: 'Copiar DM' })).not.toBeInTheDocument();
  });

  it.each(['clear', 'unmount'])('discards stale success after %s', async action => {
    let finish;
    vi.stubGlobal('fetch', vi.fn(() => new Promise(resolve => { finish = resolve; })));
    const view = render(<RawDM token="fictional" />);
    fireEvent.change(input(), { target: { value: 'historial ficticio' } });
    await userEvent.click(send());
    if (action === 'clear') await userEvent.click(screen.getByRole('button', { name: 'Limpiar' }));
    else { view.unmount(); render(<RawDM token="fictional" />); }
    await act(async () => finish(response(dm)));
    expect(screen.queryByText(dm.text)).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Copiar DM' })).not.toBeInTheDocument();
  });

  it('keeps a newly typed draft separate from the pending submitted history', async () => {
    let finish;
    vi.stubGlobal('fetch', vi.fn(() => new Promise(resolve => { finish = resolve; })));
    render(<RawDM token="fictional" />);
    fireEvent.change(input(), { target: { value: 'historial enviado' } });
    fireEvent.click(send());
    fireEvent.change(input(), { target: { value: 'nuevo historial' } });
    await act(async () => finish(response(dm)));
    expect(input()).toHaveValue('nuevo historial');
    expect(screen.getByRole('region', { name: 'Historial enviado completo' })).toHaveTextContent('historial enviado');
    expect(screen.getByText(dm.text)).toBeVisible();
  });

  it.each(['reject', 'conflict'])('shows the submitted %s result separately from new input', async outcome => {
    let finish, fail;
    vi.stubGlobal('fetch', vi.fn(() => new Promise((resolve, reject) => { finish = resolve; fail = reject; })));
    render(<RawDM token="fictional" />);
    fireEvent.change(input(), { target: { value: 'inventado' } });
    await userEvent.click(send());
    fireEvent.change(input(), { target: { value: 'nuevo inventado' } });
    await act(async () => outcome === 'reject' ? fail(new Error('invented internal detail')) : finish(response({}, 409)));
    expect(screen.getByRole('alert')).toBeVisible();
    expect(input()).toHaveValue('nuevo inventado');
  });

  it.each([{ type: 'dm', text: 'partial', extra: true }, { type: 'needs_context', text: 'partial' },
    { type: 'dm', text: '' }, { type: 'dm', text: '\ud800' }, { type: 'dm', text: 'x'.repeat(24001) },
    { type: 'unknown', text: 'partial' }])('rejects malformed success without echo or retry', async body => {
    const fetch = vi.fn().mockResolvedValue(response(body));
    vi.stubGlobal('fetch', fetch);
    render(<RawDM token="fictional" />);
    fireEvent.change(input(), { target: { value: 'inventado' } });
    await userEvent.click(send());
    expect(await screen.findByRole('alert')).toHaveTextContent('No se pudo generar');
    expect(screen.queryByText('partial')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Copiar DM' })).not.toBeInTheDocument();
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it('copy is manual, renders markup literally, and edits invalidate the copyable result', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal('navigator', { clipboard: { writeText } });
    const output = { type: 'dm', text: '<b>salida ficticia</b>' };
    const fetch = vi.fn().mockResolvedValue(response(output));
    vi.stubGlobal('fetch', fetch);
    render(<RawDM token="fictional" />);
    fireEvent.change(input(), { target: { value: 'inventado' } });
    fireEvent.click(send());
    expect(await screen.findByText(output.text)).toBeVisible();
    expect(document.querySelector('b')).toBeNull();
    expect(writeText).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: 'Copiar DM' }));
    expect(writeText).toHaveBeenCalledWith(output.text);
    await screen.findByText('DM copiado. No se envió.');
    writeText.mockRejectedValueOnce(new Error('invented detail'));
    fireEvent.click(screen.getByRole('button', { name: 'Copiar DM' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('No se pudo copiar el DM.');
    fireEvent.click(screen.getByRole('button', { name: 'Editar historial' }));
    expect(screen.queryByRole('button', { name: 'Copiar DM' })).not.toBeInTheDocument();
    expect(screen.queryByText(output.text)).not.toBeInTheDocument();
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it.each([409, 502])('HTTP %s errors are fixed and never echo provider data or retry', async status => {
    const fetch = vi.fn().mockResolvedValue(response({ error: 'invented raw detail' }, status));
    vi.stubGlobal('fetch', fetch);
    render(<RawDM token="fictional" />);
    fireEvent.change(input(), { target: { value: 'inventado' } });
    await userEvent.click(send());
    expect(await screen.findByRole('alert')).not.toHaveTextContent('invented raw detail');
    expect(screen.queryByRole('button', { name: 'Copiar DM' })).not.toBeInTheDocument();
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it('counts Unicode scalars, never truncates, and requires token and nonempty valid text', async () => {
    const fetch = vi.fn().mockResolvedValue(response(dm));
    vi.stubGlobal('fetch', fetch);
    const view = render(<RawDM />);
    fireEvent.change(input(), { target: { value: 'inventado' } });
    expect(send()).toBeDisabled();
    view.rerender(<RawDM token="fictional" />);
    for (const value of [' ', '\ud800', 'x\u0000', '🪁'.repeat(24001)]) {
      fireEvent.change(input(), { target: { value } });
      expect(send()).toBeDisabled();
      expect(input()).toHaveValue(value);
    }
    fireEvent.change(input(), { target: { value: '🪁'.repeat(24000) } });
    expect(send()).toBeEnabled();
    expect(fetch).not.toHaveBeenCalled();
  });
});
