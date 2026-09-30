import { describe, it, expect } from 'vitest';
import { parseManychat, restoreBlock, draftMessages, validateBlocks } from './manychatHistory.js';

describe('local ManyChat segmentation with invented data', () => {
  it.each(['Hoy', '09:20'])('restoring %s removes false inherited context until the next timestamp', value => {
    const raw = value + '\n\nProspecto: dato\n\n3 Oct 2025, 09:20\nProspecto: otro';
    const initial = parseManychat(raw).blocks;
    const restored = restoreBlock(initial, initial[0].id);
    expect(restored.map(b => b.source).join('')).toBe(raw);
    expect(draftMessages(restored)).toEqual([
      { role: 'unknown', text: value }, { role: 'user', text: 'dato' },
      { role: 'user', text: '[Fecha/hora original: 3 Oct 2025, 09:20]\notro' }]);
  });
  it('recomputes remaining date and clock context without a removed date anchor', () => {
    let blocks = parseManychat('14 Jan 2025\n09:20\nProspecto: primero\nHoy\n10:30\nProspecto: segundo').blocks;
    blocks = restoreBlock(blocks, blocks.find(b => b.text === 'Hoy').id);
    expect(blocks.find(b => b.text === 'segundo').time_context).toBe('14 Jan 2025\n10:30');
    blocks = restoreBlock(blocks, blocks.find(b => b.text === '14 Jan 2025').id);
    expect(blocks.find(b => b.text === 'primero').time_context).toBe('09:20');
    expect(blocks.find(b => b.text === 'segundo').time_context).toBe('10:30');
  });
  it('handles Spanish channel headers with blanks and full interface notices without losing source', () => {
    const metadata = ['La automatización Flujo ficticio se activó', 'Etiqueta añadida: Prueba inventada',
      'La conversación fue movida de Abierta a Cerrada', 'La conversación fue asignada a Agente Ficticio',
      'Agente Ficticio ha pausado temporalmente las respuestas automáticas en esta conversación, puedes editar la pausa o reanudar la automatización en cualquier momento',
      'respondió a tu historia', 'Contenido no disponible', 'La historia expiró hace 12 horas'];
    const header = 'Todo el historial de canales\n\n\nPersona Inventada\n\nYo\n';
    const raw = header + '\n14 Jan 2025, 16:35\n' + metadata.join('\n')
      + '\n\nquiero mejorar\n\nqué probaste?\n\nhttps://example.com/ficticio\n\n❤️\n\n3 Oct 2025, 09:20\notro intento\n\nWednesday, 11:42\núltimo dato';
    const { blocks } = parseManychat(raw);
    expect(blocks.map(b => b.source).join('')).toBe(raw);
    const messages = blocks.filter(b => b.kind === 'message');
    expect(messages.map(b => b.text)).toEqual(['quiero mejorar', 'qué probaste?', 'https://example.com/ficticio', 'otro intento', 'último dato']);
    expect(messages.map(b => b.time_context)).toEqual(['14 Jan 2025, 16:35', '14 Jan 2025, 16:35', '14 Jan 2025, 16:35', '3 Oct 2025, 09:20', 'Wednesday, 11:42']);
    expect(messages.every(b => b.role === 'unknown')).toBe(true);
    expect(blocks[0]).toMatchObject({ kind: 'metadata', source: header });
    for (const excluded of blocks.filter(b => ['metadata', 'reaction'].includes(b.kind))) {
      expect(restoreBlock(blocks, excluded.id).find(b => b.id === excluded.id)).toMatchObject({ kind: 'message', text: excluded.text, role: 'unknown' });
    }
  });
  it('preserves quoted, partial and mid-chat header prose', () => {
    const text = 'dijo La automatización Flujo ficticio se activó ayer\n\n"Etiqueta añadida: Prueba"\n\nLa historia expiró hace varias horas\n\nTodo el historial de canales\n\nPersona Inventada\n\nYo';
    const { blocks } = parseManychat(text);
    expect(blocks.filter(b => b.kind === 'metadata')).toHaveLength(0);
    expect(blocks.map(b => b.source).join('')).toBe(text);
  });
  it.each(['3 October 2025, 09:20', '14 January 2025, 16:35'])('accepts named month date %s literally', value => {
    expect(parseManychat(value + '\nhola').blocks.find(b => b.kind === 'message').time_context).toBe(value);
  });
  it('segments paragraphs, keeps dates literally, isolates reversible known notices without speaker guesses', () => {
    const source = 'Instagram channel history\r\nPersona Ficticia\r\nYo\r\n\r\nMonday 10:30\r\nAutomation paused\r\n\r\nquiero fuerza\r\ny control\r\n\r\nqué intentaste?\r\n\r\nhttps://example.com/a:b\r\n\r\n❤️\r\n\r\nLa automatización me ayuda a entrenar';
    const result = parseManychat(source);
    const messages = result.blocks.filter(b => b.kind === 'message');
    expect(messages.map(b => b.text)).toEqual(['quiero fuerza\ny control', 'qué intentaste?', 'https://example.com/a:b', 'La automatización me ayuda a entrenar']);
    expect(messages.every(b => b.role === 'unknown')).toBe(true);
    expect(messages.every(b => b.time_context === 'Monday 10:30')).toBe(true);
    expect(result.blocks.map(b => b.source).join('')).toBe(source.replace(/\r\n?/g, '\n'));
    const notice = result.blocks.find(b => b.text === 'Automation paused');
    const restored = restoreBlock(result.blocks, notice.id);
    expect(restored.find(b => b.id === notice.id)).toMatchObject({ kind: 'message', text: 'Automation paused', role: 'unknown' });
  });
  it('recognizes only exact role labels, keeps repeated content distinct and reparsing creates fresh IDs', () => {
    const input = 'Prospecto: igual\nTato: igual\n\nNombre inventado\nYo\n\nHorario: raro';
    const a = parseManychat(input), b = parseManychat(input);
    expect(a.blocks.filter(b => b.kind === 'message').map(b => b.role)).toEqual(['user', 'assistant', 'unknown', 'unknown']);
    expect(new Set(a.blocks.map(b => b.id)).size).toBe(a.blocks.length);
    expect(a.blocks.some(x => b.blocks.some(y => y.id === x.id))).toBe(false);
  });
  it.each(['12/08/2026 18:30', 'martes 14:05', 'Tuesday, 9:15 PM', '2026-08-12', 'Hoy 10:00'])('preserves exact source date %s without anchors', date => {
    const { blocks } = parseManychat(date + '\nProspecto: ficticio');
    const message = blocks.find(b => b.kind === 'message');
    expect(message.time_context).toBe(date);
    expect(draftMessages([message])).toEqual([{ role: 'user', text: `[Fecha/hora original: ${date}]\nficticio` }]);
  });
  it('does not silently truncate limits or hide ambiguous prose', () => {
    expect(() => parseManychat('😀'.repeat(24001))).toThrow(/24.000/);
    expect(() => parseManychat('x'.repeat(4001))).toThrow(/4.000/);
    expect(() => parseManychat(Array(101).fill('texto').join('\n\n'))).toThrow(/100/);
    const { blocks } = parseManychat('Automation paused quizá\n  Prospecto: ambiguo');
    expect(blocks[0].text).toBe('Automation paused quizá\n  Prospecto: ambiguo');
    expect(validateBlocks(blocks)).toBe('');
  });
});
