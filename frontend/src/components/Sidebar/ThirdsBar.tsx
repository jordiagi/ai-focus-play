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
  unavailableReason: string;
}

const hasThirds = (t?: Thirds): t is Required<Thirds> =>
  !!t && typeof t.defensive === 'number' && typeof t.middle === 'number' && typeof t.attacking === 'number';

/**
 * Renders the home-side pitch-thirds breakdown as a stacked bar, exactly the
 * way the original "Thirds Breakdown" panel rendered pass locations. Shared
 * by Pass location and Possession location, since the spec requires the
 * latter to render "exactly the way Pass location renders its thirds."
 *
 * If the thirds are not populated (an empty {} from the backend, not a real
 * zero), this renders the honest unavailable state instead of three
 * fabricated zeros.
 */
export const ThirdsBar: React.FC<ThirdsBarProps> = ({ label, home, unavailableReason }) => {
  if (!hasThirds(home)) {
    return <Unavailable reason={unavailableReason} />;
  }

  return (
    <div>
      <div className="flex justify-between text-[11px] text-gray-400 mb-1">
        <span>{label}</span>
        <span>{home.defensive}% • {home.middle}% • {home.attacking}%</span>
      </div>
      <div className="h-2.5 rounded-full overflow-hidden flex bg-[#1e2330]">
        <div style={{ width: `${home.defensive}%` }} className="bg-blue-600" />
        <div style={{ width: `${home.middle}%` }} className="bg-[#00E676]" />
        <div style={{ width: `${home.attacking}%` }} className="bg-yellow-500" />
      </div>
    </div>
  );
};
