import { fireEvent, render, screen, within } from '@testing-library/react';
import { expect, it, vi } from 'vitest';
import { SidebarDrawer } from '../components/Sidebar/SidebarTabs';
import { api } from '../services/api';
import type { AnalyticsData, Match, Highlight, Event } from '../types';

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

it('renders top KPI delta cards with measured metrics and diff badges', () => {
  renderDrawer(analytics);
  expect(screen.getByText('Goals scored')).toBeTruthy();
  expect(screen.getByText('+1')).toBeTruthy();
  expect(screen.getByText('Shots attempted')).toBeTruthy();
  expect(screen.getByText('-5')).toBeTruthy();
  expect(screen.getByText('Match possession')).toBeTruthy();
  expect(screen.getByText('-1%')).toBeTruthy();
});

it('renders pass strings summary metrics when data is present', () => {
  const analyticsWithStrings: AnalyticsData = {
    ...analytics,
    pass_strings: {
      home: [15, 10, 1, 4, 2, 0, 1, 2], // 3..10+
      away: [12, 3, 2, 1, 0, 0, 0, 0],
    },
  };
  renderDrawer(analyticsWithStrings);
  // Expand pass strings accordion
  const passStringsSummary = screen.getByRole('button', { name: /Pass strings/ });
  fireEvent.click(passStringsSummary);

  expect(screen.getByText('3 to 5 passes')).toBeTruthy();
  expect(screen.getByText('26')).toBeTruthy(); // 15 + 10 + 1
  const sixPlusContainer = screen.getByText('6+ passes').parentElement!;
  expect(within(sixPlusContainer).getByText('9')).toBeTruthy(); // 4 + 2 + 0 + 1 + 2
  expect(screen.getByText('Longest string')).toBeTruthy();
  expect(screen.getByText('10')).toBeTruthy();
});

it('toggles benchmark mode and displays ground truth comparison rows', async () => {
  const fakeBenchmark = {
    match_id: 'literal-match',
    benchmark_match: 'Arlington vs Skyline',
    comparison: {
      metrics: {
        goal: { ref_home: 3, ref_away: 3, pred_home: 2, pred_away: 0, status: 'measured', reason: null, home_delta: -1, away_delta: -3, exact_match: false },
        shot: { ref_home: 9, ref_away: 10, pred_home: 3, pred_away: 1, status: 'measured', reason: null, home_delta: -6, away_delta: -9, exact_match: false },
      },
      evaluated_count: 2,
      exact_match_count: 0,
      exact_match_ratio: 0.0,
    },
    live_ground_truth: {
      shot_map: {
        own: {
          goals: 3, shots: 9, total_attempts: 12, conversion_rate_pct: 25,
          inside_box_conversion_rate_pct: 50, outside_box_conversion_rate_pct: 0,
          attempts_inside_box_pct: 50, attempts_outside_box_pct: 50,
          markers: [{ type: 'goal', time_str: '02:43', time_s: 163, left_pct: 90.28, bottom_pct: 55.84 }],
        },
        opponent: {
          goals: 3, shots: 10, total_attempts: 13, conversion_rate_pct: 23,
          inside_box_conversion_rate_pct: 20, outside_box_conversion_rate_pct: 25,
          attempts_inside_box_pct: 38, attempts_outside_box_pct: 62,
          markers: [{ type: 'shot', time_str: '07:59', time_s: 479, left_pct: 86.66, bottom_pct: 63.70 }],
        },
      },
    },
  };
  vi.spyOn(api, 'getBenchmark').mockResolvedValueOnce(fakeBenchmark);

  renderDrawer();
  const toggleBtn = screen.getByRole('button', { name: 'Compare Veo' });
  fireEvent.click(toggleBtn);

  expect(await screen.findByText('Veo Benchmark ON')).toBeTruthy();
  expect(await screen.findByText('Veo Benchmark Reference')).toBeTruthy();
  expect(screen.getByText(/Arlington vs Skyline/)).toBeTruthy();
  expect(screen.getByText('Δ-1')).toBeTruthy();
  expect(screen.getByText('Veo: 25%')).toBeTruthy();
  expect(screen.getAllByText('Veo: 50%').length).toBeGreaterThanOrEqual(1);
  expect(screen.getByText('Veo Goal')).toBeTruthy();
  expect(screen.getByText('Veo Shot')).toBeTruthy();
});

it('renders tactical half-pitch shot map with 5 conversion breakdown lines', () => {
  const analyticsWithShots: AnalyticsData = {
    ...analytics,
    shot_map: [
      { id: 's1', timestamp: 10, period: 1, team: 'home', player_jersey: '10', outcome: 'goal', x: 95, y: 34, is_inside_box: true, label: 'Goal' },
      { id: 's2', timestamp: 25, period: 1, team: 'home', player_jersey: '8', outcome: 'saved', x: 80, y: 25, is_inside_box: false, label: 'Shot' },
    ],
  };
  renderDrawer(analyticsWithShots);

  const conversionLines = screen.getAllByText(/conversion rate\./);
  expect(conversionLines.length).toBeGreaterThanOrEqual(3);
  expect(screen.getByText(/of total attempts inside box\./)).toBeTruthy();
  expect(screen.getByText(/of total attempts outside box\./)).toBeTruthy();
  expect(screen.getByText(/LEFT WING →/)).toBeTruthy();
  expect(screen.getByText(/RIGHT WING →/)).toBeTruthy();
  expect(screen.getByRole('img', { name: '2D soccer half-pitch shot map' })).toBeTruthy();
});

it('renders player moments list and allows seeking when a player jersey is selected', () => {
  const onSeek = vi.fn();
  const onSelectJersey = vi.fn();
  const testMatch: Match = {
    ...match,
    lineup: [
      { jersey: '10', name: 'Player 10', position: 'FWD', is_starter: true, minutes_played: 80 },
      { jersey: '14', name: 'Player 14', position: 'MID', is_starter: true, minutes_played: null },
    ],
  };
  const testHighlights: Highlight[] = [
    {
      id: 'h1',
      match_id: testMatch.id,
      title: 'Goal - #10',
      event_type: 'goal',
      start_time: 18.0,
      end_time: 28.0,
      period: 1,
      team: 'home',
      player_jersey: '10',
      is_ai_detected: true,
      tags: ['Goal', 'Inside Box'],
      comments_count: 0,
    },
  ];
  const testEvents: Event[] = [
    {
      id: 'e1',
      match_id: testMatch.id,
      timestamp: 45.0,
      period: 1,
      event_type: 'Shot',
      team: 'home',
      player_jersey: '10',
      description: 'Shot on goal by #10',
      pitch_x: 95.0,
      pitch_y: 34.0,
    },
  ];

  // 1. Render all players view (selectedJersey = null)
  const { rerender } = render(
    <SidebarDrawer
      activeTab="players"
      onClose={vi.fn()}
      match={testMatch}
      highlights={testHighlights}
      events={testEvents}
      analytics={analytics}
      onSeek={onSeek}
      onPlayAllHighlights={vi.fn()}
      selectedJersey={null}
      onSelectJersey={onSelectJersey}
    />
  );

  // Checks both players exist with honest unmeasured / measured minutes
  expect(screen.getByText('Player 10')).toBeTruthy();
  expect(screen.getByText('FWD • 80 mins played')).toBeTruthy();
  expect(screen.getByText('Player 14')).toBeTruthy();
  expect(screen.getByText('MID • — mins played')).toBeTruthy();

  // Click on Player 10 card to select
  fireEvent.click(screen.getByText('Player 10'));
  expect(onSelectJersey).toHaveBeenCalledWith('10');

  // 2. Re-render with selectedJersey="10"
  rerender(
    <SidebarDrawer
      activeTab="players"
      onClose={vi.fn()}
      match={testMatch}
      highlights={testHighlights}
      events={testEvents}
      analytics={analytics}
      onSeek={onSeek}
      onPlayAllHighlights={vi.fn()}
      selectedJersey="10"
      onSelectJersey={onSelectJersey}
    />
  );

  // Verify dedicated player header and moments count
  expect(screen.getByText('2 moments')).toBeTruthy();
  expect(screen.getByText('Timeline Moments')).toBeTruthy();

  // Verify moments items
  expect(screen.getByText('Goal - #10')).toBeTruthy();
  expect(screen.getByText('Shot on goal by #10')).toBeTruthy();

  // Click on a moment to seek
  fireEvent.click(screen.getByText('Goal - #10'));
  expect(onSeek).toHaveBeenCalledWith(18.0);

  // Click "All Players" button to clear
  const allPlayersBtn = screen.getByRole('button', { name: /All Players/ });
  fireEvent.click(allPlayersBtn);
  expect(onSelectJersey).toHaveBeenCalledWith(null);
});

it('filters highlights list when a player jersey is selected', () => {
  const onSelectJersey = vi.fn();
  const testHighlights: Highlight[] = [
    {
      id: 'h1',
      match_id: 'literal-match',
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
      match_id: 'literal-match',
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

  render(
    <SidebarDrawer
      activeTab="highlights"
      onClose={vi.fn()}
      match={match}
      highlights={testHighlights}
      events={[]}
      analytics={analytics}
      onSeek={vi.fn()}
      onPlayAllHighlights={vi.fn()}
      selectedJersey="10"
      onSelectJersey={onSelectJersey}
    />
  );

  // Active filter badge is displayed
  expect(screen.getByText('Filtered to #10')).toBeTruthy();
  expect(screen.getByText('(1 clip)')).toBeTruthy();

  // Only Player 10 highlight is rendered
  expect(screen.getByText('Goal - #10')).toBeTruthy();
  expect(screen.queryByText('Shot - #14')).toBeNull();

  // Clicking Clear invokes onSelectJersey(null)
  const clearBtn = screen.getByRole('button', { name: 'Clear' });
  fireEvent.click(clearBtn);
  expect(onSelectJersey).toHaveBeenCalledWith(null);
});
