import React, { useState, useMemo } from 'react';
import { RadarFrame } from '../../types';
import { RotateCw, Maximize2, Minimize2 } from 'lucide-react';

interface PitchRadarProps {
  currentFrame: RadarFrame | null;
  historyFrames?: RadarFrame[];
  isFloating?: boolean;
  onToggleFloating?: () => void;
}

export const PitchRadar: React.FC<PitchRadarProps> = ({
  currentFrame,
  historyFrames = [],
  isFloating = false,
  onToggleFloating,
}) => {
  const [connectPlayers, setConnectPlayers] = useState(true);
  const [showTrails, setShowTrails] = useState(true);
  const [rotated, setRotated] = useState(false);

  // Field dimensions in standard units for SVG viewBox
  const pitchW = 105;
  const pitchH = 68;

  // Scale functions
  const getX = (x: number) => (rotated ? pitchW - x : x);
  const getY = (y: number) => (rotated ? pitchH - y : y);

  const homePlayers = useMemo(() => {
    return currentFrame?.players.filter(p => p.team === 'home') || [];
  }, [currentFrame]);

  const awayPlayers = useMemo(() => {
    return currentFrame?.players.filter(p => p.team === 'away') || [];
  }, [currentFrame]);

  // Generate tactical lines for Home team (e.g. connecting defenders & midfielders)
  const homeLines = useMemo(() => {
    if (!connectPlayers || homePlayers.length < 3) return [];
    // Sort by X position
    const sorted = [...homePlayers].sort((a, b) => a.x - b.x);
    const lines = [];
    for (let i = 0; i < sorted.length - 1; i++) {
      if (Math.hypot(sorted[i].x - sorted[i+1].x, sorted[i].y - sorted[i+1].y) < 30) {
        lines.push({ p1: sorted[i], p2: sorted[i+1] });
      }
    }
    return lines;
  }, [homePlayers, connectPlayers]);

  return (
    <div className="bg-[#141822] border border-[#262c3b] rounded-xl p-3 shadow-lg flex flex-col space-y-2">
      {/* Radar Header & Controls */}
      <div className="flex items-center justify-between border-b border-[#262c3b] pb-2">
        <div className="flex items-center space-x-2">
          <div className="w-2.5 h-2.5 rounded-full bg-[#00E676] animate-pulse" />
          <span className="text-xs font-bold text-white uppercase tracking-wider">
            2D Pitch Radar
          </span>
        </div>

        <div className="flex items-center space-x-1">
          {/* Connect players toggle */}
          <button
            onClick={() => setConnectPlayers(!connectPlayers)}
            className={`px-2 py-0.5 text-[10px] font-medium rounded transition ${
              connectPlayers ? 'bg-[#00E676]/20 text-[#00E676] border border-[#00E676]/40' : 'text-gray-400 hover:bg-[#202634]'
            }`}
            title="Connect tactical lines"
          >
            Lines
          </button>

          {/* Player trails toggle */}
          <button
            onClick={() => setShowTrails(!showTrails)}
            className={`px-2 py-0.5 text-[10px] font-medium rounded transition ${
              showTrails ? 'bg-blue-500/20 text-blue-400 border border-blue-500/40' : 'text-gray-400 hover:bg-[#202634]'
            }`}
            title="Show movement trails"
          >
            Trails
          </button>

          {/* Rotate pitch 180 */}
          <button
            onClick={() => setRotated(!rotated)}
            className="p-1 text-gray-400 hover:text-white hover:bg-[#202634] rounded transition"
            title="Rotate pitch orientation"
          >
            <RotateCw className="w-3.5 h-3.5" />
          </button>

          {onToggleFloating && (
            <button
              onClick={onToggleFloating}
              className="p-1 text-gray-400 hover:text-white hover:bg-[#202634] rounded transition"
              title={isFloating ? 'Dock in panel' : 'Float on video'}
            >
              {isFloating ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
            </button>
          )}
        </div>
      </div>

      {/* 2D Pitch SVG Canvas */}
      <div className="relative w-full aspect-[105/68] bg-[#1a472a] rounded-lg overflow-hidden border border-[#2d5f3e] shadow-inner">
        <svg
          viewBox={`0 0 ${pitchW} ${pitchH}`}
          className="w-full h-full select-none"
        >
          {/* Pitch Grass Bands */}
          {[...Array(9)].map((_, i) => (
            <rect
              key={i}
              x={(i * pitchW) / 9}
              y={0}
              width={pitchW / 9}
              height={pitchH}
              fill={i % 2 === 0 ? '#1f4e2e' : '#1b4428'}
            />
          ))}

          {/* Outer Boundary Line */}
          <rect
            x={1}
            y={1}
            width={pitchW - 2}
            height={pitchH - 2}
            fill="none"
            stroke="rgba(255,255,255,0.7)"
            strokeWidth="0.8"
          />

          {/* Center Halfway Line */}
          <line
            x1={pitchW / 2}
            y1={1}
            x2={pitchW / 2}
            y2={pitchH - 1}
            stroke="rgba(255,255,255,0.7)"
            strokeWidth="0.8"
          />

          {/* Center Circle & Spot */}
          <circle
            cx={pitchW / 2}
            cy={pitchH / 2}
            r={9.15}
            fill="none"
            stroke="rgba(255,255,255,0.7)"
            strokeWidth="0.8"
          />
          <circle
            cx={pitchW / 2}
            cy={pitchH / 2}
            r={0.8}
            fill="white"
          />

          {/* Left Penalty Area (Home Defense) */}
          <rect
            x={1}
            y={(pitchH - 40.32) / 2}
            width={16.5}
            height={40.32}
            fill="none"
            stroke="rgba(255,255,255,0.7)"
            strokeWidth="0.8"
          />
          {/* Left Goal Area */}
          <rect
            x={1}
            y={(pitchH - 18.32) / 2}
            width={5.5}
            height={18.32}
            fill="none"
            stroke="rgba(255,255,255,0.7)"
            strokeWidth="0.8"
          />
          {/* Left Penalty Spot */}
          <circle cx={11} cy={pitchH / 2} r={0.8} fill="white" />

          {/* Right Penalty Area (Away Defense) */}
          <rect
            x={pitchW - 17.5}
            y={(pitchH - 40.32) / 2}
            width={16.5}
            height={40.32}
            fill="none"
            stroke="rgba(255,255,255,0.7)"
            strokeWidth="0.8"
          />
          {/* Right Goal Area */}
          <rect
            x={pitchW - 6.5}
            y={(pitchH - 18.32) / 2}
            width={5.5}
            height={18.32}
            fill="none"
            stroke="rgba(255,255,255,0.7)"
            strokeWidth="0.8"
          />
          {/* Right Penalty Spot */}
          <circle cx={pitchW - 11} cy={pitchH / 2} r={0.8} fill="white" />

          {/* Movement Trails */}
          {showTrails && historyFrames.map((hf, hIdx) => {
            const opacity = 0.15 + (hIdx / historyFrames.length) * 0.4;
            return hf.players.map(p => (
              <circle
                key={`trail-${p.id}-${hIdx}`}
                cx={getX(p.x)}
                cy={getY(p.y)}
                r={0.8}
                fill={p.team === 'home' ? '#FFD700' : '#2979FF'}
                opacity={opacity}
              />
            ));
          })}

          {/* Tactical Connection Lines */}
          {homeLines.map((line, idx) => (
            <line
              key={`line-${idx}`}
              x1={getX(line.p1.x)}
              y1={getY(line.p1.y)}
              x2={getX(line.p2.x)}
              y2={getY(line.p2.y)}
              stroke="#00E676"
              strokeWidth="0.5"
              strokeDasharray="1 1"
              opacity="0.8"
            />
          ))}

          {/* Player Dots: Home Team (Yellow/Gold with dark ring) */}
          {homePlayers.map(p => (
            <g key={`home-${p.id}`} className="transition-all duration-300">
              <circle
                cx={getX(p.x)}
                cy={getY(p.y)}
                r={p.jersey === 'GK' ? 2.6 : 2.2}
                fill="#FFD700"
                stroke="#000"
                strokeWidth="0.5"
              />
              <text
                x={getX(p.x)}
                y={getY(p.y) + 0.9}
                textAnchor="middle"
                fontSize="1.8"
                fontWeight="bold"
                fill="#000"
                className="pointer-events-none select-none"
              >
                {p.jersey || ''}
              </text>
            </g>
          ))}

          {/* Player Dots: Away Team (Electric Blue) */}
          {awayPlayers.map(p => (
            <g key={`away-${p.id}`} className="transition-all duration-300">
              <circle
                cx={getX(p.x)}
                cy={getY(p.y)}
                r={2.2}
                fill="#2979FF"
                stroke="#fff"
                strokeWidth="0.5"
              />
              <text
                x={getX(p.x)}
                y={getY(p.y) + 0.9}
                textAnchor="middle"
                fontSize="1.8"
                fontWeight="bold"
                fill="#fff"
                className="pointer-events-none select-none"
              >
                {p.jersey || ''}
              </text>
            </g>
          ))}

          {/* Ball (Glowing white dot).
              Rendered ONLY when the tracker actually detected it. A dimmed ball at a
              coasted position still asserts a position we did not measure, which is
              the fabrication this app exists to avoid. Not detected -> draw nothing;
              the "Ball not detected" note below says so explicitly. */}
          {currentFrame?.ball && currentFrame.ball.detected !== false && (
            <g className="transition-all duration-200">
              <circle
                cx={getX(currentFrame.ball.x)}
                cy={getY(currentFrame.ball.y)}
                r={1.5}
                fill="#FFFFFF"
                stroke="#FF3D00"
                strokeWidth="0.6"
              />
            </g>
          )}
        </svg>
      </div>

      {/* Legend & Stats below Radar */}
      {currentFrame?.ball && currentFrame.ball.detected === false && (
        <div
          className="text-[10px] text-amber-400/90 px-1 pt-1"
          title="The tracker did not find the ball in this frame. No position is shown because none was measured."
        >
          Ball not detected
        </div>
      )}
      <div className="flex items-center justify-between text-[11px] text-gray-400 px-1 pt-1">
        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-1.5">
            <div className="w-2.5 h-2.5 rounded-full bg-[#FFD700] border border-black" />
            <span>Home</span>
          </div>
          <div className="flex items-center space-x-1.5">
            <div className="w-2.5 h-2.5 rounded-full bg-[#2979FF] border border-white" />
            <span>Away</span>
          </div>
          <div className="flex items-center space-x-1.5">
            <div className="w-2.5 h-2.5 rounded-full bg-white border border-[#FF3D00]" />
            <span>Ball</span>
          </div>
        </div>
        <div className="font-mono text-[10px] text-gray-400">
          {currentFrame ? `${currentFrame.players.length} Tracked` : '0 Tracked'}
        </div>
      </div>
    </div>
  );
};
