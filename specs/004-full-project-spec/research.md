# Research: Full Project Implementation Decisions

## Decision: CV pipeline uses lightweight models first, GPU optional later

**Rationale**: The MVP targets local macOS development without requiring CUDA. Start with YOLOv8n (nano), template-based jersey recognition, HSV color extraction — all CPU-feasible. If GPU is available, YOLO can auto-detect and use it. Future optimization can swap to faster/more accurate models.

**Alternatives considered**:
- Full DETR/Transformers stack: too heavy for MVP, unnecessary accuracy gain at this stage
- Pre-built sports analytics SDKs: none open-source and capable of what we need
- Custom player re-ID network: requires training data we don't have yet

## Decision: Jersey recognition uses template matching in Phase 1, OCR later

**Rationale**: Building a production-grade jersey OCR model requires thousands of annotated soccer jersey images. Template matching (digit grid templates + match scoring) gives us enough accuracy for MVP with zero training data and no ML framework dependency. When we have enough captured evidence, train a CNN classifier on real jersey numbers.

**Alternatives considered**:
- Tesseract/OCR: works but heavy dependency, poor results on curved/stadium jerseys
- YOLO-based digit detection: requires model training
- Manual-only: defeats the purpose of automated candidate generation

## Decision: Color extraction uses HSV with canonical team palette

**Rationale**: Soccer jerseys have distinct, saturated colors that map well to HSV space. A curated palette of ~10 canonical team colors covers 95%+ of real cases. Per-pixel HSV histogram → dominant channel → nearest palette entry gives a fast, interpretable result.

**Alternatives considered**:
- K-means clustering on pixels: more accurate but overkill for MVP
- Color name CNN: requires training data + ML dependency

## Decision: Tracklet association uses IoU + Hungarian algorithm

**Rationale**: Standard multi-object tracking with IoU matching and Hungarian assignment is well-understood, fast (O(n log n)), and works reliably for soccer's large-person bboxes at our sampling rate (every 15 frames ≈ 0.5s). Gap tolerance handles brief occlusions without needing a heavy Kalman filter or DeepSORT embedding model.

**Alternatives considered**:
- DeepSORT/ByteTrack: better re-ID but heavier dependency chain
- Simple proximity-based matching: fails more often with crossing players

## Decision: Identity clustering uses rule-based scoring, not ML

**Rationale**: We have a small, well-defined feature space (jersey number, team color, body proportions, pitch position). A weighted scoring function is interpretable, debuggable, and doesn't require training data. When we accumulate enough confirmed evidence, we can train a classifier later.

**Alternatives considered**:
- DBSCAN/gaussian mixture clustering: overkill for ~5 features with clear semantics
- Neural re-ID embedding: requires training data + GPU

## Decision: Video processing is local and sequential per project

**Rationale**: MVP targets single-user, single-video workflows. No concurrent processing needed. Sequential processing simplifies state management, artifact lifecycle, and memory management. Remote/GPU workers can be added later.

**Alternatives considered**:
- Distributed task queue (Celery/RQ): overkill for v1
- Cloud-based processing: adds cost, latency, dependency

## Decision: Reel assembly uses FFmpeg concat + overlay filters

**Rationale**: FFmpeg's `concat` demuxer and `drawbox`/`box` filter handle clip assembly, crossfade transitions, and player marker overlay — all without recompiling or additional dependencies. This matches what Hudl does under the hood (video concatenation) but in a single CLI tool.

**Alternatives considered**:
- MoviePy: Python-based but slower and larger dependency
- Manual frame manipulation with OpenCV: reinventing video muxing

## Decision: Artifact storage is project-scoped directory, not database

**Rationale**: Evidence frames, tracklets, detections are all project-local disposable data. Storing under `~/.ai-focus-play/projects/{project_id}/artifacts/` is simpler than migrating to blob storage or embedding base64 in JSON (which bloats metadata). Cleanup runs periodically.

**Alternatives considered**:
- SQLite BLOB column: complicates artifact lifecycle, harder to debug
- Cloud storage (S3): unnecessary complexity for v1 MVP
