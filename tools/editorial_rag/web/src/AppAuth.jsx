import { useEffect, useRef, useState } from 'react';
import { BookOpen, LogOut, Plug, RefreshCw, ShieldCheck, X } from 'lucide-react';

const options = { cache: 'no-store', credentials: 'omit', redirect: 'error' };
export async function localRequest(url, options) {
  let response;
  try { response = await fetch(url, options); }
  catch { throw Object.assign(new Error('transport'), { category: 'transport' }); }
  if (!response.ok) {
    const allowed = ['ok', 'not_run', 'timeout', 'unavailable', 'rejected', 'nonzero', 'invalid', 'internal'];
    const diagnostics = response.headers?.get('X-Tato-Diagnostics') === '1'
      ? ['Retrieval', 'Rules', 'Packet', 'Login', 'Exec', 'Stream', 'Raw-Result']
        .map(stage => response.headers.get(`X-Tato-${stage}-Outcome`))
        .find(value => allowed.includes(value) && !['ok', 'not_run'].includes(value)) : null;
    throw Object.assign(new Error('http'), { category: 'http', status: response.status, diagnostic: diagnostics });
  }
  try { return await response.json(); }
  catch (error) {
    const transport = error instanceof TypeError
      || (error instanceof DOMException && error.name === 'AbortError');
    throw Object.assign(new Error(transport ? 'transport' : 'json'), {
      category: transport ? 'transport' : 'invalid',
    });
  }
}

export function connectionMessage(error) {
  if (error?.category === 'transport') return 'No se pudo contactar al servidor local. Abrí start_app.cmd y usá Reconectar. Una solicitud iniciada puede seguir en curso; no se reintenta.';
  if (error?.category === 'http') {
    if (error.diagnostic === 'timeout') return 'El servidor informó un tiempo de espera agotado. Revisá el diagnóstico antes de volver a generar; no se reintenta.';
    if (error.diagnostic === 'rejected' || error.diagnostic === 'unavailable') return 'El servidor informó que un requisito no está disponible o fue rechazado. Revisá la sesión de Codex antes de volver a generar.';
    if (error.diagnostic === 'nonzero') return 'El servidor informó que el proceso terminó con error. Revisá el diagnóstico antes de generar otra vez; no se reintenta.';
    if (error.diagnostic === 'invalid') return 'El servidor rechazó un formato de generación. Revisá el diagnóstico antes de otro clic; no se reintenta.';
    if (error.diagnostic === 'internal') return 'El servidor informó un fallo interno. Revisá los requisitos locales antes de otro clic; no se reintenta.';
    return `El servidor respondió HTTP ${Number.isInteger(error.status) ? error.status : 0}. Revisá la solicitud o usá Reconectar; no se reintenta.`;
  }
  return 'La respuesta local no tiene el formato esperado. Usá Reconectar antes de volver a intentar.';
}

export function validStatus(value) {
  return value && typeof value === 'object' && !Array.isArray(value)
    && Object.keys(value).sort().join(',') === 'connected,count,empty,revision'
    && typeof value.connected === 'boolean' && typeof value.empty === 'boolean'
    && Number.isInteger(value.count) && value.count >= 0 && value.count <= 50
    && Number.isSafeInteger(value.revision) && value.revision >= 0
    && value.empty === (value.connected && value.count === 0)
    && (value.connected || value.count === 0);
}

export default function AppAuth({ token, onChange, connection, connectionEpoch = 0, onDisconnect, recoveredStatus, authTransition, authEpoch, workspace, retrieval }) {
  const [open, setOpen] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [message, setMessage] = useState('Biblioteca opcional. Podés generar sin conectarla.');
  const [busy, setBusy] = useState(false);
  const [observedCount, setObservedCount] = useState(null);
  const [verified, setVerified] = useState(false);
  const [persistence, setPersistence] = useState(null);
  const detailsRef = useRef(null);
  const metadataRevision = useRef(0);
  useEffect(() => {
    if (detailsRef.current) detailsRef.current.open = false;
    setOpen(false); setEmail(''); setPassword('');
  }, [workspace]);
  const revision = useRef(0);
  const mounted = useRef(true);
  const flight = useRef(false);
  const observedAuthEpoch = useRef(authEpoch);
  const displayedAuthEpoch = useRef(null);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; revision.current += 1; };
  }, []);

  useEffect(() => {
    setEmail(''); setPassword(''); setObservedCount(null); setVerified(false); setPersistence(null);
    setMessage(token ? 'Biblioteca opcional. Consultá el estado actual.' : 'Estado de biblioteca no verificado. Reconectá el servidor local.');
  }, [connectionEpoch]);
  useEffect(() => { if (recoveredStatus) show(recoveredStatus); }, [recoveredStatus]);

  useEffect(() => {
    const changed = observedAuthEpoch.current !== authEpoch;
    observedAuthEpoch.current = authEpoch;
    // Remounted controls may not own the POST result. Reconcile with a GET only
    // after every parent-owned Auth operation has settled; never gate baseline.
    if (changed && open && token && !authTransition?.current.pending
      && displayedAuthEpoch.current !== authEpoch && connection?.current.available !== false) refresh();
  }, [authEpoch]);

  function show(data, settling = false) {
    if (!validStatus(data)) throw new Error('status');
    setObservedCount(data.connected ? data.count : null);
    setVerified(true);
    displayedAuthEpoch.current = authTransition ? authTransition.current.epoch + (settling ? 1 : 0) : null;
    setMessage(data.connected ? data.empty ? 'Biblioteca conectada, sin criterios disponibles.'
      : 'Biblioteca conectada. Los criterios se consultan al generar.' : 'Biblioteca desconectada.');
  }

  async function loadPersistence() {
    const version = ++metadataRevision.current;
    const epoch = connection?.current.epoch;
    const authVersion = authTransition?.current.epoch;
    const current = () => mounted.current && version === metadataRevision.current
      && epoch === connection?.current.epoch && authVersion === authTransition?.current.epoch;
    try {
      const data = await localRequest('/api/auth/persistence', options);
      if (Object.keys(data ?? {}).sort().join(',') !== 'enabled,problem,remembered'
        || !['enabled', 'remembered', 'problem'].every(key => typeof data[key] === 'boolean')
        || (data.remembered && (!data.enabled || data.problem))) throw new Error('metadata');
      if (current()) setPersistence(data);
    } catch (error) {
      // Optional HTTP/format failures are harmless; current transport loss invalidates the connection.
      if (current()) {
        if (error.category === 'transport') onDisconnect?.();
        setPersistence(error.status === 404 ? 'inactive' : null);
      }
    }
  }

  async function refresh() {
    loadPersistence();
    const version = revision.current;
    const epoch = connection?.current.epoch;
    const authVersion = authTransition?.current.epoch;
    const current = () => mounted.current && version === revision.current && epoch === connection?.current.epoch
      && authVersion === authTransition?.current.epoch;
    try {
      const data = await localRequest('/api/auth/status', options);
      if (current()) show(data);
    } catch (error) {
      if (current()) {
        if (error.category === 'transport') onDisconnect?.();
        setObservedCount(null); setVerified(false);
        setMessage(connectionMessage(error));
      }
    }
  }

  async function change(connect) {
    if (!token || connection?.current.available === false || (connect && flight.current)) return;
    const version = ++revision.current;
    const epoch = connection?.current.epoch;
    const current = () => mounted.current && version === revision.current && epoch === connection?.current.epoch;
    flight.current = true;
    setBusy(true); setObservedCount(null); setVerified(false); setPersistence(null);
    metadataRevision.current += 1;
    const settle = onChange();
    // Only the outbound request retains credentials until the attempt completes.
    const body = connect ? JSON.stringify({ email, password }) : '{}';
    setEmail(''); setPassword('');
    setMessage(connect ? 'Conectando biblioteca…' : 'Desconectando biblioteca…');
    try {
      const data = await localRequest(connect ? '/api/auth/login' : '/api/auth/logout', {
        ...options, method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': connection?.current.token ?? token }, body,
      });
      if (current()) show(data, true);
    } catch (error) {
      const live = current();
      // Auth owns parent settlement even after its controls disappear. A newer
      // connection epoch still supersedes this request completely.
      if (error.category === 'transport' && epoch === connection?.current.epoch
        && (live || !mounted.current)) onDisconnect?.();
      if (live) setMessage('No se pudo completar el cambio de sesión. ' + connectionMessage(error));
    } finally {
      // Closing/navigating only removes UI; it does not cancel the Auth request.
      // Parent settlement must not depend on this component's liveness/version.
      settle?.();
      if (mounted.current && version === revision.current) {
        flight.current = false; setBusy(false);
        loadPersistence();
      }
    }
  }

  return <details ref={detailsRef} className="privacy-details library-settings" onToggle={event => {
    const expanded = event.currentTarget.open;
    setOpen(expanded);
    if (expanded) refresh();
    else { setEmail(''); setPassword(''); }
  }}>
    <summary aria-label="Biblioteca"><BookOpen aria-hidden="true" /><span>Biblioteca</span><span className="library-summary-state">{observedCount !== null ? `${observedCount} disponibles` : verified ? 'Desconectada' : 'Sin verificar'}</span></summary>
    {open && <section className="library-body" aria-label="Biblioteca editorial" onKeyDown={event => {
      if (event.key === 'Escape') {
        const details = event.currentTarget.closest('details');
        details.open = false;
        details.querySelector('summary')?.focus();
        setOpen(false); setEmail(''); setPassword('');
      }
    }}>
      <p className="eyebrow">CRITERIOS / CONEXIÓN OPCIONAL</p>
      <div className="section-head"><h2>Biblioteca editorial</h2><button type="button" className="quiet" onClick={event => {
        const details = event.currentTarget.closest('details');
        details.open = false;
        details.querySelector('summary')?.focus();
        setOpen(false); setEmail(''); setPassword('');
      }}><X aria-hidden="true" />Cerrar biblioteca</button></div>
      {observedCount !== null && <p className="library-count"><ShieldCheck aria-hidden="true" />{observedCount} criterios disponibles</p>}
      <p>Disponibles no significa aplicados. La biblioteca es opcional; no modifica las reglas actuales.</p>
      {observedCount === null && <>
      <p>Usá tu cuenta existente de EDITORIAL SUPABASE.</p>
      <p>No uses credenciales de ChatGPT ni Instagram. Esta conexión es opcional.</p>
      <label htmlFor="editorial-email">Email editorial</label>
      <input id="editorial-email" type="email" autoComplete="off" value={email} maxLength={320}
        onChange={event => setEmail(event.target.value)} />
      <label htmlFor="editorial-password">Contraseña editorial</label>
      <input id="editorial-password" type="password" autoComplete="off" value={password} maxLength={4096}
        onChange={event => setPassword(event.target.value)} />
      </>}
      <div className="actions">
        {observedCount === null && <button type="button" disabled={!token || busy || !email || !password} onClick={() => change(true)}><Plug aria-hidden="true" />Conectar</button>}
        <button type="button" disabled={!token} onClick={() => change(false)}><LogOut aria-hidden="true" />Desconectar</button>
        <button type="button" disabled={busy} onClick={refresh}><RefreshCw aria-hidden="true" />Consultar estado</button>
      </div>
      <p role="status">{message}</p>
      <p className="persistence-state">{persistence === 'inactive' || persistence?.enabled === false
        ? 'Persistencia no activada en este servidor. Requiere un reinicio coordinado posterior; no se realizó desde esta UI.'
        : persistence?.problem ? 'No se pudo guardar o quitar la sesión recordada. No se confirma persistencia; revisá el almacenamiento local.'
        : persistence?.remembered ? 'Sesión recordada con cifrado para tu usuario de Windows.'
        : persistence?.enabled ? 'Al conectar, el servidor intentará recordar la sesión cifrada. Todavía no hay una sesión recordada verificada.'
        : 'Persistencia sin verificar. No se confirma una sesión guardada.'}</p>
      <details className="privacy-details"><summary>Privacidad y límites</summary>
        <p>Generar con Codex autoriza una llamada a OpenAI con el historial completo y las siete reglas actuales; consume límites de tu sesión. No envía a Instagram. No hay anonimización ni reintentos automáticos. Revisá y quitá datos sensibles innecesarios.</p>
        <p>El historial no se recorta ni reorganiza. Historial y borradores viven solo en memoria. La retención y telemetría de OpenAI/CLI quedan fuera del control de esta app. Localhost no aísla el host; no se garantiza retención cero ni borrado seguro.</p>
        <p>Editar, limpiar o cambiar de modo no garantiza cancelar una llamada iniciada ni recuperar cuota. Modelo y esfuerzo desconocidos, no fijados por el runner.</p>
        <p>La función de sesión recordada guarda solo el token de renovación cifrado mediante DPAPI del usuario actual, fuera del repositorio y navegador. No guarda contraseña, email, historial ni borradores. No promete ingreso permanente; Windows, el disco o la sesión remota pueden impedir restaurarla.</p>
        <p>Desconectar quita la copia local cuando el almacenamiento lo permite; no cierra sesiones de Supabase, MCP ni Codex. No existe respaldo en texto plano ni alternativa para otros sistemas operativos.</p>
      </details>
      <details className="privacy-details"><summary>Criterios y fuentes</summary>
        <p>La biblioteca recibe solicitudes de lectura, nunca la conversación ni sus vectores. La búsqueda semántica es local. RAG aporta hasta dos criterios condicionales, no plantillas. Sin biblioteca se usan solo las reglas actuales.</p>
        <p>Seleccionar o aprobar criterios no está disponible en esta UI. La API informa estado y cantidad, no identifica fuentes ni demuestra aplicación.</p>
        <p>{retrieval ? retrieval.status === 'supplied' ? `${retrieval.count} criterios aportados, no necesariamente aplicados.` : `Última generación: sin criterios aportados (${retrieval.status}).` : 'Sin datos de criterios para esta generación.'}</p>
      </details>
    </section>}
  </details>;
}
