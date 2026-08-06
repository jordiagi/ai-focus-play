# Quickstart: Click-First Player Reels

Local setup for development and for running the full pipeline on real footage.
Target machine: Apple Silicon Mac (validated on M4 Max, 64 GB). Everything runs locally;
no cloud accounts or API keys.

## Prerequisites

- **FFmpeg + FFprobe** on PATH: `brew install ffmpeg` (verify: `ffmpeg -version`).
- **Python 3.11+** and **Node 18+**.
- ~2 GB free disk: ~550 MB model weights + per-project artifacts (proxy ≈ 1–2 GB for a
  full match, crops/frames a few hundred MB).

## Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate

# Development (tests run with fake models — no torch needed):
pip install -e ".[dev]"
pytest tests -m "not ml"

# Real pipeline (adds torch/MPS + models):
pip install -e ".[dev,ml]"
python -m src.ml.download_models     # one-time, ~550 MB into the HF cache
python -m src.ml.doctor              # verify: device (mps), models present, ffmpeg found

uvicorn src.app.main:app --reload
```

### Model inventory (downloaded by `download_models`)

| Role | Model | Size |
|---|---|---|
| Player detection | RT-DETRv2 R50 (`PekingU/rtdetr_v2_r50vd`) | ~170 MB |
| Appearance embeddings | DINOv2-small (`facebook/dinov2-small`) | ~90 MB |
| Jersey number OCR | PARSeq (torch.hub, pinned commit) | ~90 MB |
| Click refinement | SAM 2.1 hiera-small (`facebook/sam2.1-hiera-small`) | ~185 MB |

### Environment knobs (defaults in `src/app/config.py`)

- `AI_FOCUS_DEVICE=mps|cpu` — force compute device (default: auto, MPS preferred).
- `ANALYSIS_FPS` (default 6.0) — detection sampling rate; lower = faster, coarser.
- `PYTORCH_ENABLE_MPS_FALLBACK=1` is set automatically for SAM 2 (some ops lack MPS
  kernels; they fall back to CPU).

## Frontend

```bash
cd frontend
npm install
npm run dev        # Vite dev server, proxies to the backend
npm test           # Vitest
```

## First real run

1. Start backend and frontend; open the app.
2. Step 1: drop in a match video (`video/video.mp4` is the repo's test asset).
3. Analysis starts automatically. Expected timings for a 90-min 1080p match on an
   M4 Max — it is normal for this to run for hours; overnight is a supported mode:
   - Getting the video ready (proxy): 10–20 min
   - Watching the match (detection+tracking): 1–2 h
   - Learning what each player looks like: 5–15 min
   - Reading jersey numbers: 10–30 min
4. You don't have to wait: go to Step 2, scrub to a clear moment, click your player.
   Clicks made before analysis reaches that moment are kept as pins and resolve
   automatically.
5. Confirm from the evidence strip, review the coverage timeline, generate and
   download the reel.

## Restart/resume behavior (worth knowing while developing)

- Analysis jobs checkpoint to SQLite (`.local/data/app.db` by default). Killing the
  backend (or the machine sleeping) loses at most ~1,000 analysis frames; on restart the
  job service resumes interrupted jobs from their checkpoints.
- The frontend restores the active project from localStorage and reattaches to progress
  polling on reload.

## Running ML smoke tests (optional, local only)

```bash
cd backend && pytest tests -m ml     # requires the ml extra + downloaded models
```

## Troubleshooting

- `python -m src.ml.doctor` is the first stop: it reports device, each model's cache
  status, and ffmpeg/ffprobe versions.
- Proxy stage fails immediately → check ffmpeg supports `h264_videotoolbox`
  (`ffmpeg -encoders | grep videotoolbox`); the stage falls back to libx264 but logs it.
- MPS out-of-memory during detection → lower the batch size knob or set
  `AI_FOCUS_DEVICE=cpu` (slower, still correct).
- First model use is slow → weights load lazily per stage subprocess; this is expected.
