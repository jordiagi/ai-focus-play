import React, { useState, useRef } from 'react';
import { Highlight, Event } from '../../types';

interface TimelineProps {
  currentTime: number;
  duration: number;
  highlights: Highlight[];
  events: Event[];
  onSeek: (time: number) => void;
  clipStart?: number | null;
  clipEnd?: number | null;
  onSetClipBounds?: (start: number, end: number) => void;
}

export const Timeline: React.FC<TimelineProps> = ({
  currentTime,
  duration,
  highlights,
  events,
  onSeek,
  clipStart,
  clipEnd,
}) => {
  const barRef = useRef<HTMLDivElement | null>(null);
  const [hoverTime, setHoverTime] = useState<number | null>(null);
  const [hoverEvent, setHoverEvent] = useState<string | null>(null);

  const safeDuration = duration > 0 ? duration : 90;
  const progressPercent = Math.min(100, Math.max(0, (currentTime / safeDuration) * 100));

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!barRef.current) return;
    const rect = barRef.current.getBoundingClientRect();
    const pos = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width));
    const t = pos * safeDuration;
    setHoverTime(t);
  };

  const handleClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!barRef.current) return;
    const rect = barRef.current.getBoundingClientRect();
    const pos = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width));
    onSeek(pos * safeDuration);
  };

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const getMarkerColor = (type: string) => {
    switch (type.toLowerCase()) {
      case 'goal': return 'bg-[#00E676]';
      case 'shot': return 'bg-[#FFD700]';
      case 'save': return 'bg-[#2979FF]';
      case 'foul': return 'bg-[#FF5252]';
      case 'corner': return 'bg-[#AB47BC]';
      case 'kickoff': return 'bg-white';
      default: return 'bg-[#00E676]';
    }
  };

  return (
    <div className="w-full select-none relative group py-2">
      {/* Timecode Hover Preview */}
      {hoverTime !== null && (
        <div
          className="absolute -top-8 -translate-x-1/2 bg-[#161a23] border border-[#2d3342] text-[11px] font-mono text-white px-2 py-0.5 rounded shadow-xl pointer-events-none z-30"
          style={{ left: `${(hoverTime / safeDuration) * 100}%` }}
        >
          {formatTime(hoverTime)} {hoverEvent ? `• ${hoverEvent}` : ''}
        </div>
      )}

      {/* Main Track */}
      <div
        ref={barRef}
        onClick={handleClick}
        onMouseMove={handleMouseMove}
        onMouseLeave={() => {
          setHoverTime(null);
          setHoverEvent(null);
        }}
        className="h-3 bg-[#1e2330] hover:h-4 rounded-full cursor-pointer relative overflow-visible transition-all flex items-center"
      >
        {/* Progress Bar */}
        <div
          className="h-full bg-[#00E676] rounded-full relative transition-all"
          style={{ width: `${progressPercent}%` }}
        >
          {/* Scrubber Playhead handle */}
          <div className="absolute right-0 top-1/2 -translate-y-1/2 w-4 h-4 bg-white border-2 border-[#00E676] rounded-full shadow-lg scale-0 group-hover:scale-100 transition-transform" />
        </div>

        {/* Highlight Range Indicators (shaded intervals) */}
        {highlights.map((h) => {
          const leftPct = (h.start_time / safeDuration) * 100;
          const widthPct = ((h.end_time - h.start_time) / safeDuration) * 100;
          return (
            <div
              key={h.id}
              className="absolute top-0 bottom-0 bg-[#00E676]/20 border-x border-[#00E676]/60 pointer-events-none"
              style={{ left: `${leftPct}%`, width: `${widthPct}%` }}
            />
          );
        })}

        {/* Selected Clip Range if creating manual clip */}
        {clipStart !== null && clipStart !== undefined && clipEnd !== null && clipEnd !== undefined && (
          <div
            className="absolute top-0 bottom-0 bg-yellow-400/30 border-x-2 border-yellow-400 pointer-events-none z-10"
            style={{
              left: `${(clipStart / safeDuration) * 100}%`,
              width: `${((clipEnd - clipStart) / safeDuration) * 100}%`,
            }}
          />
        )}

        {/* Event Markers Pins */}
        {events.map((evt) => {
          const leftPct = (evt.timestamp / safeDuration) * 100;
          const isGoal = evt.event_type.toLowerCase() === 'goal';
          return (
            <button
              key={evt.id}
              onClick={(e) => {
                e.stopPropagation();
                onSeek(evt.timestamp);
              }}
              onMouseEnter={() => setHoverEvent(`${evt.event_type} (${evt.team.toUpperCase()})`)}
              className={`absolute -translate-x-1/2 z-20 transition hover:scale-150 ${
                isGoal ? 'w-3.5 h-3.5 ring-2 ring-white animate-pulse' : 'w-2.5 h-2.5'
              } rounded-full ${getMarkerColor(evt.event_type)}`}
              style={{ left: `${leftPct}%` }}
              title={`${evt.event_type}: ${evt.description}`}
            />
          );
        })}
      </div>
    </div>
  );
};
