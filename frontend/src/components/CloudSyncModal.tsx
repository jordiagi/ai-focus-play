import React, { useState, useEffect, useRef } from 'react';
import { 
  Cloud, CloudUpload, Check, Copy, ExternalLink, RefreshCw, 
  AlertCircle, Video, Film, BarChart3, Database, ShieldCheck, X, Sparkles
} from 'lucide-react';
import { Match, CloudflareSyncSummary, CloudflareSyncStatus } from '../types';
import { api } from '../services/api';

interface CloudSyncModalProps {
  isOpen: boolean;
  onClose: () => void;
  match: Match | null;
}

export const CloudSyncModal: React.FC<CloudSyncModalProps> = ({
  isOpen,
  onClose,
  match,
}) => {
  const [summary, setSummary] = useState<CloudflareSyncSummary | null>(null);
  const [status, setStatus] = useState<CloudflareSyncStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [isSyncing, setIsSyncing] = useState(false);
  const [copied, setCopied] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const pollTimerRef = useRef<number | null>(null);

  // Fetch summary when opened
  useEffect(() => {
    if (!isOpen || !match) return;

    let isMounted = true;
    const fetchSummary = async () => {
      setLoading(true);
      setErrorMsg(null);
      try {
        const data = await api.getCloudflareSyncSummary(match.id);
        if (isMounted) {
          setSummary(data);
          setStatus(data.status);
          if (data.status.status === 'syncing') {
            setIsSyncing(true);
          }
        }
      } catch (err: any) {
        if (isMounted) {
          setErrorMsg(err.message || 'Failed to load sync details');
        }
      } finally {
        if (isMounted) setLoading(false);
      }
    };

    fetchSummary();

    return () => {
      isMounted = false;
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };
  }, [isOpen, match]);

  // Polling when syncing
  useEffect(() => {
    if (!isSyncing || !match) return;

    const poll = async () => {
      try {
        const current = await api.getCloudflareSyncStatus(match.id);
        setStatus(current);
        if (current.status !== 'syncing') {
          setIsSyncing(false);
          if (pollTimerRef.current) {
            clearInterval(pollTimerRef.current);
            pollTimerRef.current = null;
          }
        }
      } catch (err) {
        console.error('Error polling sync status:', err);
      }
    };

    pollTimerRef.current = window.setInterval(poll, 1000);

    return () => {
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
        pollTimerRef.current = null;
      }
    };
  }, [isSyncing, match]);

  if (!isOpen || !match) return null;

  const publicUrl = status?.public_url || summary?.public_url || `https://focusplay.pages.dev/?match=${match.id}`;

  const handleCopyLink = () => {
    navigator.clipboard.writeText(publicUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleStartSync = async (metadataOnly: boolean = false) => {
    setErrorMsg(null);
    setIsSyncing(true);
    try {
      await api.triggerCloudflareSync(match.id, metadataOnly);
      // Immediate poll
      const current = await api.getCloudflareSyncStatus(match.id);
      setStatus(current);
    } catch (err: any) {
      setIsSyncing(false);
      setErrorMsg(err.message || 'Failed to start sync');
    }
  };

  const isConfigured = summary?.is_configured ?? false;
  const isCompleted = status?.status === 'completed';
  const needsCredentials = status?.status === 'needs_credentials';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-xs p-4 animate-in fade-in duration-150">
      <div className="bg-[#12141a] border border-[#262c3b] w-full max-w-2xl rounded-2xl shadow-2xl overflow-hidden flex flex-col text-gray-200 max-h-[90vh]">
        {/* Header */}
        <div className="p-4 sm:p-5 border-b border-[#222736] flex items-center justify-between bg-[#151922]">
          <div className="flex items-center space-x-3">
            <div className="w-10 h-10 rounded-xl bg-[#F38020]/15 border border-[#F38020]/30 flex items-center justify-center text-[#F38020]">
              <Cloud className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h2 className="text-sm sm:text-base font-bold text-white tracking-tight">Cloudflare Match Sync & Host</h2>
                <span className="text-[10px] font-semibold bg-[#F38020]/15 text-[#F38020] px-2 py-0.5 rounded-full border border-[#F38020]/30 flex items-center space-x-1">
                  <Sparkles className="w-2.5 h-2.5 inline mr-1" />
                  Pages + R2
                </span>
              </div>
              <p className="text-xs text-gray-400 mt-0.5 truncate max-w-md">
                {match.title} • {match.date}
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

        {/* Body Content */}
        <div className="p-4 sm:p-6 overflow-y-auto space-y-5 text-xs sm:text-sm">
          {errorMsg && (
            <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-xl flex items-start space-x-2 text-red-400 text-xs">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{errorMsg}</span>
            </div>
          )}

          {/* Cloudflare Destination Card */}
          <div className="bg-[#181d28] border border-[#262f42] rounded-xl p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
            <div className="space-y-1">
              <div className="flex items-center space-x-2">
                <ShieldCheck className="w-4 h-4 text-[#00E676]" />
                <span className="font-semibold text-white">Target Infrastructure</span>
              </div>
              <div className="text-gray-400 text-xs">
                Cloudflare Pages (<code className="text-gray-300">focusplay.pages.dev</code>) + R2 Bucket (<code className="text-gray-300">{summary?.bucket_name || 'aifp-media'}</code>)
              </div>
            </div>
            <div>
              {isConfigured ? (
                <span className="inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-medium bg-[#00E676]/15 text-[#00E676] border border-[#00E676]/30">
                  Ready to Sync
                </span>
              ) : (
                <span className="inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-medium bg-amber-500/15 text-amber-400 border border-amber-500/30">
                  Local Bundle Mode
                </span>
              )}
            </div>
          </div>

          {/* Credentials Notice if not configured */}
          {!isConfigured && (
            <div className="p-3.5 bg-amber-500/10 border border-amber-500/25 rounded-xl text-amber-300/90 text-xs space-y-1">
              <div className="font-semibold flex items-center space-x-1.5 text-amber-300">
                <AlertCircle className="w-3.5 h-3.5" />
                <span>Cloudflare Credentials Ready for Activation</span>
              </div>
              <p>
                Add your <code className="bg-black/30 px-1 py-0.5 rounded text-amber-200">CF_ACCOUNT_ID</code>, <code className="bg-black/30 px-1 py-0.5 rounded text-amber-200">CF_R2_ACCESS_KEY_ID</code>, and <code className="bg-black/30 px-1 py-0.5 rounded text-amber-200">CF_R2_SECRET_ACCESS_KEY</code> in <code className="bg-black/30 px-1 py-0.5 rounded text-amber-200">scripts/config.local.env</code>.
              </p>
              <p className="text-[11px] text-amber-400/80">
                Syncing now will export the complete bundle locally and prepare all files for R2 upload.
              </p>
            </div>
          )}

          {/* Media Assets Breakdown */}
          <div className="space-y-2">
            <h3 className="text-xs font-bold uppercase tracking-wider text-gray-400">Match Assets to Sync</h3>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
              {/* Full Video */}
              <div className="bg-[#151922] border border-[#222736] p-3 rounded-xl flex items-center space-x-3">
                <div className="w-8 h-8 rounded-lg bg-blue-500/15 border border-blue-500/30 flex items-center justify-center text-blue-400 shrink-0">
                  <Video className="w-4 h-4" />
                </div>
                <div className="min-w-0">
                  <div className="text-[11px] text-gray-400">Full Video</div>
                  <div className="font-semibold text-white text-xs truncate">
                    {summary?.video.formatted_size || '3.40 GB'}
                  </div>
                  <div className="text-[10px] text-gray-500 truncate">
                    {summary?.video.exists ? 'Ready' : 'Missing'}
                  </div>
                </div>
              </div>

              {/* Highlights & Clips */}
              <div className="bg-[#151922] border border-[#222736] p-3 rounded-xl flex items-center space-x-3">
                <div className="w-8 h-8 rounded-lg bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center text-emerald-400 shrink-0">
                  <Film className="w-4 h-4" />
                </div>
                <div className="min-w-0">
                  <div className="text-[11px] text-gray-400">Highlights & Clips</div>
                  <div className="font-semibold text-white text-xs truncate">
                    {summary?.clips.count || 0} Clips
                  </div>
                  <div className="text-[10px] text-gray-500">
                    Seek-enabled timeline
                  </div>
                </div>
              </div>

              {/* Radar & Analytics */}
              <div className="bg-[#151922] border border-[#222736] p-3 rounded-xl flex items-center space-x-3">
                <div className="w-8 h-8 rounded-lg bg-purple-500/15 border border-purple-500/30 flex items-center justify-center text-purple-400 shrink-0">
                  <BarChart3 className="w-4 h-4" />
                </div>
                <div className="min-w-0">
                  <div className="text-[11px] text-gray-400">Radar & Analytics</div>
                  <div className="font-semibold text-white text-xs truncate">
                    {summary?.metadata.events_count || 0} Events • Radar
                  </div>
                  <div className="text-[10px] text-gray-500">
                    2D Minimap & stats
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Sync Progress Bar */}
          {isSyncing && (
            <div className="p-4 bg-[#151922] border border-[#222736] rounded-xl space-y-2.5">
              <div className="flex items-center justify-between text-xs">
                <span className="font-medium text-white flex items-center space-x-2">
                  <RefreshCw className="w-3.5 h-3.5 text-[#F38020] animate-spin" />
                  <span>Syncing to Cloudflare R2...</span>
                </span>
                <span className="font-mono text-[#F38020] font-bold">
                  {status?.progress_percent ? `${status.progress_percent.toFixed(1)}%` : 'Processing...'}
                </span>
              </div>
              <div className="w-full bg-[#222736] h-2 rounded-full overflow-hidden">
                <div 
                  className="bg-gradient-to-r from-[#F38020] to-[#00E676] h-full transition-all duration-300"
                  style={{ width: `${status?.progress_percent || 10}%` }}
                />
              </div>
              <div className="text-[11px] text-gray-400 truncate flex items-center justify-between">
                <span>{status?.current_file || 'Uploading assets...'}</span>
                {status?.total_files ? (
                  <span>{status.completed_files} of {status.total_files} assets</span>
                ) : null}
              </div>
            </div>
          )}

          {/* Success / Synced Card */}
          {(isCompleted || needsCredentials) && !isSyncing && (
            <div className="p-4 bg-[#151922] border border-[#222736] rounded-xl space-y-3">
              <div className="flex items-center space-x-2 text-[#00E676] font-semibold text-xs">
                <Check className="w-4 h-4" />
                <span>
                  {isCompleted ? 'Match is live and hosted on Cloudflare' : 'Match bundle exported and ready for Cloudflare'}
                </span>
              </div>

              {/* Public Link Box */}
              <div className="space-y-1.5">
                <label className="text-[11px] text-gray-400">Public Third-Party Share Link:</label>
                <div className="flex items-center space-x-2">
                  <input
                    type="text"
                    readOnly
                    value={publicUrl}
                    className="flex-1 bg-[#0d1017] border border-[#262c3b] rounded-lg px-3 py-2 text-xs text-white font-mono selection:bg-[#F38020]/30 focus:outline-none"
                  />
                  <button
                    onClick={handleCopyLink}
                    className="px-3 py-2 rounded-lg bg-[#1c2230] hover:bg-[#283145] text-white text-xs font-semibold flex items-center space-x-1.5 border border-[#2c3547] transition shrink-0"
                  >
                    {copied ? (
                      <>
                        <Check className="w-3.5 h-3.5 text-[#00E676]" />
                        <span className="text-[#00E676]">Copied!</span>
                      </>
                    ) : (
                      <>
                        <Copy className="w-3.5 h-3.5" />
                        <span>Copy Link</span>
                      </>
                    )}
                  </button>
                  <a
                    href={publicUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="p-2 rounded-lg bg-[#1c2230] hover:bg-[#283145] text-gray-300 hover:text-white border border-[#2c3547] transition shrink-0"
                    title="Open public viewer"
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                  </a>
                </div>
              </div>
              <p className="text-[11px] text-gray-400">
                Third parties can open this link to view match video with follow-cam, player moments, 2D radar, and analytics.
              </p>
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="p-4 sm:p-5 border-t border-[#222736] bg-[#151922] flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="text-[11px] text-gray-400 text-center sm:text-left">
            Pipeline unaffected • Zero egress video streaming via R2
          </div>
          <div className="flex items-center space-x-2.5 w-full sm:w-auto">
            <button
              onClick={() => handleStartSync(true)}
              disabled={isSyncing || loading}
              className="flex-1 sm:flex-none px-3.5 py-2 rounded-xl bg-[#1c2230] hover:bg-[#283145] disabled:opacity-50 text-gray-300 hover:text-white text-xs font-semibold border border-[#2c3547] transition flex items-center justify-center space-x-1.5"
              title="Fast sync for events, drawings, and analytics only"
            >
              <Database className="w-3.5 h-3.5" />
              <span>Sync Data Only</span>
            </button>
            <button
              onClick={() => handleStartSync(false)}
              disabled={isSyncing || loading}
              className="flex-1 sm:flex-none px-4 py-2 rounded-xl bg-[#F38020] hover:bg-[#ff8f33] disabled:opacity-50 text-white text-xs font-bold shadow-lg shadow-[#F38020]/20 transition flex items-center justify-center space-x-1.5"
            >
              <CloudUpload className="w-4 h-4" />
              <span>{isSyncing ? 'Syncing...' : 'Sync Everything to Cloud'}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
