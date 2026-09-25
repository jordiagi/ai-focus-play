import React from 'react';
import { Info } from 'lucide-react';
import { PlayerRoster } from '../types';

interface PlayerMomentsBarProps {
  lineup: PlayerRoster[];
  selectedJersey: string | null;
  onSelectJersey: (jersey: string | null) => void;
}

const isUnknownJersey = (jersey?: string | null): boolean => {
  if (!jersey) return true;
  const trimmed = jersey.trim();
  return trimmed === '' || trimmed === '?' || trimmed.toLowerCase() === 'unknown';
};

export const PlayerMomentsBar: React.FC<PlayerMomentsBarProps> = ({
  lineup,
  selectedJersey,
  onSelectJersey,
}) => {
  return (
    <div className="flex flex-col items-center justify-center py-2 bg-[#000000] select-none">
      {/* Title with Info icon */}
      <div className="flex items-center space-x-1.5 text-[11px] font-bold text-[#8e8e8e] tracking-wider uppercase mb-1.5">
        <span>PLAYER MOMENTS</span>
        <Info className="w-3.5 h-3.5 text-[#666] cursor-pointer hover:text-gray-300 transition" />
      </div>

      {(!lineup || lineup.length === 0) ? (
        /* Empty State */
        <div className="flex items-center space-x-1.5 bg-[#12141a] px-4 py-1.5 rounded-full border border-[#22242c] text-xs text-gray-500">
          <span>No players detected</span>
        </div>
      ) : (
        /* Dark Pill Container with Jersey Numbers */
        <div className="flex items-center space-x-1.5 bg-[#12141a] px-3.5 py-1.5 rounded-full border border-[#22242c] shadow-lg max-w-full overflow-x-auto">
          {/* Team Crest Badge */}
          <div className="w-6 h-6 rounded-full bg-gradient-to-tr from-blue-700 via-blue-500 to-red-500 p-0.5 flex items-center justify-center shrink-0 shadow border border-white/20" title="Team Crest">
            <div className="w-full h-full rounded-full bg-[#12141a] flex items-center justify-center">
              <span className="text-[8px] font-black text-white tracking-tighter">ARL</span>
            </div>
          </div>

          <button
            onClick={() => onSelectJersey(null)}
            className={`px-2 py-0.5 rounded-full text-[11px] font-bold transition shrink-0 ${
              selectedJersey === null ? 'bg-[#00E676] text-black' : 'text-gray-400 hover:text-white'
            }`}
          >
            ALL
          </button>

          {lineup.map((player, idx) => {
            const unknown = isUnknownJersey(player.jersey);
            const jerseyVal = unknown ? '' : player.jersey;
            const isSelected = selectedJersey !== null && selectedJersey === jerseyVal;
            const label = unknown ? 'Player ' : `Player ${jerseyVal}`;
            const badgeInitials = player.is_captain ? 'AV' : (player.is_player_of_match ? 'LA' : null);

            return (
              <button
                key={player.jersey ? `${player.jersey}-${idx}` : `unknown-${idx}`}
                onClick={() => onSelectJersey(isSelected ? null : jerseyVal)}
                className={`h-7 px-1.5 min-w-[28px] rounded-full text-xs font-bold transition flex items-center justify-center shrink-0 ${
                  isSelected 
                    ? 'bg-[#FFD700] text-black ring-2 ring-white scale-110 shadow' 
                    : 'bg-[#1b1e28] text-gray-300 hover:bg-[#282d3c] hover:text-white'
                }`}
                title={label}
                aria-label={label}
              >
                <span>{jerseyVal}</span>
                {badgeInitials && (
                  <span className={`text-[8px] font-black ml-1 px-1 rounded ${
                    player.is_captain ? 'bg-[#FFD700] text-black' : 'bg-[#00E676] text-black'
                  }`}>
                    {badgeInitials}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
};
