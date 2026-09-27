import React, { useState, useMemo } from 'react';
import { 
  Video, Users, Camera, User, AtSign, BarChart2, Settings, 
  HelpCircle, ChevronDown, X, Check, Cloud
} from 'lucide-react';
import { Match, Team } from '../types';
import { TeamsModal } from './TeamsModal';

interface BurgerMenuProps {
  isOpen: boolean;
  onClose: () => void;
  matches: Match[];
  currentMatch: Match | null;
  onSelectMatch: (match: Match) => void;
  onOpenAnalytics: () => void;
  onOpenPlayerMoments: () => void;
  teams?: Team[];
  selectedTeam?: Team | null;
  onSelectTeam?: (team: Team) => void;
  onCreateTeam?: (name: string, clubName?: string, federationUrl?: string) => Promise<Team | void>;
  onUpdateTeam?: (teamId: string, data: { name?: string; club_name?: string; federation_url?: string }) => Promise<Team | void>;
  onDeleteTeam?: (teamId: string) => Promise<void>;
  onOpenUpload?: (preselectedTeam?: Team) => void;
  onOpenCloudSync?: () => void;
}

export const BurgerMenu: React.FC<BurgerMenuProps> = ({
  isOpen,
  onClose,
  matches,
  currentMatch,
  onSelectMatch,
  onOpenAnalytics,
  onOpenPlayerMoments,
  teams = [],
  selectedTeam = null,
  onSelectTeam,
  onCreateTeam,
  onUpdateTeam,
  onDeleteTeam,
  onOpenUpload,
  onOpenCloudSync,
}) => {
  const [showTeamsModal, setShowTeamsModal] = useState(false);
  const [showSettingsModal, setShowSettingsModal] = useState(false);
  const [showSeaCamsModal, setShowSeaCamsModal] = useState(false);
  const [showProfileModal, setShowProfileModal] = useState(false);
  const [showMentionsModal, setShowMentionsModal] = useState(false);
  const [showHelpModal, setShowHelpModal] = useState(false);

  // Derive crest abbreviation for active team
  const crestInitials = useMemo(() => {
    const name = selectedTeam?.name || 'Arlington Soccer';
    const parts = name.trim().split(/\s+/);
    if (parts.length >= 3) return (parts[0][0] + parts[1][0] + parts[2][0]).toUpperCase();
    if (parts.length === 2) return (parts[0][0] + parts[1].slice(0, 2)).toUpperCase();
    return name.slice(0, 3).toUpperCase();
  }, [selectedTeam]);

  // Compute matches count for selected team
  const selectedTeamMatchCount = useMemo(() => {
    if (!selectedTeam) return matches.length;
    return matches.filter(m => {
      if (m.team_id) return m.team_id === selectedTeam.id;
      return m.home_team.toLowerCase().includes(selectedTeam.name.toLowerCase()) ||
             selectedTeam.name.toLowerCase().includes(m.home_team.toLowerCase());
    }).length;
  }, [matches, selectedTeam]);

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={onClose}
        className="fixed inset-0 z-40 bg-black/60 backdrop-blur-xs transition-opacity"
      />

      {/* Slide-over Drawer */}
      <aside className="fixed inset-y-0 left-0 z-50 w-72 bg-[#000000] border-r border-[#1a1a1a] flex flex-col shadow-2xl select-none animate-in slide-in-from-left duration-200">
        {/* Drawer Header */}
        <div className="h-14 px-4 flex items-center space-x-4 border-b border-[#181818]">
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full bg-[#181818] hover:bg-[#252525] flex items-center justify-center text-white transition"
            title="Close menu"
          >
            <div className="space-y-1 w-4">
              <div className="h-[2px] bg-white rounded-full" />
              <div className="h-[2px] bg-white rounded-full" />
              <div className="h-[2px] bg-white rounded-full" />
            </div>
          </button>

          {/* Stylized Sea Logo */}
          <div className="flex items-center space-x-1 cursor-pointer" onClick={onClose}>
            <span className="font-extrabold italic text-2xl tracking-tighter text-white font-sans">
              sea
            </span>
          </div>
        </div>

        {/* Drawer Body */}
        <div className="flex-1 overflow-y-auto px-3 py-3 space-y-3">
          {/* Club / Team Switcher Card */}
          <div
            onClick={() => setShowTeamsModal(true)}
            className="flex items-center justify-between p-2.5 rounded-xl hover:bg-[#141414] cursor-pointer transition border border-transparent hover:border-[#222]"
            title="Manage and switch teams"
          >
            <div className="flex items-center space-x-3 min-w-0 flex-1">
              {/* Crest Badge */}
              <div className="w-10 h-10 rounded-lg bg-white p-0.5 flex items-center justify-center overflow-hidden shrink-0 shadow">
                <div className="w-full h-full rounded-md bg-[#002d62] flex items-center justify-center font-black text-[9px] text-white border border-[#c41230]">
                  {crestInitials}
                </div>
              </div>
              <div className="min-w-0 flex-1">
                <div className="text-sm font-bold text-white tracking-tight truncate">
                  {selectedTeam?.name || 'Arlington Soccer'}
                </div>
                <div className="text-xs text-[#8e8e8e]">
                  {selectedTeamMatchCount} {selectedTeamMatchCount === 1 ? 'Game' : 'Games'} • {teams.length} {teams.length === 1 ? 'Team' : 'Teams'}
                </div>
              </div>
            </div>
            <ChevronDown className="w-4 h-4 text-[#8e8e8e] shrink-0" />
          </div>

          <div className="h-[1px] bg-[#1a1a1a]" />

          {/* Primary Navigation */}
          <nav className="space-y-1">
            <button
              onClick={() => {
                setShowTeamsModal(true);
              }}
              className="w-full flex items-center space-x-3 px-3 py-2.5 rounded-lg text-sm text-gray-200 hover:bg-[#141414] hover:text-white transition font-normal cursor-pointer"
            >
              <Video className="w-4 h-4 text-gray-400" />
              <span>Library</span>
            </button>

            <button
              onClick={() => {
                setShowTeamsModal(true);
              }}
              className="w-full flex items-center space-x-3 px-3 py-2.5 rounded-lg text-sm text-gray-200 hover:bg-[#141414] hover:text-white transition font-normal cursor-pointer"
            >
              <Users className="w-4 h-4 text-gray-400" />
              <span>Teams</span>
            </button>

            <button
              onClick={() => setShowSeaCamsModal(true)}
              className="w-full flex items-center space-x-3 px-3 py-2.5 rounded-lg text-sm text-gray-200 hover:bg-[#141414] hover:text-white transition font-normal cursor-pointer"
            >
              <Camera className="w-4 h-4 text-gray-400" />
              <span>Sea Cams</span>
            </button>
          </nav>

          <div className="h-[1px] bg-[#1a1a1a]" />

          {/* Player & Mentions */}
          <nav className="space-y-1">
            <button
              onClick={() => {
                onOpenPlayerMoments();
                onClose();
              }}
              className="w-full flex items-center space-x-3 px-3 py-2.5 rounded-lg text-sm text-gray-200 hover:bg-[#141414] hover:text-white transition font-normal cursor-pointer"
            >
              <Video className="w-4 h-4 text-gray-400" />
              <span>Player Moments</span>
            </button>

            <button
              onClick={() => setShowProfileModal(true)}
              className="w-full flex items-center space-x-3 px-3 py-2.5 rounded-lg text-sm text-gray-200 hover:bg-[#141414] hover:text-white transition font-normal cursor-pointer"
            >
              <User className="w-4 h-4 text-gray-400" />
              <span>Player Profile</span>
            </button>

            <button
              onClick={() => setShowMentionsModal(true)}
              className="w-full flex items-center space-x-3 px-3 py-2.5 rounded-lg text-sm text-gray-200 hover:bg-[#141414] hover:text-white transition font-normal"
            >
              <AtSign className="w-4 h-4 text-gray-400" />
              <span>Mentions</span>
            </button>
          </nav>

          <div className="h-[1px] bg-[#1a1a1a]" />

          {/* More From Sea Section */}
          <div>
            <div className="px-3 pt-2 pb-1 text-[11px] font-semibold tracking-wider text-[#6e6e6e] uppercase">
              More From Sea
            </div>

            <nav className="space-y-1">
              <button
                onClick={() => {
                  onClose();
                  onOpenAnalytics();
                }}
                className="w-full flex items-center space-x-3 px-3 py-2.5 rounded-lg text-sm text-gray-200 hover:bg-[#141414] hover:text-white transition font-normal"
              >
                <BarChart2 className="w-4 h-4 text-gray-400" />
                <span>Analytics Studio</span>
              </button>

              {onOpenCloudSync && (
                <button
                  onClick={() => {
                    onClose();
                    onOpenCloudSync();
                  }}
                  className="w-full flex items-center space-x-3 px-3 py-2.5 rounded-lg text-sm text-[#F38020] hover:bg-[#141414] hover:text-[#ff8f33] transition font-normal"
                >
                  <Cloud className="w-4 h-4 text-[#F38020]" />
                  <span>Cloudflare Sync</span>
                </button>
              )}

              <button
                onClick={() => setShowSettingsModal(true)}
                className="w-full flex items-center space-x-3 px-3 py-2.5 rounded-lg text-sm text-gray-200 hover:bg-[#141414] hover:text-white transition font-normal"
              >
                <Settings className="w-4 h-4 text-gray-400" />
                <span>Settings</span>
              </button>
            </nav>
          </div>
        </div>

        {/* Drawer Footer */}
        <div className="p-3 border-t border-[#181818] space-y-2">
          <button
            onClick={() => setShowHelpModal(true)}
            className="w-full flex items-center space-x-3 px-3 py-2 rounded-lg text-sm text-gray-300 hover:bg-[#141414] transition"
          >
            <HelpCircle className="w-4 h-4 text-gray-400" />
            <span>Help & Resources</span>
          </button>

          <div className="px-3 py-1.5 bg-[#141414] border border-[#222] rounded-lg flex items-center justify-between text-xs text-[#8e8e8e]">
            <span>Support ID</span>
            <span className="font-mono font-bold text-gray-200">A0EXC</span>
          </div>
        </div>
      </aside>

      {/* Modal: Teams & Match Folders */}
      <TeamsModal
        isOpen={showTeamsModal}
        onClose={() => setShowTeamsModal(false)}
        teams={teams}
        selectedTeam={selectedTeam}
        matches={matches}
        currentMatch={currentMatch}
        onSelectTeam={(team) => {
          onSelectTeam?.(team);
        }}
        onSelectMatch={(match) => {
          onSelectMatch(match);
          setShowTeamsModal(false);
          onClose();
        }}
        onCreateTeam={onCreateTeam || (async () => {})}
        onUpdateTeam={onUpdateTeam}
        onDeleteTeam={onDeleteTeam || (async () => {})}
        onOpenUpload={(team) => {
          setShowTeamsModal(false);
          onClose();
          onOpenUpload?.(team);
        }}
      />

      {/* Modal: Sea Cams Hardware */}
      {showSeaCamsModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs p-4">
          <div className="bg-[#12141a] border border-[#262c3b] w-full max-w-md rounded-2xl p-5 shadow-2xl text-white">
            <div className="flex items-center justify-between mb-4 border-b border-[#222] pb-3">
              <div className="flex items-center space-x-2">
                <Camera className="w-5 h-5 text-[#00E676]" />
                <h3 className="text-base font-bold">Registered Sea Cameras</h3>
              </div>
              <button onClick={() => setShowSeaCamsModal(false)} className="text-gray-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="bg-[#181c25] border border-[#2d3342] rounded-xl p-4 flex items-center justify-between">
              <div>
                <div className="text-xs font-bold text-white">Sea Cam 3 (5G Dual-Lens)</div>
                <div className="text-[11px] text-gray-400">Serial: SC3-98412-ARL • Firmware: 3.4.1</div>
                <div className="text-[10px] text-[#00E676] font-medium mt-1">● Ready for match upload</div>
              </div>
              <span className="text-xs bg-[#242b3b] text-gray-200 px-2.5 py-1 rounded">Synced</span>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Account Settings */}
      {showSettingsModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs p-4">
          <div className="bg-[#12141a] border border-[#262c3b] w-full max-w-md rounded-2xl p-5 shadow-2xl text-white">
            <div className="flex items-center justify-between mb-4 border-b border-[#222] pb-3">
              <h3 className="text-base font-bold">Account Settings</h3>
              <button onClick={() => setShowSettingsModal(false)} className="text-gray-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="space-y-3 text-xs">
              <div>
                <label className="text-gray-400">Name</label>
                <div className="text-white font-medium mt-0.5">Eric Yeh-Fuentes</div>
              </div>
              <div>
                <label className="text-gray-400">Email Address</label>
                <div className="text-white font-medium mt-0.5">yehfuenteseric@gmail.com</div>
              </div>
              <div>
                <label className="text-gray-400">Phone Number</label>
                <div className="text-white font-medium mt-0.5">+1 301 547 3461</div>
              </div>
              <div>
                <label className="text-gray-400">Language & Units</label>
                <div className="text-white font-medium mt-0.5">English • Yards (yd) • Miles per hour (mph)</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Player Profile */}
      {showProfileModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs p-4">
          <div className="bg-[#12141a] border border-[#262c3b] w-full max-w-md rounded-2xl p-5 shadow-2xl text-white">
            <div className="flex items-center justify-between mb-4 border-b border-[#222] pb-3">
              <h3 className="text-base font-bold">Player Profile</h3>
              <button onClick={() => setShowProfileModal(false)} className="text-gray-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="flex items-center space-x-4 p-3 bg-[#181c25] rounded-xl">
              <div className="w-12 h-12 rounded-full bg-white text-black font-black text-base flex items-center justify-center">
                EY
              </div>
              <div>
                <div className="text-sm font-bold text-white">Eric Yeh-Fuentes (#10)</div>
                <div className="text-xs text-gray-400">Arlington SA U16B ECNL • Attacking Midfielder</div>
                <div className="text-[10px] text-[#00E676] mt-0.5">Sea Player Profile Active</div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Modal: Mentions */}
      {showMentionsModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs p-4">
          <div className="bg-[#12141a] border border-[#262c3b] w-full max-w-md rounded-2xl p-5 shadow-2xl text-white">
            <div className="flex items-center justify-between mb-4 border-b border-[#222] pb-3">
              <h3 className="text-base font-bold">Mentions & Notifications</h3>
              <button onClick={() => setShowMentionsModal(false)} className="text-gray-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-4 text-center text-xs text-gray-400">
              No new player mentions or coach tags for this match.
            </div>
          </div>
        </div>
      )}

      {/* Modal: Help & Shortcuts */}
      {showHelpModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-xs p-4">
          <div className="bg-[#12141a] border border-[#262c3b] w-full max-w-md rounded-2xl p-5 shadow-2xl text-white">
            <div className="flex items-center justify-between mb-4 border-b border-[#222] pb-3">
              <h3 className="text-base font-bold">Sea Player Shortcuts</h3>
              <button onClick={() => setShowHelpModal(false)} className="text-gray-400 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="space-y-2.5 text-xs">
              <div className="flex justify-between py-1 border-b border-[#222]">
                <span className="text-gray-400">Play / Pause</span>
                <span className="font-mono bg-[#1f2430] px-2 py-0.5 rounded text-[#00E676]">Space</span>
              </div>
              <div className="flex justify-between py-1 border-b border-[#222]">
                <span className="text-gray-400">Skip ±10 Seconds</span>
                <span className="font-mono bg-[#1f2430] px-2 py-0.5 rounded text-[#00E676]">J / L or ← / →</span>
              </div>
              <div className="flex justify-between py-1 border-b border-[#222]">
                <span className="text-gray-400">Jump Highlights</span>
                <span className="font-mono bg-[#1f2430] px-2 py-0.5 rounded text-[#00E676]">[ / ]</span>
              </div>
              <div className="flex justify-between py-1 border-b border-[#222]">
                <span className="text-gray-400">Toggle Telestrator Drawing</span>
                <span className="font-mono bg-[#1f2430] px-2 py-0.5 rounded text-[#00E676]">D</span>
              </div>
              <div className="flex justify-between py-1 pt-2 text-[11px] text-gray-500">
                <span>Support ID: A0EXC</span>
                <span>Sea Cam 3 Connected</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
