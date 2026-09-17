import React, { useState, useEffect } from 'react';
import { Match, Highlight, Event, Drawing, RadarFrame, AnalyticsData } from './types';
import { api } from './services/api';
import { Header } from './components/Header';
import { BurgerMenu } from './components/BurgerMenu';
import { VideoPlayer } from './components/VideoPlayer/VideoPlayer';
import { PlayerMomentsBar } from './components/PlayerMomentsBar';
import { RightToolbar, ActiveDrawerType } from './components/Sidebar/RightToolbar';
import { SidebarDrawer } from './components/Sidebar/SidebarTabs';
import { Loader2 } from 'lucide-react';

export const App: React.FC = () => {
  const [matches, setMatches] = useState<Match[]>([]);
  const [currentMatch, setCurrentMatch] = useState<Match | null>(null);
  const [highlights, setHighlights] = useState<Highlight[]>([]);
  const [events, setEvents] = useState<Event[]>([]);
  const [drawings, setDrawings] = useState<Drawing[]>([]);
  const [radarFrames, setRadarFrames] = useState<RadarFrame[]>([]);
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);

  const [currentTime, setCurrentTime] = useState(0);
  const [selectedJersey, setSelectedJersey] = useState<string | null>(null);
  const [isBurgerOpen, setIsBurgerOpen] = useState(false);
  const [activeDrawer, setActiveDrawer] = useState<ActiveDrawerType>(null);
  const [loading, setLoading] = useState(true);

  // Load initial matches from SQLite
  useEffect(() => {
    loadMatches();
  }, []);

  const loadMatches = async () => {
    try {
      setLoading(true);
      const data = await api.listMatches();
      setMatches(data);
      if (data.length > 0) {
        selectMatch(data[0]);
      }
    } catch (err) {
      console.error('Failed to load matches:', err);
    } finally {
      setLoading(false);
    }
  };

  const selectMatch = async (match: Match) => {
    setCurrentMatch(match);
    try {
      const [h, e, d, r, a] = await Promise.all([
        api.getHighlights(match.id),
        api.getEvents(match.id),
        api.getDrawings(match.id),
        api.getRadarFrames(match.id),
        api.getAnalytics(match.id),
      ]);
      setHighlights(h);
      setEvents(e);
      setDrawings(d);
      setRadarFrames(r);
      setAnalytics(a);
    } catch (err) {
      console.error('Error fetching match details:', err);
    }
  };

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
      setActiveDrawer('players');
    }
  };

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-[#000000] text-white">
      {/* 1. Exact Veo Header */}
      <Header
        currentMatch={currentMatch}
        onOpenBurgerMenu={() => setIsBurgerOpen(true)}
        onOpenUpload={() => alert('Read-Only Mode: Uploading or creating new match clips is disabled.')}
      />

      {/* 2. Slide-Over Burger Menu */}
      <BurgerMenu
        isOpen={isBurgerOpen}
        onClose={() => setIsBurgerOpen(false)}
        matches={matches}
        currentMatch={currentMatch}
        onSelectMatch={selectMatch}
        onOpenAnalytics={() => setActiveDrawer('analytics')}
        onOpenPlayerMoments={() => setActiveDrawer('players')}
      />

      {/* 3. Main Workspace Split Layout */}
      {loading ? (
        <div className="flex-1 flex items-center justify-center space-x-2 text-gray-400">
          <Loader2 className="w-5 h-5 animate-spin text-[#00E676]" />
          <span className="text-sm font-medium">Loading Veo Video Analysis...</span>
        </div>
      ) : currentMatch ? (
        <div className="flex-1 flex overflow-hidden">
          {/* Center Stage: Match Video Player & Player Moments Pill */}
          <div className="flex-1 flex flex-col h-full overflow-hidden bg-[#000000]">
            {/* Video Player */}
            <div className="flex-1 relative flex flex-col min-h-0">
              <VideoPlayer
                match={currentMatch}
                highlights={highlights}
                events={events}
                drawings={drawings}
                radarFrames={radarFrames}
                onSaveDrawing={handleSaveDrawing}
              />
            </div>

            {/* Exact Player Moments Pill Bar below Video */}
            <PlayerMomentsBar
              lineup={currentMatch.lineup}
              selectedJersey={selectedJersey}
              onSelectJersey={handleSelectJersey}
            />
          </div>

          {/* Expandable Right Drawer (opens when a tool rail icon is selected) */}
          <SidebarDrawer
            activeTab={activeDrawer}
            onClose={() => setActiveDrawer(null)}
            match={currentMatch}
            highlights={highlights}
            events={events}
            analytics={analytics}
            onSeek={(time) => {
              const v = document.querySelector('video');
              if (v) {
                v.currentTime = time;
                setCurrentTime(time);
              }
            }}
            onPlayAllHighlights={() => {
              if (highlights.length > 0) {
                const v = document.querySelector('video');
                if (v) {
                  v.currentTime = highlights[0].start_time;
                  v.play();
                }
              }
            }}
            selectedJersey={selectedJersey}
            onSelectJersey={handleSelectJersey}
          />

          {/* Right Vertical Tool Rail (matching real Veo toolbar) */}
          <RightToolbar
            activeDrawer={activeDrawer}
            onToggleDrawer={setActiveDrawer}
          />
        </div>
      ) : null}
    </div>
  );
};

export default App;
