import React, { useState } from 'react';
import { Match } from '../types';
import { Upload, Download, Check, Video, FileArchive } from 'lucide-react';
import { api } from '../services/api';

interface HeaderProps {
  currentMatch: Match | null;
  onOpenBurgerMenu: () => void;
  onOpenUpload: () => void;
  canUpload?: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  currentMatch,
  onOpenBurgerMenu,
  onOpenUpload,
  canUpload = true,
}) => {
  const [showDownloadMenu, setShowDownloadMenu] = useState(false);
  const [copiedShare, setCopiedShare] = useState(false);

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

        {/* Match Title & Subtitle */}
        <div className="pl-1">
          <div className="flex items-center space-x-2">
            <h1 className="text-[14px] font-semibold text-white tracking-normal leading-tight truncate max-w-[280px] md:max-w-[480px]">
              {currentMatch?.title || 'Arlington SA U16B ECNL (26-27) vs. Skyline U16B ECNL'}
            </h1>

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
