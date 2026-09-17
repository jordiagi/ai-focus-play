import React, { useState } from 'react';
import { Match } from '../types';
import { Upload, Download, Check, Video } from 'lucide-react';

interface HeaderProps {
  currentMatch: Match | null;
  onOpenBurgerMenu: () => void;
  onOpenUpload: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  currentMatch,
  onOpenBurgerMenu,
  onOpenUpload,
}) => {
  const [showDownloadMenu, setShowDownloadMenu] = useState(false);
  const [copiedShare, setCopiedShare] = useState(false);

  const handleShare = () => {
    navigator.clipboard.writeText(window.location.href);
    setCopiedShare(true);
    setTimeout(() => setCopiedShare(false), 2000);
  };

  return (
    <header className="h-14 bg-[#000000] border-b border-[#141414] px-4 flex items-center justify-between select-none z-30 relative">
      {/* Left: Hamburger Icon + Stylized veo Logo + Match Title */}
      <div className="flex items-center space-x-4">
        {/* Hamburger 3-line button */}
        <button
          onClick={onOpenBurgerMenu}
          className="p-2 -ml-2 rounded-lg text-white hover:bg-[#1a1a1a] transition focus:outline-none"
          title="Open Veo Menu"
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
          <h1 className="text-[14px] font-semibold text-white tracking-normal leading-tight truncate max-w-[320px] md:max-w-[600px]">
            {currentMatch?.title || 'Arlington SA U16B ECNL (26-27) vs. Skyline U16B ECNL'}
          </h1>
          <div className="text-[11px] text-[#8e8e8e] flex items-center space-x-1.5 leading-none mt-0.5">
            <span>{currentMatch?.date || 'Sep 13, 2026'}</span>
            <span>-</span>
            <span>{currentMatch?.views_count || 95} views</span>
          </div>
        </div>
      </div>

      {/* Right: Share, Download, Profile */}
      <div className="flex items-center space-x-5">
        {/* Share Button (Veo style tray arrow) */}
        <button
          onClick={handleShare}
          className="flex items-center space-x-1.5 text-[#e1e1e1] hover:text-white text-xs font-medium transition cursor-pointer"
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
          >
            <Download className="w-4 h-4" />
            <span>Download</span>
          </button>

          {showDownloadMenu && (
            <div className="absolute right-0 mt-2 w-56 bg-[#12141a] border border-[#262c3b] rounded-xl shadow-2xl py-1 z-50">
              <a
                href={currentMatch?.video_url}
                download
                onClick={() => setShowDownloadMenu(false)}
                className="flex items-center space-x-2.5 px-3 py-2 text-xs text-gray-200 hover:bg-[#1a1e28] transition"
              >
                <Video className="w-4 h-4 text-[#00E676]" />
                <div>
                  <div className="font-semibold text-white">Full Match (1080p)</div>
                  <div className="text-[10px] text-gray-400">AI Follow-Cam MP4</div>
                </div>
              </a>
              <div
                onClick={() => {
                  alert('Compiling highlight clips into export package...');
                  setShowDownloadMenu(false);
                }}
                className="flex items-center space-x-2.5 px-3 py-2 text-xs text-gray-200 hover:bg-[#1a1e28] cursor-pointer transition border-t border-[#222]"
              >
                <Download className="w-4 h-4 text-blue-400" />
                <div>
                  <div className="font-semibold text-white">Highlights Reel</div>
                  <div className="text-[10px] text-gray-400">Export detected clips</div>
                </div>
              </div>
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
