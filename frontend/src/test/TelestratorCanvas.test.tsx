import { render, screen, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { TelestratorCanvas } from '../components/VideoPlayer/TelestratorCanvas';
import type { Drawing } from '../types';

describe('TelestratorCanvas', () => {
  const defaultProps = {
    matchId: 'match-1',
    currentTime: 42.5,
    existingDrawings: [] as Drawing[],
    onSaveDrawing: vi.fn(),
    onClose: vi.fn(),
  };

  it('renders all drawing tools and action buttons', () => {
    render(<TelestratorCanvas {...defaultProps} />);

    expect(screen.getByTitle('Directional Arrow')).toBeTruthy();
    expect(screen.getByTitle('Player Spotlight')).toBeTruthy();
    expect(screen.getByTitle('Player Tactical Ring')).toBeTruthy();
    expect(screen.getByTitle('Freehand Pen')).toBeTruthy();
    expect(screen.getByTitle('Text Label')).toBeTruthy();

    expect(screen.getByRole('button', { name: /export frame snapshot/i })).toBeTruthy();
    expect(screen.getByRole('button', { name: /undo active stroke/i })).toBeTruthy();
  });

  it('calls onClose when close button is clicked', () => {
    render(<TelestratorCanvas {...defaultProps} />);
    const closeBtn = screen.getByTitle('Exit Telestrator (Hotkey D)');
    fireEvent.click(closeBtn);
    expect(defaultProps.onClose).toHaveBeenCalled();
  });

  it('invokes snapshot export without error', () => {
    const video = document.createElement('video');
    render(<TelestratorCanvas {...defaultProps} videoElement={video} />);

    const exportBtn = screen.getByRole('button', { name: /export frame snapshot/i });
    expect(() => fireEvent.click(exportBtn)).not.toThrow();
  });

  it('disables undo button when there are no active coordinates', () => {
    render(<TelestratorCanvas {...defaultProps} />);
    const undoBtn = screen.getByRole('button', { name: /undo active stroke/i }) as HTMLButtonElement;
    expect(undoBtn.disabled).toBe(true);
  });
});
