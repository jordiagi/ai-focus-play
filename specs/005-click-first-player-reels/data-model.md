# Data Model: Click-First Player Reels

**Input**: [spec.md](./spec.md)
**Storage**: SQLite (stdlib `sqlite3`, WAL mode) at `{data_dir}/app.db` for all metadata,
including per-frame detections; project-scoped directories on disk for all pixels
(proxy, frames, crops, masks, evidence, exports). The existing JSON store
(`backend/src/storage/database.py`) is deleted.

## Why SQLite (not the existing JSON store)

A 90-minute match at 6 fps analysis with ~15 visible people yields ~500k detection rows
(~50 MB). The current `JsonDatabase` rewrites one JSON blob on every repository call and
cannot serve the frame-overlay endpoint (`GET /frame-detections?t=`) without loading
everything. SQLite with an index on `(source_id, ts)` makes that a single range query.

## Schema

Module: `backend/src/storage/db.py` (connection factory, WAL pragma, migration runner)
and `backend/src/storage/schema.sql`. Migrations: a `schema_migrations(version INT)`
table; `schema.sql` is version 1; later changes append numbered migration files under
`backend/src/storage/migrations/`.

```sql
CREATE TABLE projects (
  project_id        TEXT PRIMARY KEY,
  name              TEXT NOT NULL,
  status            TEXT NOT NULL,   -- draft | ingesting | analyzing | awaiting_target_selection | target_confirmed | ready_to_export
  source_id         TEXT,
  jersey_hint       TEXT,            -- optional user-entered number, supporting cue only
  target_cluster_id TEXT,
  created_at        TEXT NOT NULL,
  updated_at        TEXT NOT NULL
);

CREATE TABLE source_videos (
  source_id         TEXT PRIMARY KEY,
  project_id        TEXT NOT NULL REFERENCES projects(project_id),
  file_path         TEXT NOT NULL,   -- original full-res file (analysis input)
  original_filename TEXT,
  content_hash      TEXT,
  duration_s        REAL,
  fps               REAL,
  width             INTEGER,
  height            INTEGER,
  codec             TEXT,
  proxy_path        TEXT,            -- 720p proxy (all UI serving)
  proxy_status      TEXT,            -- pending | ready | failed
  created_at        TEXT NOT NULL
);

CREATE TABLE pipeline_jobs (
  job_id           TEXT PRIMARY KEY,
  project_id       TEXT NOT NULL REFERENCES projects(project_id),
  stage            TEXT NOT NULL,    -- proxy | detect_track | embed_cluster | jersey_ocr | assemble_candidates | sam2_refine | export
  status           TEXT NOT NULL,    -- queued | running | succeeded | failed | cancelled
  progress_pct     REAL NOT NULL DEFAULT 0,
  progress_message TEXT,             -- plain-language, e.g. "Watching the match — 38 of 92 minutes"
  checkpoint_json  TEXT,             -- stage-specific resume state (e.g. {"last_ts": 2280.5})
  params_json      TEXT,             -- stage inputs (e.g. click_id for sam2_refine, output_id for export)
  error            TEXT,
  created_at       TEXT NOT NULL,
  started_at       TEXT,
  finished_at      TEXT
);
CREATE INDEX idx_jobs_project ON pipeline_jobs(project_id, created_at);

CREATE TABLE tracklets (
  tracklet_id        TEXT PRIMARY KEY,
  source_id          TEXT NOT NULL REFERENCES source_videos(source_id),
  start_ts           REAL NOT NULL,
  end_ts             REAL NOT NULL,
  frame_count        INTEGER NOT NULL,
  avg_conf           REAL,
  kit_color_name     TEXT,           -- canonical color word, e.g. "red"
  kit_color_hsv      TEXT,           -- JSON [h,s,v]
  cluster_id         TEXT,           -- nullable until embed_cluster
  cluster_assignment TEXT,           -- auto | user_click | sam2 | user_removed
  synthetic          INTEGER NOT NULL DEFAULT 0  -- 1 = minted from SAM 2 masks (no detector boxes)
);
CREATE INDEX idx_tracklets_source ON tracklets(source_id);
CREATE INDEX idx_tracklets_cluster ON tracklets(cluster_id);

CREATE TABLE detections (
  detection_id INTEGER PRIMARY KEY,  -- rowid
  source_id    TEXT NOT NULL,
  tracklet_id  TEXT,
  ts           REAL NOT NULL,
  x            REAL NOT NULL,        -- normalized [0,1], top-left
  y            REAL NOT NULL,
  w            REAL NOT NULL,
  h            REAL NOT NULL,
  conf         REAL
);
CREATE INDEX idx_detections_source_ts ON detections(source_id, ts);
CREATE INDEX idx_detections_tracklet ON detections(tracklet_id);

CREATE TABLE tracklet_crops (
  crop_id     TEXT PRIMARY KEY,
  tracklet_id TEXT NOT NULL REFERENCES tracklets(tracklet_id),
  ts          REAL NOT NULL,
  crop_path   TEXT NOT NULL,         -- relative to project artifact dir
  sharpness   REAL,                  -- Laplacian variance (keyframe selection)
  bbox_h_px   INTEGER,               -- native-res box height (legibility filter)
  purpose     TEXT NOT NULL          -- sample | ocr_keyframe
);
CREATE INDEX idx_crops_tracklet ON tracklet_crops(tracklet_id);

CREATE TABLE tracklet_embeddings (
  tracklet_id TEXT PRIMARY KEY REFERENCES tracklets(tracklet_id),
  model       TEXT NOT NULL,         -- e.g. "dinov2-small"
  dim         INTEGER NOT NULL,
  vector      BLOB NOT NULL,         -- float32 little-endian bytes, mean-pooled over crops
  crop_count  INTEGER NOT NULL
);

CREATE TABLE identity_clusters (
  cluster_id     TEXT PRIMARY KEY,
  source_id      TEXT NOT NULL REFERENCES source_videos(source_id),
  jersey_number  TEXT,               -- voted result, nullable
  jersey_conf    REAL,               -- vote agreement ratio
  kit_color_name TEXT,
  tracklet_count INTEGER NOT NULL,
  screen_time_s  REAL NOT NULL,
  rep_crop_path  TEXT,               -- representative crop for candidate cards
  status         TEXT NOT NULL       -- candidate | confirmed | rejected
);

CREATE TABLE jersey_votes (
  vote_id     TEXT PRIMARY KEY,
  tracklet_id TEXT NOT NULL REFERENCES tracklets(tracklet_id),
  ts          REAL NOT NULL,
  crop_path   TEXT,
  text        TEXT NOT NULL,         -- recognized string, digits only
  conf        REAL NOT NULL,
  model       TEXT NOT NULL
);
CREATE INDEX idx_votes_tracklet ON jersey_votes(tracklet_id);

CREATE TABLE user_clicks (
  click_id             TEXT PRIMARY KEY,
  project_id           TEXT NOT NULL REFERENCES projects(project_id),
  ts                   REAL NOT NULL,
  x_norm               REAL NOT NULL,
  y_norm               REAL NOT NULL,
  label                TEXT NOT NULL,  -- positive | negative
  status               TEXT NOT NULL,  -- resolved | pinned | refining | no_player
  resolved_tracklet_id TEXT,
  sam2_job_id          TEXT,
  created_at           TEXT NOT NULL
);
CREATE INDEX idx_clicks_project ON user_clicks(project_id);

CREATE TABLE appearance_segments (
  segment_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(project_id),
  cluster_id TEXT NOT NULL,
  start_ts   REAL NOT NULL,
  end_ts     REAL NOT NULL,
  score      REAL,                    -- duration/size/centrality score for profile selection
  included   INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX idx_segments_project ON appearance_segments(project_id, start_ts);

CREATE TABLE reel_outputs (
  output_id        TEXT PRIMARY KEY,
  project_id       TEXT NOT NULL REFERENCES projects(project_id),
  profile          TEXT NOT NULL,    -- short_highlight | medium_best_plays | full_appearances
  overlay_mode     TEXT NOT NULL,    -- none | target_marker
  status           TEXT NOT NULL,    -- queued | rendering | ready | failed
  file_path        TEXT,
  duration_s       REAL,
  segment_ids_json TEXT NOT NULL,    -- segments included at render time (traceability, FR-016)
  created_at       TEXT NOT NULL
);
```

### Semantics and invariants

- **Cannot-link invariant** (FR-011): two tracklets whose `[start_ts, end_ts]` ranges
  overlap by more than 0.5 s can never share a `cluster_id`. Enforced in the clustering
  stage, re-checked by a unit test on fakes.
- **Negative evidence**: a "Not them" action sets `tracklets.cluster_assignment =
  'user_removed'` and clears `cluster_id`; re-clustering must respect `user_removed` as
  a cannot-link against the target cluster. Negative `user_clicks` rows persist the
  intent.
- **Pins**: a click with `status = 'pinned'` has no `resolved_tracklet_id` yet; the
  detect_track stage, on each checkpoint, attempts to resolve pins whose `ts` is now
  within the processed range.
- **Synthetic tracklets** (`synthetic = 1`) come from SAM 2 refinement where no detector
  boxes existed; their `detections` rows are mask-derived boxes and are excluded from
  re-clustering (they are already assigned to the target cluster).
- **Timestamps** are seconds from video start (REAL). All box coordinates are normalized
  to [0,1] against the **original** video dimensions, so the same rows serve full-res
  analysis, proxy-res UI overlays, and export overlays.
- **Job checkpoints** (`checkpoint_json`) per stage:
  - `proxy`: none (FFmpeg restart is cheap).
  - `detect_track`: `{"last_ts": float, "tracker_state": null}` — resume re-seeks to
    `last_ts - 5.0` and re-primes the tracker with a 5 s warmup before persisting again.
  - `embed_cluster`: `{"embedded_tracklet_ids": [...]}` (embedding is resumable;
    clustering itself is fast and reruns whole).
  - `jersey_ocr`: `{"done_tracklet_ids": [...]}`.
  - `sam2_refine`: none (windows are ≤ 2 min; rerun whole).
  - `export`: `{"rendered_segment_ids": [...]}`.

## On-disk artifact layout

Extends `backend/src/services/artifact_service.py` (keep its path-traversal guards).
All under `{data_dir}/{project_id}/`:

```
proxy/proxy_720p.mp4              # UI serving: frames, previews, evidence clips
frames/frame_{ts_ms}.jpg          # click-UI frame cache (LRU-pruned by cleanup service)
crops/{tracklet_id}/{ts_ms}.jpg   # sampled person crops (evidence strips, embeddings, OCR)
masks/{click_id}/                 # SAM 2 temp frames+masks; deleted when the refine job finishes
evidence/                         # 003 evidence artifacts; serving route unchanged
exports/{output_id}.mp4           # rendered reels
```

Cleanup (`backend/src/services/cleanup_service.py`, extended): `frames/` is an LRU cache
capped by count; `masks/` is deleted at refine-job end; `crops/`, `proxy/`, `evidence/`,
`exports/` live for the project lifetime and are removed on project deletion.

## Entity relationships

```
projects 1─1 source_videos ─┬─* tracklets ─┬─* detections
                            │              ├─* tracklet_crops
                            │              ├─1 tracklet_embeddings
                            │              └─* jersey_votes
                            └─* identity_clusters 1─* tracklets (via cluster_id)
projects ─* pipeline_jobs
projects ─* user_clicks (resolved_tracklet_id → tracklets)
projects ─* appearance_segments (cluster_id → identity_clusters)
projects ─* reel_outputs (segment_ids_json → appearance_segments)
```

## Domain model changes (`backend/src/domain/models/`)

- Keep `project.py` concepts; `Project` gains `jersey_hint`, `target_cluster_id`.
- Replace `detection.py` contents with dataclasses mirroring the tables above
  (`Detection`, `Tracklet`, `IdentityCluster`, `JerseyVote`).
- Extend `video.py`: `SourceVideo` gains `proxy_path`, `proxy_status`, `content_hash`;
  drop `FrameIndexEntry` (the frame index table is removed — SQLite + proxy seeks
  replace it).
- New `pipeline.py`: `PipelineJob`, `JobStage`, `JobStatus`, `Checkpoint` helpers.
- New `selection.py`: `UserClick`, `AppearanceSegment`.
- `player.py`'s `ConfirmedPlayer` evolves to reference `cluster_id` + supporting
  evidence rather than jersey-number-first cues.
