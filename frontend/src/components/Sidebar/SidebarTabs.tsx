import React, { useState } from 'react';
import { 
  Video, List, Shirt, BarChart2, LayoutGrid, FileText, 
  Play, Download, ChevronRight, X, Eye
} from 'lucide-react';
import { Match, Highlight, Event, AnalyticsData } from '../../types';

interface SidebarDrawerProps {
  activeTab: 'analytics' | 'players' | 'highlights' | 'events' | 'lineup' | 'summary' | null;
  onClose: () => void;
  match: Match;
  highlights: Highlight[];
  events: Event[];
  analytics: AnalyticsData | null;
  onSeek: (time: number) => void;
  onPlayAllHighlights: () => void;
  selectedJersey: string | null;
  onSelectJersey: (jersey: string | null) => void;
}

export const SidebarDrawer: React.FC<SidebarDrawerProps> = ({
  activeTab,
  onClose,
  match,
  highlights,
  events,
  analytics,
  onSeek,
  onPlayAllHighlights,
  selectedJersey,
  onSelectJersey,
}) => {
  const [highlightFilter, setHighlightFilter] = useState<string>('all');
  const [eventPeriod, setEventPeriod] = useState<number>(1);

  if (!activeTab) return null;

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const filteredHighlights = highlights.filter(h => {
    if (highlightFilter === 'all') return true;
    if (highlightFilter === 'goals') return h.event_type === 'goal';
    if (highlightFilter === 'shots') return h.event_type === 'shot';
    return true;
  });

  return (
    <div className="w-80 md:w-96 bg-[#0a0c10] border-l border-[#1a1a1a] flex flex-col h-full text-gray-200 z-20 shadow-2xl select-none animate-in slide-in-from-right duration-150 shrink-0">
      {/* Drawer Header with Close Button */}
      <div className="h-12 px-4 border-b border-[#181818] flex items-center justify-between">
        <div className="flex items-center space-x-2">
          {activeTab === 'highlights' && <Video className="w-4 h-4 text-[#00E676]" />}
          {activeTab === 'events' && <List className="w-4 h-4 text-[#00E676]" />}
          {activeTab === 'players' && <Shirt className="w-4 h-4 text-[#00E676]" />}
          {activeTab === 'analytics' && <BarChart2 className="w-4 h-4 text-[#00E676]" />}
          {activeTab === 'lineup' && <LayoutGrid className="w-4 h-4 text-[#00E676]" />}
          {activeTab === 'summary' && <FileText className="w-4 h-4 text-[#00E676]" />}
          <span className="text-xs font-bold text-white uppercase tracking-wider">
            {activeTab === 'highlights' && 'Highlights'}
            {activeTab === 'events' && 'Match Events Log'}
            {activeTab === 'players' && 'Player Moments'}
            {activeTab === 'analytics' && 'Analytics Studio'}
            {activeTab === 'lineup' && 'Lineup & Tactics'}
            {activeTab === 'summary' && 'Match Summary & Notes'}
          </span>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded-lg text-gray-400 hover:text-white hover:bg-[#181818] transition"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Drawer Content */}
      <div className="flex-1 overflow-y-auto">
        {/* ================= HIGHLIGHTS TAB ================= */}
        {activeTab === 'highlights' && (
          <div className="p-3 space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-[#181818]">
              <span className="text-xs text-gray-400 font-medium">
                {filteredHighlights.length} Highlights (Read-Only)
              </span>
              <button
                onClick={onPlayAllHighlights}
                className="flex items-center space-x-1 bg-[#181818] hover:bg-[#222] text-[#00E676] text-xs px-2.5 py-1 rounded-md border border-[#262626] transition font-semibold"
              >
                <Play className="w-3 h-3 fill-[#00E676]" />
                <span>Play all</span>
              </button>
            </div>

            {/* Filter buttons */}
            <div className="flex items-center space-x-1.5 pb-1">
              {['all', 'goals', 'shots'].map(f => (
                <button
                  key={f}
                  onClick={() => setHighlightFilter(f)}
                  className={`px-3 py-1 rounded-full text-xs capitalize transition ${
                    highlightFilter === f ? 'bg-white text-black font-bold' : 'bg-[#141414] text-gray-400 hover:text-white'
                  }`}
                >
                  {f}
                </button>
              ))}
            </div>

            {/* Clips List */}
            <div className="space-y-2.5">
              {filteredHighlights.map(h => (
                <div
                  key={h.id}
                  onClick={() => onSeek(h.start_time)}
                  className="bg-[#12141a] hover:bg-[#181c25] border border-[#1e222d] hover:border-[#00E676]/60 rounded-xl p-2.5 cursor-pointer transition flex space-x-3 group"
                >
                  <div className="w-20 h-14 bg-[#0a0c10] rounded-lg border border-[#222] relative flex items-center justify-center shrink-0 overflow-hidden">
                    <Play className="w-4 h-4 text-white fill-white group-hover:scale-125 transition" />
                    <span className="absolute bottom-1 right-1 bg-black/80 text-[9px] font-mono px-1 rounded text-gray-300">
                      {formatTime(h.start_time)}
                    </span>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <h4 className="text-xs font-bold text-white truncate group-hover:text-[#00E676] transition">
                        {h.title}
                      </h4>
                      <span className="text-[9px] bg-[#00E676]/20 text-[#00E676] px-1.5 py-0.5 rounded font-bold">
                        AI
                      </span>
                    </div>
                    <div className="text-[11px] text-gray-400 mt-0.5 flex items-center space-x-1.5">
                      <span className="capitalize">{h.event_type}</span>
                      {h.player_jersey && (
                        <>
                          <span>•</span>
                          <span className="bg-[#1f2430] text-gray-200 px-1 rounded text-[10px]">#{h.player_jersey}</span>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ================= EVENTS TAB ================= */}
        {activeTab === 'events' && (
          <div>
            {/* Period Switcher */}
            <div className="p-3 border-b border-[#181818] flex items-center justify-between">
              <span className="text-xs text-gray-400">{events.length} Granular Events</span>
              <div className="flex items-center space-x-1 bg-[#141414] p-0.5 rounded-lg text-xs">
                <button
                  onClick={() => setEventPeriod(1)}
                  className={`px-2.5 py-0.5 rounded-md transition ${eventPeriod === 1 ? 'bg-[#00E676] text-black font-bold' : 'text-gray-400'}`}
                >
                  1st Period
                </button>
                <button
                  onClick={() => setEventPeriod(2)}
                  className={`px-2.5 py-0.5 rounded-md transition ${eventPeriod === 2 ? 'bg-[#00E676] text-black font-bold' : 'text-gray-400'}`}
                >
                  2nd Period
                </button>
              </div>
            </div>

            <div className="divide-y divide-[#181818]">
              {events.filter(e => e.period === eventPeriod).map(e => (
                <div
                  key={e.id}
                  onClick={() => onSeek(e.timestamp)}
                  className="p-3 hover:bg-[#12141a] cursor-pointer transition flex items-center justify-between group"
                >
                  <div className="flex items-center space-x-3">
                    <span className="text-xs font-mono text-gray-400 group-hover:text-[#00E676]">
                      {formatTime(e.timestamp)}
                    </span>
                    <div>
                      <div className="text-xs font-semibold text-white group-hover:text-[#00E676] transition">
                        {e.description}
                      </div>
                      <div className="text-[10px] text-gray-500">
                        {e.event_type} • {e.team.toUpperCase()}
                      </div>
                    </div>
                  </div>
                  <ChevronRight className="w-4 h-4 text-gray-500 group-hover:text-white transition" />
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ================= PLAYER MOMENTS TAB ================= */}
        {activeTab === 'players' && (
          <div className="p-3 space-y-3">
            {/* Active player indicator */}
            {selectedJersey ? (
              <div className="bg-[#12141a] border border-[#22242c] p-3 rounded-xl flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <div className="w-9 h-9 rounded-full bg-[#FFD700] text-black font-black text-sm flex items-center justify-center shadow">
                    #{selectedJersey}
                  </div>
                  <div>
                    <div className="text-xs font-bold text-white">
                      {match.lineup.find(p => p.jersey === selectedJersey)?.name || `Player #${selectedJersey}`}
                    </div>
                    <div className="text-[11px] text-gray-400">
                      {match.lineup.find(p => p.jersey === selectedJersey)?.position || 'MID'} • 90 mins played
                    </div>
                  </div>
                </div>
                <button
                  onClick={() => onSelectJersey(null)}
                  className="text-xs text-gray-400 hover:text-white"
                >
                  Reset
                </button>
              </div>
            ) : (
              <div className="text-xs text-gray-400 bg-[#12141a] p-3 rounded-xl border border-[#1e222d]">
                Click any jersey in the bottom bar to filter actions and highlight clips.
              </div>
            )}

            {/* List of player moments */}
            <div className="space-y-2">
              <span className="text-[11px] font-bold text-gray-400 uppercase tracking-wider">
                Moments Feed
              </span>
              {events.filter(e => !selectedJersey || e.player_jersey === selectedJersey).map(e => (
                <div
                  key={e.id}
                  onClick={() => onSeek(e.timestamp)}
                  className="p-2.5 bg-[#12141a] hover:bg-[#181c25] border border-[#1e222d] rounded-xl cursor-pointer transition flex items-center justify-between"
                >
                  <div className="flex items-center space-x-2">
                    <span className="text-[10px] font-mono text-[#00E676] bg-[#00E676]/10 px-1.5 py-0.5 rounded font-bold">
                      {formatTime(e.timestamp)}
                    </span>
                    <span className="text-xs text-white font-medium">{e.description}</span>
                  </div>
                  <Play className="w-3.5 h-3.5 text-gray-400" />
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ================= ANALYTICS STUDIO TAB ================= */}
        {activeTab === 'analytics' && analytics && (
          <div className="p-3 space-y-4">
            {/* Match Comparison */}
            <div className="bg-[#12141a] border border-[#1e222d] rounded-xl p-3 space-y-2 text-xs">
              <div className="flex items-center justify-between font-bold text-gray-300 pb-1.5 border-b border-[#222]">
                <span className="text-[#FFD700] truncate max-w-[100px]">{match.home_team}</span>
                <span className="text-[10px] text-gray-500 font-mono">VS</span>
                <span className="text-[#2979FF] truncate max-w-[100px]">{match.away_team}</span>
              </div>
              {[
                { label: 'Goals', h: analytics.home_stats.goals, a: analytics.away_stats.goals },
                { label: 'Shots', h: analytics.home_stats.shots, a: analytics.away_stats.shots },
                { label: 'Possession %', h: `${analytics.home_stats.possession_percent}%`, a: `${analytics.away_stats.possession_percent}%` },
                { label: 'Passes Completed', h: analytics.home_stats.passes_completed, a: analytics.away_stats.passes_completed },
                { label: 'Corners', h: analytics.home_stats.corners, a: analytics.away_stats.corners },
                { label: 'Tackles', h: analytics.home_stats.tackles, a: analytics.away_stats.tackles },
              ].map((r, i) => (
                <div key={i} className="flex items-center justify-between py-1 border-b border-[#1a1e28]">
                  <span className="font-bold text-white w-8 text-left">{r.h}</span>
                  <span className="text-gray-400 text-[11px]">{r.label}</span>
                  <span className="font-bold text-white w-8 text-right">{r.a}</span>
                </div>
              ))}
            </div>

            {/* 2D Shot Map */}
            <div className="bg-[#12141a] border border-[#1e222d] rounded-xl p-3 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-white uppercase tracking-wider">Shot Map</span>
                <span className="text-[10px] text-[#00E676] font-bold">23% Conversion</span>
              </div>
              <div className="relative w-full aspect-[105/68] bg-[#1a472a] rounded-lg border border-[#2d5f3e] overflow-hidden">
                <svg viewBox="0 0 105 68" className="w-full h-full">
                  <rect x="1" y="1" width="103" height="66" fill="none" stroke="rgba(255,255,255,0.4)" strokeWidth="0.8" />
                  <line x1="52.5" y1="1" x2="52.5" y2="67" stroke="rgba(255,255,255,0.4)" strokeWidth="0.8" />
                  <circle cx="52.5" cy="34" r="9.15" fill="none" stroke="rgba(255,255,255,0.4)" strokeWidth="0.8" />
                  <rect x="88.5" y="14" width="16.5" height="40" fill="none" stroke="rgba(255,255,255,0.4)" strokeWidth="0.8" />
                  <rect x="1" y="14" width="16.5" height="40" fill="none" stroke="rgba(255,255,255,0.4)" strokeWidth="0.8" />
                  {analytics.shot_map.map(s => (
                    <circle
                      key={s.id}
                      cx={s.x}
                      cy={s.y}
                      r={s.outcome === 'goal' ? 3.5 : 2.5}
                      fill={s.outcome === 'goal' ? '#00E676' : s.outcome === 'saved' ? '#FFD700' : '#FF5252'}
                      stroke="#000"
                      strokeWidth="0.6"
                      onClick={() => onSeek(s.timestamp)}
                      className="cursor-pointer hover:scale-150 transition"
                    />
                  ))}
                </svg>
              </div>
            </div>

            {/* Pitch Thirds Breakdown */}
            <div className="bg-[#12141a] border border-[#1e222d] rounded-xl p-3 space-y-2">
              <span className="text-xs font-bold text-white uppercase tracking-wider">Thirds Breakdown</span>
              <div>
                <div className="flex justify-between text-[11px] text-gray-400 mb-1">
                  <span>Passes</span>
                  <span>{analytics.pass_locations.home.defensive}% • {analytics.pass_locations.home.middle}% • {analytics.pass_locations.home.attacking}%</span>
                </div>
                <div className="h-2.5 rounded-full overflow-hidden flex bg-[#1e2330]">
                  <div style={{ width: `${analytics.pass_locations.home.defensive}%` }} className="bg-blue-600" />
                  <div style={{ width: `${analytics.pass_locations.home.middle}%` }} className="bg-[#00E676]" />
                  <div style={{ width: `${analytics.pass_locations.home.attacking}%` }} className="bg-yellow-500" />
                </div>
              </div>
            </div>

            {/* Pass Strings */}
            <div className="bg-[#12141a] border border-[#1e222d] rounded-xl p-3 space-y-2">
              <span className="text-xs font-bold text-white uppercase tracking-wider">Pass Strings</span>
              <div className="flex items-end space-x-2 h-16 pt-2">
                {analytics.pass_strings.home.map((val, idx) => (
                  <div key={idx} className="flex-1 flex flex-col items-center">
                    <div
                      style={{ height: `${Math.max(10, val * 5)}%` }}
                      className="w-full bg-[#00E676] rounded-t hover:bg-[#00c968] transition"
                    />
                    <span className="text-[9px] text-gray-400 mt-1">{idx + 3}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* ================= LINEUP TAB ================= */}
        {activeTab === 'lineup' && (
          <div className="p-3 space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-[#181818]">
              <div>
                <h4 className="text-xs font-bold text-white">Starting XI (4-3-3)</h4>
                <p className="text-[10px] text-gray-400">Arlington SA U16B ECNL</p>
              </div>
              <span className="text-xs font-mono font-bold text-[#FFD700] bg-[#1a1e28] px-2 py-0.5 rounded">
                4-3-3
              </span>
            </div>

            {/* 2D Pitch Lineup View */}
            <div className="relative w-full aspect-[4/3] bg-[#1a472a] rounded-xl border border-[#2d5f3e] p-2 flex flex-col justify-between">
              {/* Forwards */}
              <div className="flex justify-around pt-1">
                {match.lineup.filter(p => p.position === 'FWD').slice(0, 3).map(p => (
                  <div key={p.jersey} className="flex flex-col items-center">
                    <div className="w-6 h-6 rounded-full bg-[#FFD700] text-black font-black text-[10px] flex items-center justify-center border border-black shadow">
                      {p.jersey}
                    </div>
                    <span className="text-[8px] font-bold text-white bg-black/60 px-1 rounded mt-0.5">{p.name.split(' ')[1] || p.name}</span>
                  </div>
                ))}
              </div>

              {/* Midfielders */}
              <div className="flex justify-around">
                {match.lineup.filter(p => p.position === 'MID').slice(0, 3).map(p => (
                  <div key={p.jersey} className="flex flex-col items-center">
                    <div className="w-6 h-6 rounded-full bg-[#FFD700] text-black font-black text-[10px] flex items-center justify-center border border-black shadow">
                      {p.jersey}
                    </div>
                    <span className="text-[8px] font-bold text-white bg-black/60 px-1 rounded mt-0.5">{p.name.split(' ')[1] || p.name}</span>
                  </div>
                ))}
              </div>

              {/* Defenders */}
              <div className="flex justify-around">
                {match.lineup.filter(p => p.position === 'DEF').slice(0, 4).map(p => (
                  <div key={p.jersey} className="flex flex-col items-center">
                    <div className="w-6 h-6 rounded-full bg-[#FFD700] text-black font-black text-[10px] flex items-center justify-center border border-black shadow">
                      {p.jersey}
                    </div>
                    <span className="text-[8px] font-bold text-white bg-black/60 px-1 rounded mt-0.5">{p.name.split(' ')[1] || p.name}</span>
                  </div>
                ))}
              </div>

              {/* Goalkeeper */}
              <div className="flex justify-center pb-1">
                {match.lineup.filter(p => p.position === 'GK').slice(0, 1).map(p => (
                  <div key={p.jersey} className="flex flex-col items-center">
                    <div className="w-6 h-6 rounded-full bg-[#FF3D00] text-white font-black text-[10px] flex items-center justify-center border border-white shadow">
                      {p.jersey}
                    </div>
                    <span className="text-[8px] font-bold text-white bg-black/60 px-1 rounded mt-0.5">{p.name.split(' ')[1] || p.name}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Substitutes */}
            <div className="space-y-1 pt-1">
              <span className="text-[11px] font-bold text-gray-400 uppercase">Substitutes</span>
              {match.lineup.filter(p => !p.is_starter).map(p => (
                <div key={p.jersey} className="flex items-center justify-between p-2 bg-[#12141a] rounded-lg text-xs">
                  <div className="flex items-center space-x-2">
                    <span className="w-5 h-5 rounded-full bg-[#1e222d] text-gray-300 font-bold flex items-center justify-center text-[10px]">
                      {p.jersey}
                    </span>
                    <span className="text-white font-medium">{p.name}</span>
                  </div>
                  <span className="text-gray-400 text-[10px]">{p.position}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ================= SUMMARY TAB ================= */}
        {activeTab === 'summary' && (
          <div className="p-3 space-y-4">
            <div className="bg-[#12141a] border border-[#1e222d] rounded-xl p-4 text-center space-y-2">
              <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">FINAL RESULT</span>
              <div className="flex items-center justify-center space-x-6 text-2xl font-black text-white">
                <span>{match.home_score}</span>
                <span className="text-gray-500 font-normal">–</span>
                <span>{match.away_score}</span>
              </div>
              <div className="flex justify-between text-xs text-gray-300 pt-1 border-t border-[#1e222d]">
                <span className="font-semibold text-[#FFD700] truncate max-w-[120px]">{match.home_team}</span>
                <span className="font-semibold text-[#2979FF] truncate max-w-[120px]">{match.away_team}</span>
              </div>
            </div>

            <div className="bg-[#12141a] border border-[#1e222d] rounded-xl p-3 space-y-2">
              <span className="text-xs font-bold text-white uppercase tracking-wider">Coach's Journal</span>
              <p className="text-xs text-gray-300 font-mono bg-[#0a0c10] p-3 rounded-lg border border-[#1e222d]">
                {match.journal_notes || 'No coach notes for this match.'}
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
