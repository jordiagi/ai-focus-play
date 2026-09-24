import React, { useRef, useState, useEffect, useImperativeHandle, forwardRef, useCallback } from 'react';
import { 
  Play, Pause, RotateCcw, RotateCw, SkipBack, SkipForward, 
  Volume2, VolumeX, Maximize, Minimize, Compass, Camera, 
  Pencil, X, RefreshCw
} from 'lucide-react';
import confetti from 'canvas-confetti';
import { Match, Highlight, Event, Drawing, RadarFrame } from '../../types';
import { Timeline } from './Timeline';
import { TelestratorCanvas } from './TelestratorCanvas';
import { PitchRadar } from '../PitchRadar/PitchRadar';
import { useRadarFrame } from '../../hooks/useRadarFrame';

export interface PlayerHandle {
  seekTo: (time: number) => void;
  play: () => Promise<void>;
  pause: () => void;
  playHighlightReel: (highlights: Highlight[]) => void;
  stopHighlightReel: () => void;
}

interface VideoPlayerProps {
  match: Match;
  highlights: Highlight[];
  events: Event[];
  drawings: Drawing[];
  radarFrames: RadarFrame[];
  onSaveDrawing: (drawing: Omit<Drawing, 'id'>) => void;
  onTimeUpdate?: (time: number) => void;
  onDurationChange?: (duration: number) => void;
  onEnded?: () => void;
  selectedJersey?: string | null;
  onSelectJersey?: (jersey: string | null) => void;
}

export const VideoPlayer = forwardRef<PlayerHandle, VideoPlayerProps>(({
  match,
  highlights,
  events,
  drawings,
  radarFrames,
  onSaveDrawing,
  onTimeUpdate,
  onDurationChange,
  onEnded,
  selectedJersey,
  onSelectJersey,
}, ref) => {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(match.duration_seconds || 90);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [isMuted, setIsMuted] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isMatchEnded, setIsMatchEnded] = useState(false);

  // Modes: 'follow' (Broadcast Follow-Cam) vs 'interactive' (User Pan/Zoom)
  const [viewMode, setViewMode] = useState<'follow' | 'interactive'>('follow');
  const [isTelestratorOpen, setIsTelestratorOpen] = useState(false);
  const [isRadarVisible, setIsRadarVisible] = useState(true);

  // Highlight Reel Queue state (P0-4)
  const [reelQueue, setReelQueue] = useState<Highlight[] | null>(null);
  const [reelIndex, setReelIndex] = useState(0);
  const reelQueueRef = useRef<Highlight[] | null>(null);
  const reelIndexRef = useRef(0);

  // Pan & Zoom state for Interactive Mode (P3-3)
  const [panX, setPanX] = useState(0);
  const [panY, setPanY] = useState(0);
  const [zoomScale, setZoomScale] = useState(1);
  const [isPanning, setIsPanning] = useState(false);
  const [startPan, setStartPan] = useState({ x: 0, y: 0 });

  // Refs for throttling and stable keyboard listeners
  const lastSentTimeRef = useRef<number>(0);
  const currentTimeRef = useRef<number>(0);
  const isPlayingRef = useRef<boolean>(false);
  const highlightsRef = useRef<Highlight[]>(highlights);

  useEffect(() => {
    currentTimeRef.current = currentTime;
    isPlayingRef.current = isPlaying;
    highlightsRef.current = highlights;
  }, [currentTime, isPlaying, highlights]);

  // Goal celebration confetti ref (P0-5)
  const celebratedGoalsRef = useRef<Set<string>>(new Set());

  const stopHighlightReel = useCallback(() => {
    reelQueueRef.current = null;
    reelIndexRef.current = 0;
    setReelQueue(null);
    setReelIndex(0);
  }, []);


  // Derive dynamic 2-3 letter team abbreviations (P0-6)
  const abbr = (name: string) => {
    if (!name) return 'FC';
    const words = name.split(/\s+/).filter(Boolean);
    if (words.length >= 2) {
      return (words[0][0] + words[1][0]).toUpperCase();
    }
    return name.slice(0, 3).toUpperCase();
  };

  const homeAbbr = abbr(match.home_team);
  const awayAbbr = abbr(match.away_team);

  // Find nearest radar frame and recent history for trails (O(log N) binary search)
  const { currentFrame: currentRadarFrame, historyFrames: historyRadarFrames } = useRadarFrame(radarFrames, currentTime);

  // Goal celebration confetti - fires only ONCE per goal ID (P0-5)
  useEffect(() => {
    if (typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      return;
    }
    const goal = events.find(e => 
      e.event_type.toLowerCase() === 'goal' && 
      currentTime >= e.timestamp && 
      currentTime < e.timestamp + 0.8
    );
    if (goal && !celebratedGoalsRef.current.has(goal.id)) {
      celebratedGoalsRef.current.add(goal.id);
      confetti({
        particleCount: 100,
        spread: 70,
        origin: { y: 0.7 }
      });
    }
  }, [currentTime, events]);

  const seekTo = useCallback((time: number) => {
    if (!videoRef.current) return;
    const bounded = Math.max(0, Math.min(time, duration));
    videoRef.current.currentTime = bounded;
    setCurrentTime(bounded);
    setIsMatchEnded(false);
    lastSentTimeRef.current = bounded;
    onTimeUpdate?.(bounded);
  }, [duration, onTimeUpdate]);

  const play = useCallback(async () => {
    if (!videoRef.current) return;
    try {
      await videoRef.current.play();
      setIsPlaying(true);
      setIsMatchEnded(false);
    } catch (err) {
      console.warn('Playback prevented or failed:', err);
    }
  }, []);

  const pause = useCallback(() => {
    if (!videoRef.current) return;
    videoRef.current.pause();
    setIsPlaying(false);
  }, []);


  const playHighlightReel = useCallback((clips: Highlight[]) => {
    if (!clips || clips.length === 0) return;
    const sorted = [...clips].sort((a, b) => a.start_time - b.start_time);
    reelQueueRef.current = sorted;
    reelIndexRef.current = 0;
    setReelQueue(sorted);
    setReelIndex(0);
    seekTo(sorted[0].start_time);
    play();
  }, [seekTo, play]);

  // Imperative handle for parent component (P0-3)
  useImperativeHandle(ref, () => ({
    seekTo,
    play,
    pause,
    playHighlightReel,
    stopHighlightReel
  }), [seekTo, play, pause, playHighlightReel, stopHighlightReel]);

  const togglePlay = () => {
    if (isPlaying) {
      pause();
    } else {
      play();
    }
  };

  const handleTimeUpdate = () => {
    if (!videoRef.current) return;
    const t = videoRef.current.currentTime;
    setCurrentTime(t);

    // Reel Queue advancement (P0-4)
    if (reelQueueRef.current && reelQueueRef.current.length > 0) {
      const activeClip = reelQueueRef.current[reelIndexRef.current];
      if (activeClip && t >= activeClip.end_time) {
        const nextIdx = reelIndexRef.current + 1;
        if (nextIdx < reelQueueRef.current.length) {
          reelIndexRef.current = nextIdx;
          setReelIndex(nextIdx);
          seekTo(reelQueueRef.current[nextIdx].start_time);
          play();
        } else {
          // Finished all clips in reel
          pause();
          stopHighlightReel();
        }
      }
    }

    // Throttle emit to parent to 0.1s (P0-2)
    if (Math.abs(t - lastSentTimeRef.current) >= 0.1) {
      lastSentTimeRef.current = t;
      onTimeUpdate?.(t);
    }
  };

  const handleLoadedMetadata = () => {
    if (!videoRef.current) return;
    const dur = videoRef.current.duration || match.duration_seconds || 90;
    setDuration(dur);
    onDurationChange?.(dur);
  };

  const handleEnded = () => {
    setIsPlaying(false);
    setIsMatchEnded(true);
    stopHighlightReel();
    onEnded?.();
  };

  const seekRelative = useCallback((delta: number) => {
    stopHighlightReel();
    seekTo(currentTimeRef.current + delta);
  }, [seekTo, stopHighlightReel]);

  const jumpHighlight = useCallback((direction: number) => {
    stopHighlightReel();
    if (!highlightsRef.current.length) return;
    const sorted = [...highlightsRef.current].sort((a, b) => a.start_time - b.start_time);
    if (direction > 0) {
      const next = sorted.find(h => h.start_time > currentTimeRef.current + 1.0);
      if (next) seekTo(next.start_time);
    } else {
      const prev = [...sorted].reverse().find(h => h.start_time < currentTimeRef.current - 1.0);
      if (prev) seekTo(prev.start_time);
    }
  }, [seekTo, stopHighlightReel]);

  // Keyboard Shortcuts with stable references (P3-4)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      if (target && (target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.isContentEditable)) {
        return;
      }

      if (e.code === 'Space') {
        e.preventDefault();
        if (isPlayingRef.current) {
          videoRef.current?.pause();
          setIsPlaying(false);
        } else {
          videoRef.current?.play().catch(() => {});
          setIsPlaying(true);
        }
      } else if (e.code === 'KeyD') {
        e.preventDefault();
        setIsTelestratorOpen(prev => !prev);
      } else if (e.code === 'ArrowLeft' || e.code === 'KeyJ') {
        e.preventDefault();
        seekRelative(-10);
      } else if (e.code === 'ArrowRight' || e.code === 'KeyL') {
        e.preventDefault();
        seekRelative(10);
      } else if (e.code === 'BracketLeft') {
        jumpHighlight(-1);
      } else if (e.code === 'BracketRight') {
        jumpHighlight(1);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [seekRelative, jumpHighlight]);

  const changeSpeed = (rate: number) => {
    if (!videoRef.current) return;
    videoRef.current.playbackRate = rate;
    setPlaybackRate(rate);
  };

  const toggleMute = () => {
    if (!videoRef.current) return;
    videoRef.current.muted = !isMuted;
    setIsMuted(!isMuted);
  };

  const toggleFullscreen = () => {
    if (!containerRef.current) return;
    if (!document.fullscreenElement) {
      containerRef.current.requestFullscreen();
      setIsFullscreen(true);
    } else {
      document.exitFullscreen();
      setIsFullscreen(false);
    }
  };

  // Pan & Zoom Handlers for Interactive 180 Mode with clamping and pointer capture (P3-3)
  const handlePointerDown = (e: React.PointerEvent) => {
    if (viewMode !== 'interactive' || isTelestratorOpen) return;
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
    setIsPanning(true);
    setStartPan({ x: e.clientX - panX, y: e.clientY - panY });
  };

  const handlePointerMove = (e: React.PointerEvent) => {
    if (!isPanning || viewMode !== 'interactive' || isTelestratorOpen) return;
    // Bounded pan: clamp pan range based on current zoom
    const maxPan = 400 * (zoomScale - 1);
    const newX = Math.max(-maxPan, Math.min(maxPan, e.clientX - startPan.x));
    const newY = Math.max(-maxPan, Math.min(maxPan, e.clientY - startPan.y));
    setPanX(newX);
    setPanY(newY);
  };

  const handlePointerUp = (e: React.PointerEvent) => {
    if (isPanning) {
      try {
        (e.target as HTMLElement).releasePointerCapture(e.pointerId);
      } catch {
        // ignore
      }
      setIsPanning(false);
    }
  };

  // Wheel zoom via non-passive event listener
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const onWheel = (e: WheelEvent) => {
      if (viewMode !== 'interactive' || isTelestratorOpen) return;
      e.preventDefault();
      const zoomDelta = e.deltaY * -0.001;
      setZoomScale(prev => Math.min(3.0, Math.max(1.0, prev + zoomDelta)));
    };

    container.addEventListener('wheel', onWheel, { passive: false });
    return () => container.removeEventListener('wheel', onWheel);
  }, [viewMode, isTelestratorOpen]);

  const resetPanZoom = () => {
    setPanX(0);
    setPanY(0);
    setZoomScale(1);
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  return (
    <div
      ref={containerRef}
      className="relative flex-1 bg-[#000000] flex flex-col justify-between overflow-hidden select-none p-2 md:p-3"
    >
      {/* Centered Main Video Wrapper with rounded corners */}
      <div 
        className="relative flex-1 w-full h-full bg-[#050505] rounded-2xl overflow-hidden border border-[#161616] flex items-center justify-center cursor-grab active:cursor-grabbing shadow-2xl"
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onPointerCancel={handlePointerUp}
        onClick={() => {
          if (!isTelestratorOpen && viewMode === 'follow') togglePlay();
        }}
      >
        {/* Real Veo Scoreboard Pill (Dynamic team abbreviations) (P0-6) */}
        <div className="absolute top-4 left-4 z-20 pointer-events-auto flex items-center space-x-2.5">
          <div 
            className="bg-black/80 backdrop-blur-md border border-[#2a2a2a] px-3 py-1.5 rounded-lg flex items-center space-x-2 text-xs font-bold text-white shadow-xl"
            title={`${match.home_team} vs. ${match.away_team}`}
          >
            <span className="text-[#FFD700] tracking-wider">{homeAbbr}</span>
            <span className="bg-[#1f2430] px-1.5 py-0.5 rounded text-white">{match.home_score}</span>
            <span className="text-gray-500 font-normal">-</span>
            <span className="bg-[#1f2430] px-1.5 py-0.5 rounded text-white">{match.away_score}</span>
            <span className="text-[#2979FF] tracking-wider">{awayAbbr}</span>
          </div>
          <div className="bg-black/80 backdrop-blur-md border border-[#2a2a2a] px-2.5 py-1.5 rounded-lg text-xs font-mono font-bold text-[#00E676] shadow-xl">
            {formatTime(currentTime)}
          </div>
        </div>

        {/* Highlight Reel Active Banner (P0-4) */}
        {reelQueue && (
          <div className="absolute top-4 left-1/2 -translate-x-1/2 z-30 pointer-events-auto bg-[#00E676] text-black px-3.5 py-1.5 rounded-full text-xs font-bold flex items-center space-x-2.5 shadow-2xl animate-pulse">
            <span>
              Clip {reelIndex + 1} / {reelQueue.length} — {reelQueue[reelIndex]?.title}
            </span>
            <button
              onClick={(e) => {
                e.stopPropagation();
                stopHighlightReel();
              }}
              className="bg-black text-white hover:bg-gray-800 p-0.5 rounded-full"
              title="Stop highlight reel"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {/* Top-Right Mode Switchers, Reset View & Telestrator Button */}
        <div className="absolute top-4 right-4 z-20 pointer-events-auto flex items-center space-x-2">
          {(zoomScale > 1 || panX !== 0 || panY !== 0) && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                resetPanZoom();
              }}
              className="bg-black/80 backdrop-blur-md border border-[#2a2a2a] text-gray-200 hover:text-white px-2.5 py-1.5 rounded-lg text-xs font-semibold flex items-center space-x-1 shadow-xl"
              title="Reset pan and zoom"
            >
              <RefreshCw className="w-3.5 h-3.5" />
              <span>Reset</span>
            </button>
          )}

          <div className="bg-black/80 backdrop-blur-md border border-[#2a2a2a] p-0.5 rounded-lg flex items-center shadow-xl">
            <button
              onClick={(e) => {
                e.stopPropagation();
                setViewMode('follow');
                resetPanZoom();
              }}
              className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-md text-xs font-semibold transition ${
                viewMode === 'follow' ? 'bg-[#00E676] text-black' : 'text-gray-300 hover:text-white'
              }`}
            >
              <Camera className="w-3.5 h-3.5" />
              <span>Follow-Cam</span>
            </button>
            <button
              onClick={(e) => {
                e.stopPropagation();
                setViewMode('interactive');
              }}
              className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-md text-xs font-semibold transition ${
                viewMode === 'interactive' ? 'bg-[#00E676] text-black' : 'text-gray-300 hover:text-white'
              }`}
              title="Drag to pan, scroll to zoom"
            >
              <Compass className="w-3.5 h-3.5" />
              <span>Pan & Zoom</span>
            </button>
          </div>

          <button
            onClick={(e) => {
              e.stopPropagation();
              if (isPlaying) pause();
              setIsTelestratorOpen(!isTelestratorOpen);
            }}
            className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition shadow-xl ${
              isTelestratorOpen 
                ? 'bg-[#00E676] text-black border-[#00E676]' 
                : 'bg-black/80 backdrop-blur-md text-gray-200 border-[#2a2a2a] hover:bg-[#1f2430]'
            }`}
            title="Telestrator drawing (Hotkey D)"
          >
            <Pencil className="w-3.5 h-3.5" />
            <span>Draw (D)</span>
          </button>
        </div>

        {/* HTML5 Video Element - NO loop attribute (P0-7) */}
        <video
          ref={videoRef}
          src={match.video_url}
          onTimeUpdate={handleTimeUpdate}
          onLoadedMetadata={handleLoadedMetadata}
          onPlay={() => setIsPlaying(true)}
          onPause={() => setIsPlaying(false)}
          onEnded={handleEnded}
          playsInline
          className={`w-full h-full object-contain pointer-events-none ${isPanning ? '' : 'transition-transform duration-75 ease-out'}`}
          style={{
            transform: `translate(${panX}px, ${panY}px) scale(${zoomScale})`,
          }}
        />

        {/* Match Ended Overlay (P0-7) */}
        {isMatchEnded && (
          <div className="absolute inset-0 bg-black/85 backdrop-blur-md flex flex-col items-center justify-center z-25 pointer-events-auto">
            <h2 className="text-xl font-bold text-white mb-2">Match Finished</h2>
            <p className="text-sm text-gray-400 mb-6">Final whistle reached at {formatTime(duration)}</p>
            <div className="flex items-center space-x-3">
              <button
                onClick={() => {
                  seekTo(0);
                  play();
                }}
                className="px-4 py-2 bg-[#00E676] text-black font-bold rounded-lg hover:bg-[#00c864] transition flex items-center space-x-2 text-sm shadow-xl"
              >
                <RotateCcw className="w-4 h-4" />
                <span>Replay Match</span>
              </button>
              {highlights.length > 0 && (
                <button
                  onClick={() => {
                    playHighlightReel(highlights);
                  }}
                  className="px-4 py-2 bg-[#1f2430] border border-[#2a2a2a] text-white font-semibold rounded-lg hover:bg-[#2c3444] transition flex items-center space-x-2 text-sm shadow-xl"
                >
                  <SkipForward className="w-4 h-4" />
                  <span>Play Highlights Reel</span>
                </button>
              )}
            </div>
          </div>
        )}

        {/* Telestrator Drawing Layer */}
        {isTelestratorOpen && (
          <TelestratorCanvas
            matchId={match.id}
            currentTime={currentTime}
            existingDrawings={drawings}
            videoElement={videoRef.current}
            onSaveDrawing={onSaveDrawing}
            onClose={() => setIsTelestratorOpen(false)}
          />
        )}

        {/* Top-Right 2D Pitch Radar Overlay */}
        {isRadarVisible && (
          <div className="absolute top-16 right-4 w-64 z-20 shadow-2xl pointer-events-auto">
            <PitchRadar
              currentFrame={currentRadarFrame}
              historyFrames={historyRadarFrames}
              isFloating={true}
              onToggleFloating={() => setIsRadarVisible(false)}
            />
          </div>
        )}

        {/* Play indicator on pause */}
        {!isPlaying && !isTelestratorOpen && !isMatchEnded && (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div className="w-16 h-16 rounded-full bg-black/60 backdrop-blur border border-white/20 flex items-center justify-center text-white shadow-2xl">
              <Play className="w-8 h-8 fill-white ml-1" />
            </div>
          </div>
        )}
      </div>

      {/* ================= BOTTOM CONTROLS & TIMELINE ================= */}
      <div className="pt-2 flex flex-col space-y-2 z-20">
        <Timeline
          currentTime={currentTime}
          duration={duration}
          highlights={highlights}
          events={events}
          selectedJersey={selectedJersey}
          onSelectJersey={onSelectJersey}
          onSeek={(t) => {
            stopHighlightReel();
            seekTo(t);
          }}
        />

        {/* Control Buttons */}
        <div className="flex items-center justify-between text-xs text-gray-300 px-1">
          <div className="flex items-center space-x-2">
            <button
              onClick={togglePlay}
              className="p-2 bg-[#181818] hover:bg-[#252525] rounded-full text-white transition focus-visible:ring-2 focus-visible:ring-[#00E676]"
              title={isPlaying ? 'Pause (Space)' : 'Play (Space)'}
              aria-label={isPlaying ? 'Pause video' : 'Play video'}
            >
              {isPlaying ? <Pause className="w-4 h-4 fill-white" /> : <Play className="w-4 h-4 fill-white ml-0.5" />}
            </button>

            <button
              onClick={() => seekRelative(-10)}
              className="p-1.5 hover:text-[#00E676] transition"
              title="Skip -10s (J)"
              aria-label="Skip backwards 10 seconds"
            >
              <RotateCcw className="w-4 h-4" />
            </button>
            <button
              onClick={() => seekRelative(10)}
              className="p-1.5 hover:text-[#00E676] transition"
              title="Skip +10s (L)"
              aria-label="Skip forward 10 seconds"
            >
              <RotateCw className="w-4 h-4" />
            </button>

            <button
              onClick={() => jumpHighlight(-1)}
              className="p-1.5 hover:text-[#00E676] transition"
              title="Previous Highlight ([)"
              aria-label="Previous highlight"
            >
              <SkipBack className="w-4 h-4" />
            </button>
            <button
              onClick={() => jumpHighlight(1)}
              className="p-1.5 hover:text-[#00E676] transition"
              title="Next Highlight (])"
              aria-label="Next highlight"
            >
              <SkipForward className="w-4 h-4" />
            </button>

            <button 
              onClick={toggleMute} 
              className="p-1.5 hover:text-white transition"
              title={isMuted ? "Unmute" : "Mute"}
              aria-label={isMuted ? "Unmute audio" : "Mute audio"}
            >
              {isMuted ? <VolumeX className="w-4 h-4 text-red-400" /> : <Volume2 className="w-4 h-4" />}
            </button>

            <span className="font-mono text-xs text-gray-400 ml-2">
              {formatTime(currentTime)} / {formatTime(duration)}
            </span>
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={() => setIsTelestratorOpen(!isTelestratorOpen)}
              className={`px-2.5 py-1 rounded border text-xs font-semibold transition flex items-center space-x-1 ${
                isTelestratorOpen ? 'bg-[#00E676] text-black border-[#00E676]' : 'bg-[#141414] text-gray-300 border-[#222] hover:border-gray-500'
              }`}
              title="Toggle Telestrator / Drawing (Hotkey D)"
              aria-label="Toggle Telestrator drawing tools"
            >
              <Pencil className="w-3.5 h-3.5" />
              <span>Draw</span>
            </button>

            <button
              onClick={() => setIsRadarVisible(!isRadarVisible)}
              className={`px-2.5 py-1 rounded border text-xs font-semibold transition ${
                isRadarVisible ? 'bg-[#00E676] text-black border-[#00E676]' : 'bg-[#141414] text-gray-300 border-[#222]'
              }`}
              title="Toggle radar minimap"
            >
              Radar
            </button>

            <select
              value={playbackRate}
              onChange={e => changeSpeed(parseFloat(e.target.value))}
              className="bg-[#141414] border border-[#222] text-gray-300 px-2 py-1 rounded text-xs focus:outline-none cursor-pointer"
              title="Playback speed"
              aria-label="Select playback speed"
            >
              <option value="0.5">0.5x</option>
              <option value="0.75">0.75x</option>
              <option value="1">1.0x</option>
              <option value="1.25">1.25x</option>
              <option value="1.5">1.5x</option>
              <option value="2">2.0x</option>
            </select>

            <button 
              onClick={toggleFullscreen} 
              className="p-1.5 hover:text-white transition"
              title={isFullscreen ? "Exit Fullscreen" : "Fullscreen"}
              aria-label={isFullscreen ? "Exit fullscreen" : "Enter fullscreen"}
            >
              {isFullscreen ? <Minimize className="w-4 h-4" /> : <Maximize className="w-4 h-4" />}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
});

VideoPlayer.displayName = 'VideoPlayer';
