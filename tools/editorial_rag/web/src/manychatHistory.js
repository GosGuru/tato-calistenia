// Local transformations only: no network, storage, sender inference or date arithmetic.
export const count = text => Array.from(text).length;
export const freshId = () => `m-${crypto.randomUUID()}`;
const ROLES = ['user', 'assistant', 'unknown'];
const notices = new Set([
  'Automation paused', 'Automation resumed', 'Automatización pausada', 'Automatización reanudada',
  'Automatizaciones pausadas', 'Automatizaciones reanudadas',
  'Conversation assigned', 'Conversación asignada', 'Tag added', 'Etiqueta añadida',
  'Replied to your story', 'Respondió a tu historia', 'Story unavailable', 'Historia no disponible',
  'This story is no longer available', 'Esta historia ya no está disponible',
  'Content expired', 'Contenido caducado', 'respondió a tu historia', 'Contenido no disponible',
]);
// Full, case-sensitive interface lines only. Quoted/inline mentions stay content.
const noticePatterns = [
  /^La automatización \S(?:[^\n]*\S)? se activó$/u,
  /^Etiqueta añadida: \S(?:[^\n]*\S)?$/u,
  /^La conversación fue movida de \S(?:[^\n]*\S)? a \S(?:[^\n]*\S)?$/u,
  /^La conversación fue asignada a \S(?:[^\n]*\S)?$/u,
  /^\p{L}[\p{L}\p{M}\d ._-]* ha pausado temporalmente las respuestas automáticas en esta conversación, puedes editar la pausa o reanudar la automatización en cualquier momento$/u,
  /^La historia expiró hace \d+ horas$/u,
];
const isNotice = text => notices.has(text) || noticePatterns.some(pattern => pattern.test(text));
const headers = new Set(['Todo el historial de canales', 'Instagram channel history', 'Historial del canal de Instagram', 'Historial del canal Instagram']);
const weekdays = '(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday|lunes|martes|miércoles|jueves|viernes|sábado|domingo|Today|Yesterday|Hoy|Ayer)';
const clock = '(?:[01]?\\d|2[0-3]):[0-5]\\d(?: ?(?:AM|PM|am|pm))?';
const date = '(?:\\d{1,2}[/. -]\\d{1,2}[/. -]\\d{4}|\\d{4}-\\d{2}-\\d{2})';
const month = '(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)';
const monthDate = `(?:[1-9]|[12]\\d|3[01]) ${month} \\d{4}`;
const timestamp = new RegExp(`^(?:${weekdays}(?:,? ${clock})?|(?:${date}|${monthDate})(?:,? ${clock})?|${clock})$`, 'i');
const timeOnly = new RegExp(`^${clock}$`, 'i');
const reactions = new Set(['❤️', '❤', '👍', '🔥', '💪', '😂', '😍', '👏', '🙏', '🙌']);
const marker = /^(Prospecto|Tato):(.*)$/i;
const validText = text => typeof text === 'string' && text.trim()
  && !/[\x00-\x08\x0b-\x1f\uD800-\uDFFF]/u.test(text);

export function validateBlocks(blocks) {
  const messages = blocks.filter(b => b.kind === 'message');
  if (!messages.length) return 'Agregá al menos un mensaje para revisar.';
  if (messages.length > 100) return 'Hay más de 100 mensajes. Reducí la conversación antes de continuar.';
  if (messages.some(b => count(b.text) > 4000)) return 'Un mensaje supera 4.000 caracteres. Dividilo o editá el pegado.';
  if (messages.some(b => !validText(b.text))) return 'Cada mensaje necesita texto y Unicode válido, sin caracteres de control.';
  if (messages.some(b => b.time_context && count(b.time_context) > 200)) return 'El contexto de fecha supera 200 caracteres. Revisá las fechas.';
  if (messages.reduce((sum, b) => sum + count(b.text) + count(b.time_context || ''), 0) > 24000)
    return 'Los mensajes con sus fechas superan 24.000 caracteres. Reducí el historial revisado.';
  return '';
}

export function parseManychat(raw) {
  if (typeof raw !== 'string') throw new Error('Pegá texto para revisar.');
  if (count(raw) > 24000) throw new Error('El pegado supera 24.000 caracteres. Reducilo; no se recortó texto.');
  const normalized = raw.replace(/\r\n?/g, '\n');
  const lines = normalized.match(/[^\n]*\n|[^\n]+$/g) || [];
  const bare = line => line.replace(/\n$/, '');
  const blocks = [];
  let pending = null;
  let time = null;
  let dateContext = null;
  const add = (kind, text, source, role = 'unknown') => {
    const id = freshId();
    const block = { id, source_id: id, kind, text, source, role, time_context: time,
      uncertain: role === 'unknown', proposed: false };
    blocks.push(block);
    return block;
  };
  const flush = () => {
    if (pending) {
      add('message', pending.text, pending.source, pending.role);
      pending = null;
    }
  };
  let start = 0;
  // Only the explicit leading channel-history structure can separate a name header.
  const nonblank = [];
  for (let i = 0; i < lines.length && nonblank.length < 3; i += 1) {
    if (bare(lines[i]).trim()) nonblank.push(i);
  }
  if (nonblank.length === 3 && headers.has(bare(lines[nonblank[0]]))
    && bare(lines[nonblank[2]]) === 'Yo'
    && !marker.test(bare(lines[nonblank[1]])) && !timestamp.test(bare(lines[nonblank[1]]))
    && !isNotice(bare(lines[nonblank[1]]))) {
    start = nonblank[2] + 1;
    const source = lines.slice(0, start).join('');
    add('metadata', source.replace(/\n$/, ''), source);
  }
  for (let i = start; i < lines.length; i += 1) {
    const source = lines[i], text = bare(source);
    const label = marker.exec(text);
    if (!text.trim()) {
      flush(); add('separator', text, source);
    } else if (label) {
      flush();
      pending = { role: label[1].toLowerCase() === 'tato' ? 'assistant' : 'user',
        text: label[2].replace(/^ /, ''), source };
    } else if (timestamp.test(text) || isNotice(text) || reactions.has(text)) {
      flush();
      if (timestamp.test(text)) {
        if (timeOnly.test(text)) time = dateContext ? `${dateContext}\n${text}` : text;
        else { dateContext = text; time = text; }
        add('time', text, source);
      } else add(reactions.has(text) ? 'reaction' : 'metadata', text, source);
    } else if (pending) {
      pending.text += '\n' + text;
      pending.source += source;
    } else pending = { role: 'unknown', text, source };
  }
  flush();
  const issue = validateBlocks(blocks);
  if (issue && blocks.some(b => b.kind === 'message')) throw new Error(issue);
  return { normalized, blocks };
}

export function restoreBlock(blocks, id) {
  const restored = blocks.map(b => b.id === id ? { ...b, kind: 'message', role: 'unknown', uncertain: true, proposed: false } : b);
  // Recompute exclusively from remaining time blocks, never from cached inherited dates.
  let time = null, dateContext = null;
  return restored.map(b => {
    if (b.kind === 'time') {
      if (timeOnly.test(b.text)) time = dateContext ? `${dateContext}\n${b.text}` : b.text;
      else { dateContext = b.text; time = b.text; }
    }
    return { ...b, time_context: time };
  });
}

export function organizationBlocks(blocks) {
  return blocks.filter(b => b.kind === 'message').map(b => ({ id: b.id, text: b.text,
    // Suggestions are never upgraded to explicit attributions by a subsequent AI call.
    role: b.proposed ? 'unknown' : b.role, time_context: b.time_context }));
}

export function applyAssignments(blocks, data) {
  const source = organizationBlocks(blocks);
  if (!data || Object.keys(data).join() !== 'assignments' || !Array.isArray(data.assignments)
    || data.assignments.length !== source.length) throw new Error('Invalid organization');
  data.assignments.forEach((a, index) => {
    const b = source[index];
    if (!a || Object.keys(a).sort().join() !== 'id,role,uncertain' || a.id !== b.id
      || !ROLES.includes(a.role) || typeof a.uncertain !== 'boolean'
      || (a.role === 'unknown' && !a.uncertain) || (b.role !== 'unknown' && a.role !== b.role))
      throw new Error('Invalid organization');
  });
  const assignments = new Map(data.assignments.map(a => [a.id, a]));
  return blocks.map(b => {
    const a = assignments.get(b.id);
    if (!a) return b;
    return { ...b, role: a.role, uncertain: a.uncertain, proposed: b.role === 'unknown' || b.proposed };
  });
}

export function draftMessages(blocks) {
  return blocks.filter(b => b.kind === 'message').map(b => ({ role: b.role,
    text: b.time_context ? `[Fecha/hora original: ${b.time_context}]\n${b.text}` : b.text }));
}
export function canDraft(blocks) {
  return !validateBlocks(blocks) && blocks.filter(b => b.kind === 'message').every(b => b.role !== 'unknown' && !b.uncertain)
    && draftMessages(blocks).every(b => count(b.text) <= 4000)
    && draftMessages(blocks).reduce((sum, b) => sum + count(b.text), 0) <= 24000;
}
