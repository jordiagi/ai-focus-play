import React, { useState, useEffect } from 'react';
import { X, Copy, Check, Share2, Sparkles, RefreshCw, AtSign, Camera, FileText } from 'lucide-react';
import { Match } from '../types';
import { api } from '../services/api';

interface SocialShareModalProps {
  isOpen: boolean;
  onClose: () => void;
  match: Match | null;
}

type TabType = 'short' | 'medium' | 'long';

export const SocialShareModal: React.FC<SocialShareModalProps> = ({
  isOpen,
  onClose,
  match,
}) => {
  const [activeTab, setActiveTab] = useState<TabType>('short');
  const [recaps, setRecaps] = useState<{ short: string; medium: string; long: string } | null>(null);
  const [editedText, setEditedText] = useState<{ short: string; medium: string; long: string }>({
    short: '',
    medium: '',
    long: '',
  });
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!isOpen || !match) return;

    let isMounted = true;
    const fetchRecap = async () => {
      setLoading(true);
      try {
        const data = await api.getSocialRecap(match.id);
        if (isMounted) {
          setRecaps(data);
          setEditedText({
            short: data.short,
            medium: data.medium,
            long: data.long,
          });
        }
      } catch (err) {
        console.error('Failed to load social recap:', err);
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    fetchRecap();
    return () => {
      isMounted = false;
    };
  }, [isOpen, match]);

  if (!isOpen || !match) return null;

  const currentText = editedText[activeTab];
  const charCount = currentText.length;
  const isShortOverLimit = activeTab === 'short' && charCount > 280;

  const handleCopy = () => {
    navigator.clipboard.writeText(currentText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleReset = () => {
    if (!recaps) return;
    setEditedText(prev => ({
      ...prev,
      [activeTab]: recaps[activeTab],
    }));
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-xs p-4 animate-in fade-in duration-150">
      <div className="bg-[#12141a] border border-[#262c3b] w-full max-w-2xl rounded-2xl shadow-2xl overflow-hidden flex flex-col text-gray-200 max-h-[90vh]">
        {/* Header */}
        <div className="p-4 sm:p-5 border-b border-[#222736] flex items-center justify-between bg-[#151922]">
          <div className="flex items-center space-x-3">
            <div className="w-9 h-9 rounded-xl bg-[#00E676]/15 border border-[#00E676]/30 flex items-center justify-center text-[#00E676]">
              <Share2 className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h2 className="text-sm sm:text-base font-bold text-white tracking-tight">Social Media & Match Recap Generator</h2>
                <span className="text-[10px] font-semibold bg-[#00E676]/10 text-[#00E676] px-2 py-0.5 rounded-full border border-[#00E676]/20 flex items-center space-x-1">
                  <Sparkles className="w-2.5 h-2.5 inline mr-1" />
                  AI Generated
                </span>
              </div>
              <p className="text-xs text-gray-400 mt-0.5 truncate max-w-md">
                {match.title} • {match.date} • {match.home_score} - {match.away_score}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg bg-[#1c2230] hover:bg-[#283145] text-gray-400 hover:text-white flex items-center justify-center transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Tab Navigation */}
        <div className="flex border-b border-[#222736] bg-[#0e1015] px-4 pt-2 gap-2">
          <button
            onClick={() => setActiveTab('short')}
            className={`flex items-center space-x-2 px-3.5 py-2.5 rounded-t-lg text-xs font-semibold transition border-b-2 ${
              activeTab === 'short'
                ? 'border-[#00E676] text-white bg-[#151922]'
                : 'border-transparent text-gray-400 hover:text-gray-200 hover:bg-[#151922]/50'
            }`}
          >
            <AtSign className="w-3.5 h-3.5 text-[#1DA1F2]" />
            <span>Short (X / Twitter)</span>
            <span className={`text-[10px] px-1.5 py-0.2 rounded-full font-mono ${
              isShortOverLimit ? 'bg-rose-500/20 text-rose-400' : 'bg-emerald-500/20 text-[#00E676]'
            }`}>
              {charCount}/280
            </span>
          </button>

          <button
            onClick={() => setActiveTab('medium')}
            className={`flex items-center space-x-2 px-3.5 py-2.5 rounded-t-lg text-xs font-semibold transition border-b-2 ${
              activeTab === 'medium'
                ? 'border-[#00E676] text-white bg-[#151922]'
                : 'border-transparent text-gray-400 hover:text-gray-200 hover:bg-[#151922]/50'
            }`}
          >
            <Camera className="w-3.5 h-3.5 text-[#E1306C]" />
            <span>Medium (Instagram / FB)</span>
          </button>

          <button
            onClick={() => setActiveTab('long')}
            className={`flex items-center space-x-2 px-3.5 py-2.5 rounded-t-lg text-xs font-semibold transition border-b-2 ${
              activeTab === 'long'
                ? 'border-[#00E676] text-white bg-[#151922]'
                : 'border-transparent text-gray-400 hover:text-gray-200 hover:bg-[#151922]/50'
            }`}
          >
            <FileText className="w-3.5 h-3.5 text-amber-400" />
            <span>Long (Match Report)</span>
          </button>
        </div>

        {/* Content Body */}
        <div className="p-4 sm:p-5 flex-1 flex flex-col min-h-[280px]">
          {loading ? (
            <div className="flex-1 flex flex-col items-center justify-center py-12 text-gray-400 space-y-2">
              <RefreshCw className="w-5 h-5 animate-spin text-[#00E676]" />
              <span className="text-xs">Synthesizing match analytics & narrative...</span>
            </div>
          ) : (
            <div className="flex-1 flex flex-col">
              <div className="flex items-center justify-between text-xs text-gray-400 mb-2">
                <span>Edit or copy the generated recap below:</span>
                <button
                  onClick={handleReset}
                  className="flex items-center space-x-1 hover:text-white transition text-[11px]"
                  title="Reset to generated default"
                >
                  <RefreshCw className="w-3 h-3" />
                  <span>Reset</span>
                </button>
              </div>
              <textarea
                value={currentText}
                onChange={(e) => setEditedText(prev => ({ ...prev, [activeTab]: e.target.value }))}
                className="w-full flex-1 min-h-[220px] bg-[#0c0e13] border border-[#262c3b] rounded-xl p-3.5 text-xs sm:text-sm font-sans text-gray-200 focus:outline-hidden focus:border-[#00E676]/60 leading-relaxed resize-y"
                placeholder="Match recap will appear here..."
              />
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="p-4 border-t border-[#222736] bg-[#151922] flex items-center justify-between">
          <div className="text-[11px] text-gray-400">
            {activeTab === 'short' && (
              <span>Tailored for rapid X / Twitter broadcast with key stats & hashtags.</span>
            )}
            {activeTab === 'medium' && (
              <span>Engaging story format with tactical progression bullets for club social channels.</span>
            )}
            {activeTab === 'long' && (
              <span>Structured press release with executive summary & box score table.</span>
            )}
          </div>

          <div className="flex items-center space-x-2.5">
            <button
              onClick={onClose}
              className="px-3.5 py-1.5 text-xs text-gray-400 hover:text-white rounded-lg transition"
            >
              Close
            </button>
            <button
              onClick={handleCopy}
              disabled={loading || !currentText}
              className={`flex items-center space-x-1.5 px-4 py-2 rounded-xl text-xs font-bold transition shadow-lg ${
                copied
                  ? 'bg-emerald-600 text-white'
                  : 'bg-[#00E676] hover:bg-[#00c864] text-black'
              }`}
            >
              {copied ? (
                <>
                  <Check className="w-3.5 h-3.5" />
                  <span>Copied to Clipboard!</span>
                </>
              ) : (
                <>
                  <Copy className="w-3.5 h-3.5" />
                  <span>Copy Recap</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
