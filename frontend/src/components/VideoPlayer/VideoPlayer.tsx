import React, { useRef, useState, useEffect } from 'react';
import { 
  Play, Pause, RotateCcw, RotateCw, SkipBack, SkipForward, 
  Volume2, VolumeX, Maximize, Minimize, Compass, Camera, 
  Pencil
} from 'lucide-react';
import confetti from 'canvas-confetti';
import { Match, Highlight, Event, Drawing, RadarFrame } from '../../types';
import { Timeline } from './Timeline';
import { TelestratorCanvas } from './TelestratorCanvas';
import { PitchRadar } from '../PitchRadar/PitchRadar';

interface VideoPlayerProps {
  match: Match;
  highlights: Highlight[];
  events: Event[];
  drawings: Drawing[];
  radarFrames: RadarFrame[];
  onSaveDrawing: (drawing: Omit<Drawing, 'id'>) => void;
  onSeekTime?: (time: number) => void;
}

export const VideoPlayer: React.FC<VideoPlayerProps> = ({
  match,
  highlights,
  events,
  drawings,
  radarFrames,
  onSaveDrawing,
}) => {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(match.duration_seconds || 90);
  const [playbackRate, setPlaybackRate] = useState(1);
  const [isMuted, setIsMuted] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);

  // Modes: 'follow' (Broadcast Follow-Cam) vs 'interactive' (User Pan/Zoom)
  const [viewMode, setViewMode] = useState<'follow' | 'interactive'>('follow');
  const [isTelestratorOpen, setIsTelestratorOpen] = useState(false);
  const [isRadarVisible, setIsRadarVisible] = useState(true);

  // Pan & Zoom state for Interactive 180 Mode
  const [panX, setPanX] = useState(0);
  const [panY, setPanY] = useState(0);
  const [zoomScale, setZoomScale] = useState(1);
  const [isPanning, setIsPanning] = useState(false);
  const [startPan, setStartPan] = useState({ x: 0, y: 0 });

  // Find nearest radar frame for current time
  const currentRadarFrame = React.useMemo(() => {
    if (!radarFrames.length) return null;
    return radarFrames.reduce((prev, curr) => 
      Math.abs(curr.timestamp - currentTime) < Math.abs(prev.timestamp - currentTime) ? curr : prev
    );
  }, [radarFrames, currentTime]);

  // Recent history frames for movement trails
  const historyRadarFrames = React.useMemo(() => {
    if (!radarFrames.length) return [];
    return radarFrames.filter(f => f.timestamp <= currentTime && f.timestamp >= currentTime - 2.5);
  }, [radarFrames, currentTime]);

  // Goal celebration confetti
  useEffect(() => {
    const activeGoal = events.find(e => e.event_type.toLowerCase() === 'goal' && Math.abs(e.timestamp - currentTime) < 0.8);
    if (activeGoal) {
      confetti({
        particleCount: 60,
        spread: 70,
        origin: { y: 0.7 }
      });
    }
  }, [currentTime, events]);

  // Keyboard Shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;

      if (e.code === 'Space') {
        e.preventDefault();
        togglePlay();
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
  }, [isPlaying, currentTime, highlights]);

  const togglePlay = () => {
    if (!videoRef.current) return;
    if (isPlaying) {
      videoRef.current.pause();
    } else {
      videoRef.current.play();
    }
    setIsPlaying(!isPlaying);
  };

  const handleTimeUpdate = () => {
    if (!videoRef.current) return;
    setCurrentTime(videoRef.current.currentTime);
  };

  const handleLoadedMetadata = () => {
    if (!videoRef.current) return;
    setDuration(videoRef.current.duration || match.duration_seconds || 90);
  };

  const seekTo = (time: number) => {
    if (!videoRef.current) return;
    videoRef.current.currentTime = Math.max(0, Math.min(time, duration));
    setCurrentTime(videoRef.current.currentTime);
  };

  const seekRelative = (delta: number) => {
    seekTo(currentTime + delta);
  };

  const jumpHighlight = (direction: number) => {
    if (!highlights.length) return;
    const sorted = [...highlights].sort((a, b) => a.start_time - b.start_time);
    if (direction > 0) {
      const next = sorted.find(h => h.start_time > currentTime + 1.0);
      if (next) seekTo(next.start_time);
    } else {
      const prev = [...sorted].reverse().find(h => h.start_time < currentTime - 1.0);
      if (prev) seekTo(prev.start_time);
    }
  };

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

  // Pan & Zoom Handlers for Interactive 180 Mode
  const handleMouseDown = (e: React.MouseEvent) => {
    if (viewMode !== 'interactive' || isTelestratorOpen) return;
    setIsPanning(true);
    setStartPan({ x: e.clientX - panX, y: e.clientY - panY });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isPanning || viewMode !== 'interactive' || isTelestratorOpen) return;
    setPanX(e.clientX - startPan.x);
    setPanY(e.clientY - startPan.y);
  };

  const handleMouseUp = () => {
    setIsPanning(false);
  };

  const handleWheel = (e: React.WheelEvent) => {
    if (viewMode !== 'interactive' || isTelestratorOpen) return;
    e.preventDefault();
    const zoomDelta = e.deltaY * -0.001;
    setZoomScale(prev => Math.min(3.0, Math.max(1.0, prev + zoomDelta)));
  };

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
      onWheel={handleWheel}
    >
      {/* Centered Main Video Wrapper with rounded corners */}
      <div 
        className="relative flex-1 w-full h-full bg-[#050505] rounded-2xl overflow-hidden border border-[#161616] flex items-center justify-center cursor-grab active:cursor-grabbing shadow-2xl"
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onClick={() => {
          if (!isTelestratorOpen && viewMode === 'follow') togglePlay();
        }}
      >
        {/* Real Veo Scoreboard Pill (Top-Left inside video) */}
        <div className="absolute top-4 left-4 z-20 pointer-events-auto flex items-center space-x-2.5">
          <div className="bg-black/80 backdrop-blur-md border border-[#2a2a2a] px-3 py-1.5 rounded-lg flex items-center space-x-2 text-xs font-bold text-white shadow-xl">
            <span className="text-[#FFD700]">ARL</span>
            <span className="bg-[#1f2430] px-1.5 py-0.5 rounded text-white">{match.home_score}</span>
            <span className="text-gray-500 font-normal">-</span>
            <span className="bg-[#1f2430] px-1.5 py-0.5 rounded text-white">{match.away_score}</span>
            <span className="text-[#2979FF]">SKY</span>
          </div>
          <div className="bg-black/80 backdrop-blur-md border border-[#2a2a2a] px-2.5 py-1.5 rounded-lg text-xs font-mono font-bold text-[#00E676] shadow-xl">
            {formatTime(currentTime)}
          </div>
        </div>

        {/* Top-Right Mode Switchers & Telestrator Button */}
        <div className="absolute top-4 right-4 z-20 pointer-events-auto flex items-center space-x-2">
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
              <span>Interactive 180°</span>
            </button>
          </div>

          <button
            onClick={(e) => {
              e.stopPropagation();
              if (isPlaying) togglePlay();
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

        {/* HTML5 Video Element */}
        <video
          ref={videoRef}
          src={match.video_url}
          onTimeUpdate={handleTimeUpdate}
          onLoadedMetadata={handleLoadedMetadata}
          onPlay={() => setIsPlaying(true)}
          onPause={() => setIsPlaying(false)}
          playsInline
          loop
          className="w-full h-full object-contain pointer-events-none transition-transform duration-75 ease-out"
          style={{
            transform: `translate(${panX}px, ${panY}px) scale(${zoomScale})`,
          }}
        />

        {/* Telestrator Drawing Layer */}
        {isTelestratorOpen && (
          <TelestratorCanvas
            matchId={match.id}
            currentTime={currentTime}
            existingDrawings={drawings}
            onSaveDrawing={onSaveDrawing}
            onClose={() => setIsTelestratorOpen(false)}
          />
        )}

        {/* Top-Right 2D Pitch Radar Overlay (like in live Veo screenshot) */}
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
        {!isPlaying && !isTelestratorOpen && (
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
          onSeek={seekTo}
        />

        {/* Control Buttons */}
        <div className="flex items-center justify-between text-xs text-gray-300 px-1">
          <div className="flex items-center space-x-2">
            <button
              onClick={togglePlay}
              className="p-2 bg-[#181818] hover:bg-[#252525] rounded-full text-white transition"
              title={isPlaying ? 'Pause (Space)' : 'Play (Space)'}
            >
              {isPlaying ? <Pause className="w-4 h-4 fill-white" /> : <Play className="w-4 h-4 fill-white ml-0.5" />}
            </button>

            <button
              onClick={() => seekRelative(-10)}
              className="p-1.5 hover:text-[#00E676] transition"
              title="Skip -10s (J)"
            >
              <RotateCcw className="w-4 h-4" />
            </button>
            <button
              onClick={() => seekRelative(10)}
              className="p-1.5 hover:text-[#00E676] transition"
              title="Skip +10s (L)"
            >
              <RotateCw className="w-4 h-4" />
            </button>

            <button
              onClick={() => jumpHighlight(-1)}
              className="p-1.5 hover:text-[#00E676] transition"
              title="Previous Highlight ([)"
            >
              <SkipBack className="w-4 h-4" />
            </button>
            <button
              onClick={() => jumpHighlight(1)}
              className="p-1.5 hover:text-[#00E676] transition"
              title="Next Highlight (])"
            >
              <SkipForward className="w-4 h-4" />
            </button>

            <button onClick={toggleMute} className="p-1.5 hover:text-white transition">
              {isMuted ? <VolumeX className="w-4 h-4 text-red-400" /> : <Volume2 className="w-4 h-4" />}
            </button>

            <span className="font-mono text-xs text-gray-400 ml-2">
              {formatTime(currentTime)} / {formatTime(duration)}
            </span>
          </div>

          <div className="flex items-center space-x-2">
            <button
              onClick={() => setIsRadarVisible(!isRadarVisible)}
              className={`px-2.5 py-1 rounded border text-xs font-semibold transition ${
                isRadarVisible ? 'bg-[#00E676] text-black border-[#00E676]' : 'bg-[#141414] text-gray-300 border-[#222]'
              }`}
            >
              Radar
            </button>

            <select
              value={playbackRate}
              onChange={e => changeSpeed(parseFloat(e.target.value))}
              className="bg-[#141414] border border-[#222] text-gray-300 px-2 py-1 rounded text-xs focus:outline-none cursor-pointer"
            >
              <option value="0.5">0.5x</option>
              <option value="0.75">0.75x</option>
              <option value="1">1.0x</option>
              <option value="1.25">1.25x</option>
              <option value="1.5">1.5x</option>
              <option value="2">2.0x</option>
            </select>

            <button onClick={toggleFullscreen} className="p-1.5 hover:text-white transition">
              {isFullscreen ? <Minimize className="w-4 h-4" /> : <Maximize className="w-4 h-4" />}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
