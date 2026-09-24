import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Header } from '../components/Header';
import { Match } from '../types';

const mockMatch1: Match = {
  id: 'demo-arlington-skyline',
  title: 'Arlington SA U16B ECNL (26-27) vs. Skyline U16B ECNL',
  home_team: 'Arlington SA U16B ECNL',
  away_team: 'Skyline U16B ECNL',
  home_score: 3,
  away_score: 3,
  date: 'Sep 13, 2026',
  duration_seconds: 90.0,
  status: 'ready',
  processing_progress: 100.0,
  lineup: [],
  journal_notes: '',
  video_url: '/media/demo_match.mp4',
  panoramic_url: '/media/demo_match.mp4',
  thumbnail_url: '/media/demo_thumb.jpg',
  views_count: 0,
  analysis_mode: 'demo',
  analysis_confidence: 'low',
};

const mockMatch2: Match = {
  id: 'fairfax-union-20260920',
  title: 'Arlington SA U16B ECNL (26-27) vs. Fairfax Union',
  home_team: 'Arlington SA U16B ECNL',
  away_team: 'Fairfax Union',
  home_score: 3,
  away_score: 0,
  date: 'Sep 20, 2026',
  duration_seconds: 30.0,
  status: 'ready',
  processing_progress: 100.0,
  lineup: [],
  journal_notes: '',
  video_url: '/media/fairfax_union_sample_30s.mp4',
  panoramic_url: '/media/fairfax_union_sample_30s.mp4',
  thumbnail_url: '/media/demo_thumb.jpg',
  views_count: 32,
  analysis_mode: 'ml',
  analysis_confidence: 'medium',
};

describe('Header component', () => {
  it('renders current match title and mode badge', () => {
    render(
      <Header
        currentMatch={mockMatch1}
        matches={[mockMatch1, mockMatch2]}
        onOpenBurgerMenu={vi.fn()}
        onOpenUpload={vi.fn()}
      />
    );
    expect(screen.getByText('Arlington SA U16B ECNL (26-27) vs. Skyline U16B ECNL')).toBeTruthy();
    expect(screen.getByText('Demo Data')).toBeTruthy();
  });

  it('opens match switcher dropdown and triggers onSelectMatch', () => {
    const onSelectMatch = vi.fn();
    render(
      <Header
        currentMatch={mockMatch1}
        matches={[mockMatch1, mockMatch2]}
        onSelectMatch={onSelectMatch}
        onOpenBurgerMenu={vi.fn()}
        onOpenUpload={vi.fn()}
      />
    );

    // Click match title trigger
    const trigger = screen.getByTitle('Click to switch match recording');
    fireEvent.click(trigger);

    // Dropdown should be open and show second match
    expect(screen.getByText('Switch Match Recording (2)')).toBeTruthy();
    const secondMatchBtn = screen.getByText('Arlington SA U16B ECNL (26-27) vs. Fairfax Union');
    expect(secondMatchBtn).toBeTruthy();

    // Click to select
    fireEvent.click(secondMatchBtn);
    expect(onSelectMatch).toHaveBeenCalledWith(mockMatch2);
  });

  it('opens download menu and renders full match video, zip, json, and csv options', async () => {
    render(
      <Header
        currentMatch={mockMatch1}
        matches={[mockMatch1]}
        onOpenBurgerMenu={vi.fn()}
        onOpenUpload={vi.fn()}
      />
    );

    const downloadTrigger = screen.getByRole('button', { name: /download match media/i });
    fireEvent.click(downloadTrigger);

    expect(screen.getByText('Full Match Video')).toBeTruthy();
    expect(screen.getByText('Export Highlights (ZIP)')).toBeTruthy();
    expect(screen.getByText('Match Analytics (JSON)')).toBeTruthy();
    expect(screen.getByText('Events & Highlights (CSV)')).toBeTruthy();

    const videoLink = screen.getByText('Full Match Video').closest('a');
    expect(videoLink?.getAttribute('href')).toBe('/media/demo_match.mp4');

    const zipLink = screen.getByText('Export Highlights (ZIP)').closest('a');
    expect(zipLink?.getAttribute('href')).toContain('/matches/demo-arlington-skyline/highlights/export');
  });
});
