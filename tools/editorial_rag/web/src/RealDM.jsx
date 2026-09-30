import { useEffect, useRef, useState } from 'react';
import { localRequest, connectionMessage } from './AppAuth.jsx';
import * as Dialog from '@radix-ui/react-dialog';
import ChatReview from './components/ChatReview.jsx';
import { DraftMessage } from './components/workspace/DraftMessage';
import { PromptInput, PromptInputTextarea } from './components/ai-elements/prompt-input';
import { parseManychat, validateBlocks, organizationBlocks, applyAssignments, draftMessages, canDraft, count } from './manychatHistory.js';

export default function RealDM({ token, connection, connectionEpoch = 0, onDisconnect }) {
  const [history, setHistory] = useState('');
  const [blocks, setBlocks] = useState([]);
  const [step, setStep] = useState(1);
  const [sourceReviewed, setSourceReviewed] = useState(false);
  const [reviewed, setReviewed] = useState(false);
  const [confirming, setConfirming] = useState(null);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [calls, setCalls] = useState(0);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('Todavía no se transmitió ningún historial.');
  const revision = useRef(0), mounted = useRef(true), flight = useRef(false);
  const returnFocus = useRef(null), cancel = useRef(null);
  const confirmationEpoch = useRef(null);
  const issue = validateBlocks(blocks);
  const ready = canDraft(blocks);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; revision.current += 1; };
  }, []);
  useEffect(() => {
    revision.current += 1;
    confirmationEpoch.current = null;
    setDraft(''); setConfirming(null); setError('');
  }, [connectionEpoch]);
  function invalidate() {
    revision.current += 1;
    confirmationEpoch.current = null;
    setReviewed(false); setSourceReviewed(false); setDraft(''); setConfirming(null); setError('');
    setStatus('Cambios locales pendientes de revisión. Una llamada iniciada puede seguir en curso.');
  }
  function changeBlocks(next) { invalidate(); setBlocks(next); }
  function clear() {
    invalidate(); setHistory(''); setBlocks([]); setStep(1);
    // Keep attempted call count truthful even if a request is still running.
    setStatus('Pantalla limpia. No garantiza cancelar llamadas ya iniciadas ni borrar memoria del sistema.');
  }
  function parse() {
    invalidate();
    try { setBlocks(parseManychat(history).blocks); setStep(2); setStatus('Separación local lista. Revisá autores, fechas y avisos. Cero llamadas para separar.'); }
    catch (e) { setBlocks([]); setError(e.message); }
  }
  function open(kind, target) {
    confirmationEpoch.current = connection?.current.epoch;
    returnFocus.current = target; setDraft(''); setError(''); setConfirming(kind);
  }
  function close() { confirmationEpoch.current = null; setConfirming(null); setStatus('Confirmación cancelada. No se inició otra llamada.'); }
  async function run() {
    const kind = confirming;
    if (!kind || !token || confirmationEpoch.current !== connection?.current.epoch
      || connection?.current.available === false || flight.current || (kind === 'organize' ? !sourceReviewed || issue : !reviewed || !ready)) return;
    confirmationEpoch.current = null;
    const snapshot = blocks;
    const version = ++revision.current;
    flight.current = true; setBusy(true); setConfirming(null); setError(''); setDraft('');
    setCalls(n => n + 1);
    setStatus(kind === 'organize' ? 'Organizando autores… No se genera un DM automáticamente.' : 'Generando un DM… No se envía al prospecto.');
    const epoch = connection?.current.epoch;
    const current = () => mounted.current && revision.current === version && connection?.current.epoch === epoch;
    const body = kind === 'organize' ? { blocks: organizationBlocks(snapshot), reviewed: true, consent: true }
      : { messages: draftMessages(snapshot), reviewed: true, consent: true };
    try {
      const data = await localRequest(`/api/${kind}`, {
        method: 'POST', cache: 'no-store', credentials: 'omit', redirect: 'error',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': connection?.current.token ?? token }, body: JSON.stringify(body),
      });

      if (kind === 'organize') {
        const next = applyAssignments(snapshot, data);
        if (current()) {
          setBlocks(next); setReviewed(false); setSourceReviewed(false);
          setStatus('Organización recibida como propuesta. Confirmá los roles inciertos y revisá toda la conversación antes de generar.');
        }
      } else {
        if (!data || Object.keys(data).join() !== 'draft' || typeof data.draft !== 'string' || !data.draft.trim()) throw new Error('draft');
        if (current()) { setDraft(data.draft); setStatus('Revisá el DM antes de copiarlo. No se envió ningún mensaje.'); }
      }
    } catch (error) {
      if (current()) {
        if (error.category === 'transport') onDisconnect?.();
        setError(error.status === 409 ? 'Ya hay una organización, generación o comparación en curso. Esperá a que termine.' : 'No se pudo completar la solicitud. No hubo reintentos automáticos ni resultados parciales. ' + connectionMessage(error));
        setStatus('Sin resultado nuevo.');
      }
    } finally {
      flight.current = false;
      if (mounted.current) setBusy(false);
    }
  }
  async function copy() {
    if (!draft || connection?.current.available === false) return;
    const version = revision.current;
    const epoch = connection?.current.epoch;
    let text;
    try { await navigator.clipboard.writeText(draft); text = 'DM copiado. No se envió ningún mensaje.'; }
    catch { text = 'No se pudo copiar. Seleccioná el DM y copialo manualmente.'; }
    if (mounted.current && revision.current === version && connection?.current.epoch === epoch) setStatus(text);
  }
  return <section className="real-dm" aria-labelledby="real-title">
    <div className="flow-heading"><div><p className="eyebrow">CONVERSACIÓN / REVISIÓN HUMANA</p><h2 id="real-title">Un chat claro. Una respuesta.</h2></div>
      <button className="quiet" onClick={clear}>Limpiar conversación</button></div>
    <ol className="stepper" aria-label="Pasos"><li aria-current={step === 1 ? 'step' : undefined}>1 · Pegar</li>
      <li aria-current={step === 2 && !reviewed ? 'step' : undefined}>2 · Revisar</li><li aria-current={reviewed ? 'step' : undefined}>3 · Responder</li></ol>
    {step === 1 ? <section className="panel paste-panel">
      <h3>Pegá la conversación de ManyChat</h3><p className="subtle" id="history-help">Del mensaje más antiguo al más reciente. Los párrafos se separan automáticamente; no necesitás formatear etiquetas.</p>
      <label htmlFor="real-history">Historial revisable</label>
      <PromptInput className="advanced-composer"><PromptInputTextarea id="real-history" value={history} onChange={e => { invalidate(); setHistory(e.target.value); setBlocks([]); }}
        aria-describedby="history-help history-limits" autoComplete="off" spellCheck={false} placeholder="Pegá acá el historial completo…" /></PromptInput>
      <div className="composer-footer"><p id="history-limits" className="footnote">{count(history)} / 24.000 caracteres Unicode · 100 mensajes · 4.000 por mensaje</p>
        <button className="primary" disabled={!history.trim()} onClick={parse}>Revisar conversación</button></div>
      <p className="privacy-note">Solo en memoria de esta pantalla. Pegar y separar no transmite el chat ni consulta enlaces.</p>
    </section> : <div className="review-layout">
      <section className="panel conversation-panel"><div className="section-head"><h3>Conversación organizada</h3>
        <button className="quiet" onClick={() => { invalidate(); setBlocks([]); setStep(1); }}>Volver al pegado</button></div>
        <p className="subtle">Confirmá quién habla. Ni la alternancia ni las pausas prueban el autor. Las fechas conservan el texto original.</p>
        <ChatReview blocks={blocks} onChange={changeBlocks} />
      </section>
      <aside className="response-sidebar">
        <section className="panel optional-panel"><p className="eyebrow">OPCIONAL / 1 LLAMADA</p><h3>Ayuda para ordenar autores</h3>
          <p className="subtle">Codex propone roles, sin reescribir mensajes. Podés omitir este paso y asignarlos vos.</p>
          <label className="review-label"><input type="checkbox" checked={sourceReviewed} disabled={busy}
            onChange={e => { revision.current += 1; setSourceReviewed(e.target.checked); setConfirming(null); }} />
            Revisé los datos de los mensajes visibles y permito compartirlos; retiré identificadores y datos sensibles innecesarios.</label>
          <button disabled={!token || !!issue || !sourceReviewed || busy} onClick={e => open('organize', e.currentTarget)}>Organizar con Codex</button>
        </section>
        <section className="panel draft-panel"><p className="eyebrow">3 / PRÓXIMO DM · 1 LLAMADA</p><h3>Prepará la respuesta</h3>
          <label className="review-label"><input type="checkbox" checked={reviewed} disabled={busy || !ready}
            onChange={e => { revision.current += 1; setReviewed(e.target.checked); setDraft(''); setConfirming(null); }} />
            Revisé la conversación completa, sus roles, fechas y los datos que permito compartir, incluidas las propuestas de Codex.</label>
          {!ready && <p className="footnote">{issue || 'Resolvé los roles pendientes y verificá los límites incluyendo el contexto de fechas antes de generar.'}</p>}
          <button className="primary" disabled={!token || !ready || !reviewed || busy} onClick={e => open('draft', e.currentTarget)}>Generar respuesta</button>
          {draft ? <section aria-label="Próximo DM"><h3>Próximo DM · borrador</h3><DraftMessage text={draft} /><button onClick={copy}>Copiar DM</button>
            <p className="footnote">Copiar no envía. Revisá y enviá manualmente.</p></section> : <p className="placeholder">Tu próximo DM aparecerá acá, solo después de confirmar.</p>}
        </section>
      </aside>
    </div>}
    <p role="status" className="status">{status}</p>{error && <p role="alert" className="error">{error}</p>}
    <p className="footnote">Solicitudes confirmadas en esta pantalla: {calls}. Separar localmente = 0; organizar con Codex = 1; generar DM = otra 1.
      Un fallo o conflicto puede no ejecutar el modelo; la app no verifica cuota consumida.</p>
    <details className="privacy-details"><summary>Privacidad y límites</summary><p>No hay anonimización automática, RAG, fichas editoriales, registro ni envíos automáticos.
      La app no guarda chats ni borradores. Navegador, sistema operativo, portapapeles y proveedor tienen límites propios.
      Codex no es hermético ni offline; no se garantiza retención cero. Limpiar, salir o cambiar de sección no garantiza cancelar llamadas iniciadas.</p></details>
    <Dialog.Root open={!!confirming} onOpenChange={open => { if (!open) close(); }}>
      <Dialog.Portal><div className="dialog-overlay" aria-hidden="true" />
        <Dialog.Content className="dialog-content" onOpenAutoFocus={e => { e.preventDefault(); cancel.current?.focus(); }}
          onCloseAutoFocus={e => { e.preventDefault(); returnFocus.current?.focus(); }}>
          <Dialog.Title>{confirming === 'organize' ? 'Confirmar organización opcional' : 'Confirmar generación del próximo DM'}</Dialog.Title>
          <Dialog.Description>{confirming === 'organize'
            ? 'Se transmitirán solo los mensajes activos revisados y sus fechas a OpenAI/Codex para UNA llamada de organización. No incluye avisos separados ni el pegado crudo. No genera un DM después.'
            : 'Se transmitirán los mensajes revisados, sus fechas y las siete reglas completas a OpenAI/Codex para UNA llamada. Devuelve un único DM, sin envío automático.'}</Dialog.Description>
          <p>Consume cuota de ChatGPT/Codex. Los roles propuestos no son atribuciones verificadas; pueden necesitar corrección.</p>
          <p>La app no guarda el chat. La retención del proveedor/CLI y el acceso no hermético al host quedan fuera de su control. No es una garantía de retención cero.</p>
          <p>Limpiar, cambiar de sección o cerrar no garantiza cancelar una llamada ya iniciada.</p>
          <div className="actions"><button className="primary" onClick={run}>Confirmar una llamada</button><Dialog.Close asChild><button ref={cancel}>Cancelar</button></Dialog.Close></div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  </section>;
}
