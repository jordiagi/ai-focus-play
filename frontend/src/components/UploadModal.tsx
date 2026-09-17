import React, { useState, useRef } from 'react';
import { UploadCloud, X, Film, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';
import { Match } from '../types';
import { api } from '../services/api';

interface UploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onMatchUploaded: (match: Match) => void;
}

export const UploadModal: React.FC<UploadModalProps> = ({
  isOpen,
  onClose,
  onMatchUploaded,
}) => {
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [homeTeam, setHomeTeam] = useState('Arlington SA U16B');
  const [awayTeam, setAwayTeam] = useState('Opponent FC');
  const [date, setDate] = useState('Sep 17, 2026');
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      setSelectedFile(e.dataTransfer.files[0]);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setSelectedFile(e.target.files[0]);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) {
      setUploadError('Please select a video file.');
      return;
    }

    setIsUploading(true);
    setUploadError(null);

    const formData = new FormData();
    formData.append('file', selectedFile);
    formData.append('home_team', homeTeam);
    formData.append('away_team', awayTeam);
    formData.append('date', date);
    formData.append('title', `${homeTeam} vs. ${awayTeam}`);

    try {
      const match = await api.uploadMatch(formData);
      onMatchUploaded(match);
      onClose();
    } catch (err: any) {
      setUploadError(err.message || 'Failed to upload video');
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-sm p-4">
      <div className="bg-[#161a23] border border-[#2d3342] w-full max-w-lg rounded-2xl p-6 shadow-2xl relative text-gray-200">
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-gray-400 hover:text-white transition"
        >
          <X className="w-5 h-5" />
        </button>

        <div className="flex items-center space-x-2.5 mb-5">
          <div className="w-8 h-8 rounded-full bg-[#00E676]/20 flex items-center justify-center text-[#00E676]">
            <UploadCloud className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-bold text-white">Upload Soccer Match Video</h2>
            <p className="text-xs text-gray-400">Process AI tracking, radar, and highlight analysis</p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* File Dropzone */}
          <div
            onDragOver={e => e.preventDefault()}
            onDrop={handleFileDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition flex flex-col items-center justify-center ${
              selectedFile ? 'border-[#00E676] bg-[#00E676]/5' : 'border-[#2d3342] hover:border-gray-500 bg-[#111317]'
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="video/*,.mp4,.mov,.mkv,.webm"
              onChange={handleFileSelect}
              className="hidden"
            />
            {selectedFile ? (
              <div className="flex flex-col items-center space-y-2">
                <Film className="w-8 h-8 text-[#00E676]" />
                <span className="text-xs font-semibold text-white truncate max-w-xs">
                  {selectedFile.name}
                </span>
                <span className="text-[11px] text-gray-400">
                  {(selectedFile.size / (1024 * 1024)).toFixed(1)} MB
                </span>
              </div>
            ) : (
              <div className="flex flex-col items-center space-y-2">
                <UploadCloud className="w-8 h-8 text-gray-400" />
                <span className="text-xs font-semibold text-white">
                  Drop match video here or browse
                </span>
                <span className="text-[10px] text-gray-400">
                  MP4, MOV, MKV, 1080p, 4K, or 180° panoramic
                </span>
              </div>
            )}
          </div>

          {/* Form Fields */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-300 mb-1">Home Team</label>
              <input
                type="text"
                value={homeTeam}
                onChange={e => setHomeTeam(e.target.value)}
                required
                className="w-full bg-[#111317] border border-[#2d3342] rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[#00E676]"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-300 mb-1">Away Team</label>
              <input
                type="text"
                value={awayTeam}
                onChange={e => setAwayTeam(e.target.value)}
                required
                className="w-full bg-[#111317] border border-[#2d3342] rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[#00E676]"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-gray-300 mb-1">Match Date</label>
            <input
              type="text"
              value={date}
              onChange={e => setDate(e.target.value)}
              required
              className="w-full bg-[#111317] border border-[#2d3342] rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[#00E676]"
            />
          </div>

          {uploadError && (
            <div className="flex items-center space-x-2 text-red-400 text-xs bg-red-500/10 p-2.5 rounded-lg border border-red-500/30">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{uploadError}</span>
            </div>
          )}

          {/* Submit */}
          <button
            type="submit"
            disabled={isUploading || !selectedFile}
            className="w-full bg-[#00E676] hover:bg-[#00c968] disabled:opacity-50 text-black font-bold text-xs py-2.5 rounded-lg transition flex items-center justify-center space-x-2"
          >
            {isUploading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Uploading & Starting AI CV Pipeline...</span>
              </>
            ) : (
              <span>Start Analysis</span>
            )}
          </button>
        </form>
      </div>
    </div>
  );
};
