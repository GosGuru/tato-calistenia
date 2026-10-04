import { useEffect, useState } from 'react';
import {
  AlertCircle,
  Bot,
  CheckCircle2,
  CheckSquare,
  Clock,
  ExternalLink,
  Filter,
  Loader2,
  Play,
  RefreshCw,
  Send,
  ShieldCheck,
  Square,
  User,
} from 'lucide-react';
import { localRequest } from './AppAuth.jsx';
import { getActiveProviderPayload } from './ModelSelector.jsx';

export default function FollowUpWorkspace({ token, modelConfig, onDisconnect }) {
  const [browserStatus, setBrowserStatus] = useState({ active: false, logged_in: false });
  const [connectingBrowser, setConnectingBrowser] = useState(false);
  const [scanning, setScanning] = useState(false);
  const [sendingBatch, setSendingBatch] = useState(false);
  const [leads, setLeads] = useState([]);
  const [dateFilter, setDateFilter] = useState('septiembre');
  const [limit, setLimit] = useState(20);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');

  // Fetch browser status
  async function checkBrowserStatus() {
    try {
      const data = await localRequest('/api/manychat/status', {
        headers: { 'X-CSRF-Token': token },
      });
      setBrowserStatus(data);
    } catch (e) {
      console.error(e);
    }
  }

  useEffect(() => {
    if (token) checkBrowserStatus();
  }, [token]);

  // Launch browser for human login / session
  async function launchBrowser() {
    setConnectingBrowser(true);
    setError('');
    setNotice('');
    try {
      const data = await localRequest('/api/manychat/launch', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': token,
        },
        body: JSON.stringify({ headless: false }),
      });
      setBrowserStatus(data);
      if (data.active || data.logged_in) {
        setNotice('Ventana de ManyChat abierta. Si no estás logueado, iniciá sesión en ManyChat.');
      } else if (data.error) {
        setError(data.error);
      } else {
        setError('No se pudo abrir el navegador de ManyChat. Verificá que Playwright esté instalado.');
      }
    } catch (e) {
      setError('No se pudo abrir el navegador. Verificá la conexión y que el servidor local esté activo.');
    } finally {
      setConnectingBrowser(false);
    }
  }

  // Scan conversations and generate proposals
  async function scanLeads(isMock = false) {
    setScanning(true);
    setError('');
    setNotice('');
    try {
      const providerPayload = getActiveProviderPayload(modelConfig);
      const data = await localRequest('/api/manychat/scan', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': token,
        },
        body: JSON.stringify({
          date_filter: dateFilter,
          limit: Number(limit),
          mock: isMock,
          provider_config: providerPayload,
        }),
      });

      if (data.status === 'error') {
        setError(data.error || 'Error al escanear ManyChat.');
        return;
      }

      const fetched = data.leads || [];
      setLeads(fetched);
      const eligibleCount = fetched.filter(l => l.eligible).length;
      if (fetched.length === 0) {
        setNotice(data.notice || 'No se encontraron conversaciones para el período seleccionado.');
      } else {
        setNotice(`Escaneo completo: ${fetched.length} contactos revisados, ${eligibleCount} elegibles para seguimiento.`);
      }
    } catch (e) {
      setError('Error al escanear ManyChat o evaluar los leads.');
    } finally {
      setScanning(false);
    }
  }

  // Toggle selection for a single lead
  function toggleSelect(id) {
    setLeads(prev =>
      prev.map(lead => (lead.id === id ? { ...lead, selected: !lead.selected } : lead))
    );
  }

  // Select all eligible leads with valid draft
  function selectAllEligible() {
    setLeads(prev =>
      prev.map(lead => ({
        ...lead,
        selected: Boolean(lead.eligible && lead.draft && lead.draft.trim())
      }))
    );
  }

  // Deselect all
  function deselectAll() {
    setLeads(prev => prev.map(lead => ({ ...lead, selected: false })));
  }

  // Update draft text directly in table
  function updateDraft(id, newText) {
    setLeads(prev =>
      prev.map(lead => (lead.id === id ? { ...lead, draft: newText } : lead))
    );
  }

  // Send batch of selected leads with real-time per-lead progress
  async function sendSelected() {
    const selected = leads.filter(l => l.selected && l.draft && l.draft.trim());
    if (selected.length === 0) return;

    setSendingBatch(true);
    setError('');
    const isMock = !browserStatus.logged_in;
    let sentCount = 0;

    for (let i = 0; i < selected.length; i++) {
      const current = selected[i];
      setNotice(`Enviando ${i + 1} de ${selected.length}: @${current.handle || current.name}...`);

      // Update UI: mark this specific lead as 'sending'
      setLeads(prev =>
        prev.map(l => (l.id === current.id ? { ...l, status: 'sending' } : l))
      );

      try {
        const data = await localRequest('/api/manychat/send-batch', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRF-Token': token,
          },
          body: JSON.stringify({
            leads: [{ id: current.id, draft: current.draft }],
            mock: isMock,
          }),
        });

        const res = (data.results || [])[0];
        const ok = res && res.status === 'sent';
        if (ok) sentCount++;

        setLeads(prev =>
          prev.map(l =>
            l.id === current.id
              ? {
                  ...l,
                  status: ok ? 'sent' : 'failed',
                  error: res ? res.error : 'Error al enviar',
                  selected: false,
                }
              : l
          )
        );
      } catch (err) {
        setLeads(prev =>
          prev.map(l =>
            l.id === current.id
              ? { ...l, status: 'failed', error: 'Error de conexión', selected: false }
              : l
          )
        );
      }
    }

    setNotice(`Envío completado: ${sentCount} de ${selected.length} mensajes enviados y verificados.`);
    setSendingBatch(false);
  }

  const selectedCount = leads.filter(l => l.selected).length;
  const eligibleCount = leads.filter(l => l.eligible).length;

  return (
    <div className="followup-container" style={{ padding: '1.5rem', maxWidth: '1200px', margin: '0 auto' }}>
      {/* Top Header Card */}
      <div className="card" style={{ padding: '1.25rem', marginBottom: '1.5rem', background: 'var(--card-bg, #1a1a1a)', borderRadius: '8px', border: '1px solid var(--border-color, #333)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem' }}>
          <div>
            <h2 style={{ fontSize: '1.25rem', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '0.5rem', margin: 0 }}>
              <Bot className="w-5 h-5 text-blue-400" /> Operador de Seguimientos ManyChat
            </h2>
            <p style={{ margin: '0.25rem 0 0', fontSize: '0.875rem', color: '#888' }}>
              Opera ManyChat como humano con perfil persistente. Secuencia Holly: FUP 1 Nombre?, FUP 2 🙃. Máximo 2 toques sin respuesta.
            </p>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <span style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.35rem',
              padding: '0.25rem 0.65rem',
              borderRadius: '9999px',
              fontSize: '0.75rem',
              fontWeight: 500,
              background: browserStatus.logged_in ? '#14532d' : browserStatus.active ? '#854d0e' : '#262626',
              color: browserStatus.logged_in ? '#86efac' : browserStatus.active ? '#fef08a' : '#a3a3a3',
              border: '1px solid ' + (browserStatus.logged_in ? '#22c55e' : '#444')
            }}>
              {browserStatus.logged_in ? <CheckCircle2 size={13} /> : <AlertCircle size={13} />}
              {browserStatus.logged_in ? 'ManyChat Conectado' : browserStatus.active ? 'Navegador Abierto (Falta Login)' : 'Navegador Desconectado'}
            </span>

            <button
              type="button"
              onClick={launchBrowser}
              disabled={connectingBrowser}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.4rem',
                padding: '0.4rem 0.8rem',
                borderRadius: '6px',
                fontSize: '0.85rem',
                background: '#2563eb',
                color: '#fff',
                border: 'none',
                cursor: 'pointer'
              }}
            >
              {connectingBrowser ? <Loader2 className="animate-spin" size={14} /> : <ExternalLink size={14} />}
              Conectar ManyChat
            </button>
          </div>
        </div>
      </div>

      {/* Filter and Scan Toolbar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '1rem', marginBottom: '1.25rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.85rem' }}>
            <Filter size={15} className="text-gray-400" />
            <label htmlFor="date-filter">Período:</label>
            <select
              id="date-filter"
              value={dateFilter}
              onChange={e => setDateFilter(e.target.value)}
              style={{ background: '#262626', color: '#fff', border: '1px solid #444', borderRadius: '4px', padding: '0.3rem 0.6rem', fontSize: '0.85rem' }}
            >
              <option value="septiembre">Septiembre</option>
              <option value="ultimos_30_dias">Últimos 30 días</option>
              <option value="todos">Todos los pendientes</option>
            </select>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.85rem' }}>
            <label htmlFor="limit-select">Límite:</label>
            <select
              id="limit-select"
              value={limit}
              onChange={e => setLimit(e.target.value)}
              style={{ background: '#262626', color: '#fff', border: '1px solid #444', borderRadius: '4px', padding: '0.3rem 0.6rem', fontSize: '0.85rem' }}
            >
              <option value={10}>10 chats</option>
              <option value={20}>20 chats</option>
              <option value={50}>50 chats</option>
            </select>
          </div>

          <button
            type="button"
            onClick={() => scanLeads(false)}
            disabled={scanning || sendingBatch}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.4rem',
              padding: '0.4rem 0.9rem',
              borderRadius: '6px',
              fontSize: '0.85rem',
              fontWeight: 500,
              background: '#059669',
              color: '#fff',
              border: 'none',
              cursor: 'pointer'
            }}
          >
            {scanning ? <Loader2 className="animate-spin" size={14} /> : <RefreshCw size={14} />}
            Escanear ManyChat
          </button>

          <button
            type="button"
            onClick={() => scanLeads(true)}
            disabled={scanning || sendingBatch}
            title="Prueba inmediata con leads de demostración sin necesidad de tener ManyChat abierto"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.4rem',
              padding: '0.4rem 0.75rem',
              borderRadius: '6px',
              fontSize: '0.8rem',
              background: '#374151',
              color: '#d1d5db',
              border: '1px solid #4b5563',
              cursor: 'pointer'
            }}
          >
            <Play size={13} />
            Demo de prueba
          </button>
        </div>

        {leads.length > 0 && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <button
              type="button"
              onClick={selectAllEligible}
              style={{ background: 'transparent', color: '#38bdf8', border: '1px solid #0284c7', borderRadius: '4px', padding: '0.3rem 0.6rem', fontSize: '0.8rem', cursor: 'pointer' }}
            >
              Seleccionar elegibles ({eligibleCount})
            </button>
            <button
              type="button"
              onClick={deselectAll}
              style={{ background: 'transparent', color: '#9ca3af', border: '1px solid #4b5563', borderRadius: '4px', padding: '0.3rem 0.6rem', fontSize: '0.8rem', cursor: 'pointer' }}
            >
              Deseleccionar todos
            </button>
            <button
              type="button"
              onClick={sendSelected}
              disabled={selectedCount === 0 || sendingBatch}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.4rem',
                padding: '0.45rem 1rem',
                borderRadius: '6px',
                fontSize: '0.85rem',
                fontWeight: 600,
                background: selectedCount > 0 ? '#2563eb' : '#374151',
                color: selectedCount > 0 ? '#fff' : '#6b7280',
                border: 'none',
                cursor: selectedCount > 0 ? 'pointer' : 'not-allowed'
              }}
            >
              {sendingBatch ? <Loader2 className="animate-spin" size={14} /> : <Send size={14} />}
              Enviar Seleccionados ({selectedCount})
            </button>
          </div>
        )}
      </div>

      {notice && (
        <div style={{ padding: '0.75rem 1rem', marginBottom: '1rem', borderRadius: '6px', background: '#064e3b', color: '#a7f3d0', fontSize: '0.85rem' }}>
          {notice}
        </div>
      )}

      {error && (
        <div style={{ padding: '0.75rem 1rem', marginBottom: '1rem', borderRadius: '6px', background: '#7f1d1d', color: '#fecaca', fontSize: '0.85rem' }}>
          {error}
        </div>
      )}

      {/* Leads Table */}
      {leads.length > 0 ? (
        <div style={{ background: '#171717', border: '1px solid #333', borderRadius: '8px', overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left', fontSize: '0.85rem' }}>
            <thead>
              <tr style={{ background: '#262626', borderBottom: '1px solid #333', color: '#9ca3af' }}>
                <th style={{ padding: '0.75rem 1rem', width: '40px' }}>Sel</th>
                <th style={{ padding: '0.75rem 1rem', width: '180px' }}>Lead</th>
                <th style={{ padding: '0.75rem 1rem', width: '130px' }}>Estado</th>
                <th style={{ padding: '0.75rem 1rem' }}>Borrador propuesto (editable)</th>
                <th style={{ padding: '0.75rem 1rem', width: '120px', textAlign: 'center' }}>Acción</th>
              </tr>
            </thead>
            <tbody>
              {leads.map(lead => {
                const isSent = lead.status === 'sent';
                const isSending = lead.status === 'sending';
                return (
                  <tr
                    key={lead.id}
                    style={{
                      borderBottom: '1px solid #262626',
                      background: lead.selected ? 'rgba(37, 99, 235, 0.08)' : 'transparent',
                    }}
                  >
                    <td style={{ padding: '0.75rem 1rem', verticalAlign: 'top' }}>
                      <input
                        type="checkbox"
                        checked={lead.selected}
                        disabled={isSent || isSending || (!lead.draft || !lead.draft.trim())}
                        onChange={() => toggleSelect(lead.id)}
                        style={{ cursor: 'pointer', width: '16px', height: '16px' }}
                      />
                    </td>
                    <td style={{ padding: '0.75rem 1rem', verticalAlign: 'top' }}>
                      <div style={{ fontWeight: 600, color: '#f3f4f6' }}>{lead.name}</div>
                      {lead.handle && <div style={{ fontSize: '0.75rem', color: '#9ca3af' }}>@{lead.handle}</div>}
                      {lead.last_date && (
                        <div style={{ fontSize: '0.75rem', color: '#6b7280', display: 'flex', alignItems: 'center', gap: '0.25rem', marginTop: '0.2rem' }}>
                          <Clock size={11} /> {lead.last_date}
                        </div>
                      )}
                    </td>
                    <td style={{ padding: '0.75rem 1rem', verticalAlign: 'top' }}>
                      {lead.eligible ? (
                        <span style={{
                          display: 'inline-block',
                          padding: '0.2rem 0.5rem',
                          borderRadius: '4px',
                          fontSize: '0.75rem',
                          fontWeight: 500,
                          background: lead.followup_number === 1 ? '#065f46' : '#92400e',
                          color: lead.followup_number === 1 ? '#6ee7b7' : '#fde68a'
                        }}>
                          FUP {lead.followup_number}
                        </span>
                      ) : (
                        <span style={{
                          display: 'inline-block',
                          padding: '0.2rem 0.5rem',
                          borderRadius: '4px',
                          fontSize: '0.72rem',
                          background: '#374151',
                          color: '#9ca3af'
                        }}>
                          {lead.reason || 'No elegible'}
                        </span>
                      )}
                    </td>
                    <td style={{ padding: '0.75rem 1rem', verticalAlign: 'top' }}>
                      {lead.eligible ? (
                        <textarea
                          value={lead.draft}
                          onChange={e => updateDraft(lead.id, e.target.value)}
                          disabled={isSent || isSending}
                          rows={2}
                          style={{
                            width: '100%',
                            background: '#0a0a0a',
                            border: '1px solid #404040',
                            borderRadius: '4px',
                            padding: '0.4rem 0.6rem',
                            color: '#fff',
                            fontSize: '0.85rem',
                            resize: 'vertical',
                          }}
                        />
                      ) : (
                        <span style={{ color: '#6b7280', fontSize: '0.8rem', fontStyle: 'italic' }}>
                          {lead.reason}
                        </span>
                      )}
                    </td>
                    <td style={{ padding: '0.75rem 1rem', verticalAlign: 'top', textAlign: 'center' }}>
                      {isSent ? (
                        <span style={{ color: '#22c55e', fontSize: '0.8rem', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
                          <CheckCircle2 size={14} /> Enviado
                        </span>
                      ) : isSending ? (
                        <span style={{ color: '#38bdf8', fontSize: '0.8rem', display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
                          <Loader2 className="animate-spin" size={14} /> Mandando
                        </span>
                      ) : lead.status === 'failed' ? (
                        <span style={{ color: '#ef4444', fontSize: '0.8rem' }}>Error</span>
                      ) : lead.eligible ? (
                        <button
                          type="button"
                          onClick={async () => {
                            setLeads(prev => prev.map(l => l.id === lead.id ? { ...l, status: 'sending' } : l));
                            try {
                              const isMock = !browserStatus.logged_in;
                              await localRequest('/api/manychat/send-batch', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': token },
                                body: JSON.stringify({ leads: [{ id: lead.id, draft: lead.draft }], mock: isMock }),
                              });
                              setLeads(prev => prev.map(l => l.id === lead.id ? { ...l, status: 'sent', selected: false } : l));
                            } catch (e) {
                              setLeads(prev => prev.map(l => l.id === lead.id ? { ...l, status: 'failed' } : l));
                            }
                          }}
                          style={{
                            background: '#1e3a8a',
                            color: '#93c5fd',
                            border: '1px solid #2563eb',
                            borderRadius: '4px',
                            padding: '0.35rem 0.65rem',
                            fontSize: '0.78rem',
                            cursor: 'pointer'
                          }}
                        >
                          Enviar
                        </button>
                      ) : (
                        <span style={{ color: '#525252', fontSize: '0.75rem' }}>—</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div style={{ textAlign: 'center', padding: '3rem 1rem', border: '1px dashed #333', borderRadius: '8px', color: '#6b7280' }}>
          <p style={{ margin: 0, fontSize: '0.95rem' }}>No hay contactos cargados.</p>
          <p style={{ margin: '0.5rem 0 0', fontSize: '0.85rem' }}>
            Tocá <strong>"Escanear ManyChat"</strong> para traer los chats del período seleccionado o <strong>"Demo de prueba"</strong> para simular el lote.
          </p>
        </div>
      )}
    </div>
  );
}
