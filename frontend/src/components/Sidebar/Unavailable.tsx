import React from 'react';
import { Info } from 'lucide-react';

interface UnavailableProps {
  /** The measured reason this capability is not available. Shown visibly, never as a tooltip only. */
  reason: string;
  className?: string;
}

/**
 * Shared "this is not available, and here is the measured reason" state.
 *
 * Used anywhere a control or panel would otherwise have to fabricate a number,
 * render an empty chart as if it were flat data, or silently show nothing.
 */
export const Unavailable: React.FC<UnavailableProps> = ({ reason, className = '' }) => (
  <div
    role="status"
    className={`flex items-start gap-2 rounded-lg border border-dashed border-[#2a2f3a] bg-[#0d0f14] p-3 text-[11px] leading-relaxed text-gray-400 ${className}`}
  >
    <Info className="w-3.5 h-3.5 mt-0.5 text-gray-500 shrink-0" aria-hidden="true" />
    <span>{reason}</span>
  </div>
);
