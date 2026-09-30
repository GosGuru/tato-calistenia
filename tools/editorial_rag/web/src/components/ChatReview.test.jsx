import { it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import ChatReview from './ChatReview.jsx';
import { parseManychat } from '../manychatHistory.js';

it('shows bubbles, on-demand editing, exact dates and reversible notices', async () => {
  const onChange = vi.fn();
  const blocks = parseManychat('Monday 10:30\nAutomation paused\n\nhola ficticia\n\nTato: respuesta').blocks;
  render(<ChatReview blocks={blocks} onChange={onChange} />);
  expect(screen.getByText('hola ficticia')).toBeVisible();
  expect(screen.queryByRole('textbox')).not.toBeInTheDocument();
  await userEvent.click(screen.getByRole('button', { name: 'Editar mensaje 1' }));
  expect(screen.getByRole('dialog')).toBeVisible();
  expect(screen.getByLabelText('Texto del mensaje')).toHaveValue('hola ficticia');
  await userEvent.keyboard('{Escape}');
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  await userEvent.click(screen.getByText(/Ver avisos separados/));
  expect(screen.getByText('Automation paused')).toBeVisible();
  await userEvent.click(screen.getByRole('button', { name: 'Restaurar como mensaje 1' }));
  expect(onChange.mock.calls[0][0].filter(b => b.kind === 'message')).toHaveLength(3);
});

it('splits only inside text, creates fresh IDs and never breaks Unicode or loses selection', async () => {
  const onChange = vi.fn();
  const blocks = parseManychat('Prospecto: a😀b').blocks;
  render(<ChatReview blocks={blocks} onChange={onChange} />);
  await userEvent.click(screen.getByRole('button', { name: 'Editar mensaje 1' }));
  const editor = screen.getByLabelText('Texto del mensaje');
  for (const at of [0, 2, 4]) {
    editor.setSelectionRange(at, at);
    await userEvent.click(screen.getByRole('button', { name: 'Dividir en el cursor' }));
    expect(onChange).not.toHaveBeenCalled();
  }
  editor.setSelectionRange(1, 3);
  await userEvent.click(screen.getByRole('button', { name: 'Dividir en el cursor' }));
  const parts = onChange.mock.calls[0][0];
  expect(parts.map(b => b.text).join('')).toBe('a😀b');
  expect(parts.map(b => b.source).join('')).toBe('Prospecto: a😀b');
  expect(parts.every(b => b.source_id === blocks[0].source_id)).toBe(true);
  expect(parts.every(b => b.role === 'unknown' && b.id !== blocks[0].id)).toBe(true);
  expect(parts[0].id).not.toBe(parts[1].id);
});

it('preserves exact-once provenance after editing and repeatedly splitting either child', async () => {
  const original = 'Prospecto: original😀\n';
  let blocks = parseManychat(original).blocks;
  const onChange = next => { blocks = next; view.rerender(<ChatReview blocks={blocks} onChange={onChange} />); };
  const view = render(<ChatReview blocks={blocks} onChange={onChange} />);
  const sourceId = blocks[0].source_id;
  for (const [index, text, at] of [[1, 'nuevo😀texto', 5], [2, 'otra división', 4], [1, 'abc', 1]]) {
    await userEvent.click(screen.getByRole('button', { name: `Editar mensaje ${index}` }));
    fireEvent.change(screen.getByLabelText('Texto del mensaje'), { target: { value: text } });
    screen.getByLabelText('Texto del mensaje').setSelectionRange(at, at);
    await userEvent.click(screen.getByRole('button', { name: 'Dividir en el cursor' }));
    expect(blocks.map(b => b.source).join('')).toBe(original);
    expect(sourceId).toBeTruthy();
    expect(blocks.every(b => b.source_id === sourceId)).toBe(true);
    expect(blocks.filter(b => b.source)).toHaveLength(1);
  }
});

it('restores a time-like message through the same exclusion controls', async () => {
  let blocks = parseManychat('Hoy\n\nProspecto: dato ficticio').blocks;
  const onChange = next => { blocks = next; view.rerender(<ChatReview blocks={blocks} onChange={onChange} />); };
  const view = render(<ChatReview blocks={blocks} onChange={onChange} />);
  await userEvent.click(screen.getByText(/Ver avisos separados/));
  await userEvent.click(screen.getByRole('button', { name: 'Restaurar como mensaje 1' }));
  expect(blocks.filter(b => b.kind === 'message').map(b => b.text)).toEqual(['Hoy', 'dato ficticio']);
  expect(blocks.every(b => b.time_context === null)).toBe(true);
  expect(screen.getByText('Hoy')).toBeVisible();
});

it('edits only on explicit save and pending filtering does not modify source', async () => {
  const onChange = vi.fn();
  const blocks = parseManychat('dato ficticio\n\nTato: pregunta').blocks;
  render(<ChatReview blocks={blocks} onChange={onChange} />);
  await userEvent.click(screen.getByRole('checkbox', { name: 'Solo pendientes' }));
  expect(screen.queryByText('pregunta')).not.toBeInTheDocument();
  expect(onChange).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole('button', { name: 'Editar mensaje 1' }));
  fireEvent.change(screen.getByLabelText('Texto del mensaje'), { target: { value: 'corrección ficticia' } });
  await userEvent.click(screen.getByRole('button', { name: 'Guardar mensaje' }));
  expect(onChange.mock.calls[0][0][0].text).toBe('corrección ficticia');
});
