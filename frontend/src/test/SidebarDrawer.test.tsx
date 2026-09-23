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

// --- Regression: the `unavailable` map must actually reach the DOM. ---
//
// This is the test that was missing. An adversarial audit rendered the real ML
// analytics payload and found the stats table printed "3 Goal 0" -- a 3-0 scoreline
// for a match the backend explicitly documents as having finished 3-3 -- plus
// "50% Possession % 50%", because the frontend never read the backend's
// `unavailable` map. Fifteen tests passed while that was true.
//
// A row named in `unavailable` must render its measured reason, WHATEVER numeric
// value the matching TeamStats field carries. The value alone cannot express
// "never measured": possession_percent is non-Optional and defaults to 50.0, and an
// ML match carries a real detection count in `goals` that is not a scoreline.
const mlAnalytics: AnalyticsData = {
  ...analytics,
  provenance: 'ml',
  home_stats: { ...analytics.home_stats, goals: 3, throw_ins: 28, possession_percent: 50 },
  away_stats: { ...analytics.away_stats, goals: 0, throw_ins: 18, possession_percent: 50 },
  unavailable: {
    goals: 'detection count, not a scoreline: the match was 3-3',
    throw_ins: 'over-counts: 52 detected against 38 in the reference',
    possession_percent: 'Tier B closed by the pre-registered 15 fps gate',
  },
};

it('renders the measured reason, not the number, for a row named in unavailable', () => {
  renderDrawer(mlAnalytics);

  for (const [label, reason] of [
    ['Goal', /not a scoreline/],
    ['Throw-in', /over-counts/],
    ['Possession %', /15 fps gate/],
  ] as const) {
    const row = screen.getByRole('button', { name: new RegExp(`— ${label} —`) });
    const dashes = within(row).getAllByText('—');
    expect(dashes.length).toBe(2);
    for (const d of dashes) expect(d.getAttribute('title')).toMatch(reason);
  }
});

it('never renders a detected goal count as a scoreline', () => {
  renderDrawer(mlAnalytics);
  const row = screen.getByRole('button', { name: /Goal/ });
  // The 3 and the 0 must NOT be present: together they read as "3 - 0".
  expect(within(row).queryByText('3')).toBeNull();
  expect(within(row).queryByText('0')).toBeNull();
});

it('still renders a real number when the row is not named in unavailable', () => {
  renderDrawer(mlAnalytics);
  const row = screen.getByRole('button', { name: '3 Shot 1' });
  expect(within(row).getByText('3')).toBeTruthy();
  expect(within(row).queryByText('—')).toBeNull();
});
