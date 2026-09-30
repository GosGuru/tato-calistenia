import { useEffect, useRef, useState } from 'react';
import { Info, RefreshCw, Unplug, Wifi } from 'lucide-react';
import RealDM from './RealDM.jsx';
import RawDM from './RawDM.jsx';
import AppAuth, { localRequest, connectionMessage, validStatus } from './AppAuth.jsx';
import ModelSelector, { getSavedModelConfig } from './ModelSelector.jsx';
import * as Tabs from '@radix-ui/react-tabs';
import { SidebarProvider, SidebarTrigger } from './components/ui/sidebar';
import { Navigation } from './components/workspace/Navigation';
import { DraftMessage } from './components/workspace/DraftMessage';

const FAILED = 'No se pudo completar el par. No se muestran borradores. No hubo reintentos automáticos.';
const SIGNALS = [
  ['exact_previous', 'Igual al mensaje anterior'],
  ['same_opening', 'Mismos dos tokens iniciales'],
  ['shared_trigrams', 'Trigramas con mensaje anterior'],
  ['guidance_trigrams', 'Trigramas con orientación'],
];

function validPair(data, mode) {
  return data?.mode === mode && ['current', 'editorial'].every(variant =>
    typeof data.drafts?.[variant] === 'string' && data.drafts[variant].trim()
    && SIGNALS.every(([key], index) => index < 2
      ? typeof data.signals?.[variant]?.[key] === 'boolean'
      : Number.isInteger(data.signals?.[variant]?.[key]) && data.signals[variant][key] >= 0));
}

function signalValue(result, variant, key) {
  if (!result) return '—';
  const value = result.signals[variant][key];
  if (typeof value === 'boolean') return value ? 'Sí' : 'No';
  return value;
}

export default function App() {
  const [context, setContext] = useState(null);
  const [token, setToken] = useState(null);
  const connection = useRef({ epoch: 0, available: false, token: null });
  const [connectionEpoch, setConnectionEpoch] = useState(0);
  const [reconnecting, setReconnecting] = useState(false);
  const [recoveredStatus, setRecoveredStatus] = useState(null);
  const [retrieval, setRetrieval] = useState(null);
  // Client invalidation epoch, independent of the server's session revision.
  const [authEpoch, setAuthEpoch] = useState(0);
  const authTransition = useRef({ epoch: 0, pending: 0 });
  const [modelConfig, setModelConfig] = useState(getSavedModelConfig);
  const [connectionError, setConnectionError] = useState('');
  const [mode, setMode] = useState('real');
  const [result, setResult] = useState(null);
  const [status, setStatus] = useState('Cargando caso sintético…');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [consent, setConsent] = useState(false);
  const flight = useRef(false);
  const revision = useRef(0);
  const mounted = useRef(true);
  const confirmationRevision = useRef(null);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; revision.current += 1; };
  }, []);
  const confirmInput = useRef(null);
  const generateButton = useRef(null);
  const restoreFocus = useRef(false);

  function disconnect() {
    if (!mounted.current) return;
    connection.current.available = false;
    connection.current.token = null;
    connection.current.epoch += 1;
    revision.current += 1;
    confirmationRevision.current = null;
    setConnectionEpoch(connection.current.epoch);
    setReconnecting(false);
    setToken(null); setRecoveredStatus(null); setResult(null); setRetrieval(null);
    setConfirming(false); setConsent(false);
    setConnectionError(connectionMessage({ category: 'transport' }));
    setStatus('Sin resultados nuevos. Una llamada iniciada puede seguir en curso.');
  }

  async function reconnect(withStatus = true) {
    const epoch = ++connection.current.epoch;
    connection.current.available = false;
    connection.current.token = null;
    setConnectionEpoch(epoch); setToken(null); setRecoveredStatus(null);
    revision.current += 1; confirmationRevision.current = null;
    setResult(null); setConfirming(false); setConsent(false); setReconnecting(true);
    const current = () => mounted.current && connection.current.epoch === epoch;
    const options = { cache: 'no-store', credentials: 'omit', redirect: 'error' };
    try {
      const data = await localRequest('/api/bootstrap', options);
      if (data?.app !== 'tato-local' || data?.protocol !== 1 || typeof data.csrf_token !== 'string' || !data.csrf_token) throw new Error('bootstrap');
      if (!current()) return;
      connection.current.token = data.csrf_token;
      connection.current.available = true;
      setToken(data.csrf_token); setConnectionError('');
      // Status is optional for baseline generation and must not gate it.
      setReconnecting(false);
      if (withStatus) {
        const authVersion = authTransition.current.epoch;
        const state = await localRequest('/api/auth/status', options);
        if (!validStatus(state)) throw new Error('status');
        if (current() && authTransition.current.epoch === authVersion) setRecoveredStatus(state);
      }
    } catch (error) {
      if (current()) {
        if (error.category === 'transport') disconnect();
        setConnectionError(connectionMessage(error));
      }
    } finally { if (current()) setReconnecting(false); }
  }

  useEffect(() => { reconnect(false); }, []);

  useEffect(() => {
    if (mode !== 'synthetic' || context || !token || !connection.current.available) return;
    let active = true;
    const epoch = connection.current.epoch;
    const current = () => active && mounted.current && connection.current.epoch === epoch;
    localRequest('/api/context', { cache: 'no-store', credentials: 'omit', redirect: 'error' })
      .then(data => {
        if (!data?.csrf_token || !Array.isArray(data.messages) || !data.guidance) throw new Error('context');
        if (current()) { setContext(data); setStatus('Listo para explorar. Ninguna llamada realizada.'); }
      })
      .catch(error => {
        if (current()) {
          if (error.category === 'transport') disconnect();
          setError('No se pudo cargar el caso. ' + connectionMessage(error)); setStatus('');
        }
      });
    return () => { active = false; };
  }, [mode, context, connectionEpoch, token]);

  useEffect(() => {
    if (confirming) confirmInput.current?.focus();
    else if (restoreFocus.current) {
      generateButton.current?.focus();
      restoreFocus.current = false;
    }
  }, [confirming]);

  function beginAuthTransition() {
    const transition = authTransition.current;
    setRetrieval(null);
    transition.pending += 1;
    transition.epoch += 1;
    if (mounted.current) setAuthEpoch(transition.epoch);
    let settled = false;
    // Each request owns its settlement, including superseded or unmounted settings.
    return () => {
      if (settled) return;
      settled = true;
      transition.pending -= 1;
      transition.epoch += 1;
      if (mounted.current) setAuthEpoch(transition.epoch);
    };
  }

  function closeConfirmation() {
    restoreFocus.current = true;
    confirmationRevision.current = null;
    setConfirming(false);
    setConsent(false);
    setStatus('Confirmación cancelada. Sin borradores; no se inició una nueva llamada.');
  }

  async function run(mode) {
    if (!mounted.current || !token || !connection.current.available || flight.current || !context || (mode === 'codex'
      && (!consent || !confirming || confirmationRevision.current !== revision.current))) return;
    const version = ++revision.current;
    const current = () => mounted.current && revision.current === version;
    confirmationRevision.current = null;
    flight.current = true;
    setLoading(true);
    setResult(null);
    setError('');
    setConfirming(false);
    setConsent(false);
    setStatus(mode === 'codex' ? 'Generando el par completo… Puede tardar varios minutos.' : 'Preparando demo simulada…');
    try {
      const data = await localRequest(mode === 'codex' ? '/api/generate' : '/api/demo', {
        method: 'POST', cache: 'no-store', credentials: 'omit', redirect: 'error',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': connection.current.token },
        body: JSON.stringify(mode === 'codex' ? { consent: true } : {}),
      });

      if (!validPair(data, mode)) throw new Error('incomplete');
      if (current()) {
        setResult(data);
        setStatus('Par completo disponible. No se envió ningún mensaje.');
      }
    } catch (error) {
      if (current()) {
        if (error.category === 'transport') disconnect();
        setError(error.status === 409 ? 'Ya hay una comparación en curso. Esperá a que termine.' : FAILED + ' ' + connectionMessage(error));
      }
    } finally {
      flight.current = false;
      if (mounted.current) setLoading(false);
      if (current()) setStatus(value => value.startsWith('Par completo') ? value : 'Sin resultados nuevos.');
    }
  }

  return <SidebarProvider className="editorial-shell" data-workspace={mode === 'real' ? 'raw' : undefined}>
    <Tabs.Root className="workspace-root" orientation="vertical" value={mode} onValueChange={value => {
      revision.current += 1; confirmationRevision.current = null;
      setMode(value); setConfirming(false); setConsent(false); setResult(null);
      if (context) setError('');
      setStatus('Sin resultados. Cambiar de sección no garantiza cancelar una llamada iniciada.');
    }}>
    <Navigation mode={mode} />
    <main className="workspace-main">
      <header className="workspace-header">
        <SidebarTrigger aria-label="Alternar navegación" />
        <div className="header-title"><h1>{mode === 'real' ? 'Responder conversación' : mode === 'advanced' ? 'Revisión avanzada' : 'Tato · Laboratorio editorial'}</h1>
          <p>{mode === 'real' ? 'Pegá el historial. Recibí el próximo DM.' : mode === 'advanced' ? 'Revisá cada mensaje antes de compartirlo.' : 'Comparación ficticia, sin evidencia de mejora.'}</p></div>
        <div className="header-controls">
        <div className="connection-tools"><span className={`connection-state ${token ? 'available' : ''}`}>{token ? <Wifi aria-hidden="true" /> : <Unplug aria-hidden="true" />}{reconnecting ? 'Conectando…' : token ? 'Servidor local conectado' : 'Sin conexión local'}</span>
          <button type="button" disabled={reconnecting} onClick={() => reconnect()}><RefreshCw aria-hidden="true" />Reconectar</button></div>
        <ModelSelector modelConfig={modelConfig} onModelChange={setModelConfig} token={token} onDisconnect={disconnect} />
        <AppAuth workspace={mode} retrieval={retrieval} token={token} authTransition={authTransition} authEpoch={authEpoch} onChange={beginAuthTransition} connection={connection} connectionEpoch={connectionEpoch} onDisconnect={disconnect} recoveredStatus={recoveredStatus} />
        <details className="technical-details"><summary><Info aria-hidden="true" /><span>Detalles técnicos</span></summary>
          <div className="technical-body"><p>Interfaz local React + Vite. Modelo configurable (Codex CLI, DeepSeek, OpenRouter, Gemini, OpenCode y APIs compatibles) con claves guardadas localmente en navegador.</p>
          <p>Sin historial persistente ni herramientas externas. Cambiar de modo descarta la entrada actual; abrir Biblioteca o Modelos no.</p></div>
        </details>
        </div>
      </header>
      <div className="workspace-page">
      {connectionError && <p className="error" role="alert">{connectionError}</p>}
    <Tabs.Content value="real">{mode === 'real' && <>
      {!token && <p role="status">{connectionError || 'Cargando conexión local…'}</p>}
      <RawDM modelConfig={modelConfig} onRetrieval={setRetrieval} token={token} authRevision={authEpoch} authTransition={authTransition} connection={connection} connectionEpoch={connectionEpoch} onDisconnect={disconnect} />
    </>}</Tabs.Content>
    <Tabs.Content value="advanced">{mode === 'advanced' && <>
      {!token && <p role="status">{connectionError || 'Cargando conexión local…'}</p>}
      <RealDM modelConfig={modelConfig} token={token} connection={connection} connectionEpoch={connectionEpoch} onDisconnect={disconnect} />
    </>}</Tabs.Content>
    <Tabs.Content value="synthetic">{mode === 'synthetic' && <div className="workspace">
      <aside className="panel conversation" aria-labelledby="case-title">
        <div className="section-head"><h2 id="case-title">Caso sintético</h2><span className="badge muted">Brecha</span></div>
        <p className="subtle">Conversación ficticia y fija. El destino está claro; falta conocer el obstáculo.</p>
        <ol className="messages">{context?.messages.map((message, index) =>
          <li className={message.role === 'user' ? 'lead' : 'tato'} key={index}>
            <span className="speaker">{message.role === 'user' ? 'Prospecto ficticio' : 'Tato'}</span>
            <p>{message.text}</p>
          </li>)}</ol>
        <p className="footnote">Este comparador usa solo el caso ficticio fijo, sin chats reales ni archivos.</p>
      </aside>

      <section className="experiment" aria-label="Comparación editorial">
        <div className="panel controls">
          <p className="eyebrow">01 / EXPLORAR</p><h2>Dos variantes, una conversación</h2>
          <p>Actual conserva las reglas vigentes. Editorial suma solo orientación de voz, sin cambiar fase, seguridad ni oferta.</p>
          <div className="actions">
            <button type="button" className="primary" disabled={!token || !context || loading || confirming} onClick={() => run('simulated')}>Ver demo simulada</button>
            <button type="button" ref={generateButton} disabled={!token || !context || loading || confirming} onClick={() => {
              confirmationRevision.current = revision.current;
              setConsent(false); setConfirming(true); setResult(null); setError('');
              setStatus('Sin borradores. Confirmación pendiente; no se inició una nueva llamada.');
            }}>Generar con Codex Pro</button>
          </div>
          <p className="footnote">La demo usa borradores manuales de muestra, no salidas de un modelo ni evidencia de mejora.</p>
          {confirming && <section className="consent" aria-labelledby="consent-title" onKeyDown={event => {
            if (event.key === 'Escape') closeConfirmation();
          }}>
            <h3 id="consent-title">Confirmar generación real</h3>
            <p>Se harán dos llamadas a Codex. El caso sintético, las reglas actuales y el criterio editorial se transmitirán a OpenAI.</p>
            <p>Consume límites de tu suscripción ChatGPT/Codex. No se verificó tu cuenta ni se garantiza disponibilidad Pro. No envía mensajes ni guarda borradores.</p>
            <p>Localhost no aísla el host. La retención y la telemetría del proveedor o del CLI no están controladas por esta app.</p>
            <label><input ref={confirmInput} type="checkbox" checked={consent} onChange={event => setConsent(event.target.checked)} />
              Autorizo estas dos llamadas con entradas sintéticas.</label>
            <div className="actions"><button type="button" className="primary" disabled={!consent} onClick={() => run('codex')}>Confirmar dos llamadas</button>
              <button type="button" onClick={closeConfirmation}>Cancelar</button></div>
          </section>}
          <p role="status" className="status">{status}</p>
          {error && <p role="alert" className="error">{error}</p>}
        </div>

        <section aria-labelledby="draft-title" aria-busy={loading}>
          <div className="section-head results-head"><h2 id="draft-title">02 / Borradores</h2>
            <button type="button" className="quiet" disabled={loading || !result} onClick={() => {
              revision.current += 1; confirmationRevision.current = null;
              setConfirming(false); setConsent(false);
              setResult(null); setError(''); setStatus('Resultados borrados de esta pantalla.');
            }}>Limpiar resultados</button></div>
          {result && <p className={`result-label ${result.mode}`}>
            {result.mode === 'simulated' ? 'Demo simulada · borradores manuales' : 'Codex · caso sintético'}</p>}
          <div className="draft-grid">{[['current', 'DM actual'], ['editorial', 'DM editorial']].map(([variant, title]) =>
            <article className={`panel draft ${variant}`} key={variant}>
              <h3>{title}</h3><p className="subtle">{variant === 'current' ? 'Reglas actuales' : 'Mismas reglas + criterio de voz'}</p>
              {result ? <DraftMessage text={result.drafts[variant]} /> : <p className="placeholder">El borrador completo aparecerá acá.</p>}
              <h4>Señales mecánicas</h4>
              <dl className="signals">{SIGNALS.map(([key, label]) => <div key={key}><dt>{label}</dt>
                <dd>{signalValue(result, variant, key)}</dd></div>)}</dl>
            </article>)}</div>
          <p className="footnote">Estas señales no son puntajes de calidad. No eligen ganador ni prueban originalidad, seguridad o calidad de voz.</p>
        </section>

        <section className="panel guidance" aria-labelledby="guidance-title">
          <p className="eyebrow">03 / CRITERIO, NO PLANTILLA</p><h2 id="guidance-title">Orientación editorial</h2>
          <p>{context?.guidance.positive_voice || 'Cargando orientación…'}</p>
          <p className="avoid">{context?.guidance.negative_repetition}</p>
          <p className="footnote">Ficha sintética elegible solo para esta prueba. No es aprobación de producción ni aprendizaje humano aprobado.</p>
        </section>
      </section>
    </div>}</Tabs.Content>
    {mode !== 'real' && <footer>Modelo y esfuerzo desconocidos, no fijados por el runner. Sin historial persistente, Supabase ni conexión al setter.
      <br />Los borradores viven solo en memoria. El navegador, el sistema operativo y el proveedor tienen límites propios de privacidad.</footer>}
      </div>
    </main>
    </Tabs.Root>
  </SidebarProvider>;
}
