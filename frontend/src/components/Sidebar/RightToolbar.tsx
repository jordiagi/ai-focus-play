import React from 'react';
import { 
  Plus, BarChart2, Shirt, Video, List, LayoutGrid, FileText, 
  HelpCircle, Columns
} from 'lucide-react';

export type ActiveDrawerType = 'analytics' | 'players' | 'highlights' | 'events' | 'lineup' | 'summary' | null;

interface RightToolbarProps {
  activeDrawer: ActiveDrawerType;
  onToggleDrawer: (drawer: ActiveDrawerType) => void;
}

export const RightToolbar: React.FC<RightToolbarProps> = ({
  activeDrawer,
  onToggleDrawer,
}) => {
  return (
    <aside className="w-12 bg-[#000000] border-l border-[#1a1a1a] flex flex-col justify-between py-3 items-center z-30 select-none shrink-0">
      {/* Top Icons */}
      <div className="flex flex-col items-center space-y-4">
        {/* Plus icon (Read-only indication) */}
        <button
          onClick={() => alert('Read-Only Mode: Adding new clips or modifying match data is disabled.')}
          className="text-[#00E676] hover:opacity-80 transition p-1"
          title="Create clip (Disabled - Read Only)"
        >
          <Plus className="w-5 h-5 stroke-[2.5]" />
        </button>

        {/* 📊 Analytics Studio */}
        <button
          onClick={() => onToggleDrawer(activeDrawer === 'analytics' ? null : 'analytics')}
          className={`p-1.5 rounded-lg transition ${
            activeDrawer === 'analytics' ? 'text-[#00E676] bg-[#141414]' : 'text-gray-400 hover:text-white'
          }`}
          title="Analytics Studio"
        >
          <BarChart2 className="w-5 h-5" />
        </button>

        {/* 👕 Player Moments */}
        <button
          onClick={() => onToggleDrawer(activeDrawer === 'players' ? null : 'players')}
          className={`p-1.5 rounded-lg transition ${
            activeDrawer === 'players' ? 'text-[#00E676] bg-[#141414]' : 'text-gray-400 hover:text-white'
          }`}
          title="Player Moments"
        >
          <Shirt className="w-5 h-5" />
        </button>

        {/* 📹 Highlights */}
        <button
          onClick={() => onToggleDrawer(activeDrawer === 'highlights' ? null : 'highlights')}
          className={`p-1.5 rounded-lg transition ${
            activeDrawer === 'highlights' ? 'text-[#00E676] bg-[#141414]' : 'text-gray-400 hover:text-white'
          }`}
          title="Highlights"
        >
          <Video className="w-5 h-5" />
        </button>

        {/* ☰ Events List */}
        <button
          onClick={() => onToggleDrawer(activeDrawer === 'events' ? null : 'events')}
          className={`p-1.5 rounded-lg transition ${
            activeDrawer === 'events' ? 'text-[#00E676] bg-[#141414]' : 'text-gray-400 hover:text-white'
          }`}
          title="Events Chronology"
        >
          <List className="w-5 h-5" />
        </button>

        {/* ⚏ Lineup & Formations */}
        <button
          onClick={() => onToggleDrawer(activeDrawer === 'lineup' ? null : 'lineup')}
          className={`p-1.5 rounded-lg transition ${
            activeDrawer === 'lineup' ? 'text-[#00E676] bg-[#141414]' : 'text-gray-400 hover:text-white'
          }`}
          title="Lineup & Formations"
        >
          <LayoutGrid className="w-5 h-5" />
        </button>

        {/* 📄 Summary & Journal */}
        <button
          onClick={() => onToggleDrawer(activeDrawer === 'summary' ? null : 'summary')}
          className={`p-1.5 rounded-lg transition ${
            activeDrawer === 'summary' ? 'text-[#00E676] bg-[#141414]' : 'text-gray-400 hover:text-white'
          }`}
          title="Summary & Journal"
        >
          <FileText className="w-5 h-5" />
        </button>
      </div>

      {/* Bottom Icons */}
      <div className="flex flex-col items-center space-y-3">
        <button
          onClick={() => alert('Veo Analysis Guide: Spacebar to Play/Pause, J/L to skip 10s, D to draw, [ and ] to jump highlights.')}
          className="text-gray-400 hover:text-white transition p-1"
          title="Help & Shortcuts"
        >
          <HelpCircle className="w-5 h-5" />
        </button>
        <button
          onClick={() => onToggleDrawer(activeDrawer ? null : 'highlights')}
          className="text-gray-400 hover:text-white transition p-1"
          title="Toggle Drawer Layout"
        >
          <Columns className="w-5 h-5" />
        </button>
      </div>
    </aside>
  );
};
