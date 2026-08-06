# Implementation Plan: Click-First Player Reels

**Branch**: `005-click-first-player-reels` | **Date**: 2026-07-13 | **Spec**: [spec.md](./spec.md)
**Input**: Full product re-spec from `/specs/005-click-first-player-reels/spec.md` (supersedes specs 001–004)

## Summary

Rebuild the product's internals around a modern, fully local CV pipeline while keeping
the working app shell: RT-DETRv2 detection + ByteTrack tracking + DINOv2 identity
clustering + PARSeq jersey voting, with SAM 2 as a bounded click-refinement tool. The
identification UX becomes click-first (scrub a frame, click your player, confirm from an
evidence strip). Storage moves from a whole-file JSON blob to SQLite; background work
moves from stub runners to checkpointed, resumable subprocess jobs. Legacy heuristic CV
code, the JSON store, the remote-runner path, and the 001-era review queue are deleted.

## Technical Context

**Language/Version**: Python 3.11+ backend (FastAPI, Pydantic), TypeScript 5 / React 18 / Vite frontend
**Primary Dependencies**: FFmpeg/FFprobe (subprocess); new `ml` extra: torch (MPS),
transformers (RT-DETRv2, DINOv2), supervision (ByteTrack), sam2, PARSeq via torch.hub,
opencv-python-headless, scikit-learn, timm — see [research.md](./research.md) D-01…D-05
and the pyproject sketch below
**Storage**: SQLite (stdlib sqlite3, WAL) at `{data_dir}/app.db`; project-scoped artifact
dirs for pixels — see [data-model.md](./data-model.md)
**Testing**: pytest unit/contract/integration with fake models behind protocols
(`pytest -m "not ml"` default; `@pytest.mark.ml` local smoke); Vitest for components;
manual real-video checklists
**Target Platform**: single Apple Silicon Mac (validated on M4 Max, 64 GB), PyTorch MPS
with CPU fallback (`AI_FOCUS_DEVICE` override, `PYTORCH_ENABLE_MPS_FALLBACK=1` for SAM 2)
**Project Type**: Web application (backend API + background worker subprocesses + frontend wizard)
**Observability**: structured events per OR-003; real progress derived from work done
**Performance Goals**: full 90-min 1080p match analyzed unattended in ~2–4 h (SC-005);
click-to-highlight < 2 s on analyzed frames (SC-002)
**Constraints**: fully local models only; click-first identification; resumable jobs
(≤ 1,000 analysis frames lost on kill, SC-004); no placeholder media; plain-language UI
**Scale/Scope**: one project = one video = one confirmed identity at a time

## Constitution Check

- [x] Scope traces to explicit user stories (US1–US3) and requirements (FR-001…FR-020).
- [x] Each user story remains independently implementable and verifiable.
- [x] Verification defined before implementation: protocol fakes + synthetic fixture for
      automation; manual checklists for visual quality (OR-002, OR-004).
- [x] Observability (OR-003), operator impact (model downloads, doctor CLI), and
      quickstart changes are captured.
- [x] Added complexity is justified in research.md D-01…D-13; AGPL avoided; heavy deps
      isolated in the `ml` extra.

## Project Structure

### Documentation (this feature)

```text
specs/005-click-first-player-reels/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── api.yaml
│   └── ui-flow.md
├── checklists/
│   ├── requirements.md
│   └── manual-validation.md
└── tasks.md
```

### Source code (target state; new files marked ★, deletions listed in the inventory)

```text
backend/
├── src/
│   ├── api/
│   │   ├── routes/          # sources.py→source attach; projects.py reworked; ★clicks/frames/timeline handlers; exports.py kept
│   │   └── schemas/
│   ├── app/                 # config.py (drop remote_*; add analysis_fps etc.), dependencies.py rewired
│   ├── domain/models/       # detection.py rewritten; ★pipeline.py; ★selection.py; video.py extended
│   ├── ml/                  # ★ device.py, model_registry.py, interfaces.py, download_models.py, doctor.py
│   │   └── impl/            # ★ rtdetr_detector.py, dinov2_embedder.py, parseq_ocr.py, sam2_propagator.py
│   ├── services/
│   │   ├── pipeline/        # ★ proxy_stage.py, detect_track_stage.py, embed_cluster_stage.py,
│   │   │                    #   jersey_ocr_stage.py, assemble_candidates_stage.py, sam2_refine_stage.py
│   │   ├── job_service.py   # ★ enqueue/claim/cancel/spawn
│   │   ├── click_service.py # ★ hit-test, pins, resolution
│   │   ├── identity_service.py  # ★ confirm/adjust/negative evidence
│   │   ├── timeline_service.py  # ★ segment build/merge/pad/score
│   │   ├── artifact_service.py  # extended
│   │   ├── video_ingest_service.py  # kept, frame index dropped
│   │   ├── evidence_artifact_service.py  # kept, reused for strips/previews
│   │   └── export_service.py    # render core kept; ★ sendcmd marker overlay
│   ├── storage/             # ★ db.py, schema.sql, migrations/; repositories rewritten on SQLite
│   └── workers/
│       └── run_stage.py     # ★ subprocess entrypoint (replaces local_runner/remote_runner/detection_worker)
└── tests/
    ├── contract/  ├── integration/  ├── unit/
    ├── fakes/fake_models.py         # ★
    └── fixtures/make_synthetic_match.py  # ★

frontend/src/
├── features/projects/       # FindPlayerStep★, FrameClickSelector★, AnalysisProgressCard★,
│                            # IdentityEvidenceStrip★ (from CandidateEvidencePanel), CoverageTimeline★,
│                            # VideoSourceStep kept, ReelGenerationStep kept
├── features/exports/        # kept
└── services/                # projects.ts extended, sources.ts kept
```

## Keep / Replace / Delete inventory

| Fate | Paths |
|---|---|
| **Keep (extend)** | `backend/src/app/{main,errors,logging}.py`; `app/config.py` (strip `remote_*`, add pipeline knobs); `services/artifact_service.py`; `services/video_ingest_service.py`; `services/evidence_artifact_service.py`; `services/export_service.py` render core; `services/cleanup_service.py`; routes `exports.py` + evidence-media serving; frontend wizard shell, `VideoSourceStep.tsx`, `ReelGenerationStep.tsx`, `ExportsPage.tsx`, `apiClient.ts` |
| **Replace** | `storage/database.py` (JSON→SQLite `db.py`); `storage/project_repository.py`, `job_repository.py`; `domain/models/detection.py`; routes `projects.py` workflow semantics; `services/player_evidence_service.py`, `player_candidate_matcher.py`, `player_confirmation_service.py`, `highlight_service.py` (→ click/identity/timeline services); frontend `PlayerConfirmationStep.tsx` (→ `FindPlayerStep.tsx`), `CandidateEvidencePanel.tsx` (→ `IdentityEvidenceStrip.tsx`) |
| **Delete** (FR-020) | `services/detection_pipeline.py`, `services/tracking_pipeline.py`, `services/jersey_recognition_service.py`; `workers/local_runner.py`, `workers/remote_runner.py`, `workers/detection_worker.py`, `workers/base.py`; `services/match_inference_service.py`, `services/analysis_service.py` + `routes/analysis.py`; `routes/reviews.py` + review services/models; frontend `TargetPlayerStep.tsx`, `MatchWindowStep.tsx`, `SourceStep.tsx`, `features/review/*`; obsolete unit tests for deleted modules; `FrameIndexEntry` + frame-index code |

## pyproject additions (backend)

```toml
[project.optional-dependencies]
ml = [
  "torch>=2.5,<3", "torchvision>=0.20",
  "transformers>=4.48,<5", "huggingface_hub>=0.27",
  "supervision>=0.25", "sam2>=1.1",
  "opencv-python-headless>=4.10", "numpy>=1.26",
  "pillow>=10", "scikit-learn>=1.5", "timm>=1.0",
]
dev = ["pytest>=8.0.0", "httpx>=0.27.0"]   # unchanged; CI installs base+dev only
```

All torch/transformers imports must be function-local inside `src/ml/impl/*` so the app
imports cleanly without the `ml` extra (fakes run everywhere).

## Implementation Phases (gates are hard: do not start N+1 before N's gate passes)

Full task detail in [tasks.md](./tasks.md). Summary:

- **Phase 0 — SQLite foundation.** `storage/db.py` + `schema.sql` + migrations;
  repositories rewritten; projects/sources/outputs ported.
  *Gate*: `pytest backend/tests -m "not ml"` green; app boots; create-project +
  attach-source works against SQLite.
- **Phase 1 — Job infrastructure.** `pipeline_jobs`, `job_service.py`,
  `workers/run_stage.py` with a `sleep_demo` stage; jobs + cancel endpoints.
  *Gate*: demo job shows live polled progress; cancel works; kill-and-resume works.
- **Phase 2 — ML foundation.** `src/ml/` package (device, registry, interfaces,
  download/doctor CLIs), fakes, `ml` extra.
  *Gate*: `python -m src.ml.doctor` reports device+models+ffmpeg; base install (no ml
  extra) passes all `-m "not ml"` tests.
- **Phase 3 — Proxy + frame plumbing.** `proxy_stage`, `GET /frame`,
  `GET /frame-detections` (empty ok), frames cache; `FrameClickSelector` scrubbing.
  *Gate*: upload → scrub any timestamp in the browser.
- **Phase 4 — Detection + tracking.** `detect_track_stage` (RT-DETR + ByteTrack,
  checkpointed), crops, persistence.
  *Gate*: real run on `video/video.mp4`; boxes overlay in scrubber; kill/resume test.
- **Phase 5 — Embeddings + clustering.** `embed_cluster_stage` with cannot-link
  constraint, kit color, `GET /candidates`.
  *Gate*: candidates return clusters with rep crops; constraint unit test passes.
- **Phase 6 — Jersey OCR.** `jersey_ocr_stage` (keyframes, PARSeq, voting), hint
  ranking + agreement fields.
  *Gate*: voting unit tests on fakes; real-video numbers spot-checked.
- **Phase 7 — Click-to-confirm UX.** `click_service` + `/clicks`, `identity_service` +
  `/target(/adjust)`, `FindPlayerStep`, `IdentityEvidenceStrip`, pins.
  *Gate*: manual flow upload → analyze → click → evidence → confirm on real video.
- **Phase 8 — SAM 2 refinement.** `sam2_refine_stage` (windowed propagation, IoU
  voting, synthetic tracklets), click-miss escalation, negative clicks.
  *Gate*: click on an undetected player queues refinement and extends coverage.
- **Phase 9 — Timeline + export v2.** `timeline_service`, timeline endpoints,
  `CoverageTimeline`, export job with sendcmd-interpolated target marker.
  *Gate*: end-to-end reel with a moving marker from real footage.
- **Phase 10 — Hardening, cleanup, docs.** Deletions per inventory, cleanup-service
  coverage for new caches, resume/cancel integration tests, quickstart, checklists run.
  *Gate*: `checklists/manual-validation.md` executed once on real footage; no deleted
  module referenced anywhere.

## Verification approach

- Contract tests per new endpoint (shape + status codes + plain-language error copy).
- Unit tests on protocol fakes for every pipeline stage (including cannot-link and
  vote-aggregation invariants) and services (hit-test, segment merge/pad).
- Integration tests with real FFmpeg + fake models over the generated synthetic fixture
  (proxy, frame serving, crops, export).
- `@pytest.mark.ml` local smoke tests: 10-frame real-model sanity per impl.
- Manual: [checklists/manual-validation.md](./checklists/manual-validation.md) on
  `video/video.mp4`.
