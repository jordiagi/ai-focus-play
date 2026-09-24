import React, { useState } from 'react';
import {
  Video, List, Shirt, BarChart2, LayoutGrid, FileText,
  Play, ArrowLeftRight, ArrowUpRight, ArrowLeft, ChevronDown, X, Info
} from 'lucide-react';
import { Match, Highlight, Event, AnalyticsData, EventTypeLabel } from '../../types';
import { api } from '../../services/api';
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

const METRIC_KEY_MAP: Record<string, string> = {
  goals: 'goal',
  shots: 'shot',
  attempts: 'total_attempts',
  corners: 'corner',
  free_kicks: 'free_kick',
  throw_ins: 'throw_in',
  fouls: 'foul',
  penalties: 'penalty',
  tackles: 'tackle',
  passes_completed: 'passes_completed',
  possession_percent: 'possession_percent',
  possession_minutes: 'possession_minutes',
  possession_won: 'possession_won',
};

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
  const [shotMapTeam, setShotMapTeam] = useState<'home' | 'away'>('home');
  const [passLocTeam, setPassLocTeam] = useState<'home' | 'away'>('home');
  const [possLocTeam, setPossLocTeam] = useState<'home' | 'away'>('home');
  const [passStringsTeam, setPassStringsTeam] = useState<'home' | 'away'>('home');
  const [showBenchmark, setShowBenchmark] = useState(false);
  const [benchmarkData, setBenchmarkData] = useState<any>(null);
  const [loadingBenchmark, setLoadingBenchmark] = useState(false);

  const handleToggleBenchmark = async () => {
    const next = !showBenchmark;
    setShowBenchmark(next);
    if (next && !benchmarkData && match?.id) {
      setLoadingBenchmark(true);
      try {
        const data = await api.getBenchmark(match.id);
        setBenchmarkData(data);
      } catch (err) {
        console.warn('Could not load Veo benchmark data', err);
      } finally {
        setLoadingBenchmark(false);
      }
    }
  };

  const toggleSection = (key: AnalyticsSectionKey) =>
    setOpenSections(prev => ({ ...prev, [key]: !prev[key] }));

  if (!activeTab) return null;

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const filteredHighlights = highlights.filter(h => {
    if (selectedJersey && h.player_jersey !== selectedJersey) return false;
    if (highlightFilter === 'all') return true;
    if (highlightFilter === 'goals') return h.event_type === 'goal';
    if (highlightFilter === 'shots') return h.event_type === 'shot';
    return true;
  });

  const getPlayerMoments = (jersey: string) => {
    const list: Array<{
      id: string;
      timestamp: number;
      title: string;
      event_type: string;
      tags?: string[];
      team?: string;
    }> = [];

    // Add highlights matching jersey
    highlights
      .filter(h => h.player_jersey === jersey)
      .forEach(h => {
        list.push({
          id: `hl-${h.id}`,
          timestamp: h.start_time,
          title: h.title,
          event_type: h.event_type,
          tags: h.tags,
          team: h.team,
        });
      });

    // Add events matching jersey, deduplicating if an existing highlight covers this moment within 2.5s
    events
      .filter(e => e.player_jersey === jersey)
      .forEach(e => {
        const isCovered = list.some(m => Math.abs(m.timestamp - e.timestamp) <= 2.5);
        if (!isCovered) {
          list.push({
            id: `evt-${e.id}`,
            timestamp: e.timestamp,
            title: e.description,
            event_type: e.event_type,
            team: e.team,
          });
        }
      });

    return list.sort((a, b) => a.timestamp - b.timestamp);
  };

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

  // A row named in the backend's `unavailable` map renders as an em-dash carrying the
  // measured reason, WHATEVER numeric value the field holds. Several stat fields are
  // non-Optional server-side and default to a plausible number -- possession_percent
  // defaults to 50.0, and an ML match carries a real detection count in `goals` that
  // is NOT a scoreline -- so the value alone cannot express "never measured".
  const renderStatValue = (
    val: number | string | null | undefined,
    suffix = '',
    reason?: string,
  ) => {
    if (reason) {
      return (
        <span className="text-gray-500 font-bold cursor-help" title={reason}>
          —
        </span>
      );
    }
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

            {/* Active player filter badge if jersey selected */}
            {selectedJersey && (
              <div className="flex items-center justify-between bg-[#14261c] border border-[#00E676]/40 text-[#00E676] px-2.5 py-1.5 rounded-lg text-xs animate-in fade-in duration-150">
                <div className="flex items-center space-x-1.5 truncate">
                  <Shirt className="w-3.5 h-3.5 shrink-0" />
                  <span className="font-semibold">Filtered to #{selectedJersey}</span>
                  <span className="text-gray-400 font-normal">({filteredHighlights.length} clip{filteredHighlights.length === 1 ? '' : 's'})</span>
                </div>
                <button
                  onClick={() => onSelectJersey(null)}
                  className="text-gray-400 hover:text-white transition text-[11px] underline shrink-0 ml-2"
                >
                  Clear
                </button>
              </div>
            )}

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

            {/* Active player filter badge if jersey selected */}
            {selectedJersey && (
              <div className="flex items-center justify-between bg-[#14261c] border border-[#00E676]/40 text-[#00E676] px-2.5 py-1.5 rounded-lg text-xs animate-in fade-in duration-150">
                <div className="flex items-center space-x-1.5 truncate">
                  <Shirt className="w-3.5 h-3.5 shrink-0" />
                  <span className="font-semibold">Filtered to #{selectedJersey}</span>
                </div>
                <button
                  onClick={() => onSelectJersey(null)}
                  className="text-gray-400 hover:text-white transition text-[11px] underline shrink-0 ml-2"
                >
                  Clear
                </button>
              </div>
            )}

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
              {(() => {
                const periodEvents = events.filter(e => e.period === eventPeriod && (!selectedJersey || e.player_jersey === selectedJersey));
                if (periodEvents.length === 0) {
                  return (
                    <div className="p-6 text-center text-xs text-gray-500 bg-[#12141a] rounded-xl border border-[#1e222d]">
                      {selectedJersey ? `No events detected for #${selectedJersey} in Half ${eventPeriod}` : 'No events in this half'}
                    </div>
                  );
                }
                return periodEvents.map(e => {
                  const isActive = currentTime >= e.timestamp - 1.0 && currentTime <= e.timestamp + 3.0;
                  const isPlayerMatch = selectedJersey && e.player_jersey === selectedJersey;
                  return (
                    <div
                      key={e.id}
                      className={`p-2.5 border rounded-xl transition flex items-center justify-between ${
                        isActive
                          ? 'bg-[#14261c] border-[#00E676] shadow-lg shadow-[#00E676]/10'
                          : isPlayerMatch
                          ? 'bg-[#14261c]/60 border-[#00E676]/60'
                          : 'bg-[#12141a] border-[#1e222d]'
                      }`}
                    >
                      <div className="flex items-center space-x-2 min-w-0 pr-2">
                        <span className={`text-[10px] font-mono px-1.5 py-0.5 rounded font-bold shrink-0 ${
                          isActive ? 'bg-[#00E676] text-black' : 'text-[#00E676] bg-[#00E676]/10'
                        }`}>
                          {formatTime(e.timestamp)}
                        </span>
                        {e.player_jersey && (
                          <button
                            type="button"
                            onClick={() => onSelectJersey(selectedJersey === e.player_jersey ? null : e.player_jersey!)}
                            className={`text-[10px] font-bold px-1.5 py-0.5 rounded transition shrink-0 ${
                              selectedJersey === e.player_jersey
                                ? 'bg-[#00E676] text-black'
                                : 'bg-[#1f2430] text-[#FFD700] hover:bg-[#283244]'
                            }`}
                            title={`Filter to Player #${e.player_jersey}`}
                          >
                            #{e.player_jersey}
                          </button>
                        )}
                        <span className="text-xs text-white font-medium truncate">{e.description}</span>
                      </div>
                      <div className="flex items-center space-x-1 shrink-0">
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
                });
              })()}
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
                {/* Top KPI Delta Cards */}
                <div className="grid grid-cols-3 gap-2">
                  <div className="bg-[#12141a] border border-[#1e222d] rounded-xl p-2.5 flex flex-col justify-between">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] text-gray-400 font-medium">Goals scored</span>
                      <span className="text-[9px] font-bold px-1.5 py-0.2 rounded bg-[#00E676]/20 text-[#00E676]">+1</span>
                    </div>
                    <div className="text-lg font-bold text-white my-0.5">
                      {renderStatValue(analytics.home_stats.goals, '', analytics.unavailable?.goals)}
                    </div>
                    <span className="text-[8px] text-gray-500 leading-tight">Diff of 1 vs last match</span>
                  </div>
                  <div className="bg-[#12141a] border border-[#1e222d] rounded-xl p-2.5 flex flex-col justify-between">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] text-gray-400 font-medium">Shots attempted</span>
                      <span className="text-[9px] font-bold px-1.5 py-0.2 rounded bg-red-500/20 text-red-400">-5</span>
                    </div>
                    <div className="text-lg font-bold text-white my-0.5">
                      {renderStatValue(analytics.home_stats.shots, '', analytics.unavailable?.shots)}
                    </div>
                    <span className="text-[8px] text-gray-500 leading-tight">Diff of 5 vs last match</span>
                  </div>
                  <div className="bg-[#12141a] border border-[#1e222d] rounded-xl p-2.5 flex flex-col justify-between">
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] text-gray-400 font-medium">Match possession</span>
                      <span className="text-[9px] font-bold px-1.5 py-0.2 rounded bg-amber-500/20 text-amber-400">-1%</span>
                    </div>
                    <div className="text-lg font-bold text-white my-0.5">
                      {renderStatValue(analytics.home_stats.possession_percent, '%', analytics.unavailable?.possession_percent)}
                    </div>
                    <span className="text-[8px] text-gray-500 leading-tight">Diff of 1% vs last match</span>
                  </div>
                </div>

                {/* Stats */}
                <div className="bg-[#12141a] border border-[#1e222d] rounded-xl overflow-hidden">
                  <div className="w-full flex items-center justify-between p-3 text-left">
                    <button
                      type="button"
                      onClick={() => toggleSection('stats')}
                      aria-expanded={openSections.stats}
                      aria-controls="analytics-section-stats"
                      className="flex items-center gap-2 cursor-pointer"
                    >
                      <ChevronDown className={`w-3.5 h-3.5 text-gray-400 transition-transform ${openSections.stats ? '' : '-rotate-90'}`} aria-hidden="true" />
                      <span className="text-xs font-bold text-white uppercase tracking-wider">Stats</span>
                    </button>
                    <button
                      type="button"
                      onClick={handleToggleBenchmark}
                      className={`text-[10px] font-semibold px-2 py-0.5 rounded-full border transition cursor-pointer ${
                        showBenchmark
                          ? 'bg-[#00E676]/20 border-[#00E676]/50 text-[#00E676]'
                          : 'bg-[#1b1f2b] border-[#2c3242] text-gray-400 hover:text-gray-200'
                      }`}
                      title="Compare predictions against live Veo ground truth"
                    >
                      {loadingBenchmark ? 'Loading...' : showBenchmark ? 'Veo Benchmark ON' : 'Compare Veo'}
                    </button>
                  </div>
                  {openSections.stats && (
                  <div id="analytics-section-stats" className="px-3 pb-3 text-xs space-y-2">
                    <div className="flex items-center justify-between font-bold text-gray-300 pb-1.5 border-b border-[#222]">
                      <span className="text-[#FFD700] truncate max-w-[100px]">{match.home_team}</span>
                      <span className="text-[10px] text-gray-500 font-mono">VS</span>
                      <span className="text-[#2979FF] truncate max-w-[100px]">{match.away_team}</span>
                    </div>
                    {[
                      { label: 'Goal', statKey: 'goals', h: analytics.home_stats.goals, a: analytics.away_stats.goals, eventTypes: ['Goal'] },
                      { label: 'Shot', statKey: 'shots', h: analytics.home_stats.shots, a: analytics.away_stats.shots, eventTypes: ['Shot'] },
                      { label: 'Total attempts', statKey: 'attempts', h: analytics.home_stats.attempts, a: analytics.away_stats.attempts, eventTypes: ['Shot', 'Shot on goal'] },
                      { label: 'Corner', statKey: 'corners', h: analytics.home_stats.corners, a: analytics.away_stats.corners, eventTypes: ['Corner'] },
                      { label: 'Foul', statKey: 'fouls', h: analytics.home_stats.fouls, a: analytics.away_stats.fouls, eventTypes: ['Foul'] },
                      { label: 'Free kick', statKey: 'free_kicks', h: analytics.home_stats.free_kicks, a: analytics.away_stats.free_kicks, eventTypes: ['Free kick'] },
                      { label: 'Passes completed', statKey: 'passes_completed', h: analytics.home_stats.passes_completed, a: analytics.away_stats.passes_completed, derived: true, eventTypes: [] },
                      { label: 'Penalty', statKey: 'penalties', h: analytics.home_stats.penalties, a: analytics.away_stats.penalties, eventTypes: ['Penalty'] },
                      { label: 'Possession %', statKey: 'possession_percent', h: analytics.home_stats.possession_percent, a: analytics.away_stats.possession_percent, derived: true, suffix: '%', eventTypes: [] },
                      { label: 'Possession minutes', statKey: 'possession_minutes', h: analytics.home_stats.possession_minutes, a: analytics.away_stats.possession_minutes, eventTypes: [] },
                      { label: 'Possession won', statKey: 'possession_won', h: analytics.home_stats.possession_won, a: analytics.away_stats.possession_won, derived: true, eventTypes: [] },
                      { label: 'Tackle', statKey: 'tackles', h: analytics.home_stats.tackles, a: analytics.away_stats.tackles, eventTypes: ['Tackle'] },
                      { label: 'Throw-in', statKey: 'throw_ins', h: analytics.home_stats.throw_ins, a: analytics.away_stats.throw_ins, eventTypes: ['Throw-in'] },
                    ].map((r, i) => {
                      const metricKey = METRIC_KEY_MAP[r.statKey] || r.statKey;
                      const bm = showBenchmark && benchmarkData?.comparison?.metrics?.[metricKey];
                      return (
                        <div key={i} className="border-b border-[#1a1e28] pb-0.5">
                          <button
                            type="button"
                            disabled={r.derived}
                            onClick={() => seekToFirstEventOfType(r.eventTypes)}
                            className="w-full flex items-center justify-between py-1 disabled:cursor-not-allowed disabled:opacity-50"
                          >
                            <div className="w-12 text-left">{renderStatValue(r.h, r.suffix, analytics.unavailable?.[r.statKey])}</div>
                            <span className="text-gray-400 text-[11px]">{r.label}</span>
                            <div className="w-12 text-right">{renderStatValue(r.a, r.suffix, analytics.unavailable?.[r.statKey])}</div>
                          </button>
                          {bm && (
                            <div className="flex items-center justify-between px-1.5 py-0.5 bg-[#0b0e14] rounded text-[9px] text-gray-400 font-mono mb-1">
                              <span className="flex items-center space-x-1">
                                <span className="text-gray-500">Veo:</span>
                                <span className="text-gray-300 font-semibold">{bm.ref_home !== null ? `${bm.ref_home}${r.suffix || ''}` : '—'}</span>
                                {bm.home_delta !== null && (
                                  <span className={`px-1 py-0.2 rounded font-bold ${bm.home_delta === 0 ? 'text-[#00E676] bg-[#00E676]/10' : 'text-amber-400 bg-amber-500/10'}`}>
                                    Δ{Math.round(bm.home_delta * 10) / 10 > 0 ? `+${Math.round(bm.home_delta * 10) / 10}` : Math.round(bm.home_delta * 10) / 10}
                                  </span>
                                )}
                              </span>
                              <span className="text-[8px] uppercase tracking-wider">
                                {bm.exact_match ? <span className="text-[#00E676] font-bold">✓ Match</span> : <span className="text-gray-500">Benchmark</span>}
                              </span>
                              <span className="flex items-center space-x-1">
                                {bm.away_delta !== null && (
                                  <span className={`px-1 py-0.2 rounded font-bold ${bm.away_delta === 0 ? 'text-[#00E676] bg-[#00E676]/10' : 'text-amber-400 bg-amber-500/10'}`}>
                                    Δ{Math.round(bm.away_delta * 10) / 10 > 0 ? `+${Math.round(bm.away_delta * 10) / 10}` : Math.round(bm.away_delta * 10) / 10}
                                  </span>
                                )}
                                <span className="text-gray-300 font-semibold">{bm.ref_away !== null ? `${bm.ref_away}${r.suffix || ''}` : '—'}</span>
                                <span className="text-gray-500">:Veo</span>
                              </span>
                            </div>
                          )}
                        </div>
                      );
                    })}
                    {showBenchmark && benchmarkData?.comparison && (
                      <div className="p-2 mt-2 rounded-lg bg-[#0e1117] border border-[#1e2433] space-y-1">
                        <div className="flex items-center justify-between text-[10px]">
                          <span className="text-gray-400 font-medium">Veo Benchmark Reference</span>
                          <span className="text-[#00E676] font-bold">
                            {benchmarkData.comparison.exact_match_count} / {benchmarkData.comparison.evaluated_count} exact ({Math.round(benchmarkData.comparison.exact_match_ratio * 100)}%)
                          </span>
                        </div>
                        <div className="text-[9px] text-gray-500 truncate">
                          {typeof benchmarkData.benchmark_match === 'string'
                            ? benchmarkData.benchmark_match
                            : benchmarkData.benchmark_match?.title || 'Veo Ground Truth'}
                        </div>
                      </div>
                    )}
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
                  {openSections.shotMap && (() => {
                    const teamShots = (analytics.shot_map || []).filter(s => s.team === shotMapTeam || !s.team);
                    const goalCount = (shotMapTeam === 'home' ? analytics.home_stats.goals : analytics.away_stats.goals) ?? teamShots.filter(s => s.outcome === 'goal').length;
                    const shotCount = (shotMapTeam === 'home' ? analytics.home_stats.shots : analytics.away_stats.shots) ?? teamShots.filter(s => s.outcome !== 'goal').length;
                    const totalAttempts = goalCount + shotCount;

                    const insideBoxAttempts = teamShots.filter(s => s.is_inside_box);
                    const outsideBoxAttempts = teamShots.filter(s => !s.is_inside_box);
                    const insideBoxGoals = insideBoxAttempts.filter(s => s.outcome === 'goal');
                    const outsideBoxGoals = outsideBoxAttempts.filter(s => s.outcome === 'goal');

                    const overallConversion = totalAttempts > 0 ? Math.round((goalCount / totalAttempts) * 100) : 0;
                    const insideConversion = insideBoxAttempts.length > 0
                      ? Math.round((insideBoxGoals.length / insideBoxAttempts.length) * 100)
                      : (totalAttempts > 0 && goalCount > 0 ? Math.round((goalCount / totalAttempts) * 100) : 0);
                    const outsideConversion = outsideBoxAttempts.length > 0
                      ? Math.round((outsideBoxGoals.length / outsideBoxAttempts.length) * 100)
                      : 0;
                    const insidePct = teamShots.length > 0
                      ? Math.round((insideBoxAttempts.length / teamShots.length) * 100)
                      : (totalAttempts > 0 ? 50 : 0);
                    const outsidePct = teamShots.length > 0
                      ? Math.round((outsideBoxAttempts.length / teamShots.length) * 100)
                      : (totalAttempts > 0 ? 50 : 0);

                    const gtShotMap = showBenchmark && benchmarkData?.live_ground_truth?.shot_map;
                    const gtTeam = gtShotMap ? (shotMapTeam === 'home' ? gtShotMap.own : gtShotMap.opponent) : null;

                    return (
                      <div id="analytics-section-shot-map" className="px-3 pb-3 space-y-2.5">
                        {/* Team toggle & attacking direction */}
                        <div className="flex items-center justify-between">
                          <div className="flex items-center space-x-1">
                            <button
                              type="button"
                              onClick={() => setShotMapTeam('home')}
                              className={`px-2.5 py-0.5 rounded text-[11px] font-bold transition cursor-pointer ${
                                shotMapTeam === 'home' ? 'bg-[#FFD700]/20 text-[#FFD700] border border-[#FFD700]/40' : 'bg-[#181818] text-gray-400 hover:text-white'
                              }`}
                            >
                              {match.home_team.split(' ')[0] || 'Home'}
                            </button>
                            <button
                              type="button"
                              onClick={() => setShotMapTeam('away')}
                              className={`px-2.5 py-0.5 rounded text-[11px] font-bold transition cursor-pointer ${
                                shotMapTeam === 'away' ? 'bg-[#2979FF]/20 text-[#2979FF] border border-[#2979FF]/40' : 'bg-[#181818] text-gray-400 hover:text-white'
                              }`}
                            >
                              {match.away_team.split(' ')[0] || 'Away'}
                            </button>
                          </div>
                          <div className="text-[10px] text-gray-400 font-medium flex items-center gap-1">
                            <span>{shotMapTeam === 'home' ? match.home_team.split(' ')[0] : match.away_team.split(' ')[0]} →</span>
                            <span className="text-gray-500 font-mono">Full match</span>
                          </div>
                        </div>

                        {/* Top summary row: Goal count, Shot count, Total attempts */}
                        <div className="bg-[#0b0e14] border border-[#1e2433] rounded-lg p-2 space-y-1.5">
                          <div className="flex items-center justify-between text-xs">
                            <div className="flex items-center space-x-1.5 text-gray-300">
                              <span className="w-2.5 h-2.5 rounded-full bg-white inline-block"></span>
                              <span>Goal count</span>
                            </div>
                            <div className="flex items-center space-x-1.5">
                              <span className="font-bold text-white">{goalCount}</span>
                              {gtTeam && (
                                <span className="text-[9px] text-[#00E676] font-mono">Veo: {gtTeam.goals}</span>
                              )}
                            </div>
                          </div>
                          <div className="flex items-center justify-between text-xs">
                            <div className="flex items-center space-x-1.5 text-gray-400">
                              <span className="w-2.5 h-2.5 rounded-full border border-white inline-block"></span>
                              <span>Shot count</span>
                            </div>
                            <div className="flex items-center space-x-1.5">
                              <span className="font-bold text-gray-300">{shotCount}</span>
                              {gtTeam && (
                                <span className="text-[9px] text-[#00E676] font-mono">Veo: {gtTeam.shots}</span>
                              )}
                            </div>
                          </div>
                          <div className="flex items-center justify-between text-xs pt-1 border-t border-[#1a1f2c]">
                            <span className="text-gray-400 font-medium">Total attempts</span>
                            <div className="flex items-center space-x-1.5">
                              <span className="font-bold text-white">{totalAttempts}</span>
                              {gtTeam && (
                                <span className="text-[9px] text-[#00E676] font-mono">Veo: {gtTeam.total_attempts}</span>
                              )}
                            </div>
                          </div>
                        </div>

                        {/* 5 Veo conversion breakdown metrics */}
                        <div className="space-y-1 text-[11px] text-gray-300 bg-[#121620] border border-[#1d2331] rounded-lg p-2.5">
                          <div className="flex items-center justify-between">
                            <span><strong className="text-white font-semibold">{overallConversion}%</strong> conversion rate.</span>
                            {gtTeam && <span className="text-[9px] text-[#00E676] font-mono">Veo: {gtTeam.conversion_rate_pct}%</span>}
                          </div>
                          <div className="flex items-center justify-between">
                            <span><strong className="text-white font-semibold">{insideConversion}%</strong> inside box conversion rate.</span>
                            {gtTeam && <span className="text-[9px] text-[#00E676] font-mono">Veo: {gtTeam.inside_box_conversion_rate_pct}%</span>}
                          </div>
                          <div className="flex items-center justify-between">
                            <span><strong className="text-white font-semibold">{outsideConversion}%</strong> outside box conversion rate.</span>
                            {gtTeam && <span className="text-[9px] text-[#00E676] font-mono">Veo: {gtTeam.outside_box_conversion_rate_pct}%</span>}
                          </div>
                          <div className="flex items-center justify-between">
                            <span><strong className="text-white font-semibold">{insidePct}%</strong> of total attempts inside box.</span>
                            {gtTeam && <span className="text-[9px] text-[#00E676] font-mono">Veo: {gtTeam.attempts_inside_box_pct}%</span>}
                          </div>
                          <div className="flex items-center justify-between">
                            <span><strong className="text-white font-semibold">{outsidePct}%</strong> of total attempts outside box.</span>
                            {gtTeam && <span className="text-[9px] text-[#00E676] font-mono">Veo: {gtTeam.attempts_outside_box_pct}%</span>}
                          </div>
                        </div>

                        {/* Tactical half-pitch map */}
                        <div className="relative w-full aspect-[52.5/42] bg-[#0c1017] rounded-lg border border-[#222838] overflow-hidden p-1">
                          <svg viewBox="0 0 52.5 68" className="w-full h-full" role="img" aria-label="2D soccer half-pitch shot map">
                            {/* Touchlines and boundaries */}
                            <rect x="0.5" y="0.5" width="51.5" height="67" fill="none" stroke="rgba(255,255,255,0.3)" strokeWidth="0.8" />
                            {/* Half-way line on left */}
                            <line x1="0.5" y1="0.5" x2="0.5" y2="67.5" stroke="rgba(255,255,255,0.4)" strokeWidth="0.8" />
                            {/* Center circle arc */}
                            <path d="M 0.5 24.85 A 9.15 9.15 0 0 1 0.5 43.15" fill="none" stroke="rgba(255,255,255,0.3)" strokeWidth="0.8" />
                            {/* Center spot */}
                            <circle cx="0.5" cy="34" r="0.6" fill="rgba(255,255,255,0.5)" />
                            {/* Penalty area (16.5m depth, 40.32m width) */}
                            <rect x="36.0" y="13.84" width="16.0" height="40.32" fill="none" stroke="rgba(255,255,255,0.3)" strokeWidth="0.8" />
                            {/* 6-yard box (5.5m depth, 18.32m width) */}
                            <rect x="47.0" y="24.84" width="5.0" height="18.32" fill="none" stroke="rgba(255,255,255,0.3)" strokeWidth="0.8" />
                            {/* Penalty spot at 41.5m */}
                            <circle cx="41.5" cy="34" r="0.6" fill="rgba(255,255,255,0.5)" />
                            {/* Penalty arc outside the box */}
                            <path d="M 36.0 27.8 A 9.15 9.15 0 0 0 36.0 40.2" fill="none" stroke="rgba(255,255,255,0.3)" strokeWidth="0.8" />
                            {/* Goal posts */}
                            <rect x="52.0" y="30.34" width="0.8" height="7.32" fill="rgba(255,255,255,0.7)" />

                            {/* Wing tactical labels */}
                            <text x="2" y="7" fill="rgba(255,255,255,0.25)" fontSize="2.8" fontWeight="bold" letterSpacing="0.4">LEFT WING →</text>
                            <text x="2" y="63" fill="rgba(255,255,255,0.25)" fontSize="2.8" fontWeight="bold" letterSpacing="0.4">RIGHT WING →</text>

                            {/* Model predicted shots */}
                            {teamShots.map(s => {
                              const xHalf = s.x >= 52.5 ? s.x - 52.5 : 52.5 - s.x;
                              const clampedX = Math.max(2, Math.min(50.5, xHalf));
                              const clampedY = Math.max(2, Math.min(66, s.y));
                              const isGoal = s.outcome === 'goal';
                              return (
                                <g key={s.id} onClick={() => onSeek(s.timestamp)} className="cursor-pointer">
                                  <circle
                                    cx={clampedX}
                                    cy={clampedY}
                                    r={isGoal ? 2.2 : 1.8}
                                    fill={isGoal ? '#ffffff' : 'none'}
                                    stroke="#ffffff"
                                    strokeWidth={isGoal ? '0.4' : '0.8'}
                                    className="hover:scale-150 transition-transform"
                                  >
                                    <title>{`Model: ${isGoal ? 'Goal' : 'Shot'} at ${Math.round(s.timestamp)}s`}</title>
                                  </circle>
                                </g>
                              );
                            })}

                            {/* Veo ground-truth benchmark shot markers overlay */}
                            {showBenchmark && gtTeam?.markers && gtTeam.markers.map((m: any, idx: number) => {
                              const rawX = m.left_pct >= 50 ? ((m.left_pct - 50) / 50) * 52.5 : ((50 - m.left_pct) / 50) * 52.5;
                              const xHalf = Math.max(2, Math.min(50.5, rawX));
                              const yPos = Math.max(2, Math.min(66, (1 - m.bottom_pct / 100) * 68));
                              const isGoal = m.type === 'goal';
                              return (
                                <g key={`gt-${idx}`} onClick={() => onSeek(m.time_s)} className="cursor-pointer">
                                  <circle
                                    cx={xHalf}
                                    cy={yPos}
                                    r={isGoal ? 2.4 : 2.0}
                                    fill={isGoal ? '#00E676' : 'none'}
                                    stroke="#00E676"
                                    strokeWidth={isGoal ? '0.5' : '1.0'}
                                    strokeDasharray={isGoal ? 'none' : '1,0.5'}
                                    className="hover:scale-150 transition-transform"
                                  >
                                    <title>{`Veo Ground Truth: ${isGoal ? 'Goal' : 'Shot'} at ${m.time_str} (${m.time_s}s)`}</title>
                                  </circle>
                                </g>
                              );
                            })}
                          </svg>
                        </div>

                        {/* Benchmark legend if active */}
                        {showBenchmark && (
                          <div className="flex items-center justify-between px-2 py-1 bg-[#0b0e14] rounded border border-[#1e2433] text-[9px]">
                            <div className="flex items-center space-x-2">
                              <span className="flex items-center gap-1 text-gray-300">
                                <span className="w-1.5 h-1.5 rounded-full bg-white inline-block"></span> Model Goal
                              </span>
                              <span className="flex items-center gap-1 text-gray-400">
                                <span className="w-1.5 h-1.5 rounded-full border border-white inline-block"></span> Model Shot
                              </span>
                            </div>
                            <div className="flex items-center space-x-2">
                              <span className="flex items-center gap-1 text-[#00E676]">
                                <span className="w-1.5 h-1.5 rounded-full bg-[#00E676] inline-block"></span> Veo Goal
                              </span>
                              <span className="flex items-center gap-1 text-[#00E676]">
                                <span className="w-1.5 h-1.5 rounded-full border border-[#00E676] inline-block"></span> Veo Shot
                              </span>
                            </div>
                          </div>
                        )}

                        {/* How to read the shot map footer */}
                        <div className="flex items-center space-x-1.5 text-[10px] text-gray-400 pt-0.5">
                          <Info className="w-3 h-3 text-gray-500 shrink-0" />
                          <span>Solid circles represent goals; hollow circles represent shots.</span>
                        </div>
                      </div>
                    );
                  })()}
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
                  <div id="analytics-section-pass-location" className="px-3 pb-3 space-y-2">
                    {/* Team toggle */}
                    <div className="flex items-center space-x-1">
                      <button
                        type="button"
                        onClick={() => setPassLocTeam('home')}
                        className={`px-2 py-0.5 rounded text-[10px] font-bold transition ${
                          passLocTeam === 'home' ? 'bg-[#FFD700]/20 text-[#FFD700] border border-[#FFD700]/40' : 'bg-[#181818] text-gray-400 hover:text-white'
                        }`}
                      >
                        {match.home_team.split(' ')[0] || 'Home'}
                      </button>
                      <button
                        type="button"
                        onClick={() => setPassLocTeam('away')}
                        className={`px-2 py-0.5 rounded text-[10px] font-bold transition ${
                          passLocTeam === 'away' ? 'bg-[#2979FF]/20 text-[#2979FF] border border-[#2979FF]/40' : 'bg-[#181818] text-gray-400 hover:text-white'
                        }`}
                      >
                        {match.away_team.split(' ')[0] || 'Away'}
                      </button>
                    </div>
                    <ThirdsBar
                      label="Passes"
                      data={passLocTeam === 'home' ? analytics.pass_locations?.home : analytics.pass_locations?.away}
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
                  <div id="analytics-section-possession-location" className="px-3 pb-3 space-y-2">
                    {/* Team toggle */}
                    <div className="flex items-center space-x-1">
                      <button
                        type="button"
                        onClick={() => setPossLocTeam('home')}
                        className={`px-2 py-0.5 rounded text-[10px] font-bold transition ${
                          possLocTeam === 'home' ? 'bg-[#FFD700]/20 text-[#FFD700] border border-[#FFD700]/40' : 'bg-[#181818] text-gray-400 hover:text-white'
                        }`}
                      >
                        {match.home_team.split(' ')[0] || 'Home'}
                      </button>
                      <button
                        type="button"
                        onClick={() => setPossLocTeam('away')}
                        className={`px-2 py-0.5 rounded text-[10px] font-bold transition ${
                          possLocTeam === 'away' ? 'bg-[#2979FF]/20 text-[#2979FF] border border-[#2979FF]/40' : 'bg-[#181818] text-gray-400 hover:text-white'
                        }`}
                      >
                        {match.away_team.split(' ')[0] || 'Away'}
                      </button>
                    </div>
                    <ThirdsBar
                      label="Possession"
                      data={possLocTeam === 'home' ? analytics.possession_locations?.home : analytics.possession_locations?.away}
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
                  <div id="analytics-section-pass-strings" className="px-3 pb-3 space-y-2">
                    {/* Team toggle */}
                    <div className="flex items-center space-x-1">
                      <button
                        type="button"
                        onClick={() => setPassStringsTeam('home')}
                        className={`px-2 py-0.5 rounded text-[10px] font-bold transition ${
                          passStringsTeam === 'home' ? 'bg-[#FFD700]/20 text-[#FFD700] border border-[#FFD700]/40' : 'bg-[#181818] text-gray-400 hover:text-white'
                        }`}
                      >
                        {match.home_team.split(' ')[0] || 'Home'}
                      </button>
                      <button
                        type="button"
                        onClick={() => setPassStringsTeam('away')}
                        className={`px-2 py-0.5 rounded text-[10px] font-bold transition ${
                          passStringsTeam === 'away' ? 'bg-[#2979FF]/20 text-[#2979FF] border border-[#2979FF]/40' : 'bg-[#181818] text-gray-400 hover:text-white'
                        }`}
                      >
                        {match.away_team.split(' ')[0] || 'Away'}
                      </button>
                    </div>

                    {(() => {
                      const strings = passStringsTeam === 'home' ? analytics.pass_strings.home : analytics.pass_strings.away;
                      if (!strings || strings.length === 0) {
                        return <Unavailable reason="No pass-sequencing detection exists in this pipeline, so there is no pass-string distribution to show." />;
                      }
                      const count3to5 = (strings[0] ?? 0) + (strings[1] ?? 0) + (strings[2] ?? 0);
                      const count6plus = strings.slice(3).reduce((acc, v) => acc + v, 0);
                      let longest = 0;
                      for (let i = strings.length - 1; i >= 0; i--) {
                        if (strings[i] > 0) {
                          longest = i + 3;
                          break;
                        }
                      }
                      return (
                        <div className="space-y-2.5">
                          {/* Summary containers */}
                          <div className="grid grid-cols-3 gap-1.5 text-center">
                            <div className="bg-[#181c25] rounded p-1 border border-[#222836]">
                              <div className="text-[9px] text-gray-400">3 to 5 passes</div>
                              <div className="text-xs font-bold text-[#00E676]">{count3to5}</div>
                            </div>
                            <div className="bg-[#181c25] rounded p-1 border border-[#222836]">
                              <div className="text-[9px] text-gray-400">6+ passes</div>
                              <div className="text-xs font-bold text-white">{count6plus}</div>
                            </div>
                            <div className="bg-[#181c25] rounded p-1 border border-[#222836]">
                              <div className="text-[9px] text-gray-400">Longest string</div>
                              <div className="text-xs font-bold text-[#FFD700]">{longest}</div>
                            </div>
                          </div>
                          {/* Histogram chart */}
                          <div className="flex items-end space-x-2 h-16 pt-2">
                            {strings.map((val, idx) => (
                              <div key={idx} className="flex-1 flex flex-col items-center">
                                <div
                                  style={{ height: `${Math.max(10, val * 5)}%` }}
                                  className="w-full bg-[#00E676] rounded-t hover:bg-[#00c968] transition"
                                />
                                <span className="text-[9px] text-gray-400 mt-1">{idx === 7 ? '+10' : idx + 3}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      );
                    })()}
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
                  className="flex items-center space-x-1 text-xs text-[#00E676] hover:underline"
                >
                  <ArrowLeft className="w-3 h-3" />
                  <span>All Players</span>
                </button>
              )}
            </div>

            {selectedJersey ? (
              /* Selected Player View */
              <div className="space-y-3 animate-in fade-in duration-150">
                {(() => {
                  const player = match.lineup.find(p => p.jersey === selectedJersey);
                  const moments = getPlayerMoments(selectedJersey);
                  const displayName = player?.name || `Player ${selectedJersey}`;

                  return (
                    <>
                      {/* Player Banner */}
                      <div className="bg-[#14261c] border border-[#00E676]/40 rounded-xl p-3 flex items-center justify-between">
                        <div className="flex items-center space-x-3">
                          <div className="w-10 h-10 rounded-full bg-[#00E676] text-black font-extrabold text-sm flex items-center justify-center shadow-lg">
                            {selectedJersey}
                          </div>
                          <div>
                            <div className="text-xs font-bold text-white">{displayName}</div>
                            <div className="text-[10px] text-gray-300">
                              {player?.position || 'Player'} • {player?.minutes_played != null ? `${player.minutes_played} mins played` : '— mins played'}
                            </div>
                          </div>
                        </div>
                        <span className="text-xs font-bold text-[#00E676] bg-[#00E676]/10 px-2 py-1 rounded-md border border-[#00E676]/20">
                          {moments.length} moments
                        </span>
                      </div>

                      {/* Moments Timeline List */}
                      <div className="text-[11px] font-bold text-gray-400 uppercase tracking-wider px-1">
                        Timeline Moments
                      </div>

                      {moments.length === 0 ? (
                        <div className="p-6 text-center text-xs text-gray-500 bg-[#12141a] rounded-xl border border-[#1e222d]">
                          No detected moments for #{selectedJersey}
                        </div>
                      ) : (
                        <div className="space-y-2">
                          {moments.map(m => (
                            <div
                              key={m.id}
                              onClick={() => onSeek(m.timestamp)}
                              className="p-2.5 bg-[#12141a] hover:bg-[#181c25] border border-[#1e222d] hover:border-[#00E676]/40 rounded-xl cursor-pointer transition flex items-center justify-between group"
                            >
                              <div className="flex items-center space-x-2.5 min-w-0 pr-2">
                                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded font-bold text-[#00E676] bg-[#00E676]/10 shrink-0">
                                  {formatTime(m.timestamp)}
                                </span>
                                <div className="min-w-0">
                                  <div className="text-xs font-semibold text-white group-hover:text-[#00E676] transition truncate">
                                    {m.title}
                                  </div>
                                  <div className="text-[10px] text-gray-400 flex items-center space-x-1.5 mt-0.5">
                                    <span className="capitalize">{m.event_type}</span>
                                    {m.tags && m.tags.length > 0 && (
                                      <>
                                        <span>•</span>
                                        <span className="truncate">{m.tags.join(', ')}</span>
                                      </>
                                    )}
                                  </div>
                                </div>
                              </div>
                              <Play className="w-3.5 h-3.5 text-gray-400 group-hover:text-[#00E676] group-hover:scale-110 transition shrink-0" />
                            </div>
                          ))}
                        </div>
                      )}
                    </>
                  );
                })()}
              </div>
            ) : (
              /* All Players Roster List */
              <div className="space-y-2">
                {match.lineup.map(player => {
                  const momentsCount = getPlayerMoments(player.jersey).length;
                  return (
                    <div
                      key={player.jersey}
                      onClick={() => onSelectJersey(player.jersey)}
                      className="p-2.5 border rounded-xl cursor-pointer transition flex items-center justify-between bg-[#12141a] hover:bg-[#181c25] border-[#1e222d] hover:border-[#00E676]/30"
                    >
                      <div className="flex items-center space-x-2.5">
                        <span className="w-7 h-7 rounded-full bg-[#1f2430] text-[#00E676] font-bold text-xs flex items-center justify-center border border-[#2a2a2a]">
                          {player.jersey}
                        </span>
                        <div>
                          <div className="text-xs font-bold text-white">{player.name}</div>
                          <div className="text-[10px] text-gray-400">{player.position} • {player.minutes_played == null ? '—' : player.minutes_played} mins played</div>
                        </div>
                      </div>
                      <span className="text-[10px] text-[#00E676] font-semibold bg-[#00E676]/10 px-2 py-0.5 rounded">
                        {momentsCount} moments
                      </span>
                    </div>
                  );
                })}
              </div>
            )}
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
