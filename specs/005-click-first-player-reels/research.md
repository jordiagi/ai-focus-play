# Research & Decision Log: Click-First Player Reels

**Input**: [spec.md](./spec.md)
**Date**: 2026-07-13

Each decision: what was chosen, why, and what was rejected. These are settled — the
implementing agent should not relitigate them.

## D-01: Detector — RT-DETRv2 via HuggingFace `transformers` (no ultralytics)

- **Decision**: `PekingU/rtdetr_v2_r50vd` through `transformers`, filtered to the
  person class, behind a `Detector` protocol. Input size 1280, batch 4–8 on MPS.
- **Why**: Apache-2.0 end to end; `transformers` is already required for the embedder;
  RT-DETRv2 is competitive with YOLOv8 for person detection at this scale; compute time
  is explicitly expendable.
- **Rejected**: ultralytics YOLOv8 — AGPL-3.0 is viral into the codebase and offers no
  decisive accuracy win here. The `Detector` protocol keeps it possible as a private
  opt-in plugin later. Also rejected: keeping the color-segmentation heuristic as a
  fallback (deleted per user decision — it produced untrustworthy boxes and its
  existence would complicate every test seam).

## D-02: Tracker — ByteTrack via `supervision` (MIT)

- **Decision**: `sv.ByteTrack` fed by the detector at `analysis_fps` (default 6).
- **Why**: detector-agnostic, tiny dependency, the standard baseline for sports
  tracking-by-detection; fragmentation is acceptable because clustering re-links
  fragments downstream.
- **Rejected**: `boxmot` trackers (AGPL); DeepSORT variants with built-in ReID (extra
  weights for marginal gain given our clustering stage); the existing hand-rolled IoU
  tracker (deleted).

## D-03: Identity clustering — DINOv2-small embeddings + constrained agglomerative

- **Decision**: mean-pooled DINOv2-small (`facebook/dinov2-small`, ~90 MB) embeddings
  over each tracklet's sampled crops; agglomerative clustering with **temporal-overlap
  cannot-link constraints** (tracklets co-visible for > 0.5 s can never merge), plus
  kit-color and jersey-vote features as soft signals.
- **Why**: the cannot-link constraint does most of the correctness work (two boxes on
  screen at once are two people); DINOv2-small is 10× smaller than SigLIP and adequate
  for same-video re-identification; scikit-learn agglomerative supports connectivity
  constraints without new dependencies.
- **Rejected**: SigLIP embeddings (bigger, no measured win for same-video ReID); OSNet
  (another weights ecosystem; protocol seam allows swapping later); clustering on kit
  color + jersey number alone (fails on same-team, unreadable-number cases — exactly
  the hard cases that matter).

## D-04: Jersey OCR — legibility keyframes → PARSeq → cross-frame voting

- **Decision**: per tracklet, select top-8 keyframes by native-res box height (≥ 60 px)
  and Laplacian-variance sharpness; crop the torso region from the **original**
  full-res video; run PARSeq (`baudm/parseq` via `torch.hub` pinned to a commit,
  ~90 MB); majority-vote per tracklet, then per cluster.
- **Why**: this is the SoccerNet-winning recipe; jersey numbers are illegible in most
  frames, so keyframe selection + voting beats any single-frame OCR. PARSeq is
  Apache-2.0 and small.
- **Rejected**: the 700-line template-matching OCR (deleted — it cannot handle real
  fonts/deformation); MMOCR (heavy install); TrOCR (kept in mind as an alternate
  `TextRecognizer` implementation if PARSeq's hub load is troublesome — the protocol
  makes this a one-file swap); hosted VLM OCR (violates fully-local constraint).

## D-05: SAM 2 scope — escalation only, windowed, never full-match

- **Decision**: SAM 2.1 hiera-small (`facebook/sam2.1-hiera-small`, ~185 MB) runs only
  as a `sam2_refine` job: propagate a mask ±60 s around a clicked moment at 6 fps on
  proxy-resolution frames, then assign existing tracklets to the target cluster by
  mask↔box IoU voting per frame; mint synthetic tracklets from mask boxes only where no
  detection exists. Triggered when a click misses all boxes in an analyzed region, or
  the user fills a coverage gap.
- **Why**: precomputed tracklets are the substrate — clicks label them. Full-match SAM 2
  propagation would take hours per click and drifts; a bounded window gives the
  click-to-recover UX at 2–6 min per invocation. Requires
  `PYTORCH_ENABLE_MPS_FALLBACK=1` (some ops lack MPS kernels).
- **Rejected**: SAM 2 as the primary tracker; running SAM 2 in the API process (memory
  never reclaimed — see D-07).

## D-06: Click resolution — backend hit-test, tracklet-first

- **Decision**: `POST /clicks` hit-tests the click against detections within ±0.5 s on
  the backend; hit → tracklet → cluster → evidence. Misses escalate per D-05; clicks in
  unanalyzed regions become pins resolved at detect_track checkpoints.
- **Why**: keeps the frontend dumb (an `<img>` + divs), keeps hit-test logic testable
  in pytest, and makes the common case instant (SC-002).
- **Rejected**: client-side hit-testing (duplicates geometry logic, needs all boxes
  shipped to the client anyway); running per-click single-frame detection first (the
  full pass already exists or is coming; pins cover the gap).

## D-07: Job infrastructure — subprocess per stage + SQLite state + polling

- **Decision**: a `JobService` in the API process spawns each stage as
  `python -m src.workers.run_stage --job-id <id>`; the child writes
  `progress_pct/progress_message/checkpoint_json` to SQLite every few seconds; cancel =
  SIGTERM; one ML job runs at a time (queued→running claim via a SQLite transaction).
  Frontend polls `GET /jobs` every 2 s.
- **Why**: torch/SAM 2 memory is fully reclaimed on process exit; a crashing stage
  can't take down the API; resume falls out of the checkpoint column; polling matches
  the existing frontend service style and is trivial to implement correctly.
- **Rejected**: the existing `local_runner.py` (a stub that executes nothing — deleted);
  threads in the API process (GIL + memory); Celery/Redis (heavyweight for
  single-user local); SSE/WebSockets (complexity without user-visible benefit at 2 s
  granularity); the `remote_runner.py` GPU-cluster path (out of scope — this Mac only;
  also remove `remote_host` defaults from `config.py`).

## D-08: Proxy video — 720p H.264, UI-only

- **Decision**: `proxy` stage transcodes to `proxy/proxy_720p.mp4` (720p, CRF 27,
  `-g 30` short GOP, audio stripped, `h264_videotoolbox` hardware encode). All UI
  serving (frames, previews, evidence clips, SAM 2 windows) reads the proxy; analysis
  (detection, OCR crops) reads the original at full resolution.
- **Why**: arbitrary-timestamp JPEG extraction from a long-GOP 1080p original is slow;
  short-GOP 720p makes `GET /frame?t=` fast and cheap while native-res crops keep OCR
  quality.
- **Rejected**: serving frames from the original (seek latency); a browser `<video>`
  element with canvas overlays (sync complexity, no benefit for click-on-a-frame).

## D-09: SQLite over the JSON store

- **Decision**: stdlib `sqlite3`, WAL mode, one `app.db`, schema + numbered migrations
  (see [data-model.md](./data-model.md)). Repositories rewritten; `JsonDatabase`
  deleted. Per-frame detections live in SQLite, pixels on disk.
- **Why**: ~500k detection rows per match; the JSON store rewrites the world on every
  call and cannot index by timestamp. No ORM — the repo pattern already exists and
  SQL here is simple.
- **Rejected**: SQLAlchemy (dependency without need); keeping JSON for "small"
  entities alongside SQLite (two sources of truth).

## D-10: Frame index removal

- **Decision**: drop `_compute_frame_index` from `video_ingest_service.py` and the
  `FrameIndexEntry` model.
- **Why**: it was an O(all frames) ffprobe walk whose only consumer disappears — the
  proxy's short GOP + `detections(source_id, ts)` index serve every lookup need.

## D-11: Testing seam — protocols + fakes; ML tests are opt-in

- **Decision**: `Detector`, `Embedder`, `TextRecognizer`, `MaskPropagator` protocols in
  `backend/src/ml/interfaces.py`; pipeline stages take implementations as constructor
  args. `tests/fakes/fake_models.py` replays ground truth. A generated 10 s synthetic
  fixture video (moving colored rectangles with painted numbers + ground-truth JSON)
  exercises real FFmpeg paths with fake models. `pytest -m "not ml"` is the default;
  `@pytest.mark.ml` smoke tests run locally only. ML deps live in an `[project.optional-dependencies] ml`
  extra; all `src/ml/*` imports of torch/transformers are function-local so the base
  install (CI) never imports them.
- **Why**: OR-002; keeps CI fast and weight-free; makes every pipeline stage unit-testable.

## D-12: Checkpoint format — JSON column, stage-owned

- **Decision**: each stage owns its `checkpoint_json` schema (documented in
  data-model.md); detect_track checkpoints every 1,000 analysis frames and resumes by
  re-seeking to `last_ts - 5 s` with a tracker warm-up (warm-up frames re-associate but
  don't re-persist).
- **Why**: simplest thing that survives kill -9 and sleep; the 5 s warm-up avoids
  tracklet-id churn at the seam.
- **Rejected**: pickling tracker state (fragile across versions); a separate
  checkpoint file per job (SQLite row is atomic with status).

## D-13: Existing code kept on purpose

- `artifact_service.py` (path guards are good — extend with proxy/frames/crops/masks/
  exports helpers), `video_ingest_service.py` (validation + probe kept; index dropped),
  `evidence_artifact_service.py` (FFmpeg frame/clip mechanics reused for evidence strips
  and segment previews), `export_service.py` render core (segment extract + concat
  works; the overlay changes from a hardcoded center `drawbox` to an FFmpeg `sendcmd`
  script interpolating the target's real per-frame boxes), routes `exports.py` and the
  evidence-media serving route, the wizard shell, `VideoSourceStep`, `ExportsPage`,
  `apiClient.ts`.

## Model inventory (pinned at implementation time)

| Role | Model | Source | Size | License |
|---|---|---|---|---|
| Detector | RT-DETRv2 R50 | HF `PekingU/rtdetr_v2_r50vd` | ~170 MB | Apache-2.0 |
| Embedder | DINOv2-small | HF `facebook/dinov2-small` | ~90 MB | Apache-2.0 |
| Jersey OCR | PARSeq | `torch.hub` baudm/parseq @ pinned commit | ~90 MB | Apache-2.0 |
| Click refine | SAM 2.1 hiera-small | HF `facebook/sam2.1-hiera-small` | ~185 MB | Apache-2.0 |

Total ≈ 550 MB, cached in the HF cache dir; `python -m src.ml.download_models`
prefetches, `python -m src.ml.doctor` verifies device + models + ffmpeg.

## Performance envelope (M4 Max, 90-min 1080p match, defaults)

| Stage | Rough time | Knobs |
|---|---|---|
| proxy | 10–20 min | videotoolbox hw encode |
| detect_track (6 fps, ~32k frames) | 1–2 h | `analysis_fps` 4–8; input size 960–1280; checkpoint/1k frames |
| embed_cluster (~30–40k crops) | 5–15 min | crop sampling interval 2→3 s |
| jersey_ocr | 10–30 min | keyframes per tracklet 8→4 |
| sam2_refine (per click miss) | 2–6 min | window ±30–60 s |
| export | 5–15 min | videotoolbox encode |

Automated chain ≈ 2–3.5 h → SC-005 satisfied with margin.
