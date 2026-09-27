import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { TeamsModal } from '../components/TeamsModal';
import { Team, Match } from '../types';

const mockTeams: Team[] = [
  { id: 'arlington-sa-u16b', name: 'Arlington SA U16B', club_name: 'Arlington Soccer', matches_count: 2 },
  { id: 'mclean-sc-u16b', name: 'McLean SC U16B', club_name: 'McLean SC', matches_count: 0 },
];

const mockMatches: Match[] = [
  {
    id: 'demo-arlington-skyline',
    title: 'Arlington SA U16B ECNL vs. Skyline U16B',
    home_team: 'Arlington SA U16B',
    away_team: 'Skyline U16B',
    team_id: 'arlington-sa-u16b',
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
  },
  {
    id: 'fairfax-union-20260920',
    title: 'Arlington SA U16B ECNL vs. Fairfax Union',
    home_team: 'Arlington SA U16B',
    away_team: 'Fairfax Union',
    team_id: 'arlington-sa-u16b',
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
  },
];

describe('TeamsModal component', () => {
  it('renders teams in folder structure with branding and matches', () => {
    render(
      <TeamsModal
        isOpen={true}
        onClose={vi.fn()}
        teams={mockTeams}
        selectedTeam={mockTeams[0]}
        matches={mockMatches}
        currentMatch={mockMatches[0]}
        onSelectTeam={vi.fn()}
        onSelectMatch={vi.fn()}
        onCreateTeam={vi.fn()}
        onDeleteTeam={vi.fn()}
      />
    );

    // Displays sea branding badge
    expect(screen.getByText('sea')).toBeTruthy();
    expect(screen.getByText('Teams & Match Folders')).toBeTruthy();

    // Renders team folders
    expect(screen.getAllByText('Arlington SA U16B').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('McLean SC U16B')).toBeTruthy();

    // Active destination indicator
    expect(screen.getByText('Selected Team')).toBeTruthy();

    // Shows matches inside expanded Arlington folder
    expect(screen.getByText('Arlington SA U16B ECNL vs. Skyline U16B')).toBeTruthy();
    expect(screen.getByText('Now Playing')).toBeTruthy();
  });

  it('allows adding a new team folder', async () => {
    const onCreateTeam = vi.fn().mockResolvedValue({
      id: 'bethesda-u17',
      name: 'Bethesda SC U17G',
      club_name: 'Bethesda SC',
    });

    render(
      <TeamsModal
        isOpen={true}
        onClose={vi.fn()}
        teams={mockTeams}
        selectedTeam={mockTeams[0]}
        matches={mockMatches}
        currentMatch={mockMatches[0]}
        onSelectTeam={vi.fn()}
        onSelectMatch={vi.fn()}
        onCreateTeam={onCreateTeam}
        onDeleteTeam={vi.fn()}
      />
    );

    // Click Add Team button
    const addTeamBtn = screen.getByRole('button', { name: /add team/i });
    fireEvent.click(addTeamBtn);

    // Fill form
    const nameInput = screen.getByPlaceholderText(/e\.g\. McLean Youth Soccer U16B/i);
    fireEvent.change(nameInput, { target: { value: 'Bethesda SC U17G' } });

    // Submit
    const submitBtn = screen.getByRole('button', { name: /create team folder/i });
    fireEvent.click(submitBtn);

    expect(onCreateTeam).toHaveBeenCalledWith('Bethesda SC U17G', 'Arlington Soccer');
  });

  it('allows selecting a team and selecting a match', () => {
    const onSelectTeam = vi.fn();
    const onSelectMatch = vi.fn();
    const onClose = vi.fn();

    render(
      <TeamsModal
        isOpen={true}
        onClose={onClose}
        teams={mockTeams}
        selectedTeam={mockTeams[0]}
        matches={mockMatches}
        currentMatch={mockMatches[0]}
        onSelectTeam={onSelectTeam}
        onSelectMatch={onSelectMatch}
        onCreateTeam={vi.fn()}
        onDeleteTeam={vi.fn()}
      />
    );

    // Click "Select Team" on McLean SC U16B
    const selectBtns = screen.getAllByRole('button', { name: /select team/i });
    fireEvent.click(selectBtns[0]);
    expect(onSelectTeam).toHaveBeenCalledWith(mockTeams[1]);

    // Click on a match to switch
    const matchRow = screen.getByText('Arlington SA U16B ECNL vs. Fairfax Union');
    fireEvent.click(matchRow);
    expect(onSelectMatch).toHaveBeenCalledWith(mockMatches[1]);
    expect(onClose).toHaveBeenCalled();
  });

  it('allows removing a team with confirmation', async () => {
    const onDeleteTeam = vi.fn().mockResolvedValue(undefined);

    render(
      <TeamsModal
        isOpen={true}
        onClose={vi.fn()}
        teams={mockTeams}
        selectedTeam={mockTeams[0]}
        matches={mockMatches}
        currentMatch={mockMatches[0]}
        onSelectTeam={vi.fn()}
        onSelectMatch={vi.fn()}
        onCreateTeam={vi.fn()}
        onDeleteTeam={onDeleteTeam}
      />
    );

    // Click delete trash icon for McLean team
    const deleteBtn = screen.getByTitle('Delete team folder "McLean SC U16B"');
    fireEvent.click(deleteBtn);

    // Confirmation appears
    expect(screen.getByText('Delete team?')).toBeTruthy();
    const yesBtn = screen.getByRole('button', { name: 'Yes' });
    fireEvent.click(yesBtn);

    expect(onDeleteTeam).toHaveBeenCalledWith('mclean-sc-u16b');
  });

  it('renders federation url badge and creates team with federation url', async () => {
    const onCreateTeam = vi.fn().mockResolvedValue({
      id: 'turo-peira-ccd',
      name: 'CCD Turó de la Peira',
      club_name: 'CCD Turó de la Peira',
      federation_url: 'https://www.fcf.cat/club/2425/turo-peira-ccd',
    });

    const teamsWithFed: Team[] = [
      ...mockTeams,
      {
        id: 'turo-peira-ccd',
        name: 'CCD Turó de la Peira',
        club_name: 'CCD Turó de la Peira',
        federation_url: 'https://www.fcf.cat/club/2425/turo-peira-ccd',
      }
    ];

    render(
      <TeamsModal
        isOpen={true}
        onClose={vi.fn()}
        teams={teamsWithFed}
        selectedTeam={teamsWithFed[0]}
        matches={mockMatches}
        currentMatch={mockMatches[0]}
        onSelectTeam={vi.fn()}
        onSelectMatch={vi.fn()}
        onCreateTeam={onCreateTeam}
        onDeleteTeam={vi.fn()}
      />
    );

    // Federation badge renders
    expect(screen.getByText('FCF.cat')).toBeTruthy();

    // Open add team form
    const addBtn = screen.getByRole('button', { name: /add team/i });
    fireEvent.click(addBtn);

    // Fill form with federation URL
    const nameInput = screen.getByPlaceholderText(/e\.g\. McLean Youth Soccer/i);
    const fedInput = screen.getByPlaceholderText(/e\.g\. https:\/\/www\.fcf\.cat/i);
    fireEvent.change(nameInput, { target: { value: 'Turó Juvenil' } });
    fireEvent.change(fedInput, { target: { value: 'https://www.fcf.cat/club/2425/turo-peira-ccd' } });

    const submitBtn = screen.getByRole('button', { name: /create team folder/i });
    fireEvent.click(submitBtn);

    expect(onCreateTeam).toHaveBeenCalledWith(
      'Turó Juvenil',
      'Arlington Soccer',
      'https://www.fcf.cat/club/2425/turo-peira-ccd'
    );
  });
});
