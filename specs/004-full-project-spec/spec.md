# Project Specification: AI Focus Play — Complete Product Scope

**Created**: 2026-06-09  
**Status**: Draft  
**Inspired by**: Hudl SportsCode + Hudl Focus automated player highlight pipeline  

---

## Vision Statement

AI Focus Play is a complete, end-to-end system for producing **player-focused soccer highlight reels from broadcast match footage**. Unlike Hudl's hardware-heavy approach (cameras on the stadium) or manual coding tools (SportsCode requires hours of analyst time), this project uses AI to automate the entire pipeline: ingest video → identify target player → extract their appearances → human-verified evidence → generate polished output clips — all without cameras, analysts, or expensive infrastructure.

### What This Is NOT

- Not a replacement for Hudl's live-hardware ecosystem (Focus cameras)
- Not a tactical analysis dashboard or event-data platform (OPTA/Wyscout)
- Not a real-time coaching tool or wearable integration
- Not an automated jersey-number OCR system (we lean on human confirmation)

---

## Product Overview — Inspired by Hudl SportsCode/Focus

Hudl's product covers these stages. Here's how AI Focus Play maps to each:

| Hudl Capability | AI Focus Play Equivalent | Maturity |
|----------------|------------------------|----------|
| **Live camera capture** (Focus hardware) | Ingest existing MP4/AVI match footage (user-provided) | MVP: manual upload |
| **Automated framing/tracking** | Computer vision player detection + tracklet extraction | Phase 2+ |
| **Event coding/timing** | Jersey-number + color cues as automated event tags | Phase 1 (UI-driven) |
| **Live replay / telestration** | Evidence preview with timestamp scrubbing | Phase 1 |
| **Player clip compilation** | Candidate evidence → confirmed identity → reel extraction | Phase 1 |
| **Highlight reel generation** | Short/medium/marked output profiles from confirmed player | Phase 1 |
| **Cloud sync / sharing** | Export to MP4 + cloud storage hooks | Phase 2+ |
| **Biometric integration** | Not in scope for v1 | — |
| **Team collaboration/review** | Evidence review queue with multi-reviewer support | Phase 2 |

---

## Core Workflow (Step-by-Step)

### Step 1: Ingest Match Video
User selects a match video file. The system loads metadata (duration, FPS, resolution).

### Step 2: Specify Target Player
User enters jersey number (+ optional color hint). The system extracts timestamped frame/clip evidence from the actual video and presents candidates.

### Step 3: Review & Confirm Evidence
User reviews real video evidence for each candidate, compares identities, selects one as confirmed target player.

### Step 4: Generate Reel Outputs
System extracts all moments where the confirmed player appears and generates output clips at multiple profiles.

### Step 5: Export & Share
User downloads outputs or shares via integration hooks.

---

## Detailed Feature Requirements (Inspired by Hudl)

### FR-01: Video Ingestion Engine (Hudl Focus → Ingest)

**What Hudl does**: Cameras automatically start recording at kickoff, sync to cloud.

**AI Focus Play implementation**:
- Accept MP4/AVI/MKV video files from local filesystem
- Extract stream metadata via FFprobe (duration, FPS, resolution, codec, audio channels)
- Validate video integrity (no corruption, playable frames)
- Compute a temporal index for seekable frame extraction
- Store video reference (never copy — use original path + hash)

**Non-functional**: Support videos up to 3 hours at 1080p. Analysis must be cancelable and resumable.

### FR-02: Player Detection & Tracking Pipeline (Hudl Focus AI → CV Backend)

**What Hudl does**: Custom-trained visual processing identifies athletes on the field, tracks them frame-by-frame, and maintains persistent identity tracklets throughout the match.

**AI Focus Play implementation**:

#### 2a. Object Detection Layer
- Detect all humans in each keyframe using a lightweight detector (YOLOv8n or similar)
- Detect soccer ball when visible
- Detect goalposts/pitch boundaries for scene context
- Output bounding boxes with confidence scores per frame

#### 2b. Multi-Object Tracking Layer
- Assign stable IDs to each detected person using tracking (ByteTrack/DeepSORT)
- Maintain tracklets across frames with gap-tolerant association
- Handle ID switches due to occlusion, zoom changes, camera pans
- Track persistence = minimum contiguous frame span for a tracklet

#### 2c. Jersey Number Recognition Layer
- For each person bbox, extract ROI and attempt jersey number recognition (OCR or template matching)
- When OCR fails or is uncertain, fall back to "number present, not readable" status
- Support jersey numbers 0-99 (single and double digit)

#### 2d. Jersey Color Extraction Layer
- For each person bbox, compute dominant jersey color from upper-body ROI
- Map to canonical team colors (blue, red, white, green, yellow, black, orange, purple, etc.)
- Handle striped/complex jerseys with a "multi-color" tag

#### 2e. Player Identity Clustering Layer
- Group tracklets that likely belong to the same player:
  - Same jersey number + same team color + non-overlapping appearances in different match segments
  - Similar body proportions (bbox aspect ratio consistency)
  - Spatial proximity during shared-scene moments (same half of pitch)
- Output candidate clusters with supporting evidence count

**Non-functional**: Detection is frame-keyed, not full-frame-by-full-frame. Extract every Nth frame (configurable, default every 15 frames / ~0.5s at 30fps). Adjust sampling density based on motion detection (more samples during active play).

### FR-03: Evidence Presentation & Review Workflow (Hudl SportsCode → Manual Coding)

**What Hudl does**: Coaches code events manually using a visual timeline, tag plays, and generate clips for each coded event. They review footage, mark start/end points, and the system generates clips.

**AI Focus Play implementation**:

#### 3a. Evidence Gallery
- For the confirmed target player, display all evidence appearances as a scrollable gallery
- Each item shows: thumbnail/frame from video, timestamp, duration of appearance, jersey number (detected or manual), jersey color, confidence status
- Group by appearance segments (contiguous timestamps treated as one appearance)

#### 3b. Candidate Comparison Panel (User Story 2 scope)
- When multiple candidates exist for the same jersey number:
  - Show them side-by-side with evidence counts and visual samples
  - Highlight differences in team color, body proportions, pitch position
  - Let user confirm, reject, or mark insufficient per candidate
  - After rejection, show next available candidate

#### 3c. Evidence Scrubber (Hudl-style timeline)
- Interactive timeline showing: match duration, detected appearances as markers, current scrubbing position
- Drag to adjust appearance start/end points (like SportsCode's in/out point editing)
- Play evidence clip from the selected timestamp range

#### 3d. Confidence Indicators
- Each evidence item shows a trust level: CONFIRMED (number + color both visible and matching), INFERRED (color only, number unreadable), UNKNOWN (neither reliably detected)
- User can override confidence by manual visual inspection

### FR-04: Reel Generation Engine (Hudl SportsCode Clip Compilation → Automated Output)

**What Hudl does**: Once events are coded, SportsCode can compile clips into highlight reels based on custom scripts or templates. Analysts define what qualifies as a "highlight" and the system auto-generates compilations.

**AI Focus Play implementation**:

#### 4a. Appearance Extraction
- From confirmed player tracklets + evidence, extract all temporal segments where the player appears
- Each appearance: start_time, end_time, duration, confidence, pitch side (half), proximity to ball
- Filter by minimum/maximum appearance duration thresholds

#### 4b. Output Profile Generation

**Short Highlight Reel (`short_highlight`)**:
- Select top-K moments ranked by a composite score:
  - Ball proximity (closer = higher value)
  - Action intensity proxy (speed of camera pan, zoom level)
  - Jersey visibility quality
  - Pitch position importance (near opponent goal = higher value)
- Default: 30-60 seconds total duration from ~8-15 best clips
- Clips concatenated with subtle transition effects

**Medium Best Plays Reel (`medium_best_plays`)**:
- Select top-K moments (K configurable, default 12-20)
- Longer total duration: 2-5 minutes
- Include a broader set of appearances including less exciting moments for completeness
- Tag each segment with metadata overlay (timestamp, opponent team context if inferable)

**Target-Marked Reel (`target_marker`)**:
- Same as above profile BUT with a visual highlight marker drawn on the confirmed player in each frame
- Marker: colored bounding box outline or circle around the target player across the clip
- Useful for scouting: viewer instantly identifies "the player to watch"

#### 4c. Video Assembly
- Extract raw frames from source video using FFmpeg at requested timestamps
- Concatenate clips with crossfade transitions (0.3s default)
- Optional: add watermark/logo overlay, lower-third name bar with jersey number
- Output codec: H.264 MP4 for maximum compatibility

### FR-05: Evidence Verification & Quality Gates (Hudl Focus's automated camera validation → Quality Assurance)

**What Hudl does**: Automated cameras use AI to validate framing and detect when a player is properly in frame before committing the moment.

**AI Focus Play implementation**:
- SC-001: 100% of selectable evidence items from source video (already specified in 003)
- SC-002: 0 placeholder/synthetic selectable evidence (already specified in 003)
- SC-003: For 3+ visible appearances, show at least 3 real evidence samples
- New: Each detection bbox must have IoU ≥ 0.3 with ground truth when manual annotations exist
- New: Tracklet persistence ratio ≥ 70% for players with visible jerseys in >50% of frames

### FR-06: Review Queue & Collaboration (Hudl SportsCode Studio → Multi-Review)

**What Hudl does**: Multiple team members can review the same coded session, add telestration annotations, and collaboratively produce highlight packages.

**AI Focus Play implementation (Phase 2)**:
- Export evidence metadata as a shareable JSON manifest
- Support "review mode" where multiple users can independently confirm/reject candidates
- Export final reel with embedded evidence chain (provenance metadata in MP4 sidecar)

---

## Technical Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────┐
│                      Frontend (React + Vite)             │
│  ┌───────────┐ ┌──────────────┐ ┌──────────────────┐   │
│  │ Video     │ │ Evidence     │ │ Reel Output      │   │
│  │ Source    │ │ Review       │ │ Generation       │   │
│  │ Selection │ │ Panel        │ │ & Preview        │   │
│  └─────┬─────┘ └──────┬───────┘ └────────┬─────────┘   │
│        │               │                   │             │
│  ┌─────▼───────────────▼───────────────────▼─────────┐  │
│  │                API Client Layer                    │  │
│  └────────────────────────┬──────────────────────────┘  │
└───────────────────────────┬─────────────────────────────┘
                            │ HTTP / WebSocket
┌───────────────────────────▼─────────────────────────────┐
│                    Backend (FastAPI)                      │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────────┐  │
│  │ Video    │ │ Evidence │ │ Candidate│ │ Reel      │  │
│  │ Ingest   │ │ Analysis │ │ Matcher  │ │ Export    │  │
│  │ Service  │ │ Service  │ │ Service  │ │ Service   │  │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └─────┬─────┘  │
│       │             │             │              │        │
│  ┌────▼─────────────▼─────────────▼──────────────▼─────┐ │
│  │               Domain Models                          │ │
│  │  Project · SourceVideo · EvidenceSample ·            │ │
│  │  CandidateIdentity · ConfirmedPlayer · ReelOutput    │ │
│  └──────────────────────────┬──────────────────────────┘ │
│                             │                            │
│  ┌──────────────────────────▼──────────────────────────┐ │
│  │              Worker Pipeline                         │ │
│  │  DetectionRunner → TrackingRunner → OCRRunner        │ │
│  │  ColorRunner → ClusteringRunner → ExportRunner       │ │
│  └─────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────┐
│            Storage & External Services                   │
│  SQLite (metadata) · FFmpeg (frame extraction)           │
│  Local artifact directory (project-scoped, disposable)   │
└───────────────────────────────────────────────────────────┘
```

### Data Flow

```
Video File ──► FFprobe ──► StreamMetadata ──► Keyframe Indexing
                                                    │
                                            Every N frames
                                                    │
                                              YOLOv8n ◄──── DetectionRunner
                                                    │
                                             Bounding Boxes
                                                    │
                                             ByteTrack  ◄── TrackingRunner
                                                    │
                                              Tracklets
                                                    │
                                     ┌──────────────┼──────────────┐
                                     │                              │
                              OCR / Template                 Color ROI    ◄── OCRRunner/ColorRunner
                                     │                              │
                              Jersey # +                     Dominant
                              Color Tag                   Color Tag
                                     │                              │
                                     └──────────────┬──────────────┘
                                                    │
                                             Clustering Algorithm  ◄── ClusteringRunner
                                                    │
                                      Candidate Clusters (with evidence)
                                                    │
                                         User Confirmation Required
                                                    │
                                      Confirmed Player Identity
                                                    │
                                Extract + Concatenate Clips  ◄── ExportRunner
                                                    │
                                              MP4 Output(s)
```

---

## Complete Task List with Implementation Steps

### Phase A: Foundations & Video Ingestion (MVP Blocker)

**Goal**: Project scaffolding is solid; video can be ingested, validated, and indexed for frame extraction.

#### A1. Backend — Domain Models
- [ ] Define `SourceVideo` model: source_id, project_id, file_path, original_filename, duration_seconds, fps, width, height, codec, audio_codec, probe_json, created_at, updated_at, status (pending/validating/validated/error), validation_error
- [ ] Define `FrameIndexEntry`: keyframe_index_id, source_id, frame_number, timestamp_seconds, file_offset (if available)
- [ ] Add to `backend/src/domain/models/` — new or update existing player/output models as needed

#### A2. Backend — Video Ingestion Service
- [ ] Create `backend/src/services/video_ingest_service.py`
  - `ingest_video(project_id, file_path) -> SourceVideo` — validate, probe, index
  - `validate_video(file_path) -> bool, error_msg|None` — check playability with ffprobe
  - `compute_frame_index(source_id, interval_frames=15) -> list[FrameIndexEntry]` — extract timestamps for every Nth frame using ffprobe/ffmpeg

#### A3. Backend — FFmpeg Integration Tests
- [ ] Create `backend/tests/unit/test_video_ingest_service.py`:
  - Test: valid video ingestion produces correct metadata from a known MP4
  - Test: corrupted video returns validation_error
  - Test: frame index covers full duration at requested interval
  - Test: large video (2hr+) doesn't exhaust memory (streaming probe only)

#### A4. Backend — Video API Route
- [ ] Update `backend/src/api/routes/sources.py`:
  - POST `/sources` with multipart form upload → ingests, validates, returns SourceVideo
  - GET `/sources/{sourceId}` → returns metadata + status
  - Support both file upload and URL reference

#### A5. Frontend — Video Source Step (enhanced)
- [ ] Update `frontend/src/features/projects/VideoSourceStep.tsx`:
  - File picker drag-and-drop for video files
  - Display detected metadata after ingestion (duration, resolution, FPS, codec)
  - Show validation errors if file is invalid
  - Progress indicator during indexing

#### A6. Frontend — Video Ingestion API Service
- [ ] Update `frontend/src/services/sources.ts`:
  - `uploadVideo(projectId: string, file: File): Promise<SourceVideo>`
  - `getSourceVideo(projectId: string, sourceId: string): Promise<SourceVideo>`

---

### Phase B: Player Detection & Tracking (Core CV Pipeline)

**Goal**: System can detect players in frames, track them across time, and produce raw tracklets.

#### B1. Backend — Detection Models
- [ ] Define `DetectionResult`: detection_id, frame_timestamp, bbox_x, bbox_y, bbox_width, bbox_height, confidence, class_label (person/ball/pitch), object_id (for tracking)
- [ ] Define `Tracklet`: tracklet_id, source_id, first_frame_index, last_frame_index, frame_count, avg_bbox, appearance_frames (list of frame_indices), status (active/incomplete/truncated)

#### B2. Backend — Detection Service
- [ ] Create `backend/src/services/detection_pipeline.py`:
  - `run_detection(source_id, model="yolov8n") -> list[DetectionResult]` — detect persons in keyframes
  - `detect_in_frame(image_bytes) -> list[bbox, confidence, class]` — single-frame detection
  - Graceful fallback when detector fails: return empty detections with warning (not error)

#### B3. Backend — Tracking Service
- [ ] Create `backend/src/services/tracking_pipeline.py`:
  - `run_tracking(source_id, detections) -> list[Tracklet]` — associate detections across frames
  - Use Hungarian algorithm for assignment, IoU threshold for matching
  - Gap tolerance: allow tracklet gaps of up to K frames before splitting
  - Track persistence scoring

#### B4. Backend — Detection/Tracking Unit Tests
- [ ] Create `backend/tests/unit/test_detection_pipeline.py`:
  - Test: detector returns valid bboxes on synthetic test image
  - Test: no false positives on empty/black frame
  - Test: detection confidence threshold filtering works
- [ ] Create `backend/tests/unit/test_tracking_pipeline.py`:
  - Test: single object tracked across frames with consistent ID
  - Test: two objects maintain separate IDs when spatially separated
  - Test: temporary occlusion handled (gap tolerance)
  - Test: track persistence scoring correct

#### B5. Backend — Detection Worker Integration
- [ ] Update `backend/src/workers/local_runner.py` or create `backend/src/workers/detection_worker.py`:
  - Task definition for detection pipeline run
  - Progress reporting (frames processed, detections found)
  - Error handling and retry on failure

---

### Phase C: Jersey Recognition & Color Extraction

**Goal**: From player bboxes, extract jersey number and color cues.

#### C1. Backend — Jersey Number Recognition Service
- [ ] Create `backend/src/services/jersey_recognition_service.py`:
  - `recognize_jersey_number(roi_image) -> {number: str|None, confidence: float, readable: bool}`
  - Phase 1: template matching approach (no heavy OCR dependency)
  - Store detected number as string ("8", "10", etc.) for consistency
- [ ] `backend/src/services/jersey_color_service.py`:
  - `extract_dominant_color(roi_image) -> {color_name: str, hex: str, confidence: float}`
  - Map HSV color to canonical team names
  - Handle multi-color detection

#### C2. Backend — Player Candidate Matcher (enhance existing)
- [ ] Enhance `backend/src/services/player_candidate_matcher.py`:
  - Add jersey number + color cross-referencing across tracklets
  - Confidence scoring based on evidence quality
  - Return match reasons and review warnings

#### C3. Backend — Jersey Recognition Tests
- [ ] Create `backend/tests/unit/test_jersey_recognition_service.py`:
  - Test: template matching returns correct number on clean jersey image
  - Test: unreadable/no-number ROI returns {number: None, readable: False}
  - Test: color extraction returns plausible color for solid-color jersey
- [ ] Create `backend/tests/contract/test_jersey_color_contract.py`:
  - Test: full pipeline detection → tracking → recognition returns consistent data

---

### Phase D: Candidate Clustering & Identity Resolution (User Story 2)

**Goal**: Multiple tracklets with same jersey/color cluster into candidate identities.

#### D1. Backend — Clustering Service
- [ ] Create `backend/src/services/identity_clustering_service.py`:
  - `cluster_candidates(source_id, jersey_number, color_hint) -> list[CandidateCluster]`
  - Cluster by: jersey number match + color match + non-overlapping segments + body shape similarity
  - Each cluster: cluster_id, evidence_count, inferred_color, visible_cues, cue_summary, match_reasons, review_warning, confidence
- [ ] Update `backend/src/services/player_evidence_service.py` to use clustering

#### D2. Backend — Clustering Tests
- [ ] Create `backend/tests/unit/test_identity_clustering_service.py`:
  - Test: tracklets with same number + color cluster together
  - Test: same number, different color → separate clusters
  - Test: no-color evidence still groups by number alone (with warning)
  - Test: body shape consistency boosts confidence within cluster

---

### Phase E: Evidence Presentation & Confirmation (User Story 1+2)

**Goal**: User reviews real video evidence and confirms target player. (Already specified in 003 spec — integrate with this new full scope.)

#### E1. Backend — Evidence Artifacts (existing services)
- [ ] Complete `backend/src/services/evidence_artifact_service.py` → frame/clip extraction via FFmpeg
- [ ] Complete `backend/src/services/player_evidence_service.py` → evidence request lifecycle
- [ ] Complete `backend/src/services/player_candidate_matcher.py` → cue matching
- [ ] Complete `backend/src/services/player_confirmation_service.py` → confirmation gating

#### E2. Backend — Evidence API Route
- [ ] Ensure `backend/src/api/routes/projects.py` serves:
  - POST `/projects/{id}/player-request` → start evidence search
  - GET `/projects/{id}/player-candidates` → list candidates with evidence
  - POST `/projects/{id}/player-confirmation` → confirm/reject candidate
  - GET `/projects/{id}/evidence-media/{name}` → serve thumbnails/clips

#### E3. Backend — Evidence Contract Tests
- [ ] `backend/tests/contract/test_real_player_evidence_api.py`:
  - Test: POST player-request returns 202, source is validated, no placeholder URIs
  - Test: GET candidates returns valid evidence items with timestamps, media_uri, origin
  - Test: POST confirmation transitions project state correctly
  - Test: evidence media serving returns actual file content (not empty/mocked)

#### E4. Frontend — Evidence Review Panel
- [ ] Complete `frontend/src/features/projects/CandidateEvidencePanel.tsx`:
  - Render real thumbnails/clips from backend media URIs
  - Display candidate metadata: number, color, evidence count, confidence, warnings
  - Candidate comparison view (side-by-side cards)
  - Confirm/reject buttons per candidate
  - Rerun search control
- [ ] Complete `frontend/src/features/projects/PlayerConfirmationStep.tsx`:
  - Loading / no-result / failure states for evidence requests
  - Multi-candidate selection workflow
  - Lock Step 3 until confirmation

#### E5. Frontend — Evidence Tests
- [ ] Complete `frontend/src/features/projects/CandidateEvidencePanel.test.tsx`
- [ ] Complete `frontend/src/features/projects/PlayerConfirmationStep.test.tsx`:
  - Test: panel renders real media, not placeholders
  - Test: multi-candidate comparison displays correctly
  - Step 3 locked until confirmation
  - Rerun updates candidates without locking/unlocking incorrectly

---

### Phase F: Reel Generation & Export (User Story 3 + Output Profiles)

**Goal**: From confirmed identity, generate short/medium/marked output clips.

#### F1. Backend — Appearance Extraction Service
- [ ] Create `backend/src/services/appearance_extraction_service.py`:
  - `extract_appearances(confirmed_player_id) -> list[Appearance]`
  - Appearance: appearance_id, tracklet_id, start_time, end_time, duration, confidence, pitch_side (left/right/center), ball_proximity_score (if available)
  - Score and rank appearances by composite relevance

#### F2. Backend — Reel Export Service
- [ ] Create `backend/src/services/reel_export_service.py`:
  - `generate_reel(project_id, output_profile, overlay_mode) -> ReelOutput`
  - Profile: short_highlight (top-K ~10 clips, 30-60s total), medium_best_plays (top-K ~15 clips, 2-5min)
  - Overlay mode: none or target_marker (draw colored bbox on confirmed player)
  - Extract clips via FFmpeg → concat with crossfade → encode H.264 MP4
  - Progress reporting during export

#### F3. Backend — Export API Route
- [ ] Create/complete `backend/src/api/routes/exports.py`:
  - POST `/projects/{id}/exports` → create reel (with output_profile + target_marker)
  - GET `/projects/{id}/exports` → list outputs with status
  - GET `/exports/{outputId}/download` → serve final MP4
  - Evidence-backed identity gate on export creation

#### F4. Backend — Export Contract & Integration Tests
- [ ] `backend/tests/contract/test_evidence_backed_exports_api.py`:
  - Test: export rejected without confirmed player identity (409)
  - Test: export accepted with confirmed identity, returns processing status
- [ ] `backend/tests/integration/test_evidence_backed_export_flow.py`:
  - Test: full flow confirmation → export creation → output available for download
  - Test: short and medium profiles both generate
  - Test: target marker overlay applied correctly

#### F5. Frontend — Reel Generation Step
- [ ] Complete `frontend/src/features/projects/ReelGenerationStep.tsx`:
  - Display confirmed identity summary (number, color, evidence count)
  - Output profile selector (short / medium)
  - Target marker toggle
  - Generate button (disabled until confirmation)
  - Progress indicator during generation
- [ ] Complete `frontend/src/features/exports/ExportsPage.tsx`:
  - List generated reels with download links
  - Status indicators for each output

#### F6. Frontend — Reel Tests
- [ ] Complete `frontend/src/features/projects/ReelGenerationStep.test.tsx`:
  - Test: locked until confirmation
  - Test: enabled after confirmation with identity summary displayed

---

### Phase G: Manual Evidence Scrubber (Hudl SportsCode Timeline)

**Goal**: Interactive timeline for scrubbing through evidence appearances.

#### G1. Frontend — Evidence Scrubber Component
- [ ] Create `frontend/src/features/projects/EvidenceScrubber.tsx`:
  - Horizontal timeline spanning full video duration
  - Appearance markers as colored segments on timeline
  - Current playhead position with drag
  - Click/mouseover to show timestamped thumbnail preview
  - Visual separation by candidate cluster (color coding)

#### G2. Frontend — Scrubber Tests
- [ ] Create `frontend/src/features/projects/EvidenceScrubber.test.tsx`:
  - Test: timeline renders correctly for video duration
  - Test: appearance markers positioned at correct timestamps
  - Test: scrubbing updates displayed thumbnail
  - Test: click on marker jumps to that timestamp

---

### Phase H: Polish, Testing & Documentation

#### H1. Backend — End-to-End Integration Tests
- [ ] Create `backend/tests/integration/test_full_pipeline.py`:
  - Test: video ingest → detection → tracking → recognition → evidence → confirmation → export (all in one flow)
  - Test: cancel during processing and resume
  - Test: rerun with different jersey number updates candidates
  - Test: cleanup removes artifacts after export

#### H2. Backend — Performance Tests
- [ ] Create `backend/tests/integration/test_performance.py`:
  - Test: detection on 1080p video at reasonable speed
  - Test: memory stays bounded for 2hr+ video
  - Test: concurrent evidence requests handled (one at a time)

#### H3. Documentation & Quickstart
- [ ] Update `backend/README.md` with full pipeline documentation
- [ ] Update `specs/*/quickstart.md` with local setup steps (FFmpeg, YOLO, etc.)
- [ ] Create `MANUAL_TESTING.md` with test video recommendations and expected results

---

## Testing Strategy Summary

| Layer | What it tests | Framework | Run with |
|-------|-------------|-----------|----------|
| **Unit** | Individual service functions (detection, tracking, recognition, clustering) without external deps | pytest / Vitest | `pytest backend/tests/unit/` / `npm test frontend/` |
| **Contract** | API request/response shapes, validation, status codes match OpenAPI spec | pytest + httpx / Vitest | Same as above |
| **Integration** | Multi-service flows (full pipeline, evidence → export) with real fixtures | pytest + temp files / Vitest | Same as above |
| **Manual** | Real-video visual review on actual soccer footage with known target players | Human judgment + checklist | `specs/*/checklists/` |

### Test Fixture Strategy
- Use synthetic test images for detection/OCR unit tests (clean jersey numbers, colored rectangles)
- Use `video/video.mp4` as the primary integration test fixture
- Generate small synthetic MP4s in-memory for frame extraction tests

---

## Implementation Order Summary

1. **Phase A** — Video ingestion & indexing (foundation)
2. **Phase B** — Detection + tracking pipeline (core CV)
3. **Phase C** — Jersey recognition + color extraction (player cues)
4. **Phase D** — Candidate clustering (identity resolution)
5. **Phase E** — Evidence presentation & confirmation (US1+US2, from 003 spec)
6. **Phase F** — Reel generation & export (US3 + output profiles)
7. **Phase G** — Evidence scrubber timeline (UX polish)
8. **Phase H** — Integration tests, performance, docs

Each phase is independently testable and delivers a working increment. Phase E builds on the existing 003 spec; Phases B, C, D add the CV pipeline that was previously placeholder-level.
