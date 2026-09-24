import React, { useState, useRef, useEffect } from 'react';
import { Match } from '../types';
import { Upload, Download, Check, Video, FileArchive, ChevronDown } from 'lucide-react';
import { api } from '../services/api';

interface HeaderProps {
  currentMatch: Match | null;
  matches?: Match[];
  onSelectMatch?: (match: Match) => void;
  onOpenBurgerMenu: () => void;
  onOpenUpload: () => void;
  canUpload?: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  currentMatch,
  matches = [],
  onSelectMatch,
  onOpenBurgerMenu,
  onOpenUpload,
  canUpload = true,
}) => {
  const [showDownloadMenu, setShowDownloadMenu] = useState(false);
  const [showMatchPicker, setShowMatchPicker] = useState(false);
  const [copiedShare, setCopiedShare] = useState(false);
  const matchPickerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (matchPickerRef.current && !matchPickerRef.current.contains(e.target as Node)) {
        setShowMatchPicker(false);
      }
    };
    if (showMatchPicker) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [showMatchPicker]);

  const handleShare = () => {
    const shareUrl = new URL(window.location.href);
    if (currentMatch) {
      shareUrl.searchParams.set('match', currentMatch.id);
    }
    // window.location.href already carries the current hash route, but set it
    // explicitly so a shared link keeps whichever drawer is open even if that
    // ever stops being true.
    shareUrl.hash = window.location.hash;
    navigator.clipboard.writeText(shareUrl.toString());
    setCopiedShare(true);
    setTimeout(() => setCopiedShare(false), 2000);
  };

  const mode = currentMatch?.analysis_mode || 'demo';

  return (
    <header className="h-14 bg-[#000000] border-b border-[#141414] px-4 flex items-center justify-between select-none z-30 relative">
      {/* Left: Hamburger Icon + Stylized veo Logo + Match Title + Mode Badge */}
      <div className="flex items-center space-x-4">
        {/* Hamburger 3-line button */}
        <button
          onClick={onOpenBurgerMenu}
          className="p-2 -ml-2 rounded-lg text-white hover:bg-[#1a1a1a] transition focus:outline-none"
          title="Open Veo Menu"
          aria-label="Open Veo Menu"
        >
          <div className="space-y-1 w-4">
            <div className="h-[2px] bg-white rounded-full" />
            <div className="h-[2px] bg-white rounded-full" />
            <div className="h-[2px] bg-white rounded-full" />
          </div>
        </button>

        {/* Lowercase italic bold veo wordmark */}
        <div 
          onClick={onOpenBurgerMenu}
          className="cursor-pointer flex items-center select-none"
        >
          <span className="font-black italic text-2xl tracking-tighter text-white font-sans">
            veo
          </span>
        </div>

        {/* Match Title & Subtitle with Switcher */}
        <div className="pl-1 relative" ref={matchPickerRef}>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => matches.length > 1 && setShowMatchPicker(!showMatchPicker)}
              className={`flex items-center space-x-1.5 text-left group transition focus:outline-none ${
                matches.length > 1 ? 'cursor-pointer hover:text-[#00E676]' : 'cursor-default'
              }`}
              title={matches.length > 1 ? 'Click to switch match recording' : undefined}
            >
              <h1 className="text-[14px] font-semibold text-white tracking-normal leading-tight truncate max-w-[280px] md:max-w-[440px] group-hover:text-white">
                {currentMatch?.title || 'Arlington SA U16B ECNL (26-27) vs. Skyline U16B ECNL'}
              </h1>
              {matches.length > 1 && (
                <ChevronDown className="w-3.5 h-3.5 text-gray-400 group-hover:text-white transition shrink-0" />
              )}
            </button>

            {/* Analysis Mode Badge (P1-0) */}
            {mode === 'demo' && (
              <span 
                className="bg-amber-500/20 border border-amber-500/40 text-amber-400 text-[10px] font-semibold px-2 py-0.5 rounded-full shrink-0"
                title="Synthetic demonstration dataset — coordinates and statistics not from this video"
              >
                Demo Data
              </span>
            )}
            {mode === 'heuristic' && (
              <span 
                className="bg-zinc-800 border border-zinc-700 text-zinc-300 text-[10px] font-semibold px-2 py-0.5 rounded-full shrink-0"
                title="Heuristic computer vision pipeline — coordinates approximate"
              >
                Heuristic CV
              </span>
            )}
            {mode === 'ml' && (
              <span 
                className="bg-emerald-500/20 border border-emerald-500/40 text-[#00E676] text-[10px] font-semibold px-2 py-0.5 rounded-full shrink-0"
                title="Deep learning object detection & tracking"
              >
                AI Analysis
              </span>
            )}
          </div>

          <div className="text-[11px] text-[#8e8e8e] flex items-center space-x-1.5 leading-none mt-0.5">
            <span>{currentMatch?.date || '\u2014'}</span>
            <span>-</span>
            {/* Nothing increments views_count -- there is no view tracking. Showing a
                number here (or falling back to a literal 95) would invent a metric. */}
            <span title="View tracking is not implemented">&mdash; views</span>
          </div>

          {/* Match Switcher Dropdown */}
          {showMatchPicker && matches.length > 1 && (
            <div className="absolute left-0 top-full mt-2 w-80 bg-[#12141a] border border-[#262c3b] rounded-xl shadow-2xl p-2 z-50 animate-in fade-in slide-in-from-top-1 duration-150">
              <div className="text-[10px] uppercase font-bold tracking-wider text-gray-400 px-2.5 py-1 mb-1 border-b border-[#222]">
                Switch Match Recording ({matches.length})
              </div>
              <div className="space-y-1 max-h-64 overflow-y-auto">
                {matches.map(m => (
                  <button
                    key={m.id}
                    onClick={() => {
                      onSelectMatch?.(m);
                      setShowMatchPicker(false);
                    }}
                    className={`w-full text-left p-2.5 rounded-lg flex items-center justify-between transition cursor-pointer ${
                      m.id === currentMatch?.id
                        ? 'bg-[#1e2433] border border-[#00E676]/40 text-white'
                        : 'hover:bg-[#181c26] text-gray-300 hover:text-white'
                    }`}
                  >
                    <div className="min-w-0 pr-2">
                      <div className="text-xs font-semibold truncate">{m.title}</div>
                      <div className="text-[10px] text-gray-400 mt-0.5 flex items-center space-x-2">
                        <span>{m.date}</span>
                        <span>•</span>
                        <span>{m.home_score} - {m.away_score}</span>
                        <span>•</span>
                        <span className={m.analysis_mode === 'ml' ? 'text-[#00E676]' : 'text-amber-400'}>
                          {m.analysis_mode === 'ml' ? 'AI' : 'Demo'}
                        </span>
                      </div>
                    </div>
                    {m.id === currentMatch?.id && <Check className="w-4 h-4 text-[#00E676] shrink-0" />}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Right: Upload, Share, Download, Profile */}
      <div className="flex items-center space-x-4">
        {/* Upload Button */}
        {canUpload && (
          <button
            onClick={onOpenUpload}
            className="flex items-center space-x-1.5 bg-[#161616] hover:bg-[#222] border border-[#262626] text-white px-2.5 py-1.5 rounded-lg text-xs font-semibold transition cursor-pointer"
            title="Upload and analyze soccer match"
          >
            <Upload className="w-3.5 h-3.5 text-[#00E676]" />
            <span>Upload</span>
          </button>
        )}

        {/* Share Button (Veo style tray arrow) */}
        <button
          onClick={handleShare}
          className="flex items-center space-x-1.5 text-[#e1e1e1] hover:text-white text-xs font-medium transition cursor-pointer"
          aria-label="Share match"
        >
          {copiedShare ? (
            <Check className="w-4 h-4 text-[#00E676]" />
          ) : (
            <Upload className="w-4 h-4" />
          )}
          <span>{copiedShare ? 'Copied' : 'Share'}</span>
        </button>

        {/* Download Dropdown */}
        <div className="relative">
          <button
            onClick={() => setShowDownloadMenu(!showDownloadMenu)}
            className="flex items-center space-x-1.5 text-[#e1e1e1] hover:text-white text-xs font-medium transition cursor-pointer"
            aria-label="Download match media"
          >
            <Download className="w-4 h-4" />
            <span>Download</span>
          </button>

          {showDownloadMenu && currentMatch && (
            <div className="absolute right-0 mt-2 w-60 bg-[#12141a] border border-[#262c3b] rounded-xl shadow-2xl py-1 z-50">
              <a
                href={currentMatch.video_url}
                download
                onClick={() => setShowDownloadMenu(false)}
                className="flex items-center space-x-2.5 px-3 py-2 text-xs text-gray-200 hover:bg-[#1a1e28] transition"
              >
                <Video className="w-4 h-4 text-[#00E676]" />
                <div>
                  <div className="font-semibold text-white">Full Match Video</div>
                  <div className="text-[10px] text-gray-400">Broadcast MP4</div>
                </div>
              </a>
              <a
                href={api.getExportHighlightsUrl(currentMatch.id)}
                download
                onClick={() => setShowDownloadMenu(false)}
                className="flex items-center space-x-2.5 px-3 py-2 text-xs text-gray-200 hover:bg-[#1a1e28] transition border-t border-[#222]"
              >
                <FileArchive className="w-4 h-4 text-blue-400" />
                <div>
                  <div className="font-semibold text-white">Export Highlights (ZIP)</div>
                  <div className="text-[10px] text-gray-400">Download all clips package</div>
                </div>
              </a>
            </div>
          )}
        </div>

        {/* Profile Circle Avatar ("EY" in solid white circle with black text) */}
        <div 
          onClick={onOpenBurgerMenu}
          className="w-8 h-8 rounded-full bg-white text-black font-extrabold text-xs flex items-center justify-center cursor-pointer hover:scale-105 transition shadow"
          title="Eric Yeh-Fuentes Profile"
        >
          EY
        </div>
      </div>
    </header>
  );
};
