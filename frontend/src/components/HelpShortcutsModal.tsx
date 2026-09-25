import React, { useEffect } from 'react';
import { X, Keyboard, HelpCircle } from 'lucide-react';

interface HelpShortcutsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const HelpShortcutsModal: React.FC<HelpShortcutsModalProps> = ({
  isOpen,
  onClose,
}) => {
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div 
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-xs p-4 animate-in fade-in duration-150"
      onClick={onClose}
    >
      <div 
        className="bg-[#12141a] border border-[#262c3b] w-full max-w-lg rounded-2xl p-6 shadow-2xl text-white space-y-5 animate-in zoom-in-95 duration-150"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[#222] pb-3">
          <div className="flex items-center space-x-2.5">
            <div className="p-2 rounded-xl bg-[#00E676]/10 text-[#00E676] border border-[#00E676]/20">
              <Keyboard className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-white">Keyboard Shortcuts & Help</h3>
              <p className="text-[11px] text-gray-400">Veo Player Hotkeys & Controls</p>
            </div>
          </div>
          <button 
            onClick={onClose} 
            className="p-1 rounded-lg text-gray-400 hover:text-white hover:bg-[#1a1e28] transition"
            aria-label="Close shortcuts modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Shortcuts Group: Playback & Navigation */}
        <div className="space-y-2">
          <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider block">
            Playback & Navigation
          </span>
          <div className="space-y-1.5 text-xs bg-[#0a0c10] border border-[#1a1e28] rounded-xl p-3">
            <div className="flex items-center justify-between py-1 border-b border-[#181c25]">
              <span className="text-gray-300">Play / Pause</span>
              <kbd className="font-mono bg-[#1b2230] border border-[#2d3748] px-2 py-0.5 rounded text-[#00E676] text-xs font-semibold shadow-xs">
                Space
              </kbd>
            </div>
            <div className="flex items-center justify-between py-1 border-b border-[#181c25]">
              <span className="text-gray-300">Skip ±10 Seconds</span>
              <div className="flex space-x-1">
                <kbd className="font-mono bg-[#1b2230] border border-[#2d3748] px-1.5 py-0.5 rounded text-[#00E676] text-xs font-semibold">
                  J / L
                </kbd>
                <span className="text-gray-500">or</span>
                <kbd className="font-mono bg-[#1b2230] border border-[#2d3748] px-1.5 py-0.5 rounded text-[#00E676] text-xs font-semibold">
                  ← / →
                </kbd>
              </div>
            </div>
            <div className="flex items-center justify-between py-1 border-b border-[#181c25]">
              <span className="text-gray-300">Jump Next / Prev Highlight</span>
              <kbd className="font-mono bg-[#1b2230] border border-[#2d3748] px-2 py-0.5 rounded text-[#00E676] text-xs font-semibold">
                [ / ]
              </kbd>
            </div>
            <div className="flex items-center justify-between py-1 border-b border-[#181c25]">
              <span className="text-gray-300">Toggle Fullscreen</span>
              <kbd className="font-mono bg-[#1b2230] border border-[#2d3748] px-2 py-0.5 rounded text-[#00E676] text-xs font-semibold">
                F
              </kbd>
            </div>
            <div className="flex items-center justify-between py-1">
              <span className="text-gray-300">Mute / Unmute</span>
              <kbd className="font-mono bg-[#1b2230] border border-[#2d3748] px-2 py-0.5 rounded text-[#00E676] text-xs font-semibold">
                M
              </kbd>
            </div>
          </div>
        </div>

        {/* Shortcuts Group: Overlays & Analysis Tools */}
        <div className="space-y-2">
          <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider block">
            Visual Overlays & Telestrator
          </span>
          <div className="space-y-1.5 text-xs bg-[#0a0c10] border border-[#1a1e28] rounded-xl p-3">
            <div className="flex items-center justify-between py-1 border-b border-[#181c25]">
              <span className="text-gray-300">Toggle Telestrator Drawing Mode</span>
              <kbd className="font-mono bg-[#1b2230] border border-[#2d3748] px-2 py-0.5 rounded text-[#00E676] text-xs font-semibold">
                D
              </kbd>
            </div>
            <div className="flex items-center justify-between py-1 border-b border-[#181c25]">
              <span className="text-gray-300">Toggle Player Turf Tracking Rings</span>
              <kbd className="font-mono bg-[#1b2230] border border-[#2d3748] px-2 py-0.5 rounded text-[#00E676] text-xs font-semibold">
                T
              </kbd>
            </div>
            <div className="flex items-center justify-between py-1 border-b border-[#181c25]">
              <span className="text-gray-300">Toggle 2D Pitch Radar</span>
              <kbd className="font-mono bg-[#1b2230] border border-[#2d3748] px-2 py-0.5 rounded text-[#00E676] text-xs font-semibold">
                R
              </kbd>
            </div>
            <div className="flex items-center justify-between py-1">
              <span className="text-gray-300">Interactive Pan & Zoom / Reset</span>
              <div className="flex items-center space-x-1">
                <kbd className="font-mono bg-[#1b2230] border border-[#2d3748] px-1.5 py-0.5 rounded text-[#00E676] text-xs font-semibold">
                  Wheel
                </kbd>
                <span className="text-gray-500">/</span>
                <kbd className="font-mono bg-[#1b2230] border border-[#2d3748] px-1.5 py-0.5 rounded text-[#00E676] text-xs font-semibold">
                  Esc
                </kbd>
              </div>
            </div>
          </div>
        </div>

        {/* Footer info */}
        <div className="flex items-center justify-between pt-2 border-t border-[#1f2430] text-[11px] text-gray-400">
          <div className="flex items-center space-x-1.5">
            <HelpCircle className="w-3.5 h-3.5 text-[#00E676]" />
            <span>Press <kbd className="font-mono bg-[#1a1e28] px-1 rounded text-white font-bold">?</kbd> anywhere to open this guide</span>
          </div>
          <span className="font-mono text-gray-500">Veo Cam 3 • v4.3.0</span>
        </div>
      </div>
    </div>
  );
};
