import React, { useState } from 'react';
import {
  Video, List, Shirt, BarChart2, LayoutGrid, FileText,
  Play, ArrowLeftRight, ArrowUpRight, ChevronDown, X
} from 'lucide-react';
import { Match, Highlight, Event, AnalyticsData, EventTypeLabel } from '../../types';
import { Unavailable } from './Unavailable';
import { ThirdsBar } from './ThirdsBar';

type AnalyticsSectionKey =
  | 'stats' | 'shotMap' | 'passLocation' | 'possessionLocation' | 'passStrings' | 'heatMap';

const ANALYTICS_SECTION_DEFAULTS: Record<AnalyticsSectionKey, boolean> = {
  stats: true,
  shotMap: true,
  passLocation: false,
  possessionLocation: false,
  passStrings: false,
  heatMap: false,
};

const EVENT_TYPES: EventTypeLabel[] = [
  'Kickoff', 'Goal', 'Shot on goal', 'Shot', 'Save', 'Corner', 'Foul', 'Free kick',
  'Goal kick', 'Throw-in', 'Out of play', 'Tackle', 'Interception', 'Dribble',
  'Loose ball recovery', 'Pass',
];

const DEFAULT_DETECTED_TYPES = new Set<EventTypeLabel>(['Kickoff', 'Goal', 'Shot']);

const normalizeEventType = (eventType: string) =>
  eventType.toLowerCase().replace(/[-_\s]/g, '');

interface SidebarDrawerProps {
  activeTab: 'analytics' | 'players' | 'highlights' | 'events' | 'lineup' | 'summary' | null;
  onClose: () => void;
  match: Match;
  highlights: Highlight[];
  events: Event[];
  analytics: AnalyticsData | null;
  currentTime?: number;
  onSeek: (time: number) => void;
  onPlayAllHighlights: () => void;
  onSwapTeams?: () => void;
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
  currentTime = 0,
  onSeek,
  onPlayAllHighlights,
  onSwapTeams,
  selectedJersey,
  onSelectJersey,
}) => {
  const [highlightFilter, setHighlightFilter] = useState<string>('all');
  const [eventPeriod, setEventPeriod] = useState<number>(1);
  const [openSections, setOpenSections] = useState<Record<AnalyticsSectionKey, boolean>>(ANALYTICS_SECTION_DEFAULTS);
  const toggleSection = (key: AnalyticsSectionKey) =>
    setOpenSections(prev => ({ ...prev, [key]: !prev[key] }));

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

  const eventCount = (label: EventTypeLabel) => events.filter(
    event => normalizeEventType(event.event_type) === normalizeEventType(label),
  ).length;

  const capabilityFor = (label: EventTypeLabel) => {
    const capability = match.event_capabilities?.[label];
    if (capability) return capability;
    return DEFAULT_DETECTED_TYPES.has(label)
      ? { status: 'detected' as const, count: eventCount(label) }
      : { status: 'not_attempted' as const };
  };

  const renderStatValue = (val: number | string | null | undefined, suffix = '') => {
    if (val === null || val === undefined) {
      return (
        <span 
          className="text-gray-500 font-bold cursor-help"
          title="Not measured — requires event detection"
        >
          —
        </span>
      );
    }
    return <span className="font-bold text-white">{val}{suffix}</span>;
  };

  const seekToFirstEventOfType = (eventTypes: string[]) => {
    const event = events.find(candidate => eventTypes.some(
      eventType => normalizeEventType(candidate.event_type) === normalizeEventType(eventType),
    ));
    if (event) onSeek(event.timestamp);
  };

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
          aria-label="Close drawer"
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
                {filteredHighlights.length} Highlights
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
              {filteredHighlights.map(h => {
                const isActive = currentTime >= h.start_time && currentTime <= h.end_time;
                return (
                  <div
                    key={h.id}
                    onClick={() => onSeek(h.start_time)}
                    className={`border rounded-xl p-2.5 cursor-pointer transition flex space-x-3 group ${
                      isActive 
                        ? 'bg-[#14261c] border-[#00E676] shadow-lg shadow-[#00E676]/10' 
                        : 'bg-[#12141a] hover:bg-[#181c25] border-[#1e222d] hover:border-[#00E676]/60'
                    }`}
                  >
                    <div className="w-20 h-14 bg-[#0a0c10] rounded-lg border border-[#222] relative flex items-center justify-center shrink-0 overflow-hidden">
                      <Play className={`w-4 h-4 text-white fill-white transition ${isActive ? 'scale-125 text-[#00E676] fill-[#00E676]' : 'group-hover:scale-125'}`} />
                      <span className="absolute bottom-1 right-1 bg-black/80 text-[9px] font-mono px-1 rounded text-gray-300">
                        {formatTime(h.start_time)}
                      </span>
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between">
                        <h4 className={`text-xs font-bold truncate transition ${isActive ? 'text-[#00E676]' : 'text-white group-hover:text-[#00E676]'}`}>
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
                );
              })}
            </div>
          </div>
        )}

        {/* ================= EVENTS LOG TAB ================= */}
        {activeTab === 'events' && (
          <div className="p-3 space-y-3">
            <div className="bg-[#12141a] border border-[#1e222d] rounded-xl p-3 space-y-2">
              <span className="text-xs font-bold text-white uppercase tracking-wider">Event detection</span>
              <div className="space-y-1" aria-label="Event detection capabilities">
                {EVENT_TYPES.map(label => {
                  const capability = capabilityFor(label);
                  const detectedCount = eventCount(label);
                  return (
                    <div key={label} className="flex items-center justify-between gap-3 py-1 border-b border-[#1a1e28] last:border-0">
                      <span className="text-xs text-gray-200">{label}</span>
                      {capability.status === 'detected' ? (
                        <span className="text-[10px] text-[#00E676] font-semibold whitespace-nowrap">
                          detected ({detectedCount})
                        </span>
                      ) : capability.status === 'unavailable' ? (
                        <span className="text-[10px] text-gray-500 text-right" title={capability.reason || undefined}>
                          unavailable{capability.reason ? `: ${capability.reason}` : ''}
                        </span>
                      ) : (
                        <span className="text-[10px] text-gray-500 whitespace-nowrap">not attempted</span>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>

            <div className="flex items-center justify-between pb-2 border-b border-[#181818]">
              <span className="text-xs text-gray-400 font-medium">Timeline Events</span>
              <div className="flex space-x-1">
                <button
                  onClick={() => setEventPeriod(1)}
                  className={`px-2 py-0.5 rounded text-xs font-semibold ${
                    eventPeriod === 1 ? 'bg-white text-black' : 'text-gray-400 hover:text-white'
                  }`}
                >
                  1st Half
                </button>
                <button
                  onClick={() => setEventPeriod(2)}
                  className={`px-2 py-0.5 rounded text-xs font-semibold ${
                    eventPeriod === 2 ? 'bg-white text-black' : 'text-gray-400 hover:text-white'
                  }`}
                >
                  2nd Half
                </button>
              </div>
            </div>

            <div className="space-y-2">
              {events.filter(e => e.period === eventPeriod).map(e => {
                const isActive = currentTime >= e.timestamp - 1.0 && currentTime <= e.timestamp + 3.0;
                return (
                  <div
                    key={e.id}
                    className={`p-2.5 border rounded-xl transition flex items-center justify-between ${
                      isActive
                        ? 'bg-[#14261c] border-[#00E676] shadow-lg shadow-[#00E676]/10'
                        : 'bg-[#12141a] border-[#1e222d]'
                    }`}
                  >
                    <div className="flex items-center space-x-2">
                      <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded font-bold ${
                        isActive ? 'bg-[#00E676] text-black' : 'text-[#00E676] bg-[#00E676]/10'
                      }`}>
                        {formatTime(e.timestamp)}
                      </span>
                      <span className="text-xs text-white font-medium">{e.description}</span>
                    </div>
                    <div className="flex items-center space-x-1">
                      <button
                        type="button"
                        disabled
                        title="No backend endpoint exists to promote an event to a clip yet"
                        aria-label={`Add ${e.description} as a clip (not available)`}
                        className="p-1.5 rounded-md text-gray-400 disabled:cursor-not-allowed disabled:opacity-40"
                      >
                        <Video className="w-3.5 h-3.5" />
                      </button>
                      <button
                        type="button"
                        onClick={() => onSeek(e.timestamp)}
                        className="p-1.5 rounded-md text-gray-400 hover:text-[#00E676] hover:bg-[#20252f] transition"
                        aria-label={`Seek to ${e.description} at ${formatTime(e.timestamp)}`}
                        title="Seek to event"
                      >
                        <ArrowUpRight className={`w-3.5 h-3.5 ${isActive ? 'text-[#00E676]' : ''}`} />
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ================= ANALYTICS STUDIO TAB ================= */}
        {activeTab === 'analytics' && (
          <div className="p-3 space-y-4">
            {/* Analysis Mode & Swap Teams Controls (P1-0 & P1-2) */}
            <div className="flex items-center justify-between bg-[#12141a] border border-[#1e222d] rounded-xl p-2.5">
              <div className="flex items-center space-x-2">
                {match.analysis_mode === 'demo' ? (
                  <span className="text-[10px] font-bold text-amber-400 bg-amber-500/20 px-2 py-0.5 rounded-full border border-amber-500/40">
                    Demo Dataset
                  </span>
                ) : match.analysis_mode === 'heuristic' ? (
                  <span className="text-[10px] font-bold text-zinc-300 bg-zinc-800 px-2 py-0.5 rounded-full border border-zinc-700">
                    Heuristic Analysis
                  </span>
                ) : (
                  <span className="text-[10px] font-bold text-[#00E676] bg-emerald-500/20 px-2 py-0.5 rounded-full border border-emerald-500/40">
                    AI Analysis
                  </span>
                )}
              </div>

              {onSwapTeams && (
                <button
                  onClick={onSwapTeams}
                  className="flex items-center space-x-1.5 bg-[#1f2430] hover:bg-[#2c3444] border border-[#2a2a2a] text-xs text-white px-2.5 py-1 rounded-lg transition font-medium cursor-pointer"
                  title="Correct team kit assignment"
                >
                  <ArrowLeftRight className="w-3.5 h-3.5 text-[#00E676]" />
                  <span>Swap Teams</span>
                </button>
              )}
            </div>

            {!analytics ? (
              <Unavailable
                reason={
                  "This match was analysed by the ML pipeline. The stats table below is produced " +
                  "by a separate heuristic pipeline that this match never ran, and combining the two " +
                  "would misattribute one pipeline's numbers to the other, so no analytics are shown " +
                  "for this match."
                }
              />
            ) : (
              <>
                {/* Stats */}
                <div className="bg-[#12141a] border border-[#1e222d] rounded-xl overflow-hidden">
                  <button
                    type="button"
                    onClick={() => toggleSection('stats')}
                    aria-expanded={openSections.stats}
                    aria-controls="analytics-section-stats"
                    className="w-full flex items-center justify-between p-3 text-left cursor-pointer"
                  >
                    <span className="flex items-center gap-2">
                      <ChevronDown className={`w-3.5 h-3.5 text-gray-400 transition-transform ${openSections.stats ? '' : '-rotate-90'}`} aria-hidden="true" />
                      <span className="text-xs font-bold text-white uppercase tracking-wider">Stats</span>
                    </span>
                  </button>
                  {openSections.stats && (
                  <div id="analytics-section-stats" className="px-3 pb-3 text-xs space-y-2">
                    <div className="flex items-center justify-between font-bold text-gray-300 pb-1.5 border-b border-[#222]">
                      <span className="text-[#FFD700] truncate max-w-[100px]">{match.home_team}</span>
                      <span className="text-[10px] text-gray-500 font-mono">VS</span>
                      <span className="text-[#2979FF] truncate max-w-[100px]">{match.away_team}</span>
                    </div>
                    {[
                      { label: 'Goal', h: analytics.home_stats.goals, a: analytics.away_stats.goals, eventTypes: ['Goal'] },
                      { label: 'Shot', h: analytics.home_stats.shots, a: analytics.away_stats.shots, eventTypes: ['Shot'] },
                      { label: 'Total attempts', h: analytics.home_stats.attempts, a: analytics.away_stats.attempts, eventTypes: ['Shot', 'Shot on goal'] },
                      { label: 'Corner', h: analytics.home_stats.corners, a: analytics.away_stats.corners, eventTypes: ['Corner'] },
                      { label: 'Foul', h: analytics.home_stats.fouls, a: analytics.away_stats.fouls, eventTypes: ['Foul'] },
                      { label: 'Free kick', h: analytics.home_stats.free_kicks, a: analytics.away_stats.free_kicks, eventTypes: ['Free kick'] },
                      { label: 'Passes completed', h: analytics.home_stats.passes_completed, a: analytics.away_stats.passes_completed, derived: true, eventTypes: [] },
                      { label: 'Penalty', h: analytics.home_stats.penalties, a: analytics.away_stats.penalties, eventTypes: ['Penalty'] },
                      { label: 'Possession %', h: analytics.home_stats.possession_percent, a: analytics.away_stats.possession_percent, derived: true, suffix: '%', eventTypes: [] },
                      { label: 'Possession minutes', h: analytics.home_stats.possession_minutes, a: analytics.away_stats.possession_minutes, eventTypes: [] },
                      { label: 'Possession won', h: analytics.home_stats.possession_won, a: analytics.away_stats.possession_won, derived: true, eventTypes: [] },
                      { label: 'Tackle', h: analytics.home_stats.tackles, a: analytics.away_stats.tackles, eventTypes: ['Tackle'] },
                      { label: 'Throw-in', h: analytics.home_stats.throw_ins, a: analytics.away_stats.throw_ins, eventTypes: ['Throw-in'] },
                    ].map((r, i) => (
                      <button
                        type="button"
                        key={i}
                        disabled={r.derived}
                        onClick={() => seekToFirstEventOfType(r.eventTypes)}
                        className="w-full flex items-center justify-between py-1 border-b border-[#1a1e28] disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <div className="w-12 text-left">{renderStatValue(r.h, r.suffix)}</div>
                        <span className="text-gray-400 text-[11px]">{r.label}</span>
                        <div className="w-12 text-right">{renderStatValue(r.a, r.suffix)}</div>
                      </button>
                    ))}
                  </div>
                  )}
                </div>

                {/* Shot map */}
                <div className="bg-[#12141a] border border-[#1e222d] rounded-xl overflow-hidden">
                  <button
                    type="button"
                    onClick={() => toggleSection('shotMap')}
                    aria-expanded={openSections.shotMap}
                    aria-controls="analytics-section-shot-map"
                    className="w-full flex items-center justify-between p-3 text-left cursor-pointer"
                  >
                    <span className="flex items-center gap-2">
                      <ChevronDown className={`w-3.5 h-3.5 text-gray-400 transition-transform ${openSections.shotMap ? '' : '-rotate-90'}`} aria-hidden="true" />
                      <span className="text-xs font-bold text-white uppercase tracking-wider">Shot map</span>
                    </span>
                    <span className="text-[10px] text-[#00E676] font-bold">
                      {analytics.shot_map.length > 0
                        ? `${Math.round((analytics.shot_map.filter(s => s.outcome === 'goal').length / analytics.shot_map.length) * 100)}% Conversion`
                        : 'No shots recorded'}
                    </span>
                  </button>
                  {openSections.shotMap && (
                  <div id="analytics-section-shot-map" className="px-3 pb-3">
                    <div className="relative w-full aspect-[105/68] bg-[#1a472a] rounded-lg border border-[#2d5f3e] overflow-hidden">
                      <svg viewBox="0 0 105 68" className="w-full h-full" role="img" aria-label="2D soccer shot map">
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
                  )}
                </div>

                {/* Pass location */}
                <div className="bg-[#12141a] border border-[#1e222d] rounded-xl overflow-hidden">
                  <button
                    type="button"
                    onClick={() => toggleSection('passLocation')}
                    aria-expanded={openSections.passLocation}
                    aria-controls="analytics-section-pass-location"
                    className="w-full flex items-center justify-between p-3 text-left cursor-pointer"
                  >
                    <span className="flex items-center gap-2">
                      <ChevronDown className={`w-3.5 h-3.5 text-gray-400 transition-transform ${openSections.passLocation ? '' : '-rotate-90'}`} aria-hidden="true" />
                      <span className="text-xs font-bold text-white uppercase tracking-wider">Pass location</span>
                    </span>
                  </button>
                  {openSections.passLocation && (
                  <div id="analytics-section-pass-location" className="px-3 pb-3">
                    <ThirdsBar
                      label="Passes"
                      home={analytics.pass_locations?.home}
                      unavailableReason="No pass location data for this match — the pipeline that produced these analytics did not compute a pass-location breakdown."
                    />
                  </div>
                  )}
                </div>

                {/* Possession location */}
                <div className="bg-[#12141a] border border-[#1e222d] rounded-xl overflow-hidden">
                  <button
                    type="button"
                    onClick={() => toggleSection('possessionLocation')}
                    aria-expanded={openSections.possessionLocation}
                    aria-controls="analytics-section-possession-location"
                    className="w-full flex items-center justify-between p-3 text-left cursor-pointer"
                  >
                    <span className="flex items-center gap-2">
                      <ChevronDown className={`w-3.5 h-3.5 text-gray-400 transition-transform ${openSections.possessionLocation ? '' : '-rotate-90'}`} aria-hidden="true" />
                      <span className="text-xs font-bold text-white uppercase tracking-wider">Possession location</span>
                    </span>
                  </button>
                  {openSections.possessionLocation && (
                  <div id="analytics-section-possession-location" className="px-3 pb-3">
                    <ThirdsBar
                      label="Possession"
                      home={analytics.possession_locations?.home}
                      unavailableReason="No possession location data for this match — the pipeline that produced these analytics did not compute a possession-location breakdown."
                    />
                  </div>
                  )}
                </div>

                {/* Pass strings */}
                <div className="bg-[#12141a] border border-[#1e222d] rounded-xl overflow-hidden">
                  <button
                    type="button"
                    onClick={() => toggleSection('passStrings')}
                    aria-expanded={openSections.passStrings}
                    aria-controls="analytics-section-pass-strings"
                    className="w-full flex items-center justify-between p-3 text-left cursor-pointer"
                  >
                    <span className="flex items-center gap-2">
                      <ChevronDown className={`w-3.5 h-3.5 text-gray-400 transition-transform ${openSections.passStrings ? '' : '-rotate-90'}`} aria-hidden="true" />
                      <span className="text-xs font-bold text-white uppercase tracking-wider">Pass strings</span>
                    </span>
                  </button>
                  {openSections.passStrings && (
                  <div id="analytics-section-pass-strings" className="px-3 pb-3">
                    {analytics.pass_strings.home.length > 0 ? (
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
                    ) : (
                      <Unavailable reason="No pass-sequencing detection exists in this pipeline, so there is no pass-string distribution to show." />
                    )}
                  </div>
                  )}
                </div>

                {/* Heat map */}
                <div className="bg-[#12141a] border border-[#1e222d] rounded-xl overflow-hidden">
                  <button
                    type="button"
                    onClick={() => toggleSection('heatMap')}
                    aria-expanded={openSections.heatMap}
                    aria-controls="analytics-section-heat-map"
                    className="w-full flex items-center justify-between p-3 text-left cursor-pointer"
                  >
                    <span className="flex items-center gap-2">
                      <ChevronDown className={`w-3.5 h-3.5 text-gray-400 transition-transform ${openSections.heatMap ? '' : '-rotate-90'}`} aria-hidden="true" />
                      <span className="text-xs font-bold text-white uppercase tracking-wider">Heat map</span>
                    </span>
                  </button>
                  {openSections.heatMap && (
                  <div id="analytics-section-heat-map" className="px-3 pb-3">
                    <Unavailable reason="Unavailable — no metric pitch coordinates exist for this footage. Player positions are not calibrated to real-world metres (five measured calibration attempts failed), so no heat map can be drawn." />
                  </div>
                  )}
                </div>
              </>
            )}
          </div>
        )}

        {/* ================= PLAYERS TAB ================= */}
        {activeTab === 'players' && (
          <div className="p-3 space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-[#181818]">
              <span className="text-xs text-gray-400 font-medium">Player Moments</span>
              {selectedJersey && (
                <button
                  onClick={() => onSelectJersey(null)}
                  className="text-xs text-[#00E676] hover:underline"
                >
                  Show All Players
                </button>
              )}
            </div>

            <div className="space-y-2">
              {match.lineup.map(player => (
                <div
                  key={player.jersey}
                  onClick={() => onSelectJersey(player.jersey)}
                  className={`p-2.5 border rounded-xl cursor-pointer transition flex items-center justify-between ${
                    selectedJersey === player.jersey
                      ? 'bg-[#14261c] border-[#00E676]'
                      : 'bg-[#12141a] hover:bg-[#181c25] border-[#1e222d]'
                  }`}
                >
                  <div className="flex items-center space-x-2.5">
                    <span className="w-7 h-7 rounded-full bg-[#1f2430] text-[#00E676] font-bold text-xs flex items-center justify-center border border-[#2a2a2a]">
                      {player.jersey}
                    </span>
                    <div>
                      <div className="text-xs font-bold text-white">{player.name}</div>
                      <div className="text-[10px] text-gray-400">{player.position} • {player.minutes_played} mins played</div>
                    </div>
                  </div>
                  <span className="text-[10px] text-[#00E676] font-semibold bg-[#00E676]/10 px-2 py-0.5 rounded">
                    {highlights.filter(h => h.player_jersey === player.jersey).length} moments
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ================= LINEUP TAB ================= */}
        {activeTab === 'lineup' && (
          <div className="p-3 space-y-3">
            <div className="flex items-center justify-between pb-2 border-b border-[#181818]">
              <div>
                <h4 className="text-xs font-bold text-white">Starting XI</h4>
                <p className="text-[10px] text-gray-400">{match.home_team}</p>
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
