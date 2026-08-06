# Backend

FastAPI API + background worker services for the click-first player-reel pipeline.
Everything runs locally; no cloud accounts or hosted inference. See
[`../specs/005-click-first-player-reels/quickstart.md`](../specs/005-click-first-player-reels/quickstart.md)
for the full local setup and first-run walkthrough.

## Setup

```bash
cd backend
python -m venv .venv && source .venv/bin/activate

# Development — tests run with fake models, no torch/weights needed:
pip install -e ".[dev]"
pytest tests -m "not ml"
uvicorn src.app.main:app --reload

# Real pipeline — adds torch/MPS + model weights:
pip install -e ".[dev,ml]"
python -m src.ml.download_models   # one-time, ~550 MB into the HF cache
python -m src.ml.doctor            # verify device (MPS/CPU), models present, ffmpeg found
```

`pytest tests -m ml` runs the model-dependent smoke tests (requires the `ml` extra +
downloaded weights) and is intentionally excluded from the default run (OR-002).

## Pipeline

Attaching a source video auto-queues a background job chain (each stage checkpoints to
SQLite and is resumable after process death):

`proxy → detect_track → embed_cluster → jersey_ocr → assemble_candidates`

with two on-demand stages: `sam2_refine` (bounded click-driven mask propagation) and
`export` (reel rendering). Stages live in `src/services/pipeline/`, are registered in
`src/workers/run_stage.py`, and run as `python -m src.workers.run_stage --job-id <id>`
subprocesses managed by `JobService`.

Models (open-source, local only): RT-DETRv2 (detection), DINOv2 (appearance
embeddings), PARSeq (jersey OCR), SAM 2.1 (click refinement). Fake implementations
behind stable protocols (`src/ml/interfaces.py`) back the default test run.

## Storage & artifacts

- Metadata: SQLite (`AI_FOCUS_DB_PATH`, default `.local/data/app.db`) — schema in
  `src/storage/schema.sql`, repositories in `src/storage/`.
- Media artifacts under `AI_FOCUS_DATA_DIR/<project-id>/`: `proxy/` (720p proxy used for
  all UI serving), `frames/` (LRU-capped click frames), `crops/`, `evidence/`,
  `exports/`. Evidence/timeline media is served via
  `/projects/{project_id}/evidence-media/{artifact}` with path-traversal guards.

Relevant settings: `AI_FOCUS_VIDEO_ROOT` (trusted local video folder),
`AI_FOCUS_EVIDENCE_SAMPLE_COUNT`, `AI_FOCUS_EVIDENCE_CLIP_SECONDS`, and the pipeline
knobs in `src/app/config.py` (`ANALYSIS_FPS`, `crop_interval_s`, `sam2_window_s`,
`frames_cache_max`, `AI_FOCUS_DEVICE`).

## Reels & coverage (Phase 9)

After a target identity is confirmed, `TimelineService` derives appearance segments
(merge gaps < 2 s, drop < 1.5 s, pad ± 1.5 s, score by duration) exposed at
`GET /projects/{id}/timeline` and toggled per-segment via `PATCH .../timeline/{seg}`.
`POST /projects/{id}/exports` (gated on a confirmed target) enqueues the `export` stage,
which renders the included segments chronologically to an MP4 with an optional target
marker that follows the player's real per-frame boxes (FFmpeg `sendcmd` → `drawbox`).

Do not reintroduce placeholder/synthetic evidence, the JSON datastore, or the legacy
heuristic CV as fallbacks (FR-020).
