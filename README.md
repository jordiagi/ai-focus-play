# Veo Video Analysis Replication (`ai-focus-play`)

A full-stack soccer match video analysis platform replicating the core capabilities of [Veo](https://app.veo.co).

## Architecture

- **Backend**: FastAPI (Python 3.12) running at `http://127.0.0.1:8000`.
- **Frontend**: React 19 + TypeScript + Tailwind 4 + Vite 8 running at `http://127.0.0.1:5173`.
- **Database**: SQLite (via SQLAlchemy) stored in `backend/.local/data/veo.db`.
- **Media**: Local match videos, extracted clips, and thumbnails in `backend/.local/media/`.

## Key Capabilities

1. **Match Video Player**:
   - Follow-Cam & Pan & Zoom modes with smooth direct-manipulation gestures.
   - Hotkey `D` canvas Telestrator (arrows, freehand pen, spotlight, circle, text).
   - Event timeline with goal confetti, instant seeking, and automated highlight reel playback.
   - Synchronized top-down 2D Pitch Radar minimap tracking players and ball.
2. **Analysis & Intelligence**:
   - Explicit analysis modes: Demo, Heuristic, and AI.
   - Ball detection with constant-velocity Kalman filter tracking.
   - Metric-space Hungarian assignment tracker (pitch-scale Euclidean cost).
   - Torso Lab chroma median clustering for team assignment.
   - Grounded match statistics and heuristic event spotting (kickoff, shot, goal, corner).
3. **Coaching & Studio**:
   - Match Events list, Player Moments filter, Analytics Studio (possession by thirds, shot map, pass breakdown), Lineups, Drawings, and Match Journal.
   - Highlight clip export as downloadable ZIP.

## Getting Started

### Backend
```bash
cd backend
source .venv/bin/activate
# Run from repo root:
cd ..
uvicorn backend.src.app.main:app --host 127.0.0.1 --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Tests
```bash
backend/.venv/bin/python -m pytest backend/tests -v
```
