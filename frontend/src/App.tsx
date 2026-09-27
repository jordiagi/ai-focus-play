import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Match, Highlight, Event, Drawing, RadarFrame, AnalyticsData, DetectionFrame, Team } from './types';
import { api, ApiError } from './services/api';
import { Header } from './components/Header';
import { BurgerMenu } from './components/BurgerMenu';
import { VideoPlayer, PlayerHandle } from './components/VideoPlayer/VideoPlayer';
import { PlayerMomentsBar } from './components/PlayerMomentsBar';
import { RightToolbar, ActiveDrawerType } from './components/Sidebar/RightToolbar';
import { SidebarDrawer } from './components/Sidebar/SidebarTabs';
import { UploadModal } from './components/UploadModal';
import { SocialShareModal } from './components/SocialShareModal';
import { HelpShortcutsModal } from './components/HelpShortcutsModal';
import { Loader2, AlertTriangle, X } from 'lucide-react';

const DRAWER_ROUTES: Record<Exclude<ActiveDrawerType, null>, string> = {
  analytics: '#/analysis/',
  players: '#/player-moments/',
  highlights: '#/highlights/',
  events: '#/events/',
  lineup: '#/lineup/',
  summary: '#/summary/',
};

const getDrawerFromHash = (): ActiveDrawerType => {
  const route = Object.entries(DRAWER_ROUTES).find(([, hash]) => hash === window.location.hash);
  return route ? route[0] as Exclude<ActiveDrawerType, null> : null;
};

export const App: React.FC = () => {
  const playerRef = useRef<PlayerHandle>(null);
  const abortControllerRef = useRef<AbortController | null>(null);

  const [matches, setMatches] = useState<Match[]>([]);
  const [currentMatch, setCurrentMatch] = useState<Match | null>(null);
  const [teams, setTeams] = useState<Team[]>([]);
  const [selectedTeam, setSelectedTeam] = useState<Team | null>(null);
  const [highlights, setHighlights] = useState<Highlight[]>([]);
  const [events, setEvents] = useState<Event[]>([]);
  const [drawings, setDrawings] = useState<Drawing[]>([]);
  const [radarFrames, setRadarFrames] = useState<RadarFrame[]>([]);
  const [detectionFrames, setDetectionFrames] = useState<DetectionFrame[]>([]);
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);

  const [currentTime, setCurrentTime] = useState(0);
  const [selectedJersey, setSelectedJersey] = useState<string | null>(null);
  const [isBurgerOpen, setIsBurgerOpen] = useState(false);
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [isSocialShareOpen, setIsSocialShareOpen] = useState(false);
  const [isHelpOpen, setIsHelpOpen] = useState(false);
  const [activeDrawer, setActiveDrawer] = useState<ActiveDrawerType>(getDrawerFromHash);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Global keyboard shortcut to open Help & Shortcuts modal on '?'
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)) {
        return;
      }
      if (e.key === '?') {
        setIsHelpOpen(prev => !prev);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const selectMatch = useCallback(async (match: Match) => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    setCurrentMatch(match);
    setSelectedJersey(null);
    setCurrentTime(0);

    // Sync match param into browser query string without reloading
    try {
      const url = new URL(window.location.href);
      url.searchParams.set('match', match.id);
      window.history.replaceState(null, '', url.toString());
    } catch {
      // Ignore in non-browser test environments
    }

    try {
      const [h, e, d, r, a, dets] = await Promise.all([
        api.getHighlights(match.id, controller.signal),
        api.getEvents(match.id, controller.signal),
        api.getDrawings(match.id, controller.signal),
        api.getRadarFrames(match.id, undefined, controller.signal),
        api.getAnalytics(match.id, controller.signal),
        api.getDetections(match.id, undefined, controller.signal).catch(() => ({ match_id: match.id, frames_count: 0, detections: [] })),
      ]);

      if (!controller.signal.aborted) {
        setHighlights(h);
        setEvents(e);
        setDrawings(d);
        setRadarFrames(r);
        setAnalytics(a);
        setDetectionFrames(dets?.detections || []);
      }
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        console.error('Error fetching match details:', err);
      }
    }
  }, []);

  const loadTeams = useCallback(async () => {
    try {
      const data = await api.listTeams();
      setTeams(data);
      if (data.length > 0) {
        setSelectedTeam(prev => prev ?? data[0]);
      }
    } catch (err) {
      console.warn('Failed to load teams:', err);
    }
  }, []);

  const handleCreateTeam = async (name: string, clubName?: string, federationUrl?: string) => {
    try {
      const created = await api.createTeam(name, clubName, federationUrl);
      setTeams(prev => [...prev, created]);
      setSelectedTeam(created);
      return created;
    } catch (err: any) {
      console.error('Failed to create team:', err);
      throw err;
    }
  };

  const handleUpdateTeam = async (teamId: string, data: { name?: string; club_name?: string; federation_url?: string }) => {
    try {
      const updated = await api.updateTeam(teamId, data);
      setTeams(prev => prev.map(t => t.id === teamId ? updated : t));
      if (selectedTeam?.id === teamId) {
        setSelectedTeam(updated);
      }
      return updated;
    } catch (err: any) {
      console.error('Failed to update team:', err);
      throw err;
    }
  };

  const handleDeleteTeam = async (teamId: string) => {
    try {
      await api.deleteTeam(teamId);
      setTeams(prev => {
        const remaining = prev.filter(t => t.id !== teamId);
        if (selectedTeam?.id === teamId) {
          setSelectedTeam(remaining[0] || null);
        }
        return remaining;
      });
      const updatedMatches = await api.listMatches();
      setMatches(updatedMatches);
    } catch (err: any) {
      console.error('Failed to delete team:', err);
      throw err;
    }
  };

  const loadMatches = useCallback(async () => {
    try {
      setLoading(true);
      setErrorMessage(null);
      const data = await api.listMatches();
      setMatches(data);
      if (data.length > 0) {
        const sharedMatchId = new URLSearchParams(window.location.search).get('match');
        selectMatch(data.find(match => match.id === sharedMatchId) ?? data[0]);
      }
    } catch (err) {
      console.error('Failed to load matches:', err);
      const msg = err instanceof ApiError ? err.message : 'Failed to connect to backend';
      setErrorMessage(msg);
    } finally {
      setLoading(false);
    }
  }, [selectMatch]);

  // Load initial matches and teams from SQLite
  useEffect(() => {
    loadMatches();
    loadTeams();
  }, [loadMatches, loadTeams]);

  useEffect(() => {
    const syncDrawerWithHash = () => setActiveDrawer(getDrawerFromHash());
    window.addEventListener('hashchange', syncDrawerWithHash);
    return () => window.removeEventListener('hashchange', syncDrawerWithHash);
  }, []);

  const navigateToDrawer = useCallback((drawer: ActiveDrawerType) => {
    const nextHash = drawer ? DRAWER_ROUTES[drawer] : '';
    if (window.location.hash === nextHash) return;
    window.location.hash = nextHash;
  }, []);

  // Poll for progress when match is processing
  useEffect(() => {
    if (!currentMatch || currentMatch.status !== 'processing') return;

    const interval = setInterval(async () => {
      try {
        const progress = await api.getMatchProgress(currentMatch.id);
        if (progress.status === 'ready' || progress.status === 'error') {
          clearInterval(interval);
          const updated = await api.getMatch(currentMatch.id);
          selectMatch(updated);
        } else {
          setCurrentMatch(prev => prev ? {
            ...prev,
            processing_step: progress.step,
            processing_progress: progress.progress,
            status: progress.status as any
          } : null);
        }
      } catch (err) {
        console.warn('Progress poll error:', err);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [currentMatch, selectMatch]);

  const handleSaveDrawing = async (drawing: Omit<Drawing, 'id'>) => {
    if (!currentMatch) return;
    try {
      const saved = await api.saveDrawing(currentMatch.id, drawing);
      setDrawings(prev => [...prev, saved]);
    } catch (err) {
      console.error('Failed to save drawing:', err);
    }
  };

  const handleSelectJersey = (jersey: string | null) => {
    setSelectedJersey(jersey);
    if (jersey) {
      navigateToDrawer('players');
    }
  };

  const handleSwapTeams = async () => {
    if (!currentMatch) return;
    try {
      await api.swapTeams(currentMatch.id);
      const updated = await api.getMatch(currentMatch.id);
      selectMatch(updated);
    } catch (err) {
      console.error('Failed to swap teams:', err);
    }
  };

  const handleDeleteMatch = async (matchId: string) => {
    try {
      await api.deleteMatch(matchId);
      setMatches(prev => {
        const remaining = prev.filter(m => m.id !== matchId);
        // If we deleted the currently active match, switch to another
        if (currentMatch?.id === matchId && remaining.length > 0) {
          selectMatch(remaining[0]);
        }
        return remaining;
      });
    } catch (err) {
      console.error('Failed to delete match:', err);
    }
  };

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-[#000000] text-white">
      {/* 1. Exact Sea Header with Match Switcher */}
      <Header
        currentMatch={currentMatch}
        matches={matches}
        onSelectMatch={selectMatch}
        onOpenBurgerMenu={() => setIsBurgerOpen(true)}
        onOpenUpload={() => setIsUploadOpen(true)}
        onOpenSocialShare={() => setIsSocialShareOpen(true)}
        onDeleteMatch={handleDeleteMatch}
        canUpload={true}
      />

      {/* Error Toast if present */}
      {errorMessage && (
        <div className="bg-red-950/90 border border-red-800 text-red-200 px-4 py-2 flex items-center justify-between text-xs z-50">
          <div className="flex items-center space-x-2">
            <AlertTriangle className="w-4 h-4 text-red-400" />
            <span>{errorMessage}</span>
          </div>
          <button onClick={() => setErrorMessage(null)} className="p-1 hover:text-white">
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* 2. Slide-Over Burger Menu with Teams Integration */}
      <BurgerMenu
        isOpen={isBurgerOpen}
        onClose={() => setIsBurgerOpen(false)}
        matches={matches}
        currentMatch={currentMatch}
        onSelectMatch={selectMatch}
        onOpenAnalytics={() => navigateToDrawer('analytics')}
        onOpenPlayerMoments={() => navigateToDrawer('players')}
        teams={teams}
        selectedTeam={selectedTeam}
        onSelectTeam={setSelectedTeam}
        onCreateTeam={handleCreateTeam}
        onUpdateTeam={handleUpdateTeam}
        onDeleteTeam={handleDeleteTeam}
        onOpenUpload={(targetTeam) => {
          if (targetTeam) setSelectedTeam(targetTeam);
          setIsUploadOpen(true);
        }}
      />

      {/* 3. Upload Modal */}
      <UploadModal
        isOpen={isUploadOpen}
        onClose={() => setIsUploadOpen(false)}
        teams={teams}
        selectedTeam={selectedTeam}
        onMatchUploaded={(newMatch) => {
          setIsUploadOpen(false);
          setMatches(prev => [newMatch, ...prev]);
          selectMatch(newMatch);
          loadTeams();
        }}
      />

      {/* 3b. Social Share Modal */}
      <SocialShareModal
        isOpen={isSocialShareOpen}
        onClose={() => setIsSocialShareOpen(false)}
        match={currentMatch}
      />

      {/* 3c. Help & Shortcuts Modal */}
      <HelpShortcutsModal
        isOpen={isHelpOpen}
        onClose={() => setIsHelpOpen(false)}
      />

      {/* 4. Main Workspace Split Layout */}
      {loading ? (
        <div className="flex-1 flex items-center justify-center space-x-2 text-gray-400">
          <Loader2 className="w-5 h-5 animate-spin text-[#00E676]" />
          <span className="text-sm font-medium">Loading Sea Video Analysis...</span>
        </div>
      ) : currentMatch ? (
        <div className="flex-1 flex overflow-hidden">
          {/* Center Stage: Match Video Player & Player Moments Pill */}
          <div className="flex-1 flex flex-col h-full overflow-hidden bg-[#000000]">
            {/* Processing banner if uploaded video is analyzing */}
            {currentMatch.status === 'processing' && (
              <div className="bg-[#121620] border-b border-[#1f283d] px-4 py-2 flex items-center justify-between text-xs text-gray-300">
                <div className="flex items-center space-x-2">
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-[#00E676]" />
                  <span>{currentMatch.processing_step || 'Analyzing match footage...'}</span>
                </div>
                <div className="flex items-center space-x-2">
                  <div className="w-32 bg-[#1b2336] h-1.5 rounded-full overflow-hidden">
                    <div 
                      className="bg-[#00E676] h-full transition-all duration-300"
                      style={{ width: `${currentMatch.processing_progress || 10}%` }}
                    />
                  </div>
                  <span className="font-mono text-[10px] text-gray-400">{Math.round(currentMatch.processing_progress || 10)}%</span>
                </div>
              </div>
            )}

            {/* Video Player */}
            <div className="flex-1 relative flex flex-col min-h-0">
              <VideoPlayer
                key={currentMatch.id}
                ref={playerRef}
                match={currentMatch}
                highlights={highlights}
                events={events}
                drawings={drawings}
                radarFrames={radarFrames}
                detectionFrames={detectionFrames}
                selectedJersey={selectedJersey}
                onSelectJersey={handleSelectJersey}
                onSaveDrawing={handleSaveDrawing}
                onTimeUpdate={setCurrentTime}
              />
            </div>

            {/* Exact Player Moments Pill Bar below Video */}
            <PlayerMomentsBar
              lineup={currentMatch.lineup}
              selectedJersey={selectedJersey}
              onSelectJersey={handleSelectJersey}
            />
          </div>

          {/* Expandable Right Drawer */}
          <SidebarDrawer
            activeTab={activeDrawer}
            onClose={() => navigateToDrawer(null)}
            match={currentMatch}
            highlights={highlights}
            events={events}
            analytics={analytics}
            currentTime={currentTime}
            onSeek={(time) => {
              playerRef.current?.seekTo(time);
            }}
            onPlayAllHighlights={() => {
              if (highlights.length > 0) {
                playerRef.current?.playHighlightReel(highlights);
              }
            }}
            onSwapTeams={handleSwapTeams}
            selectedJersey={selectedJersey}
            onSelectJersey={handleSelectJersey}
          />

          {/* Right Vertical Tool Rail */}
          <RightToolbar
            activeDrawer={activeDrawer}
            onToggleDrawer={navigateToDrawer}
            onOpenHelp={() => setIsHelpOpen(true)}
          />
        </div>
      ) : null}
    </div>
  );
};

export default App;
