import { useRef, useState } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { Textarea } from './ui/textarea';
import { Button } from './ui/button';
import { count, freshId, restoreBlock } from '../manychatHistory.js';

const speaker = role => ({ user: 'Prospecto', assistant: 'Tato', unknown: 'Por confirmar' })[role];

export default function ChatReview({ blocks, onChange }) {
  const [pendingOnly, setPendingOnly] = useState(false);
  const [editing, setEditing] = useState(null);
  const [text, setText] = useState('');
  const [editError, setEditError] = useState('');
  const editor = useRef(null);
  const returnFocus = useRef(null);
  const messages = blocks.filter(b => b.kind === 'message');
  const excluded = blocks.filter(b => !['message', 'separator'].includes(b.kind));
  const pending = messages.filter(b => b.role === 'unknown' || b.uncertain).length;
  const changeRole = (id, role) => onChange(blocks.map(b => b.id === id
    ? { ...b, role, uncertain: role === 'unknown', proposed: false } : b));
  function save(split = false) {
    const at = editor.current?.selectionStart;
    if (split && (at <= 0 || at >= text.length || (/^[\uDC00-\uDFFF]$/.test(text[at]) && /^[\uD800-\uDBFF]$/.test(text[at - 1])))) {
      setEditError('Ubicá el cursor dentro del texto, sin dividir un carácter Unicode.'); return;
    }
    onChange(blocks.flatMap(b => {
      if (b.id !== editing) return [b];
      if (!split) return [{ ...b, text }];
      // source_id links both descendants to the original fragment, not edited-text offsets.
      // Only the first descendant retains literal storage, including on repeated splits.
      return [text.slice(0, at), text.slice(at)].map((part, index) => ({ ...b, id: freshId(), text: part,
        source: index === 0 ? b.source : '', role: 'unknown', uncertain: true, proposed: false }));
    }));
    setEditing(null);
  }
  return <section className="chat-review" aria-label="Revisión local de mensajes">
    <div className="review-toolbar"><p>{messages.length} mensajes · {excluded.length} avisos separados · {pending} roles pendientes</p>
      <label><input type="checkbox" checked={pendingOnly} onChange={e => setPendingOnly(e.target.checked)} /> Solo pendientes</label></div>
    <div className="chat-scroll" tabIndex={0} aria-label="Historial organizado">
      <ol className="chat-bubbles">{messages.map((b, index) => {
        if (pendingOnly && b.role !== 'unknown' && !b.uncertain) return null;
        return <li key={b.id} className={`chat-row ${b.role} ${b.proposed ? 'proposed' : ''}`}>
          {b.time_context && <p className="date-context">{b.time_context}</p>}
          <article className="chat-bubble">
            <div className="bubble-heading"><strong>{speaker(b.role)}</strong><span>#{index + 1}</span></div>
            {b.proposed && <p className="proposal-label">Propuesta de Codex · no verificada por la plataforma</p>}
            {b.uncertain && <p className="pending-label">{b.role === 'unknown' ? 'Autor pendiente' : 'Rol incierto · confirmalo o corregilo'}</p>}
            <p className="message-text">{b.text}</p>
            <div className="bubble-actions">
              <label><span className="sr-only">Quién dijo el mensaje {index + 1}</span>
                <select value={b.role} onChange={e => changeRole(b.id, e.target.value)}>
                  <option value="unknown">Por confirmar</option><option value="user">Prospecto</option><option value="assistant">Tato</option>
                </select></label>
              {b.role !== 'unknown' && b.uncertain && <button onClick={() => changeRole(b.id, b.role)}>Confirmar rol del mensaje {index + 1}</button>}
              <button className="quiet" onClick={e => { returnFocus.current = e.currentTarget; setText(b.text); setEditError(''); setEditing(b.id); }}>Editar mensaje {index + 1}</button>
              <button className="quiet" onClick={() => onChange(blocks.map(x => x.id === b.id ? { ...x, kind: 'excluded' } : x))}>Separar mensaje {index + 1}</button>
            </div>
          </article>
        </li>;
      })}</ol>
      {pendingOnly && !pending && <p className="empty-state">No quedan roles pendientes.</p>}
    </div>
    <details className="separated-notices"><summary>Ver avisos separados ({excluded.length})</summary>
      <p className="footnote">Los avisos no se transmiten; las fechas se usan como contexto literal. El reconocimiento puede equivocarse: restaurá cualquier mensaje separado por error.</p>
      {excluded.map((b, i) => <article key={b.id}>{b.kind === 'time' && <p className="footnote">Fecha/hora reconocida · restaurar recalcula el contexto posterior</p>}<p className="message-text">{b.text}</p>
        <button onClick={() => onChange(restoreBlock(blocks, b.id))}>Restaurar como mensaje {i + 1}</button></article>)}
      <details><summary>Separadores originales</summary>{blocks.filter(b => b.kind === 'separator').map(b =>
        <pre key={b.id}>{b.text || '(línea en blanco)'}</pre>)}</details>
    </details>
    <Dialog.Root open={!!editing} onOpenChange={open => { if (!open) setEditing(null); }}>
      <Dialog.Portal><div className="dialog-overlay" aria-hidden="true" />
        <Dialog.Content className="dialog-content" onCloseAutoFocus={e => { e.preventDefault(); returnFocus.current?.focus(); }}>
          <Dialog.Title>Editar mensaje</Dialog.Title>
          <Dialog.Description>Corregí el texto o dividilo en el cursor. Guardar invalida la revisión y los resultados anteriores.</Dialog.Description>
          <label htmlFor="message-edit">Texto del mensaje</label>
          <Textarea id="message-edit" ref={editor} value={text} onChange={e => setText(e.target.value)} autoComplete="off" spellCheck={false} />
          <p className="footnote">{count(text)} / 4.000 caracteres</p>
          {editError && <p role="alert">{editError}</p>}
          <div className="actions"><Button className="primary" onClick={() => save()}>Guardar mensaje</Button>
            <button onClick={() => save(true)}>Dividir en el cursor</button><Dialog.Close asChild><button>Cancelar</button></Dialog.Close></div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  </section>;
}
