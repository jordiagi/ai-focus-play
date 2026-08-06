# Tasks: Full Project Implementation (004-full-project-spec)

**Input**: [spec.md](./spec.md) — complete product scope inspired by Hudl SportsCode/Focus  
**Branch**: `004-full-project-spec` (create when ready)  
**Verification strategy**: Automated tests each phase → human manual review on real video → next phase  

---

## Execution Rules

1. **One phase at a time**. Do NOT start the next phase until current phase tests pass AND you report results.
2. **Every task includes exact file path(s)**. No ambiguity.
3. **Tests run before implementation** (TDD where applicable).
4. **After each phase**, stop and let me verify manually on `video/video.mp4`.
5. **If any test fails, fix it first** — don't move forward with broken code.

## Parallelism

- Tasks marked **[P]** can run in parallel with other [P] tasks in the same phase.
- Backend and frontend tasks can run in parallel once API contracts are stable.

---

## Phase A: Video Ingestion & Indexing (MVP Blocker)

**Goal**: User can upload/point to a match video; system validates, probes, and indexes it for frame extraction.

### A1. Domain Models
- [ ] **A01** `backend/src/domain/models/video.py` — add `SourceVideo` dataclass/model:
  ```
  source_id: str
  project_id: str
  file_path: str              # original path, never copied
  original_filename: str
  duration_seconds: float
  fps: float
  width: int
  height: int
  codec: str                  # video codec (h264, hevc, etc.)
  audio_codec: str
  probe_json: str             # raw ffprobe JSON as string
  created_at: datetime
  updated_at: datetime
  status: str                 # pending | validating | validated | error
  validation_error: str | None
  ```
- [ ] **A02** `backend/src/domain/models/video.py` — add `FrameIndexEntry`:
  ```
  keyframe_index_id: str
  source_id: str
  frame_number: int
  timestamp_seconds: float
  file_offset: int | None     # if available from probe
  ```

### A2. Video Ingest Service (Backend)
- [ ] **A03** `backend/src/services/video_ingest_service.py` — create new file:
  - `ingest_video(project_id, file_path) -> SourceVideo` — validate via ffprobe, compute frame index
  - `validate_video(file_path) -> tuple[bool, str | None]` — check file exists, is playable, extract probe data
  - `compute_frame_index(source_id, interval_frames=15) -> list[FrameIndexEntry]` — use ffprobe `select='eq(n\,{interval})'` or ffmpeg frame-step to get every Nth frame timestamp
  - Use `subprocess.run(["ffprobe", ...])` — no heavy Python dependencies

### A3. Video Ingest Tests (Backend)
- [ ] **A04** `backend/tests/unit/test_video_ingest_service.py`:
  ```python
  # Test fixtures: use video/video.mp4 or a small synthetic MP4
  def test_valid_ingestion(): ...         # file probes correctly, status=validated
  def test_corrupted_file_error(): ...    # invalid file returns validation_error
  def test_frame_index_coverage(): ...    # timestamps span full duration at interval
  def test_large_video_no_mem_exhaust(): # streaming probe only, doesn't load frames into memory
  ```

### A4. Video API Route (Backend)
- [ ] **A05** `backend/src/api/routes/sources.py` — add/update:
  - `POST /sources` with multipart form upload → calls `ingest_video()` → returns SourceVideo JSON + status
  - `GET /sources/{source_id}` → returns metadata + status
  - Add to router registration in `backend/src/api/routes/__init__.py`

### A5. Frontend — Video Source Step
- [ ] **A06** `frontend/src/features/projects/VideoSourceStep.tsx`:
  - File picker drag-and-drop for video files (update existing component)
  - After upload: display detected metadata (duration, resolution, FPS, codec, status)
  - Show validation errors with user-friendly message
  - Progress indicator during indexing phase

### A7. Frontend — Video Source API
- [ ] **A07** `frontend/src/services/sources.ts`:
  ```typescript
  uploadVideo(projectId: string, file: File): Promise<SourceVideo>
  getSourceVideo(projectId: string, sourceId: string): Promise<SourceVideo>
  ```

### A8. Frontend — Tests
- [ ] **A08** `frontend/src/features/projects/VideoSourceStep.test.tsx`:
  ```typescript
  // Test: renders file picker with drag-drop zone
  // Test: shows metadata after successful upload
  // Test: shows error on invalid file
  // Test: progress bar visible during indexing
  ```

**Phase A gate**: `pytest backend/tests/unit/test_video_ingest_service.py` passes + frontend build succeeds.

---

## Phase B: Player Detection & Tracking (Core CV Pipeline)

**Goal**: System detects all people in frames, tracks them across time with stable IDs, produces tracklets.

### B1. Detection Domain Models
- [ ] **B01** `backend/src/domain/models/detection.py` — new file:
  ```python
  class DetectionResult:
      detection_id: str
      frame_timestamp: float
      bbox_x: float        # normalized 0-1 or pixels
      bbox_y: float
      bbox_width: float
      bbox_height: float
      confidence: float
      class_label: str     # person | ball | pitch

  class Tracklet:
      tracklet_id: str
      source_id: str
      first_frame_index: int
      last_frame_index: int
      frame_count: int
      avg_bbox: tuple[float, float, float, float]
      appearance_frames: list[int]   # indices into frame index
      status: str  # active | incomplete | truncated
  ```

### B2. Detection Pipeline Service
- [ ] **B02** `backend/src/services/detection_pipeline.py` — new file:
  - `run_detection(source_id, model="yolov8n") -> list[DetectionResult]`
  - `detect_in_frame(image_bytes) -> list[bbox_dict, confidence, class_label]`
  - Fallback: if detector not available, return empty detections + warning log (don't crash)
  - Store results in project-scoped artifacts (`backend/src/services/artifact_service.py`)

### B3. Tracking Pipeline Service
- [ ] **B03** `backend/src/services/tracking_pipeline.py` — new file:
  - `run_tracking(source_id, detections) -> list[Tracklet]`
  - Hungarian algorithm assignment for frame-to-frame association
  - IoU threshold matching between consecutive frames
  - Gap tolerance: allow K-frame gaps before splitting tracklet (configurable, default 5)
  - Track persistence scoring

### B4. Detection Tests
- [ ] **B04** `backend/tests/unit/test_detection_pipeline.py`:
  ```python
  # Test: detector returns valid bboxes on test image with known person
  # Test: no detections on empty/black frame (no false positives)
  # Test: confidence threshold filtering removes low-confidence detections
  ```

### B5. Tracking Tests
- [ ] **B05** `backend/tests/unit/test_tracking_pipeline.py`:
  ```python
  # Test: single object tracked across frames with consistent ID
  # Test: two objects maintain separate IDs when spatially separated
  # Test: temporary occlusion handled (gap tolerance preserves tracklet)
  # Test: track persistence scoring is correct for each tracklet
  ```

### B6. Detection Worker Integration
- [ ] **B06** `backend/src/workers/detection_worker.py` — new file OR update `local_runner.py`:
  - Define detection pipeline task
  - Progress callback (frames processed / total frames)
  - Error handling with retry on transient failure

### B7. Artifact Storage for Detections
- [ ] **B07** `backend/src/services/artifact_service.py` — add detection/tracklet artifact methods:
  - `save_detections(project_id, detections)` → returns artifact path
  - `save_tracklets(project_id, tracklets)` → returns artifact path
  - `load_detections(project_id)` → list[DetectionResult]
  - `load_tracklets(project_id)` → list[Tracklet]

**Phase B gate**: All detection + tracking unit tests pass. Manual check: run on `video/video.mp4` and verify detections look reasonable (not too many/few false positives).

---

## Phase C: Jersey Recognition & Color Extraction

**Goal**: From player bboxes, extract jersey number and color cues for identity matching.

### C1. Jersey Number Recognition
- [ ] **C01** `backend/src/services/jersey_recognition_service.py` — new file:
  ```python
  def recognize_jersey_number(roi_image) -> dict:
      # Phase 1: template matching (no heavy OCR)
      # Returns: {number: str|None, confidence: float, readable: bool}

  def extract_dominant_color(roi_image) -> dict:
      # HSV color extraction from upper-body ROI
      # Returns: {color_name: str, hex: str, confidence: float}
  ```
  - Color mapping: HSV → canonical team names (blue, red, white, green, yellow, black, orange, purple, pink, gray)
  - Multi-color detection for striped jerseys

### C2. Player Candidate Matcher Enhancement
- [ ] **C02** `backend/src/services/player_candidate_matcher.py` — enhance existing:
  - Add jersey_number + color cross-referencing across tracklets
  - Confidence scoring based on evidence quality (number readable? color clear?)
  - Return match_reasons and review_warning strings

### C3. Jersey Recognition Tests
- [ ] **C03** `backend/tests/unit/test_jersey_recognition_service.py`:
  ```python
  # Test: template matching returns correct number on clean jersey image (synthetic)
  # Test: unreadable/no-number ROI returns {number: None, readable: False}
  # Test: color extraction returns plausible dominant color for solid-color image
  ```

### C4. Jersey Color Contract Tests
- [ ] **C04** `backend/tests/contract/test_jersey_color_contract.py`:
  ```python
  # Full pipeline: detection → tracking → recognition → consistent data shapes
  ```

### C5. Artifact Storage for Cues
- [ ] **C05** `backend/src/services/artifact_service.py` — add jersey cue methods:
  - `save_jersey_cues(project_id, tracklet_id, cues)` → artifact path
  - `load_jersey_cues(project_id)` → dict of tracklet → {number, color}

**Phase C gate**: Recognition tests pass. Manual check: run on video with known jersey numbers and verify detection accuracy.

---

## Phase D: Candidate Clustering & Identity Resolution (US2)

**Goal**: Tracklets with matching cues cluster into candidate player identities.

### D1. Clustering Service
- [ ] **D01** `backend/src/services/identity_clustering_service.py` — new file:
  ```python
  def cluster_candidates(source_id, jersey_number, color_hint=None) -> list[CandidateCluster]:
      # Cluster by: number match + color match + non-overlapping segments + body shape
      # Each candidate:
      #   cluster_id, evidence_count, inferred_color, visible_cues, cue_summary,
      #   match_reasons, review_warning, confidence (0-1)

  def compute_body_shape_similarity(tracklets) -> float:
      # Compare bbox aspect ratio consistency across tracklets
  ```

### D2. Integrate Clustering into Evidence Service
- [ ] **D02** `backend/src/services/player_evidence_service.py` — update existing:
  - Import and call `cluster_candidates()` after detection + recognition
  - Update candidate review states based on cluster evidence
  - Clear stale candidates on rerun

### D3. Clustering Tests
- [ ] **D03** `backend/tests/unit/test_identity_clustering_service.py`:
  ```python
  # Test: same number + same color → clusters together
  # Test: same number + different color → separate clusters
  # Test: no-color evidence groups by number alone (adds review_warning)
  # Test: body shape consistency boosts confidence within cluster
  ```

### D4. Clustering Contract Tests
- [ ] **D04** `backend/tests/contract/test_clustering_contract.py`:
  ```python
  # Full flow: detection → recognition → clustering → candidate shapes match spec
  ```

**Phase D gate**: All clustering tests pass. Manual check: run on video with multiple players and verify candidates are grouped correctly.

---

## Phase E: Evidence Presentation & Confirmation (US1+US2 — from 003 spec)

**This phase integrates with the existing 003-real-player-evidence spec.**
Most tasks here already exist in `specs/003-real-player-evidence/tasks.md` as T007-T065.
We reuse those but ensure they connect to the new CV pipeline from Phases B-D.

### E1. Complete Evidence Service Integration (Backend)
- [ ] **E01** `backend/src/services/player_evidence_service.py`:
  - Use real detection/tracklet data from Phase B + C for evidence samples
  - Replace any remaining synthetic/fake evidence generation
  - FFmpeg frame extraction for evidence thumbnails/clips → project-scoped artifacts

### E2. Complete Evidence API Routes (Backend)
- [ ] **E02** `backend/src/api/routes/projects.py`:
  - POST `/projects/{id}/player-request` → triggers CV pipeline + evidence extraction
  - GET `/projects/{id}/player-candidates` → returns candidates with real evidence samples
  - POST `/projects/{id}/player-confirmation` → confirms/rejects candidate
  - GET `/projects/{id}/evidence-media/{name}` → serves thumbnails/clips

### E3. Evidence Contract Tests (Backend)
- [ ] **E03** `backend/tests/contract/test_real_player_evidence_api.py`:
  ```python
  # Test: evidence request returns real media URIs, no placeholders
  # Test: candidate listing has valid samples with timestamps
  # Test: confirmation transitions project state
  # Test: evidence media returns actual file content
  ```

### E4. Frontend Evidence Panel
- [ ] **E04** `frontend/src/features/projects/CandidateEvidencePanel.tsx`:
  - Render real thumbnails/clips from backend media URIs (not placeholders)
  - Display candidate metadata in comparison cards
  - Confirm/reject buttons per candidate
  - Rerun search control
- [ ] **E05** `frontend/src/features/projects/PlayerConfirmationStep.tsx`:
  - Loading / no-result / failure states
  - Multi-candidate comparison workflow
  - Lock Step 3 until confirmation

### E5. Frontend Evidence Tests
- [ ] **E06** `frontend/src/features/projects/CandidateEvidencePanel.test.tsx` + `PlayerConfirmationStep.test.tsx`:
  ```typescript
  // Test: real media renders, not placeholder
  // Test: multi-candidate display correct
  // Test: Step 3 locked until confirmation
  // Test: rerun updates candidates correctly
  ```

**Phase E gate**: Evidence API contract tests pass + manual review on `video/video.mp4` confirms real evidence (not fake). **This is the first major human verification checkpoint.**

---

## Phase F: Reel Generation & Export (US3)

**Goal**: From confirmed identity, generate short/medium/marked output clips.

### F1. Appearance Extraction Service
- [ ] **F01** `backend/src/services/appearance_extraction_service.py` — new file:
  ```python
  class Appearance:
      appearance_id: str
      tracklet_id: str
      start_time: float
      end_time: float
      duration: float
      confidence: float
      pitch_side: str   # left | right | center
      ball_proximity_score: float  # proxy based on camera proximity

  def extract_appearances(confirmed_player_id) -> list[Appearance]:
      # Extract all temporal segments for confirmed player
      # Score and rank by composite relevance

  def score_appearance(app) -> float:
      # Ball proximity + camera zoom + jersey visibility + pitch importance
  ```

### F2. Reel Export Service
- [ ] **F02** `backend/src/services/reel_export_service.py` — new file:
  ```python
  def generate_reel(project_id, output_profile, overlay_mode="none") -> dict:
      # Profile: short_highlight (top-K ~10 clips, 30-60s) or medium_best_plays (~15 clips, 2-5min)
      # Overlay: none or target_marker (colored bbox on confirmed player)
      # Extract clips via FFmpeg → concat with crossfade → encode H.264 MP4
      # Progress callback during export
  ```

### F3. Export API Route
- [ ] **F03** `backend/src/api/routes/exports.py`:
  - POST `/projects/{id}/exports` (with output_profile + target_marker) → triggers generation
  - GET `/projects/{id}/exports` → list outputs with status
  - GET `/exports/{output_id}/download` → serve final MP4
  - Evidence-backed identity gate on creation

### F4. Export Tests
- [ ] **F04** `backend/tests/contract/test_evidence_backed_exports_api.py`:
  ```python
  # Test: export rejected without confirmed player (409)
  # Test: export accepted with confirmed player, returns processing status
  ```
- [ ] **F05** `backend/tests/integration/test_evidence_backed_export_flow.py`:
  ```python
  # Full flow: confirmation → export → output downloadable
  # Both short and medium profiles work
  # Target marker applied correctly
  ```

### F6. Frontend — Reel Generation & Exports Pages
- [ ] **F06** `frontend/src/features/projects/ReelGenerationStep.tsx`:
  - Display confirmed identity summary
  - Output profile selector + target marker toggle
  - Generate button (disabled until confirmation)
  - Progress during generation
- [ ] **F07** `frontend/src/features/exports/ExportsPage.tsx` + `ExportRequestPanel.tsx`:
  - List generated reels with status + download links

### F8. Frontend Reel Tests
- [ ] **F08** `frontend/src/features/projects/ReelGenerationStep.test.tsx`:
  ```typescript
  // Test: locked until confirmation, enabled after
  // Test: identity summary displayed correctly
  ```

**Phase F gate**: Export contract + integration tests pass. Manual check: generate reels on `video/video.mp4` and verify player focus.

---

## Phase G: Evidence Scrubber Timeline (Hudl SportsCode-style)

**Goal**: Interactive scrubber for reviewing evidence appearances with timeline visualization.

### G1. Frontend — Evidence Scrubber Component
- [ ] **G01** `frontend/src/features/projects/EvidenceScrubber.tsx`:
  - Horizontal timeline spanning video duration
  - Appearance markers as colored segments
  - Draggable playhead with timestamp display
  - Click/mouseover → timestamped thumbnail preview
  - Color-coded by candidate cluster

### G2. Frontend — Scrubber Tests
- [ ] **G02** `frontend/src/features/projects/EvidenceScrubber.test.tsx`:
  ```typescript
  // Timeline renders, markers at correct timestamps, scrubbing works
  ```

---

## Phase H: Polish, Integration Tests & Docs

### H1. Full Pipeline Integration Test
- [ ] **H01** `backend/tests/integration/test_full_pipeline.py`:
  ```python
  # Video ingest → detection → tracking → recognition → evidence → confirmation → export (full flow)
  # Cancel during processing and resume
  # Rerun with different jersey number updates candidates
  # Cleanup removes artifacts after export
  ```

### H2. Performance Tests
- [ ] **H02** `backend/tests/integration/test_performance.py`:
  ```python
  # Detection speed on 1080p video reasonable
  # Memory bounded for 2hr+ video (no full-frame loading)
  # Concurrent evidence requests handled
  ```

### H3. Documentation
- [ ] **H03** `backend/README.md` — update with pipeline architecture, setup, FFmpeg/YOLO requirements
- [ ] **H04** `specs/*/quickstart.md` — local setup steps for all phases
- [ ] **H05** `MANUAL_TESTING.md` — test video recommendations + expected results per phase

---

## Parallel Execution Opportunities

| Phase | Parallel Tasks |
|-------|---------------|
| A (Ingest) | A06/A07 (backend sources API) + A08/A09 (frontend VideoSourceStep) in parallel |
| B (Detection/Tracking) | B02 (detection service) + B03 (tracking service) + B04/B05 (tests) in parallel |
| C (Recognition) | C01 (recognition service) + C03/C04 (tests) in parallel |
| D (Clustering) | D01 (clustering) + D03/D04 (tests) in parallel |
| E (Evidence) | Backend E01+E02+E03 in parallel with Frontend E04+E05+E06 |
| F (Export) | Backend F01+F02+F03+F04/F05 in parallel with Frontend F06+F07+F08 |

---

## Phase Execution Order & Dependencies

```
Phase A (Ingest) → Phase B (Detection/Tracking) → Phase C (Jersey Recognition) → Phase D (Clustering) → Phase E (Evidence UI) → Phase F (Export) → Phase G (Scrubber) → Phase H (Polish)
```

No cross-phase parallelism recommended during initial implementation — each phase's output is consumed by the next.

---

## Verification Checkpoints (Human Review Required)

| Phase | What to verify manually | Tool needed |
|-------|----------------------|-------------|
| **A** | Upload `video/video.mp4` → correct metadata shown | Browser dev tools, network tab |
| **B** | Run detection on video → check bbox count/location in artifacts | Check artifact JSON files |
| **C** | Verify jersey number detection accuracy on known footage | Artifact inspection |
| **E** | Full evidence workflow: select video → enter #8 → review candidates → confirm | Browser (full UI flow) |
| **F** | Generate short + medium reels → verify player focus in output MP4 | Video player |
| **G** | Scrubber timeline interaction on evidence | Browser |

---

## Total Task Count by Phase

| Phase | Tasks | Parallelizable? |
|-------|-------|----------------|
| A | 8 (A01-A08) | Partially |
| B | 7 (B01-B07) | Yes |
| C | 5 (C01-C05) | Partially |
| D | 4 (D01-D04) | Partially |
| E | 6 (E01-E06) | Backend/FE parallel |
| F | 8 (F01-F08) | Backend/FE parallel |
| G | 2 (G01-G02) | No |
| H | 5 (H01-H05) | Partially |
| **Total** | **45 tasks** | — |
