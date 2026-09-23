import { fireEvent, render, screen, within } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { SidebarDrawer } from '../components/Sidebar/SidebarTabs';
import type { AnalyticsData, Match } from '../types';

const match: Match = {
  id: 'literal-match', title: 'Test match', home_team: 'Home', away_team: 'Away',
  home_score: 2, away_score: 0, date: '2026-01-01', duration_seconds: 60,
  status: 'ready', processing_progress: 100, video_url: '', views_count: 0,
  lineup: [], journal_notes: '', analysis_mode: 'ml',
};
const analytics: AnalyticsData = {
  home_stats: {
    goals: 2, shots: 3, corners: null, passes_completed: null,
    possession_percent: 60, possession_minutes: 1, possession_won: null,
  },
  away_stats: {
    goals: 0, shots: 1, corners: 4, passes_completed: null,
    possession_percent: 40, possession_minutes: 1, possession_won: null,
  },
  shot_map: [],
  pass_locations: {
    home: { defensive: 1, middle: 2, attacking: 3 },
    away: { defensive: 3, middle: 2, attacking: 1 },
  },
  possession_locations: {
    home: { defensive: 1, middle: 2, attacking: 3 },
    away: { defensive: 3, middle: 2, attacking: 1 },
  },
  pass_strings: { home: [], away: [] },
};

function renderDrawer(data: AnalyticsData | null = analytics) {
  const onSeek = vi.fn();
  render(<SidebarDrawer activeTab="analytics" onClose={vi.fn()} match={match}
    highlights={[]} events={[]} analytics={data} onSeek={onSeek}
    onPlayAllHighlights={vi.fn()} selectedJersey={null} onSelectJersey={vi.fn()} />);
  return onSeek;
}

it('renders an unmeasured stat as an em-dash beside a measured number', () => {
  renderDrawer();
  const row = screen.getByRole('button', { name: '— Corner 4' });
  expect(within(row).getByText('—').getAttribute('title')).toMatch(/Not measured/);
  expect(within(row).getByText('4')).toBeTruthy();
});

it('preserves a measured zero instead of treating it as unavailable', () => {
  renderDrawer();
  const row = screen.getByRole('button', { name: '2 Goal 0' });
  expect(within(row).getByText('0')).toBeTruthy();
  expect(within(row).queryByText('—')).toBeNull();
});

it.each(['Passes completed', 'Possession %', 'Possession won'])(
  'disables the derived metric %s', label => {
    const onSeek = renderDrawer();
    const button = screen.getByText(label).closest('button');
    expect(button).not.toBeNull();
    expect(button!.disabled).toBe(true);
    fireEvent.click(button!);
    expect(onSeek).not.toHaveBeenCalled();
  },
);

it('explains why null ML analytics cannot borrow another pipeline’s numbers', () => {
  renderDrawer(null);
  const reason = screen.getByText(/This match was analysed by the ML pipeline/);
  expect(reason.textContent).toMatch(/separate heuristic pipeline/);
  expect(reason.textContent).toMatch(/misattribute/);
  expect(screen.queryByRole('button', { name: 'Stats' })).toBeNull();
});

it('uses singular stat labels', () => {
  renderDrawer();
  for (const label of ['Goal', 'Shot', 'Corner', 'Foul', 'Free kick', 'Penalty', 'Tackle', 'Throw-in']) {
    expect(screen.getByText(label, { exact: true })).toBeTruthy();
  }
  for (const plural of ['Goals', 'Shots', 'Corners', 'Fouls', 'Free kicks', 'Penalties', 'Tackles', 'Throw-ins']) {
    expect(screen.queryByText(plural, { exact: true })).toBeNull();
  }
});
