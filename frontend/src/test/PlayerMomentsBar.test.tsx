import { render, screen } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { PlayerMomentsBar } from '../components/PlayerMomentsBar';
import type { PlayerRoster } from '../types';

it.each(['', '?', 'unknown', '   '])('keeps unknown jersey %j blank without inventing a name', jersey => {
  const player: PlayerRoster = {
    jersey, name: '', position: 'MID', is_starter: true, minutes_played: 3,
  };
  render(<PlayerMomentsBar lineup={[player]} selectedJersey={null} onSelectJersey={vi.fn()} />);
  const button = screen.getByRole('button', { name: 'Player' });
  expect(button.getAttribute('aria-label')).toBe('Player ');
  expect(button.getAttribute('title')).toBe('Player ');
  expect(button.textContent).toBe('');
});

it('shows a measured jersey number without adding a player name', () => {
  render(<PlayerMomentsBar lineup={[{
    jersey: '8', name: '', position: 'MID', is_starter: true, minutes_played: 3,
  }]} selectedJersey={null} onSelectJersey={vi.fn()} />);
  expect(screen.getByRole('button', { name: 'Player 8' }).textContent).toBe('8');
});

it('renders reel download link when a jersey is selected and matchId is provided', () => {
  render(<PlayerMomentsBar
    matchId="demo-match"
    lineup={[{ jersey: '8', name: 'John Doe', position: 'MID', is_starter: true, minutes_played: 90 }]}
    selectedJersey="8"
    onSelectJersey={vi.fn()}
  />);
  const link = screen.getByRole('link', { name: /download mp4 reel for jersey 8/i });
  expect(link).toBeTruthy();
  expect(link.getAttribute('href')).toContain('/matches/demo-match/players/8/reel');
});
