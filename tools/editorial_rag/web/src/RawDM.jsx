import React, { useEffect, useRef, useState } from 'react';
import { localRequest, connectionMessage } from './AppAuth.jsx';
import { Button } from './components/ui/button';
import { PromptInput, PromptInputTextarea, PromptInputFooter } from './components/ai-elements/prompt-input';
import { ArrowUp, Brain, Check, Compass, Copy, Eraser, Filter, Sparkles } from 'lucide-react';
import { StaticMarkdown } from './components/workspace/DraftMessage';
import { createCompletionSound } from './lib/completionSound';
import { getActiveProviderPayload, modelDisplayLabel, providerDisplayName } from './ModelSelector.jsx';
import LiquidOrb from './components/ui/LiquidOrb.jsx';

const THINKING_STAGES = [
  { id: 'context', icon: Compass, text: 'Analizando historial y contexto del prospecto…' },
  { id: 'eval', icon: Filter, text: 'Evaluando brecha, destino y directrices editoriales…' },
  { id: 'reason', icon: Brain, text: 'Sintetizando razonamiento y marco conversacional…' },
  { id: 'craft', icon: Sparkles, text: 'Pulso final: calibrando tono, ritmo y propuesta…' },
];

const FAILURE = 'No se pudo generar el DM. No se devolvió ningún borrador. Sin reintentos automáticos.';
const validText = value => typeof value === 'string' && !!value.trim()
  && [...value].length <= 24000 && [...value].every(char => {
    const code = char.codePointAt(0);
    return (code >= 32 || '\r\n\t'.includes(char)) && !(code >= 0xd800 && code <= 0xdfff);
  });
function validResult(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  const field = { dm: 'text', needs_context: 'question' }[value.type];
  return field && Object.keys(value).length === 2 && Object.hasOwn(value, field) && validText(value[field]);
}

function validEnvelope(value) {
  const retrieval = value?.retrieval;
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  const keys = Object.keys(value).sort().join(',');
  const validKeys = (keys === 'result,retrieval,revision' || keys === 'result,retrieval,revision,thinking');
  if (!validKeys) return false;
  if (value.thinking !== undefined && typeof value.thinking !== 'string') return false;
  return validResult(value.result) && Number.isSafeInteger(value.revision) && value.revision >= 0
    && retrieval && typeof retrieval === 'object' && !Array.isArray(retrieval)
    && Object.keys(retrieval).sort().join(',') === 'count,status'
    && Number.isInteger(retrieval.count)
    && (retrieval.status === 'supplied' ? retrieval.count >= 1 && retrieval.count <= 2
      : ['off', 'empty', 'expired', 'unavailable'].includes(retrieval.status) && retrieval.count === 0);
}

export default function RawDM({ token, modelConfig, authRevision = 0, authTransition, connection, connectionEpoch = 0, onDisconnect, onRetrieval, active = true }) {
  const [history, setHistory] = useState('');
  const [submittedHistory, setSubmittedHistory] = useState('');
  const [result, setResult] = useState(null);
  const [thinking, setThinking] = useState('');
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');
  const [stageIndex, setStageIndex] = useState(0);
  const [loading, setLoading] = useState(false);
  const [requestPending, setRequestPending] = useState(false);
  const revision = useRef(0);
  const flight = useRef(false);
  const copyRevision = useRef(0);
  const composing = useRef(false);
  const mounted = useRef(true);
  const completionSound = useRef(null);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false; revision.current += 1;
      completionSound.current?.dispose();
      completionSound.current = null;
    };
  }, []);

  const prevConnectionEpoch = useRef(connectionEpoch);
  const prevAuthRevision = useRef(authRevision);
  useEffect(() => {
    revision.current += 1;
    if (prevConnectionEpoch.current !== connectionEpoch) {
      prevConnectionEpoch.current = connectionEpoch;
      if (submittedHistory && !result) {
        setHistory(submittedHistory);
        setSubmittedHistory('');
      }
    }
    if (prevAuthRevision.current !== authRevision) {
      prevAuthRevision.current = authRevision;
      if (authTransition && !authTransition.current?.pending && submittedHistory) {
        setHistory(submittedHistory);
        setSubmittedHistory('');
      }
    }
    setResult(null); setThinking(''); setCopied(false); setError(''); setStatus('');
  }, [authRevision, connectionEpoch, active]);

  useEffect(() => {
    if (!loading) {
      setStageIndex(0);
      return;
    }
    const timer = setInterval(() => {
      setStageIndex(prev => (prev + 1) % THINKING_STAGES.length);
    }, 2200);
    return () => clearInterval(timer);
  }, [loading]);

  function change(value) {
    setHistory(value);
    if (submittedHistory) return;
    revision.current += 1;
    setCopied(false);
    setResult(null);
    setThinking('');
    setError('');
    setStatus('');
  }

  function reset() {
    revision.current += 1;
    setHistory(''); setSubmittedHistory(''); setResult(null); setThinking('');
    setCopied(false); setError(''); setStatus(''); setLoading(false);
  }

  function editSubmitted() {
    if (loading || !submittedHistory) return;
    revision.current += 1;
    setHistory(submittedHistory); setSubmittedHistory(''); setResult(null); setThinking('');
    setCopied(false); setError(''); setStatus('');
  }

  async function generate() {
    const targetHistory = validText(history) ? history : submittedHistory;
    if (!mounted.current || !active || connection?.current.available === false || authTransition?.current.pending || flight.current || !token || !validText(targetHistory)) return;
    completionSound.current ??= createCompletionSound();
    const playCompletion = completionSound.current.arm();
    const sentHistory = targetHistory;
    const version = ++revision.current;
    const authEpoch = authTransition?.current.epoch;
    const epoch = connection?.current.epoch;
    const current = () => mounted.current && revision.current === version
      && connection?.current.epoch === epoch && authTransition?.current.epoch === authEpoch;
    flight.current = true;
    setRequestPending(true);
    setSubmittedHistory(sentHistory);
    setHistory('');
    setLoading(true);
    setCopied(false);
    setResult(null);
    setThinking('');
    setError('');
    setStatus('Preparando el próximo DM…');
    const providerPayload = getActiveProviderPayload(modelConfig);
    const requestBody = {
      history: sentHistory,
      consent: true,
      ...(providerPayload && providerPayload.provider !== 'codex' ? { provider_config: providerPayload } : {}),
    };
    try {
      const data = await localRequest('/api/raw-draft', {
        method: 'POST', cache: 'no-store', credentials: 'omit', redirect: 'error',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': connection?.current.token ?? token },
        body: JSON.stringify(requestBody),
      });

      if (!validEnvelope(data)) throw Object.assign(new Error('result'), { category: 'invalid' });
      if (current()) {
        setResult(data.result);
        setThinking(data.thinking || '');
        onRetrieval?.(data.retrieval);
        setStatus(data.result.type === 'dm' ? 'Borrador disponible. No se envió ningún mensaje.' : 'Falta contexto. No se generó un DM.');
        if (data.result.type === 'dm') playCompletion();
      }
    } catch (error) {
      if (current()) {
        if (error.category === 'transport' || error.category === 'invalid') {
          setHistory(prev => {
            if (!prev) {
              setSubmittedHistory('');
              return sentHistory;
            }
            return prev;
          });
          if (error.category === 'transport') onDisconnect?.();
        }
        setError(error.status === 409 ? 'Solicitud ocupada o sesión cambiada/vencida. No se devolvió ningún borrador.' : FAILURE + ' ' + connectionMessage(error));
        setStatus('Sin resultado nuevo.');
      }
    } finally {
      flight.current = false;
      if (mounted.current) { setRequestPending(false); setLoading(false); }
    }
  }

  async function copy() {
    if (result?.type !== 'dm') return;
    if (connection?.current.available === false || authTransition?.current.pending) return;
    const version = revision.current;
    const attempt = ++copyRevision.current;
    const authEpoch = authTransition?.current.epoch;
    const epoch = connection?.current.epoch;
    const current = () => mounted.current && revision.current === version && copyRevision.current === attempt
      && connection?.current.epoch === epoch && authTransition?.current.epoch === authEpoch;
    setCopied(false); setError('');
    try {
      await navigator.clipboard.writeText(result.text);
      if (current()) { setCopied(true); setStatus('DM copiado. No se envió.'); }
    } catch {
      if (current()) { setStatus(''); setError('No se pudo copiar el DM.'); }
    }
  }

  const hasResponse = !!(submittedHistory || result || error || status || loading);
  return <section className="raw-composer" data-state={hasResponse ? 'response' : 'start'} aria-label="Preparar un DM" aria-busy={requestPending}>
    {!hasResponse && <div className="conversation-start"><h2>Qué conversación preparamos?</h2></div>}
    {hasResponse && <div className="raw-thread" aria-label="Intercambio actual">
    {submittedHistory && <section className="raw-submitted response-enter-up" aria-label="Historial enviado para preparar el DM">
      <div className="raw-submitted-heading"><span>Tu historial</span><Button type="button" variant="ghost" disabled={loading} onClick={editSubmitted}>Editar historial</Button></div>
      <div className="raw-submitted-text" role="region" aria-label="Historial enviado completo" tabIndex={0}>{submittedHistory}</div>
    </section>}
    {hasResponse && <section className={`raw-panel raw-draft-panel ${loading ? 'is-loading' : ''}`} aria-label="Borrador">
      {!loading && <div className="raw-panel-heading"><h2>{result?.type === 'needs_context' ? 'Aclaración pendiente' : 'Borrador'}</h2><span className="footnote">Revisión manual</span></div>}
      <div role="status" className="status">
        {loading && (
          <span className="generation-mark" aria-hidden="true">
            <LiquidOrb size={40} />
            <span>T</span>
            <i />
          </span>
        )}
        {loading ? (
          <span className="generation-copy">
            <strong>{status}</strong>
            <div className="thinking-stage-row" aria-hidden="true">
              <span className="thinking-stage-icon">
                {React.createElement(THINKING_STAGES[stageIndex].icon, { className: 'stage-lucide-icon' })}
              </span>
              <span className="shimmer-text">{THINKING_STAGES[stageIndex].text}</span>
            </div>
            <small>Este historial se usa para preparar una respuesta. No se envía a Instagram.</small>
          </span>
        ) : (
          status
        )}
      </div>
      {error && <p role="alert" className="error">{error}</p>}
      {thinking && !loading && (
        <details className="thinking-accordion" open>
          <summary className="thinking-summary">
            <div className="thinking-summary-title">
              <Brain className="thinking-summary-icon" aria-hidden="true" />
              <span>Razonamiento y pensamiento del modelo</span>
            </div>
            <span className="thinking-badge">Proceso analítico</span>
          </summary>
          <div className="thinking-content" role="region" aria-label="Razonamiento interno del modelo">
            <StaticMarkdown text={thinking} />
          </div>
        </details>
      )}
      {result && <div className="raw-draft-scroll response-enter" role="region" aria-label="Borrador completo" tabIndex={0}>
        {result?.type === 'needs_context' && <section aria-label="Aclaración para quien opera">
          <h3>Falta contexto para preparar el DM</h3><p className="draft-text">{result.question}</p>
          <p>Completá o aclará el historial antes de volver a generar. Esto no es un DM para enviar.</p>
        </section>}
        {result?.type === 'dm' && <section aria-label="DM para revisar"><StaticMarkdown text={result.text} /></section>}
      </div>}
      <div className="raw-copy-footer">
        {result?.type === 'dm' && <Button type="button" variant="ghost" onClick={copy}>{copied ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />}Copiar DM</Button>}
      </div>
    </section>}
    </div>}
    <section className="raw-panel raw-input-panel" aria-label="Historial preparado">
    <label htmlFor="raw-history">Historial completo</label>
    <PromptInput className="history-composer">
    <PromptInputTextarea id="raw-history" rows={2} value={history} autoComplete="off" spellCheck={false} aria-describedby="raw-disclosure" placeholder="Pegá el historial completo, sin separar autores…"
      onChange={event => change(event.target.value)}
      onCompositionStart={() => { composing.current = true; }} onCompositionEnd={() => { composing.current = false; }}
      onKeyDown={event => {
        if (event.key !== 'Enter' || event.shiftKey) return;
        if (composing.current || event.nativeEvent.isComposing || event.nativeEvent.keyCode === 229) return;
        event.preventDefault();
        if (!event.repeat) generate();
      }} />
    <PromptInputFooter className="raw-action-footer">
      <span className="composer-hint">Enter genera · Shift+Enter nueva línea</span>
      <div className="actions">
      <Button type="button" variant="ghost" onClick={reset}><Eraser aria-hidden="true" />Limpiar</Button>
      <Button type="button" className="primary generate-draft" aria-label="Generar borrador" title="Generar borrador" aria-describedby="raw-disclosure" disabled={!token || connection?.current.available === false || !!authTransition?.current.pending || requestPending || (!validText(history) && !validText(submittedHistory))} onClick={generate}><ArrowUp aria-hidden="true" /><span>{modelConfig && modelConfig.provider !== 'codex' ? `Generar con ${modelDisplayLabel(modelConfig)}` : 'Generar con Codex'}</span></Button>
      </div>
    </PromptInputFooter>
    </PromptInput>
    </section>
    <div className="raw-caption">
      <p id="raw-disclosure">{modelConfig && modelConfig.provider !== 'codex' ? `Al generar, autorizás una llamada a ${providerDisplayName(modelConfig.provider)} con el historial completo. No se envía a Instagram.` : 'Al generar, autorizás una llamada a OpenAI con el historial completo. No se envía a Instagram.'}</p>
      {requestPending && !loading && <p role="status">La solicitud anterior sigue en curso. Esperá para generar otra.</p>}
      <div className="raw-metadata"><span>{[...history].length} / 24.000 caracteres Unicode</span></div>
      {history && !validText(history) && <p className="error">Usá texto no vacío, sin controles inválidos y hasta 24.000 caracteres.</p>}
    </div>
  </section>;
}
