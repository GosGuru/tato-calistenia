import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import FollowUpWorkspace from './FollowUpWorkspace.jsx';

describe('FollowUpWorkspace Component', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn((url, options) => {
      if (url.includes('/api/manychat/status')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({ active: false, logged_in: false }),
        });
      }
      if (url.includes('/api/manychat/scan')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({
            leads: [
              {
                id: 'lead_1',
                name: 'Alberto H',
                handle: 'alberto',
                last_date: '15 de septiembre',
                eligible: true,
                reason: '',
                followup_number: 1,
                draft: '¿Pudiste probar las anillas?',
                selected: true,
              },
              {
                id: 'lead_2',
                name: 'Carlos M',
                handle: 'carlos',
                last_date: '10 de septiembre',
                eligible: false,
                reason: 'Límite alcanzado',
                followup_number: 2,
                draft: '',
                selected: false,
              },
            ],
            count: 2,
          }),
        });
      }
      if (url.includes('/api/manychat/send-batch')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({
            results: [{ id: 'lead_1', status: 'sent', text: '¿Pudiste probar las anillas?' }],
          }),
        });
      }
      return Promise.reject(new Error(`Unhandled URL: ${url}`));
    }));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('renders header, connection state, and action buttons', async () => {
    render(<FollowUpWorkspace token="test-token" modelConfig={{ provider: 'codex' }} onDisconnect={vi.fn()} />);

    expect(screen.getByText(/Operador de Seguimientos ManyChat/i)).toBeInTheDocument();
    expect(screen.getByText(/Navegador Desconectado/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Conectar ManyChat/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Escanear ManyChat/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Demo de prueba/i })).toBeInTheDocument();
  });

  it('loads leads on clicking Demo de prueba and allows selection toggle', async () => {
    render(<FollowUpWorkspace token="test-token" modelConfig={{ provider: 'codex' }} onDisconnect={vi.fn()} />);

    const demoBtn = screen.getByRole('button', { name: /Demo de prueba/i });
    fireEvent.click(demoBtn);

    await waitFor(() => {
      expect(screen.getByText('Alberto H')).toBeInTheDocument();
      expect(screen.getByText('Carlos M')).toBeInTheDocument();
    });

    expect(screen.getAllByText(/Límite alcanzado/i).length).toBeGreaterThan(0);
    const draftTextarea = screen.getByDisplayValue('¿Pudiste probar las anillas?');
    expect(draftTextarea).toBeInTheDocument();

    // Toggle draft edit
    fireEvent.change(draftTextarea, { target: { value: '¿Pudiste probar las anillas hoy?' } });
    expect(screen.getByDisplayValue('¿Pudiste probar las anillas hoy?')).toBeInTheDocument();

    // Toggle deselect all
    const deselectBtn = screen.getByRole('button', { name: /Deseleccionar todos/i });
    fireEvent.click(deselectBtn);
    expect(screen.getByRole('button', { name: /Enviar Seleccionados \(0\)/i })).toBeDisabled();

    // Toggle select eligible
    const selectEligibleBtn = screen.getByRole('button', { name: /Seleccionar elegibles \(1\)/i });
    fireEvent.click(selectEligibleBtn);
    expect(screen.getByRole('button', { name: /Enviar Seleccionados \(1\)/i })).not.toBeDisabled();
  });
});
