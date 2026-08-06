# Tasks: Click-First Player Reels

**Input**: Design documents from `/specs/005-click-first-player-reels/`
**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Verification**: Automated tests required (OR-002 mandates that all default tests run
without model weights, using fakes). Manual validation required (OR-004 mandates a real
video walk-through per the checklists).

## Execution rules for the implementing agent

- Work phases strictly in order. **Do not start phase N+1 until phase N's Checkpoint
  passes.** Within a phase, `[P]` tasks may be done in any order/parallel.
- Every task names its file(s). Acceptance for code tasks is the runnable command in the
  phase Checkpoint plus the task-specific tests listed with it.
- Tests-first within each phase: write the listed test tasks before their
  implementation tasks.
- Tasks marked **[MANUAL CHECKPOINT]** require a human to run/inspect something. Stop
  and ask for human review; do not self-certify visual quality.
- Decisions in [research.md](./research.md) (D-01…D-13) are settled; do not substitute
  models, storage, or job architecture.
- UI tasks must satisfy the exact section of [contracts/ui-flow.md](./contracts/ui-flow.md)
  they reference, including normative copy strings.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: parallel-safe (different files, no dependency on incomplete tasks).
- **[Story]**: US1/US2/US3 traceability where applicable.

---

## Phase 0: SQLite Foundation

**Purpose**: Replace the whole-file JSON store with SQLite (FR-017). Everything else
hangs off this.

- [X] T001 Create SQLite connection factory (WAL mode, foreign keys on, row factory) and
      migration runner (`schema_migrations` table, applies `schema.sql` as v1, then
      numbered files in `backend/src/storage/migrations/`) in `backend/src/storage/db.py`
- [X] T002 Write the full v1 schema from [data-model.md](./data-model.md) (all 12 tables
      + indexes) in `backend/src/storage/schema.sql`
- [X] T003 [P] Unit tests: migration idempotency, WAL enabled, all tables/indexes
      present, in `backend/tests/unit/test_db.py`
- [X] T004 Rewrite project persistence (CRUD, status transitions, jersey_hint,
      target_cluster_id) on SQLite in `backend/src/storage/project_repository.py`
- [X] T005 [P] Rewrite source-video persistence (insert from ingest, proxy fields) in a
      new `backend/src/storage/source_repository.py`
- [X] T006 [P] New repositories for detections/tracklets/crops/embeddings/clusters/votes
      (bulk-insert APIs; `detections` range query by `(source_id, ts±0.5)`) in
      `backend/src/storage/analysis_repository.py`
- [X] T007 [P] New repositories for clicks and appearance segments in
      `backend/src/storage/selection_repository.py`
- [X] T008 Rewrite output persistence (reel_outputs incl. `segment_ids_json`) in
      `backend/src/storage/output_repository.py` (adapt existing output storage)
- [X] T009 Delete `backend/src/storage/database.py` (JsonDatabase) and rewire
      `backend/src/app/dependencies.py` to construct repositories from `db.py`;
      update/replace any existing contract tests that assumed JSON storage under
      `backend/tests/`
- [X] T010 Update domain models per data-model.md: rewrite
      `backend/src/domain/models/detection.py` (Detection, Tracklet, IdentityCluster,
      JerseyVote); extend `backend/src/domain/models/video.py` (proxy fields, drop
      FrameIndexEntry); add `backend/src/domain/models/pipeline.py` and
      `backend/src/domain/models/selection.py`; update `__init__.py` exports

**Checkpoint 0**: `cd backend && pytest tests -m "not ml"` green; `uvicorn src.app.main:app`
boots; POST /projects + GET /projects work against SQLite.

---

## Phase 1: Job Infrastructure (US2 backbone)

**Purpose**: Real background jobs with real progress, cancel, and resume (FR-007,
FR-009, FR-010). Built new — the old runners are stubs.

- [X] T011 [P] [US2] Contract test for `GET /projects/{id}/jobs` and
      `POST /jobs/{id}/cancel` response shapes in
      `backend/tests/contract/test_jobs_api.py`
- [X] T012 [P] [US2] Unit tests for enqueue/claim (single ML job at a time via SQLite
      transaction), cancel, checkpoint write/read in
      `backend/tests/unit/test_job_service.py`
- [X] T013 [US2] Implement `JobService` (enqueue chain, claim, spawn subprocess, SIGTERM
      cancel, mark failed on nonzero exit, requeue-from-checkpoint on startup for jobs
      left `running` by a dead process) in `backend/src/services/job_service.py`
- [X] T014 [US2] Implement the stage subprocess entrypoint
      (`python -m src.workers.run_stage --job-id <id>`: load job row, dispatch to a
      stage registry, write progress/checkpoint every few seconds, handle SIGTERM
      gracefully) with a built-in `sleep_demo` stage, in
      `backend/src/workers/run_stage.py`
- [X] T015 [US2] Add `GET /projects/{id}/jobs` and `POST /jobs/{id}/cancel` routes per
      [contracts/api.yaml](./contracts/api.yaml) in
      `backend/src/api/routes/jobs.py` (+ register in `backend/src/api/__init__.py`)
- [X] T016 [US2] Integration test: enqueue `sleep_demo` → poll shows increasing real
      progress → cancel mid-run → status `cancelled`; kill the child process → restart
      service → job resumes from checkpoint, in
      `backend/tests/integration/test_job_lifecycle.py`
- [X] T017 [P] [US2] Delete `backend/src/workers/local_runner.py`,
      `backend/src/workers/remote_runner.py`, `backend/src/workers/base.py`,
      `backend/src/workers/detection_worker.py`; remove `remote_*` settings from
      `backend/src/app/config.py`; add pipeline knobs (`analysis_fps=6.0`,
      `crop_interval_s=2.0`, `ocr_keyframes_per_tracklet=8`, `sam2_window_s=60.0`,
      `frames_cache_max=500`) with env overrides

**Checkpoint 1**: `pytest backend/tests/integration/test_job_lifecycle.py` green — live
progress, cancel, and kill/resume all demonstrated with the demo stage.

---

## Phase 2: ML Foundation

**Purpose**: Model management, protocols, fakes (OR-001, OR-002, D-11).

- [X] T018 [P] Define `Detector`, `Embedder`, `TextRecognizer`, `MaskPropagator`
      protocols (typed dataclass inputs/outputs, no torch imports at module level) in
      `backend/src/ml/interfaces.py`
- [X] T019 [P] Device selection (`get_device()`: MPS→CPU fallback, `AI_FOCUS_DEVICE`
      override, sets `PYTORCH_ENABLE_MPS_FALLBACK=1`) in `backend/src/ml/device.py`
- [X] T020 [P] Pinned model registry (ids, revisions, sizes per research.md inventory) in
      `backend/src/ml/model_registry.py`
- [X] T021 `python -m src.ml.download_models` (prefetch all weights to HF cache with
      progress) and `python -m src.ml.doctor` (report device, per-model presence,
      ffmpeg/ffprobe versions) in `backend/src/ml/download_models.py` and
      `backend/src/ml/doctor.py`
- [X] T022 [P] Fake implementations replaying ground-truth JSON (`FakeDetector`,
      `FakeEmbedder` — deterministic vectors per identity, `FakeOCR`,
      `FakeMaskPropagator`) in `backend/tests/fakes/fake_models.py`
- [X] T023 [P] Synthetic fixture generator: 10 s 640×360 MP4 of moving colored
      rectangles with painted digits + ground-truth JSON (per-frame boxes, identities,
      numbers), invoked via pytest fixture with caching, in
      `backend/tests/fixtures/make_synthetic_match.py`
- [X] T024 Add the `ml` optional-dependency extra per [plan.md](./plan.md) to
      `backend/pyproject.toml`; add the `ml` pytest marker to backend pytest config;
      verify base install imports the app without torch

**Checkpoint 2**: fresh venv with base+dev only → `pytest backend/tests -m "not ml"`
green; with `ml` extra → `python -m src.ml.doctor` reports MPS, all models, ffmpeg.

---

## Phase 3: Proxy + Frame Plumbing (US1/US2 substrate)

**Purpose**: 720p proxy and the frame endpoints that power the click UI (D-08).

- [X] T025 [P] [US1] Contract tests for `GET /projects/{id}/frame?t=` (jpeg bytes; 409
      with normative copy when proxy pending) and `GET /frame-detections?t=`
      (`analyzed:false` + empty boxes pre-analysis) in
      `backend/tests/contract/test_frames_api.py`
- [X] T026 [P] Extend artifact paths (`proxy_path()`, `frames_dir()`,
      `crops_dir(tracklet_id)`, `masks_dir(click_id)`, `exports_dir()`; keep traversal
      guards) in `backend/src/services/artifact_service.py` + tests in
      `backend/tests/unit/test_artifact_service.py`
- [X] T027 [US2] Implement the `proxy` stage (FFmpeg → 720p CRF 27 `-g 30` no-audio,
      `h264_videotoolbox` with libx264 fallback; set `source_videos.proxy_*`) in
      `backend/src/services/pipeline/proxy_stage.py`, registered in `run_stage.py`
- [X] T028 [US1] Frame service (extract JPEG at t from proxy via FFmpeg, cache in
      `frames/`, LRU prune at `frames_cache_max`) in
      `backend/src/services/frame_service.py`
- [X] T029 [US1] Add `GET /frame` and `GET /frame-detections` routes (detections via
      `analysis_repository` range query; `ts_actual` = nearest sampled frame) in
      `backend/src/api/routes/frames.py`
- [X] T030 [US1] Rework source attach: `POST /projects/{id}/source` (multipart or
      file_path; sync validate+probe via existing `video_ingest_service`, minus frame
      index; auto-queue proxy→…→assemble_candidates chain; 202 shape per api.yaml) in
      `backend/src/api/routes/sources.py`; add `POST /projects/{id}/pipeline/run`
- [X] T031 [P] [US1] Frontend: `FrameClickSelector` component — img frame, debounced
      range scrubber, keyboard bindings, normalized-coord click capture, overlay divs
      from frame-detections — per ui-flow.md §2b, in
      `frontend/src/features/projects/FrameClickSelector.tsx` with tests in
      `frontend/src/features/projects/FrameClickSelector.test.tsx`
- [X] T032 [P] [US2] Frontend: `AnalysisProgressCard` with exact stage-label mapping,
      minutes-watched formatting, Retry → pipeline/run, per ui-flow.md §2a, in
      `frontend/src/features/projects/AnalysisProgressCard.tsx` (+ test file)
- [X] T033 [US1] Frontend service methods (`attachSource`, `getJobs`, `runPipeline`,
      frame URL helpers) in `frontend/src/services/projects.ts` and
      `frontend/src/services/sources.ts`; extend types in
      `frontend/src/features/projects/guidedTypes.ts`

**Checkpoint 3**: integration test uploads the synthetic fixture, proxy job completes,
`GET /frame?t=` returns a real JPEG (`backend/tests/integration/test_frame_serving.py` —
include in T025 or here); in the browser: upload → scrub any timestamp.

---

## Phase 4: Detection + Tracking

**Purpose**: The real CV backbone (D-01, D-02), checkpointed (FR-009).

- [X] T034 [P] [US2] Unit tests with `FakeDetector` + synthetic ground truth: tracklet
      persistence, crop sampling cadence, checkpoint write per 1,000 frames,
      resume-with-warmup produces no duplicate detections, pin resolution at
      checkpoint, in `backend/tests/unit/test_detect_track_stage.py`
- [X] T035 RT-DETRv2 `Detector` implementation (person class, input 1280, MPS batch,
      function-local imports) in `backend/src/ml/impl/rtdetr_detector.py`
      (+ `@pytest.mark.ml` smoke test in `backend/tests/ml/test_rtdetr_smoke.py`)
- [X] T036 [US2] Implement `detect_track_stage`: stream original via
      `ffmpeg -vf fps={analysis_fps}` rawvideo pipe → Detector → `sv.ByteTrack` →
      bulk-persist detections/tracklets; save crops every `crop_interval_s` with
      sharpness + bbox height metadata; checkpoint `{"last_ts"}` per 1,000 frames;
      resume re-seeks `last_ts-5s` with tracker warm-up; resolve pending pins each
      checkpoint; progress = minutes watched; in
      `backend/src/services/pipeline/detect_track_stage.py`
- [X] T037 [US1] Wire real boxes into `GET /frame-detections` (nearest sampled frame
      within ±0.5 s → `ts_actual`, `analyzed:true`) — extend
      `backend/src/api/routes/frames.py` + contract test update in
      `backend/tests/contract/test_frames_api.py`
- [X] T038 [MANUAL CHECKPOINT] [US2] Run detect_track on `video/video.mp4`; human
      verifies in the scrubber: boxes on ≥90% of clearly visible players at 5 spot-check
      timestamps; then kill the backend mid-run, restart, verify resume from checkpoint
      (record results in `specs/005-click-first-player-reels/checklists/manual-validation.md`)

**Checkpoint 4**: T034 tests green; T038 human-approved.

---

## Phase 5: Embeddings + Identity Clustering

**Purpose**: Group tracklets into confirmable identities (FR-011, D-03).

- [X] T039 [P] [US1] Unit tests with `FakeEmbedder`: two synthetic identities cluster
      into two clusters; temporally overlapping tracklets NEVER merge (cannot-link
      invariant); `user_removed` tracklets stay excluded after re-cluster; in
      `backend/tests/unit/test_embed_cluster_stage.py`
- [X] T040 DINOv2 `Embedder` implementation (batch 64, mean-pool per tracklet) in
      `backend/src/ml/impl/dinov2_embedder.py` (+ smoke test in `backend/tests/ml/`)
- [X] T041 [US1] Implement `embed_cluster_stage`: embed crops → tracklet vectors; kit
      color via HSV k-means on torso ROI; agglomerative clustering with temporal
      cannot-link connectivity; write `identity_clusters` (+ rep crop, screen time);
      checkpoint embedded ids; in
      `backend/src/services/pipeline/embed_cluster_stage.py`
- [X] T042 [US1] Implement `assemble_candidates_stage`: rank clusters (screen time ×
      jersey-hint agreement once votes exist), pick evidence crops spread across the
      timeline (8–12), generate any missing thumbnails/preview clips via
      `evidence_artifact_service`; set project status `awaiting_target_selection`; in
      `backend/src/services/pipeline/assemble_candidates_stage.py`
- [X] T043 [US1] `GET /projects/{id}/candidates` route per api.yaml (evidence media
      URIs resolve through the kept evidence-media route) in
      `backend/src/api/routes/projects.py`, contract test in
      `backend/tests/contract/test_candidates_api.py`

**Checkpoint 5**: full fake-model pipeline over the synthetic fixture yields ≥2 correct
clusters and a populated `/candidates` response
(`backend/tests/integration/test_analysis_chain.py`).

---

## Phase 6: Jersey OCR

**Purpose**: Numbers as a supporting cue (FR-006, D-04).

- [X] T044 [P] [US1] Unit tests with `FakeOCR`: keyframe selection honors bbox-height ≥
      60 px + sharpness ranking; majority voting per tracklet and per cluster; zero
      legible readings → cluster `jersey_number` null and project-level
      "no readable numbers" flag; in `backend/tests/unit/test_jersey_ocr_stage.py`
- [X] T045 PARSeq `TextRecognizer` implementation (torch.hub pinned commit, digits-only
      postfilter) in `backend/src/ml/impl/parseq_ocr.py` (+ smoke test)
- [X] T046 [US1] Implement `jersey_ocr_stage`: pick keyframes per tracklet, crop torso
      from the ORIGINAL video at native res, recognize, write `jersey_votes`, aggregate
      to clusters; checkpoint done tracklet ids; in
      `backend/src/services/pipeline/jersey_ocr_stage.py`
- [X] T047 [US1] `PUT /projects/{id}/jersey-hint` route + hint-aware candidate ranking +
      `jersey_agreement` fields in `/candidates` (update
      `backend/src/api/routes/projects.py` + contract test)

**Checkpoint 6**: T044 green; synthetic-fixture chain shows voted numbers on clusters;
real-video numbers spot-checked during Phase 7's manual checkpoint.

---

## Phase 7: Click-to-Confirm UX (US1 core)

**Purpose**: The product's heart — click → evidence → confirm (FR-001…FR-006).

- [X] T048 [P] [US1] Contract tests for `POST /clicks` (all four resolutions),
      `GET /clicks`, `POST /target`, `DELETE /target`, `POST /target/adjust` in
      `backend/tests/contract/test_clicks_target_api.py`
- [X] T049 [P] [US1] Unit tests for hit-testing (point-in-box ±0.5 s window; nearest box
      wins on overlap; miss → escalation decision; unanalyzed → pin) in
      `backend/tests/unit/test_click_service.py`
- [X] T050 [US1] Implement `ClickService` (hit-test via analysis_repository, click
      persistence, pin lifecycle, negative clicks) in
      `backend/src/services/click_service.py`
- [X] T051 [US1] Implement `IdentityService` (confirm cluster → build segments via
      TimelineService; adjust add/remove with `user_removed` semantics; reset target;
      structured events per OR-003) in `backend/src/services/identity_service.py`;
      delete `backend/src/services/player_evidence_service.py`,
      `player_candidate_matcher.py`, `player_confirmation_service.py` and their tests
- [X] T052 [US1] Add clicks/target routes in `backend/src/api/routes/clicks.py` and
      target/adjust in `backend/src/api/routes/projects.py` per api.yaml; remove
      superseded `player-request`/`player-confirmation` endpoints and their schemas
- [X] T053 [P] [US1] Frontend: `IdentityEvidenceStrip` (evolve from
      `CandidateEvidencePanel.tsx`, then delete the old file): real-media crops with
      timestamps, per-crop "Not them", jersey agree/disagree lines, ambiguity banner,
      "Yes, that's them" — per ui-flow.md §2d — in
      `frontend/src/features/projects/IdentityEvidenceStrip.tsx` (+ test file, porting
      relevant `CandidateEvidencePanel.test.tsx` cases)
- [X] T054 [US1] Frontend: `FindPlayerStep` composing AnalysisProgressCard +
      FrameClickSelector + jersey-hint field + IdentityEvidenceStrip + post-confirm
      coverage summary, handling all four click resolutions per ui-flow.md §2, in
      `frontend/src/features/projects/FindPlayerStep.tsx` (+ test file); delete
      `PlayerConfirmationStep.tsx`, `TargetPlayerStep.tsx`, `MatchWindowStep.tsx`,
      `SourceStep.tsx` and their tests
- [X] T055 [US1] Wizard rewire: new step labels ("Add video", "Find your player",
      "Build the reel"), step derivation from project.status + analysis state,
      localStorage project restore + polling resume, in
      `frontend/src/features/projects/ProjectWizardPage.tsx`,
      `frontend/src/features/projects/projectStore.ts`, and the shell labels in
      `frontend/src/components/GuidedWorkflowShell.tsx`
- [X] T056 [MANUAL CHECKPOINT] [US1] Human runs the full flow on `video/video.mp4`:
      upload → progress stages → click during analysis (pin path) → click after
      analysis (instant path) → evidence strip correctness → jersey cross-check → "Not
      them" → confirm. Record in `checklists/manual-validation.md`.

**Checkpoint 7**: contract + unit + component tests green; T056 human-approved. The app
is end-to-end usable (export gating already exists).

---

## Phase 8: SAM 2 Refinement (US1/US3 corrections)

**Purpose**: Recover players detection missed; fill coverage gaps (FR-012, D-05).

- [X] T057 [P] Unit tests with `FakeMaskPropagator`: mask↔box IoU voting assigns
      correct tracklets; synthetic tracklets minted only where no detections exist;
      window bounds respected; masks dir cleaned at job end; in
      `backend/tests/unit/test_sam2_refine_stage.py`
- [X] T058 SAM 2 `MaskPropagator` implementation (windowed frames from proxy to temp
      dir, propagate from click point, MPS fallback env) in
      `backend/src/ml/impl/sam2_propagator.py` (+ smoke test)
- [X] T059 Implement `sam2_refine_stage` per D-05 (params from `user_clicks` row via
      `params_json`; results → tracklet assignment + click status update; coverage
      rebuild if target confirmed) in
      `backend/src/services/pipeline/sam2_refine_stage.py`
- [X] T060 Wire escalation: analyzed-region box-miss in `ClickService` → enqueue
      `sam2_refine` and return `sam2_queued`; refine finding nothing → click status
      `no_player`; frontend pin/refining badges + toasts per ui-flow.md §2b in
      `frontend/src/features/projects/FrameClickSelector.tsx` and `FindPlayerStep.tsx`

**Checkpoint 8**: T057 green; on real video, a click on an undetected player queues
refinement and extends the confirmed identity's coverage.

---

## Phase 9: Coverage Timeline + Export v2 (US3)

**Purpose**: Coverage review, corrections, and the reel itself (FR-013…FR-016).

- [ ] T061 [P] [US3] Unit tests for segment building (merge gaps < 2 s, drop < 1.5 s,
      pad ±1.5 s, scoring) in `backend/tests/unit/test_timeline_service.py`
- [ ] T062 [P] [US3] Contract tests for `GET /timeline`, `PATCH /timeline/{segment_id}`,
      updated `POST /exports` (profile/overlay_mode; 409 with normative copy when
      unconfirmed) in `backend/tests/contract/test_timeline_exports_api.py`
- [ ] T063 [US3] Implement `TimelineService` (build/rebuild segments, summary, per-
      segment thumbnail + preview clip via `evidence_artifact_service`) in
      `backend/src/services/timeline_service.py`; add timeline routes in
      `backend/src/api/routes/projects.py`
- [ ] T064 [US3] Export as a pipeline stage: render included segments chronologically
      (keep extract+concat core from `backend/src/services/export_service.py`); target
      marker via FFmpeg `sendcmd` script interpolating the confirmed player's per-frame
      boxes (replace the hardcoded center drawbox); profiles select segments by score/
      duration budget; write `segment_ids_json`; in
      `backend/src/services/pipeline/export_stage.py` + slimmed `export_service.py`
- [ ] T065 [US3] Update exports routes to the api.yaml request shape (job-backed 202) in
      `backend/src/api/routes/exports.py`
- [ ] T066 [P] [US3] Frontend: `CoverageTimeline` per ui-flow.md §3a (segments bar,
      popover preview, include/exclude, "Not them", mass-removal escape hatch) in
      `frontend/src/features/projects/CoverageTimeline.tsx` (+ test file)
- [ ] T067 [US3] Embed CoverageTimeline in `ReelGenerationStep` and adapt its export
      request/polling to the new shapes in
      `frontend/src/features/projects/ReelGenerationStep.tsx` (+ update its test file)
- [ ] T068 [MANUAL CHECKPOINT] [US3] Human generates a reel from real footage with
      target marker on: verify chronological included-only segments, marker follows the
      player, download works. Record in `checklists/manual-validation.md`.

**Checkpoint 9**: contract/unit/component tests green; T068 human-approved.

---

## Phase 10: Hardening, Cleanup, Docs

**Purpose**: FR-020 deletions, lifecycle hygiene, docs, final validation.

- [ ] T069 Delete remaining legacy per plan.md inventory:
      `backend/src/services/detection_pipeline.py`, `tracking_pipeline.py`,
      `jersey_recognition_service.py`, `match_inference_service.py`,
      `analysis_service.py`, `highlight_service.py` (fold anything still referenced
      into timeline/export services first), `backend/src/api/routes/analysis.py`,
      `backend/src/api/routes/reviews.py` + review schemas/models,
      `frontend/src/features/review/*`, and all their test files; grep-verify no
      references remain
- [ ] T070 [P] Extend cleanup service for new artifact classes (frames LRU cap, masks
      deleted at job end, full project purge removes proxy/crops/exports + DB rows) in
      `backend/src/services/cleanup_service.py` + tests in
      `backend/tests/unit/test_cleanup_service.py`
- [ ] T071 [P] Structured events audit per OR-003 (job lifecycle, click lifecycle,
      confirmation, export) across pipeline stages and services; assert key events in
      existing integration tests
- [ ] T072 [P] Integration test: full chain on synthetic fixture with fakes —
      attach → chain runs → click → confirm → timeline → export renders a real MP4 — in
      `backend/tests/integration/test_full_flow.py`
- [ ] T073 [P] Update `backend/README.md` and `frontend/README.md` for the new setup
      (ml extra, download_models, doctor) and flow; finalize
      `specs/005-click-first-player-reels/quickstart.md` against reality
- [ ] T074 Update `AGENTS.md` to point at `specs/005-click-first-player-reels/plan.md`
      (it currently points at 003)
- [ ] T075 [MANUAL CHECKPOINT] Execute
      `specs/005-click-first-player-reels/checklists/manual-validation.md` end-to-end on
      `video/video.mp4`, including the overnight/resume scenario; file defects as new
      tasks rather than self-certifying partial passes

**Checkpoint 10 (DONE)**: all automated tests green in a base+dev venv; doctor passes in
the ml venv; manual validation checklist fully executed and recorded.

---

## Dependency notes

- T030 depends on T013–T015 (job chain) and T027 (proxy stage registered).
- T042 depends on T046 only for jersey fields — implement with null jersey data first;
  T047 backfills ranking (this ordering is intentional so Phase 5 ships without OCR).
- T054/T055 depend on T031–T033, T043, T048–T053.
- Export stage (T064) reuses per-frame boxes — requires Phase 4 data and confirmed
  target from Phase 7.

## Estimated task-level parallelism

Within phases, `[P]` groups: {T003–T008}, {T011,T012,T017}, {T018–T023}, {T025,T026,
T031,T032}, {T034}, {T039}, {T044}, {T048,T049,T053}, {T057}, {T061,T062,T066},
{T070–T073}.
