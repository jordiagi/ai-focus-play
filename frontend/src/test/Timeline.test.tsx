import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { Timeline } from '../components/VideoPlayer/Timeline';
import type { Event, Highlight } from '../types';

describe('Timeline Player Moments Filtering', () => {
  const mockHighlights: Highlight[] = [
    {
      id: 'h1',
      match_id: 'm1',
      title: 'Goal - #10',
      event_type: 'goal',
      start_time: 12.0,
      end_time: 24.0,
      period: 1,
      team: 'home',
      player_jersey: '10',
      is_ai_detected: true,
      tags: ['Goal'],
      comments_count: 0,
    },
    {
      id: 'h2',
      match_id: 'm1',
      title: 'Shot - #14',
      event_type: 'shot',
      start_time: 32.0,
      end_time: 42.0,
      period: 1,
      team: 'home',
      player_jersey: '14',
      is_ai_detected: true,
      tags: ['Shot'],
      comments_count: 0,
    },
  ];

  const mockEvents: Event[] = [
    {
      id: 'e1',
      match_id: 'm1',
      timestamp: 18.0,
      period: 1,
      event_type: 'Goal',
      team: 'home',
      player_jersey: '10',
      description: 'Goal scored by #10',
      pitch_x: 98.0,
      pitch_y: 32.0,
    },
    {
      id: 'e2',
      match_id: 'm1',
      timestamp: 36.0,
      period: 1,
      event_type: 'Shot',
      team: 'home',
      player_jersey: '14',
      description: 'Shot by #14 saved',
      pitch_x: 88.0,
      pitch_y: 35.0,
    },
  ];

  it('renders all markers normally when no jersey is selected', () => {
    const onSeek = vi.fn();
    render(
      <Timeline
        currentTime={0}
        duration={90}
        highlights={mockHighlights}
        events={mockEvents}
        onSeek={onSeek}
        selectedJersey={null}
      />
    );

    expect(screen.queryByText(/Filtered: #/)).toBeNull();
    const marker10 = screen.getByRole('button', { name: 'Player 10 Goal' });
    const marker14 = screen.getByRole('button', { name: 'Player 14 Shot' });
    expect(marker10).toBeTruthy();
    expect(marker14).toBeTruthy();
  });

  it('displays filtered player badge and emphasizes selected player markers', () => {
    const onSelectJersey = vi.fn();
    const onSeek = vi.fn();
    render(
      <Timeline
        currentTime={0}
        duration={90}
        highlights={mockHighlights}
        events={mockEvents}
        onSeek={onSeek}
        selectedJersey="10"
        onSelectJersey={onSelectJersey}
      />
    );

    // Shows filter indicator
    expect(screen.getByText('Filtered: #10')).toBeTruthy();
    expect(screen.getByText('(2 moments)')).toBeTruthy();

    // Check click on Clear
    const clearBtn = screen.getByRole('button', { name: 'Clear player filter' });
    fireEvent.click(clearBtn);
    expect(onSelectJersey).toHaveBeenCalledWith(null);

    // Selected player marker has active ring and scale
    const marker10 = screen.getByRole('button', { name: 'Player 10 Goal' });
    expect(marker10.className).toContain('ring-2 ring-white scale-150');

    // Non-selected player marker is dimmed
    const marker14 = screen.getByRole('button', { name: 'Player 14 Shot' });
    expect(marker14.className).toContain('opacity-20');

    // Clicking marker triggers seek
    fireEvent.click(marker10);
    expect(onSeek).toHaveBeenCalledWith(18.0);
  });
});
