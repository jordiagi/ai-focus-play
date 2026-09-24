import React, { useRef, useState, useEffect } from 'react';
import { Drawing, DrawingCoordinate } from '../../types';
import { 
  Pencil, ArrowUpRight, Circle, Sun, Type, Trash2, Check, X, Camera, Undo
} from 'lucide-react';

interface TelestratorProps {
  matchId: string;
  currentTime: number;
  existingDrawings: Drawing[];
  onSaveDrawing: (drawing: Omit<Drawing, 'id'>) => void;
  onClose: () => void;
  videoElement?: HTMLVideoElement | null;
}

type ToolType = 'arrow' | 'spotlight' | 'circle' | 'pen' | 'text';

const COLORS = ['#00E676', '#FFD700', '#2979FF', '#FF5252', '#FFFFFF'];

const renderDrawing = (
  ctx: CanvasRenderingContext2D,
  tool: ToolType,
  color: string,
  coords: DrawingCoordinate[],
  w: number,
  h: number,
  label?: string
) => {
  if (coords.length === 0) return;

  ctx.strokeStyle = color;
  ctx.fillStyle = color;
  ctx.lineWidth = 3;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';

  const p0 = { x: coords[0].x * w, y: coords[0].y * h };
  const p1 = coords.length > 1 ? { x: coords[coords.length - 1].x * w, y: coords[coords.length - 1].y * h } : p0;

  if (tool === 'pen') {
    ctx.beginPath();
    ctx.moveTo(p0.x, p0.y);
    for (let i = 1; i < coords.length; i++) {
      ctx.lineTo(coords[i].x * w, coords[i].y * h);
    }
    ctx.stroke();
  } else if (tool === 'arrow') {
    // Draw line from p0 to p1
    ctx.beginPath();
    ctx.moveTo(p0.x, p0.y);
    ctx.lineTo(p1.x, p1.y);
    ctx.stroke();

    // Arrow head
    const angle = Math.atan2(p1.y - p0.y, p1.x - p0.x);
    const headLen = 16;
    ctx.beginPath();
    ctx.moveTo(p1.x, p1.y);
    ctx.lineTo(p1.x - headLen * Math.cos(angle - Math.PI / 6), p1.y - headLen * Math.sin(angle - Math.PI / 6));
    ctx.lineTo(p1.x - headLen * Math.cos(angle + Math.PI / 6), p1.y - headLen * Math.sin(angle + Math.PI / 6));
    ctx.closePath();
    ctx.fill();
  } else if (tool === 'circle') {
    const rx = Math.max(20, Math.abs(p1.x - p0.x));
    const ry = Math.max(12, Math.abs(p1.y - p0.y) || rx * 0.5);
    ctx.beginPath();
    ctx.ellipse(p0.x, p0.y, rx, ry, 0, 0, Math.PI * 2);
    ctx.stroke();
    ctx.fillStyle = color + '22'; // semi-transparent fill
    ctx.fill();
  } else if (tool === 'spotlight') {
    const radius = Math.max(35, Math.hypot(p1.x - p0.x, p1.y - p0.y));
    // Outer dimming
    ctx.save();
    ctx.fillStyle = 'rgba(0, 0, 0, 0.4)';
    ctx.fillRect(0, 0, w, h);
    // Clear spotlight area
    ctx.globalCompositeOperation = 'destination-out';
    ctx.beginPath();
    ctx.arc(p0.x, p0.y, radius, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();

    // Spotlight glow ring
    ctx.beginPath();
    ctx.arc(p0.x, p0.y, radius, 0, Math.PI * 2);
    ctx.strokeStyle = color;
    ctx.lineWidth = 3;
    ctx.stroke();
  } else if (tool === 'text' && label) {
    ctx.font = 'bold 16px sans-serif';
    ctx.fillStyle = 'black';
    ctx.fillRect(p0.x - 4, p0.y - 20, ctx.measureText(label).width + 8, 26);
    ctx.fillStyle = color;
    ctx.fillText(label, p0.x, p0.y);
  }
};

export const TelestratorCanvas: React.FC<TelestratorProps> = ({
  currentTime,
  existingDrawings,
  onSaveDrawing,
  onClose,
  videoElement,
}) => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [selectedTool, setSelectedTool] = useState<ToolType>('arrow');
  const [selectedColor, setSelectedColor] = useState<string>('#00E676');
  const [isDrawing, setIsDrawing] = useState(false);
  const [currentCoords, setCurrentCoords] = useState<DrawingCoordinate[]>([]);
  const [textInput, setTextInput] = useState('');
  const [textPos, setTextPos] = useState<DrawingCoordinate | null>(null);

  // Redraw canvas whenever existing drawings or currentCoords change
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Match canvas internal resolution to display size
    const rect = canvas.getBoundingClientRect();
    if (canvas.width !== rect.width || canvas.height !== rect.height) {
      canvas.width = rect.width;
      canvas.height = rect.height;
    }

    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw existing drawings close to currentTime
    const relevant = existingDrawings.filter(d => Math.abs(d.timestamp - currentTime) <= 1.0);
    relevant.forEach(d => renderDrawing(ctx, d.tool_type, d.color, d.coordinates, canvas.width, canvas.height, d.text_label));

    // Draw current active drawing in progress
    if (currentCoords.length > 0) {
      renderDrawing(ctx, selectedTool, selectedColor, currentCoords, canvas.width, canvas.height, textInput);
    }
  }, [existingDrawings, currentCoords, selectedTool, selectedColor, currentTime, textInput]);


  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width;
    const y = (e.clientY - rect.top) / rect.height;

    if (selectedTool === 'text') {
      setTextPos({ x, y });
      return;
    }

    setIsDrawing(true);
    setCurrentCoords([{ x, y }]);
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isDrawing) return;
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width;
    const y = (e.clientY - rect.top) / rect.height;

    if (selectedTool === 'pen') {
      setCurrentCoords(prev => [...prev, { x, y }]);
    } else {
      // Arrow, circle, spotlight use start point + current drag point
      setCurrentCoords(prev => [prev[0], { x, y }]);
    }
  };

  const handleMouseUp = () => {
    if (!isDrawing) return;
    setIsDrawing(false);
  };

  const handleSave = () => {
    if (selectedTool === 'text' && textPos && textInput.trim()) {
      onSaveDrawing({
        match_id: '',
        timestamp: currentTime,
        tool_type: 'text',
        color: selectedColor,
        coordinates: [textPos],
        text_label: textInput.trim(),
      });
      setTextInput('');
      setTextPos(null);
      return;
    }

    if (currentCoords.length > 0) {
      onSaveDrawing({
        match_id: '',
        timestamp: currentTime,
        tool_type: selectedTool,
        color: selectedColor,
        coordinates: currentCoords,
      });
      setCurrentCoords([]);
    }
  };

  const handleUndo = () => {
    if (currentCoords.length > 0) {
      if (selectedTool === 'pen' && currentCoords.length > 5) {
        setCurrentCoords(prev => prev.slice(0, Math.max(1, prev.length - 10)));
      } else {
        setCurrentCoords([]);
      }
    }
  };

  const handleExportSnapshot = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const exportCanvas = document.createElement('canvas');
    exportCanvas.width = canvas.width || 1280;
    exportCanvas.height = canvas.height || 720;
    const ctx = exportCanvas.getContext('2d');
    if (!ctx) return;

    // Draw video frame if accessible
    if (videoElement && videoElement.readyState >= 2) {
      try {
        ctx.drawImage(videoElement, 0, 0, exportCanvas.width, exportCanvas.height);
      } catch {
        ctx.fillStyle = '#14281e';
        ctx.fillRect(0, 0, exportCanvas.width, exportCanvas.height);
      }
    } else {
      ctx.fillStyle = '#14281e';
      ctx.fillRect(0, 0, exportCanvas.width, exportCanvas.height);
    }

    // Draw annotations overlay
    ctx.drawImage(canvas, 0, 0);

    // Watermark
    ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
    ctx.fillRect(12, exportCanvas.height - 36, 170, 26);
    ctx.fillStyle = '#00E676';
    ctx.font = 'bold 12px sans-serif';
    const mins = Math.floor(currentTime / 60);
    const secs = Math.floor(currentTime % 60);
    ctx.fillText(`VEO COACH • ${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`, 20, exportCanvas.height - 18);

    try {
      const dataUrl = exportCanvas.toDataURL('image/png');
      const a = document.createElement('a');
      a.href = dataUrl;
      a.download = `veo-telestration-${Math.round(currentTime)}s.png`;
      a.click();
    } catch (err) {
      console.warn('Snapshot download failed:', err);
    }
  };

  return (
    <div className="absolute inset-0 z-20 pointer-events-auto flex flex-col justify-between">
      {/* Top Floating Toolbar */}
      <div className="mx-auto mt-4 bg-[#161a23]/95 backdrop-blur border border-[#2d3342] rounded-xl px-3 py-2 shadow-2xl flex items-center space-x-3 z-30">
        <span className="text-xs font-bold text-gray-300 uppercase tracking-wider pr-2 border-r border-[#2d3342]">
          Telestrator
        </span>

        {/* Tools */}
        <div className="flex items-center space-x-1">
          <button
            onClick={() => setSelectedTool('arrow')}
            className={`p-1.5 rounded-lg transition ${selectedTool === 'arrow' ? 'bg-[#00E676] text-black font-bold' : 'text-gray-300 hover:bg-[#202634]'}`}
            title="Directional Arrow"
          >
            <ArrowUpRight className="w-4 h-4" />
          </button>
          <button
            onClick={() => setSelectedTool('circle')}
            className={`p-1.5 rounded-lg transition ${selectedTool === 'circle' ? 'bg-[#00E676] text-black font-bold' : 'text-gray-300 hover:bg-[#202634]'}`}
            title="Player Tactical Ring"
          >
            <Circle className="w-4 h-4" />
          </button>
          <button
            onClick={() => setSelectedTool('spotlight')}
            className={`p-1.5 rounded-lg transition ${selectedTool === 'spotlight' ? 'bg-[#00E676] text-black font-bold' : 'text-gray-300 hover:bg-[#202634]'}`}
            title="Player Spotlight"
          >
            <Sun className="w-4 h-4" />
          </button>
          <button
            onClick={() => setSelectedTool('pen')}
            className={`p-1.5 rounded-lg transition ${selectedTool === 'pen' ? 'bg-[#00E676] text-black font-bold' : 'text-gray-300 hover:bg-[#202634]'}`}
            title="Freehand Pen"
          >
            <Pencil className="w-4 h-4" />
          </button>
          <button
            onClick={() => setSelectedTool('text')}
            className={`p-1.5 rounded-lg transition ${selectedTool === 'text' ? 'bg-[#00E676] text-black font-bold' : 'text-gray-300 hover:bg-[#202634]'}`}
            title="Text Label"
          >
            <Type className="w-4 h-4" />
          </button>
        </div>

        <div className="h-5 w-[1px] bg-[#2d3342]" />

        {/* Color Palette */}
        <div className="flex items-center space-x-1.5">
          {COLORS.map(c => (
            <button
              key={c}
              onClick={() => setSelectedColor(c)}
              className={`w-4 h-4 rounded-full border-2 transition ${selectedColor === c ? 'border-white scale-125' : 'border-transparent'}`}
              style={{ backgroundColor: c }}
            />
          ))}
        </div>

        <div className="h-5 w-[1px] bg-[#2d3342]" />

        {/* Actions */}
        <button
          onClick={handleExportSnapshot}
          className="p-1.5 text-gray-300 hover:text-[#00E676] hover:bg-[#202634] rounded-lg transition"
          title="Export Frame Snapshot PNG"
          aria-label="Export frame snapshot"
        >
          <Camera className="w-4 h-4" />
        </button>

        <button
          onClick={handleUndo}
          disabled={currentCoords.length === 0}
          className="p-1.5 text-gray-400 hover:text-white disabled:opacity-30 hover:bg-[#202634] rounded-lg transition"
          title="Undo active stroke"
          aria-label="Undo active stroke"
        >
          <Undo className="w-4 h-4" />
        </button>

        <button
          onClick={() => setCurrentCoords([])}
          className="p-1.5 text-gray-400 hover:text-white hover:bg-[#202634] rounded-lg transition"
          title="Clear active"
        >
          <Trash2 className="w-4 h-4" />
        </button>
        <button
          onClick={handleSave}
          disabled={currentCoords.length === 0 && !(selectedTool === 'text' && textInput)}
          className="flex items-center space-x-1 bg-[#00E676] disabled:opacity-40 hover:bg-[#00c968] text-black font-semibold text-xs px-2.5 py-1 rounded-md transition"
        >
          <Check className="w-3.5 h-3.5" />
          <span>Pin</span>
        </button>
        <button
          onClick={onClose}
          className="p-1 text-gray-400 hover:text-white hover:bg-[#202634] rounded-lg transition"
          title="Exit Telestrator (Hotkey D)"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Text input prompt if text tool active */}
      {selectedTool === 'text' && textPos && (
        <div className="absolute top-20 left-1/2 -translate-x-1/2 bg-[#161a23] border border-[#2d3342] p-2 rounded-lg flex items-center space-x-2 z-30">
          <input
            type="text"
            placeholder="Type tactical note..."
            value={textInput}
            onChange={e => setTextInput(e.target.value)}
            className="bg-[#0f1218] text-xs text-white px-2 py-1 rounded border border-[#2d3342] focus:outline-none focus:border-[#00E676]"
            autoFocus
          />
          <button
            onClick={handleSave}
            className="bg-[#00E676] text-black text-xs font-bold px-2 py-1 rounded"
          >
            Add
          </button>
        </div>
      )}

      {/* Interactive Drawing Canvas */}
      <canvas
        ref={canvasRef}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        className="w-full h-full cursor-crosshair"
      />
    </div>
  );
};
