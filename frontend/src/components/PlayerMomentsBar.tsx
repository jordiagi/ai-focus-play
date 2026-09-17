import React from 'react';
import { Info } from 'lucide-react';
import { PlayerRoster } from '../types';

interface PlayerMomentsBarProps {
  lineup: PlayerRoster[];
  selectedJersey: string | null;
  onSelectJersey: (jersey: string | null) => void;
}

export const PlayerMomentsBar: React.FC<PlayerMomentsBarProps> = ({
  lineup,
  selectedJersey,
  onSelectJersey,
}) => {
  // Default Arlington ECNL jersey numbers from live Veo match
  const jerseys = [
    '2', '4', '6', '8', '10', '12', '13', '14', '16', '18', '20', '24', '26', '28', '30', '32', '44'
  ];

  return (
    <div className="flex flex-col items-center justify-center py-2 bg-[#000000] select-none">
      {/* Title with Info icon */}
      <div className="flex items-center space-x-1.5 text-[11px] font-bold text-[#8e8e8e] tracking-wider uppercase mb-1.5">
        <span>PLAYER MOMENTS</span>
        <Info className="w-3.5 h-3.5 text-[#666] cursor-pointer hover:text-gray-300 transition" />
      </div>

      {/* Dark Pill Container with Jersey Numbers */}
      <div className="flex items-center space-x-1.5 bg-[#12141a] px-3.5 py-1.5 rounded-full border border-[#22242c] shadow-lg max-w-full overflow-x-auto">
        <button
          onClick={() => onSelectJersey(null)}
          className={`px-2 py-0.5 rounded-full text-[11px] font-bold transition shrink-0 ${
            selectedJersey === null ? 'bg-[#00E676] text-black' : 'text-gray-400 hover:text-white'
          }`}
        >
          ALL
        </button>

        {jerseys.map(j => {
          const isSelected = selectedJersey === j;
          const player = lineup.find(p => p.jersey === j);

          return (
            <button
              key={j}
              onClick={() => onSelectJersey(isSelected ? null : j)}
              className={`w-7 h-7 rounded-full text-xs font-bold transition flex items-center justify-center shrink-0 ${
                isSelected 
                  ? 'bg-[#FFD700] text-black ring-2 ring-white scale-110 shadow' 
                  : 'bg-[#1b1e28] text-gray-300 hover:bg-[#282d3c] hover:text-white'
              }`}
              title={player ? `${player.name} (#${j} - ${player.position})` : `Player #${j}`}
            >
              {j}
            </button>
          );
        })}
      </div>
    </div>
  );
};
