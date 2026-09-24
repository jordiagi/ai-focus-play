import React from 'react';
import { Unavailable } from './Unavailable';

interface Thirds {
  defensive?: number;
  middle?: number;
  attacking?: number;
}

interface ThirdsBarProps {
  /** Row label, e.g. "Passes" or "Possession". */
  label: string;
  home?: Thirds;
  data?: Thirds;
  unavailableReason: string;
}

const hasThirds = (t?: Thirds): t is Required<Thirds> =>
  !!t && typeof t.defensive === 'number' && typeof t.middle === 'number' && typeof t.attacking === 'number';

/**
 * Renders pitch-thirds breakdown as a stacked bar, shared
 * by Pass location and Possession location. Supports home or away team selection.
 *
 * If the thirds are not populated (an empty {} from the backend, not a real
 * zero), this renders the honest unavailable state instead of three
 * fabricated zeros.
 */
export const ThirdsBar: React.FC<ThirdsBarProps> = ({ label, home, data, unavailableReason }) => {
  const thirds = data ?? home;
  if (!hasThirds(thirds)) {
    return <Unavailable reason={unavailableReason} />;
  }

  return (
    <div>
      <div className="flex justify-between text-[11px] text-gray-400 mb-1">
        <span>{label}</span>
        <span>{thirds.defensive}% • {thirds.middle}% • {thirds.attacking}%</span>
      </div>
      <div className="h-2.5 rounded-full overflow-hidden flex bg-[#1e2330]">
        <div style={{ width: `${thirds.defensive}%` }} className="bg-blue-600" />
        <div style={{ width: `${thirds.middle}%` }} className="bg-[#00E676]" />
        <div style={{ width: `${thirds.attacking}%` }} className="bg-yellow-500" />
      </div>
    </div>
  );
};
