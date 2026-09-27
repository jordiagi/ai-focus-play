import React, { useState, useMemo } from 'react';
import { 
  Folder, FolderOpen, ChevronRight, ChevronDown, Plus, Trash2, 
  Check, X, Video, Search, UploadCloud, Shield, AlertCircle,
  Globe, ExternalLink, Edit2
} from 'lucide-react';
import { Team, Match } from '../types';

interface TeamsModalProps {
  isOpen: boolean;
  onClose: () => void;
  teams: Team[];
  selectedTeam: Team | null;
  matches: Match[];
  currentMatch: Match | null;
  onSelectTeam: (team: Team) => void;
  onSelectMatch: (match: Match) => void;
  onCreateTeam: (name: string, clubName?: string, federationUrl?: string) => Promise<Team | void>;
  onUpdateTeam?: (teamId: string, data: { name?: string; club_name?: string; federation_url?: string }) => Promise<Team | void>;
  onDeleteTeam: (teamId: string) => Promise<void>;
  onOpenUpload?: (preselectedTeam?: Team) => void;
}

export const TeamsModal: React.FC<TeamsModalProps> = ({
  isOpen,
  onClose,
  teams,
  selectedTeam,
  matches,
  currentMatch,
  onSelectTeam,
  onSelectMatch,
  onCreateTeam,
  onUpdateTeam,
  onDeleteTeam,
  onOpenUpload,
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [showAddForm, setShowAddForm] = useState(false);
  const [newTeamName, setNewTeamName] = useState('');
  const [newClubName, setNewClubName] = useState('Arlington Soccer');
  const [newFederationUrl, setNewFederationUrl] = useState('');
  const [editingTeamId, setEditingTeamId] = useState<string | null>(null);
  const [editFederationUrl, setEditFederationUrl] = useState('');
  const [expandedTeamIds, setExpandedTeamIds] = useState<Set<string>>(() => {
    // Default expand selected team or first team
    const init = new Set<string>();
    if (selectedTeam) {
      init.add(selectedTeam.id);
    } else if (teams.length > 0) {
      init.add(teams[0].id);
    }
    return init;
  });
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  const toggleExpand = (teamId: string) => {
    setExpandedTeamIds(prev => {
      const next = new Set(prev);
      if (next.has(teamId)) {
        next.delete(teamId);
      } else {
        next.add(teamId);
      }
      return next;
    });
  };

  // Helper to derive 3-letter crest initials from team name
  const getCrestInitials = (name: string) => {
    const parts = name.trim().split(/\s+/);
    if (parts.length >= 3) {
      return (parts[0][0] + parts[1][0] + parts[2][0]).toUpperCase();
    }
    if (parts.length === 2) {
      return (parts[0][0] + parts[1].slice(0, 2)).toUpperCase();
    }
    return name.slice(0, 3).toUpperCase();
  };

  // Associate matches to teams
  const teamMatchesMap = useMemo(() => {
    const map = new Map<string, Match[]>();
    for (const team of teams) {
      map.set(team.id, []);
    }

    for (const match of matches) {
      let assignedTeamId = match.team_id;
      // Fallback matching if team_id not explicitly set
      if (!assignedTeamId) {
        const found = teams.find(t => 
          match.home_team.toLowerCase().includes(t.name.toLowerCase()) || 
          t.name.toLowerCase().includes(match.home_team.toLowerCase())
        );
        assignedTeamId = found ? found.id : (teams[0]?.id || 'arlington-sa-u16b');
      }

      const list = map.get(assignedTeamId);
      if (list) {
        list.push(match);
      } else if (teams.length > 0) {
        // Fallback into first team if mapped team doesn't exist
        const defaultList = map.get(teams[0].id);
        if (defaultList) defaultList.push(match);
      }
    }
    return map;
  }, [teams, matches]);

  // Filtered teams based on search query
  const filteredTeams = useMemo(() => {
    if (!searchQuery.trim()) return teams;
    const q = searchQuery.toLowerCase();
    return teams.filter(t => {
      const nameMatch = t.name.toLowerCase().includes(q);
      const clubMatch = (t.club_name || '').toLowerCase().includes(q);
      const mList = teamMatchesMap.get(t.id) || [];
      const matchFound = mList.some(m => m.title.toLowerCase().includes(q));
      return nameMatch || clubMatch || matchFound;
    });
  }, [teams, searchQuery, teamMatchesMap]);

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = newTeamName.trim();
    if (!trimmed) {
      setFormError('Please enter a team name');
      return;
    }

    setIsSubmitting(true);
    setFormError(null);
    try {
      const fedUrl = newFederationUrl.trim();
      const created = fedUrl
        ? await onCreateTeam(trimmed, newClubName.trim() || undefined, fedUrl)
        : await onCreateTeam(trimmed, newClubName.trim() || undefined);
      if (created) {
        setExpandedTeamIds(prev => new Set([...prev, created.id]));
        onSelectTeam(created);
      }
      setNewTeamName('');
      setNewFederationUrl('');
      setShowAddForm(false);
    } catch (err: any) {
      setFormError(err.message || 'Failed to create team');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSaveFederationUrl = async (teamId: string) => {
    if (!onUpdateTeam) return;
    try {
      await onUpdateTeam(teamId, { federation_url: editFederationUrl.trim() || undefined });
      setEditingTeamId(null);
      setEditFederationUrl('');
    } catch (err: any) {
      console.error('Failed to update federation URL:', err);
    }
  };

  const handleDeleteTeam = async (teamId: string) => {
    try {
      await onDeleteTeam(teamId);
      setConfirmDeleteId(null);
    } catch (err: any) {
      console.error('Failed to delete team:', err);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-xs p-4">
      <div className="bg-[#12141a] border border-[#262c3b] w-full max-w-2xl rounded-2xl shadow-2xl flex flex-col max-h-[85vh] overflow-hidden text-white animate-in fade-in duration-150">
        
        {/* Header */}
        <div className="px-6 py-4 border-b border-[#222] flex items-center justify-between shrink-0 bg-[#161922]">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-xl bg-[#00E676]/15 border border-[#00E676]/30 flex items-center justify-center text-[#00E676]">
              <Folder className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h2 className="text-base font-bold text-white tracking-tight">Teams & Match Folders</h2>
                <span className="text-[10px] bg-[#222836] border border-[#30384a] text-gray-300 font-mono px-2 py-0.5 rounded-full">
                  sea
                </span>
              </div>
              <p className="text-xs text-gray-400">Manage club teams and organize recordings into folders</p>
            </div>
          </div>

          <div className="flex items-center space-x-2">
            {!showAddForm && (
              <button
                onClick={() => {
                  setShowAddForm(true);
                  setFormError(null);
                }}
                className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-[#00E676] hover:bg-[#00c968] text-black font-semibold text-xs transition cursor-pointer"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Add Team</span>
              </button>
            )}
            <button
              onClick={onClose}
              className="p-1.5 rounded-lg text-gray-400 hover:text-white hover:bg-[#222836] transition cursor-pointer"
              title="Close"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Search & Notice Bar */}
        <div className="px-6 py-3 border-b border-[#1f2430] bg-[#141720] flex items-center justify-between gap-3 shrink-0">
          <div className="relative flex-1">
            <Search className="w-4 h-4 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
            <input
              type="text"
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              placeholder="Filter teams or matches..."
              className="w-full bg-[#1b202c] border border-[#2b3345] rounded-xl pl-9 pr-3 py-1.5 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-[#00E676]"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery('')}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white text-xs"
              >
                Clear
              </button>
            )}
          </div>

          {selectedTeam && (
            <div className="hidden sm:flex items-center space-x-1.5 text-xs text-gray-300 bg-[#1b202c] px-3 py-1.5 rounded-xl border border-[#2d3648] shrink-0">
              <span className="text-gray-400">Active Destination:</span>
              <span className="font-semibold text-[#00E676] truncate max-w-[150px]">{selectedTeam.name}</span>
            </div>
          )}
        </div>

        {/* Add Team Inline Form */}
        {showAddForm && (
          <form onSubmit={handleCreateSubmit} className="p-4 bg-[#191e2b] border-b border-[#2b3345] shrink-0 space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-white flex items-center space-x-1.5">
                <Plus className="w-3.5 h-3.5 text-[#00E676]" />
                <span>Create New Team Folder</span>
              </span>
              <button
                type="button"
                onClick={() => setShowAddForm(false)}
                className="text-gray-400 hover:text-white text-xs"
              >
                Cancel
              </button>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <label className="block text-[11px] font-medium text-gray-300 mb-1">Team Name *</label>
                <input
                  type="text"
                  value={newTeamName}
                  onChange={e => setNewTeamName(e.target.value)}
                  placeholder="e.g. McLean Youth Soccer U16B"
                  required
                  autoFocus
                  className="w-full bg-[#11141c] border border-[#2d364a] rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[#00E676]"
                />
              </div>

              <div>
                <label className="block text-[11px] font-medium text-gray-300 mb-1">Club / Organization</label>
                <input
                  type="text"
                  value={newClubName}
                  onChange={e => setNewClubName(e.target.value)}
                  placeholder="e.g. Arlington Soccer"
                  className="w-full bg-[#11141c] border border-[#2d364a] rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[#00E676]"
                />
              </div>
            </div>

            <div>
              <label className="block text-[11px] font-medium text-gray-300 mb-1">
                Federation / League Website URL (Optional)
              </label>
              <div className="relative">
                <Globe className="w-3.5 h-3.5 text-gray-500 absolute left-2.5 top-2.5" />
                <input
                  type="url"
                  value={newFederationUrl}
                  onChange={e => setNewFederationUrl(e.target.value)}
                  placeholder="e.g. https://www.fcf.cat/club/2425/turo-peira-ccd or https://theecnl.com/sports/mbkb"
                  className="w-full bg-[#11141c] border border-[#2d364a] rounded-lg pl-8 pr-3 py-1.5 text-xs text-white focus:outline-none focus:border-[#00E676]"
                />
              </div>
              <p className="text-[10px] text-gray-500 mt-1">
                Used to verify schedules, fetch official match sheets (actas), reconcile goals/cards/subs, and reinforce jersey OCR.
              </p>
            </div>

            {formError && (
              <div className="flex items-center space-x-1.5 text-xs text-red-400">
                <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                <span>{formError}</span>
              </div>
            )}

            <div className="flex justify-end space-x-2 pt-1">
              <button
                type="button"
                onClick={() => setShowAddForm(false)}
                className="px-3 py-1.5 rounded-lg border border-[#2d364a] text-xs text-gray-300 hover:bg-[#202738] transition cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={isSubmitting || !newTeamName.trim()}
                className="px-4 py-1.5 rounded-lg bg-[#00E676] hover:bg-[#00c968] text-black font-bold text-xs disabled:opacity-50 transition cursor-pointer"
              >
                {isSubmitting ? 'Creating...' : 'Create Team Folder'}
              </button>
            </div>
          </form>
        )}

        {/* Folder Hierarchy List */}
        <div className="flex-1 overflow-y-auto p-4 space-y-2.5">
          {filteredTeams.length === 0 ? (
            <div className="py-12 text-center text-gray-400">
              <Folder className="w-10 h-10 mx-auto text-gray-600 mb-2" />
              <p className="text-sm font-semibold text-gray-300">No teams found</p>
              <p className="text-xs text-gray-500 mt-1">
                {searchQuery ? 'Try matching another search query' : 'Create a new team folder to get started'}
              </p>
            </div>
          ) : (
            filteredTeams.map(team => {
              const isSelected = selectedTeam?.id === team.id;
              const isExpanded = expandedTeamIds.has(team.id);
              const teamMatches = teamMatchesMap.get(team.id) || [];
              const initials = getCrestInitials(team.name);

              return (
                <div
                  key={team.id}
                  className={`rounded-xl border transition-all duration-150 overflow-hidden ${
                    isSelected
                      ? 'bg-[#181d29] border-[#00E676]/40 shadow-lg'
                      : 'bg-[#151822] border-[#242b3b] hover:border-[#353e52]'
                  }`}
                >
                  {/* Folder Row Header */}
                  <div className="p-3 flex items-center justify-between gap-3 group">
                    <div className="flex items-center space-x-2.5 flex-1 min-w-0">
                      {/* Expand / Collapse toggle */}
                      <button
                        onClick={() => toggleExpand(team.id)}
                        className="p-1 rounded hover:bg-[#242b3b] text-gray-400 hover:text-white transition cursor-pointer shrink-0"
                        title={isExpanded ? 'Collapse folder' : 'Expand folder'}
                      >
                        {isExpanded ? (
                          <ChevronDown className="w-4 h-4 text-[#00E676]" />
                        ) : (
                          <ChevronRight className="w-4 h-4" />
                        )}
                      </button>

                      {/* Folder Icon */}
                      <div 
                        onClick={() => toggleExpand(team.id)}
                        className="cursor-pointer shrink-0"
                      >
                        {isExpanded ? (
                          <FolderOpen className={`w-5 h-5 ${isSelected ? 'text-[#00E676]' : 'text-amber-400'}`} />
                        ) : (
                          <Folder className={`w-5 h-5 ${isSelected ? 'text-[#00E676]' : 'text-gray-400'}`} />
                        )}
                      </div>

                      {/* Team Crest Badge */}
                      <div className="w-7 h-7 rounded-lg bg-gradient-to-tr from-[#002d62] to-[#c41230] p-0.5 flex items-center justify-center shrink-0 shadow">
                        <span className="text-[9px] font-black text-white tracking-wider">
                          {initials}
                        </span>
                      </div>

                      {/* Team Info */}
                      <div 
                        onClick={() => toggleExpand(team.id)}
                        className="min-w-0 flex-1 cursor-pointer"
                      >
                        <div className="flex items-center space-x-2">
                          <span className="text-xs font-bold text-white truncate hover:text-[#00E676] transition">
                            {team.name}
                          </span>
                          {isSelected && (
                            <span className="bg-[#00E676]/20 border border-[#00E676]/40 text-[#00E676] text-[9px] font-bold px-1.5 py-0.2 rounded-full shrink-0">
                              Selected Team
                            </span>
                          )}
                        </div>
                        <div className="flex items-center space-x-2 text-[10px] text-gray-400 truncate">
                          <span>{team.club_name || 'Club'} • {teamMatches.length} {teamMatches.length === 1 ? 'game' : 'games'}</span>
                          {team.federation_url ? (
                            <a
                              href={team.federation_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              onClick={e => e.stopPropagation()}
                              className="inline-flex items-center space-x-1 text-[9px] text-[#00E676] bg-[#00E676]/10 hover:bg-[#00E676]/20 border border-[#00E676]/30 px-1.5 py-0.2 rounded font-medium transition"
                              title={`Federation URL: ${team.federation_url}`}
                            >
                              <Globe className="w-2.5 h-2.5" />
                              <span>{team.federation_url.includes('fcf.cat') ? 'FCF.cat' : (team.federation_url.includes('theecnl.com') ? 'ECNL' : 'Federation')}</span>
                              <ExternalLink className="w-2 h-2" />
                            </a>
                          ) : onUpdateTeam ? (
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                setEditingTeamId(team.id);
                                setEditFederationUrl(team.federation_url || '');
                              }}
                              className="inline-flex items-center space-x-1 text-[9px] text-gray-400 hover:text-white bg-[#222836] hover:bg-[#2c3447] border border-[#30384a] px-1.5 py-0.2 rounded transition cursor-pointer"
                              title="Add Federation / League URL"
                            >
                              <Plus className="w-2.5 h-2.5" />
                              <span>Link Fed</span>
                            </button>
                          ) : null}
                        </div>
                      </div>
                    </div>

                    {/* Folder Row Actions */}
                    <div className="flex items-center space-x-1.5 shrink-0">
                      {isSelected ? (
                        <div className="flex items-center space-x-1 text-[11px] font-medium text-[#00E676] bg-[#00E676]/10 px-2.5 py-1 rounded-lg border border-[#00E676]/30">
                          <Check className="w-3.5 h-3.5" />
                          <span>Active</span>
                        </div>
                      ) : (
                        <button
                          onClick={() => onSelectTeam(team)}
                          className="px-2.5 py-1 rounded-lg text-xs font-semibold bg-[#222838] hover:bg-[#2c3447] text-gray-200 hover:text-white border border-[#323d52] transition cursor-pointer"
                          title="Set as selected destination team for uploads"
                        >
                          Select Team
                        </button>
                      )}

                      {/* Delete Team Button */}
                      {confirmDeleteId === team.id ? (
                        <div className="flex items-center space-x-1 bg-red-950/80 border border-red-800 p-1 rounded-lg">
                          <span className="text-[10px] text-red-200 px-1">Delete team?</span>
                          <button
                            onClick={() => handleDeleteTeam(team.id)}
                            className="bg-red-600 hover:bg-red-500 text-white text-[10px] font-bold px-2 py-0.5 rounded cursor-pointer"
                          >
                            Yes
                          </button>
                          <button
                            onClick={() => setConfirmDeleteId(null)}
                            className="text-gray-300 hover:text-white text-[10px] px-1 cursor-pointer"
                          >
                            No
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => setConfirmDeleteId(team.id)}
                          className="p-1.5 rounded-lg text-gray-500 hover:text-red-400 hover:bg-red-950/40 transition opacity-0 group-hover:opacity-100 focus:opacity-100 cursor-pointer"
                          title={`Delete team folder "${team.name}"`}
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Folder Contents (Matches inside this Team) */}
                  {isExpanded && (
                    <div className="border-t border-[#202636] bg-[#11131a] px-3 py-2.5 pl-9 space-y-1.5">
                      {teamMatches.length === 0 ? (
                        <div className="py-4 px-3 text-center border border-dashed border-[#262e3f] rounded-xl">
                          <p className="text-xs text-gray-400 font-medium">
                            No match recordings in this team folder yet.
                          </p>
                          <p className="text-[11px] text-gray-500 mt-0.5">
                            Uploaded games will go to this team when it is selected.
                          </p>
                          {onOpenUpload && (
                            <button
                              onClick={() => {
                                onSelectTeam(team);
                                onClose();
                                onOpenUpload(team);
                              }}
                              className="mt-2.5 inline-flex items-center space-x-1.5 px-3 py-1 rounded-lg bg-[#00E676]/15 hover:bg-[#00E676]/25 border border-[#00E676]/40 text-[#00E676] text-xs font-semibold transition cursor-pointer"
                            >
                              <UploadCloud className="w-3.5 h-3.5" />
                              <span>Upload Game to {team.name}</span>
                            </button>
                          )}
                        </div>
                      ) : (
                        teamMatches.map(m => {
                          const isMatchCurrent = currentMatch?.id === m.id;
                          return (
                            <div
                              key={m.id}
                              onClick={() => {
                                onSelectTeam(team);
                                onSelectMatch(m);
                                onClose();
                              }}
                              className={`p-2.5 rounded-xl cursor-pointer flex items-center justify-between transition group ${
                                isMatchCurrent
                                  ? 'bg-[#1f2636] border border-[#00E676]/50 shadow'
                                  : 'bg-[#151922] hover:bg-[#1a202d] border border-[#222938]'
                              }`}
                            >
                              <div className="flex items-center space-x-2.5 min-w-0 flex-1">
                                <div className={`w-6 h-6 rounded-md flex items-center justify-center shrink-0 ${
                                  isMatchCurrent ? 'bg-[#00E676] text-black' : 'bg-[#222a3b] text-gray-400'
                                }`}>
                                  <Video className="w-3.5 h-3.5" />
                                </div>
                                <div className="min-w-0 flex-1">
                                  <div className="flex items-center space-x-1.5">
                                    <span className="text-xs font-semibold text-white truncate group-hover:text-[#00E676] transition">
                                      {m.title}
                                    </span>
                                    {isMatchCurrent && (
                                      <span className="text-[9px] bg-[#00E676]/20 text-[#00E676] font-bold px-1.5 py-0.2 rounded shrink-0">
                                        Now Playing
                                      </span>
                                    )}
                                  </div>
                                  <div className="text-[10px] text-gray-400 mt-0.5 flex items-center space-x-2">
                                    <span>{m.date}</span>
                                    <span>•</span>
                                    <span>{m.home_score} - {m.away_score}</span>
                                    <span>•</span>
                                    <span className={m.analysis_mode === 'ml' ? 'text-[#00E676]' : 'text-amber-400'}>
                                      {m.analysis_mode === 'ml' ? 'AI Analysis' : 'Demo Data'}
                                    </span>
                                  </div>
                                </div>
                              </div>

                              <div className="shrink-0 pl-2">
                                {isMatchCurrent && (
                                  <Check className="w-4 h-4 text-[#00E676]" />
                                )}
                              </div>
                            </div>
                          );
                        })
                      )}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>

        {/* Footer Info & Upload Destination */}
        <div className="p-3.5 border-t border-[#1f2432] bg-[#151821] flex flex-wrap items-center justify-between gap-2 shrink-0 text-xs">
          <div className="text-gray-400 flex items-center space-x-2">
            <span>Folders: <strong className="text-white">{teams.length}</strong></span>
            <span>•</span>
            <span>Total Games: <strong className="text-white">{matches.length}</strong></span>
          </div>

          <div className="flex items-center space-x-2">
            {selectedTeam && (
              <span className="text-gray-400 text-[11px]">
                Uploaded games will go to: <strong className="text-[#00E676]">{selectedTeam.name}</strong>
              </span>
            )}
            {onOpenUpload && (
              <button
                onClick={() => {
                  onClose();
                  onOpenUpload(selectedTeam || undefined);
                }}
                className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-[#222838] hover:bg-[#2b3347] text-white border border-[#333d52] font-semibold transition cursor-pointer"
              >
                <UploadCloud className="w-3.5 h-3.5 text-[#00E676]" />
                <span>Upload New Game</span>
              </button>
            )}
          </div>
        </div>

      </div>
    </div>
  );
};
