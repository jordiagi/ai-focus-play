CREATE TABLE projects (
  project_id        TEXT PRIMARY KEY,
  name              TEXT NOT NULL,
  status            TEXT NOT NULL,
  source_id         TEXT,
  jersey_hint       TEXT,
  target_cluster_id TEXT,
  created_at        TEXT NOT NULL,
  updated_at        TEXT NOT NULL
);

CREATE TABLE source_videos (
  source_id         TEXT PRIMARY KEY,
  project_id        TEXT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
  file_path         TEXT NOT NULL,
  original_filename TEXT,
  content_hash      TEXT,
  duration_s        REAL,
  fps               REAL,
  width             INTEGER,
  height            INTEGER,
  codec             TEXT,
  proxy_path        TEXT,
  proxy_status      TEXT,
  created_at        TEXT NOT NULL
);

CREATE TABLE pipeline_jobs (
  job_id            TEXT PRIMARY KEY,
  project_id        TEXT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
  stage             TEXT NOT NULL,
  status            TEXT NOT NULL,
  progress_pct      REAL NOT NULL DEFAULT 0,
  progress_message  TEXT,
  checkpoint_json   TEXT,
  params_json       TEXT,
  error              TEXT,
  created_at         TEXT NOT NULL,
  started_at         TEXT,
  finished_at        TEXT
);
CREATE INDEX idx_jobs_project ON pipeline_jobs(project_id, created_at);

CREATE TABLE tracklets (
  tracklet_id        TEXT PRIMARY KEY,
  source_id          TEXT NOT NULL REFERENCES source_videos(source_id) ON DELETE CASCADE,
  start_ts           REAL NOT NULL,
  end_ts             REAL NOT NULL,
  frame_count        INTEGER NOT NULL,
  avg_conf           REAL,
  kit_color_name     TEXT,
  kit_color_hsv      TEXT,
  cluster_id         TEXT,
  cluster_assignment TEXT,
  synthetic          INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_tracklets_source ON tracklets(source_id);
CREATE INDEX idx_tracklets_cluster ON tracklets(cluster_id);

CREATE TABLE detections (
  detection_id INTEGER PRIMARY KEY,
  source_id    TEXT NOT NULL REFERENCES source_videos(source_id) ON DELETE CASCADE,
  tracklet_id  TEXT,
  ts           REAL NOT NULL,
  x            REAL NOT NULL,
  y            REAL NOT NULL,
  w            REAL NOT NULL,
  h            REAL NOT NULL,
  conf         REAL
);
CREATE INDEX idx_detections_source_ts ON detections(source_id, ts);
CREATE INDEX idx_detections_tracklet ON detections(tracklet_id);

CREATE TABLE tracklet_crops (
  crop_id     TEXT PRIMARY KEY,
  tracklet_id TEXT NOT NULL REFERENCES tracklets(tracklet_id) ON DELETE CASCADE,
  ts          REAL NOT NULL,
  crop_path   TEXT NOT NULL,
  sharpness   REAL,
  bbox_h_px   INTEGER,
  purpose     TEXT NOT NULL
);
CREATE INDEX idx_crops_tracklet ON tracklet_crops(tracklet_id);

CREATE TABLE tracklet_embeddings (
  tracklet_id TEXT PRIMARY KEY REFERENCES tracklets(tracklet_id) ON DELETE CASCADE,
  model       TEXT NOT NULL,
  dim         INTEGER NOT NULL,
  vector      BLOB NOT NULL,
  crop_count  INTEGER NOT NULL
);

CREATE TABLE identity_clusters (
  cluster_id     TEXT PRIMARY KEY,
  source_id      TEXT NOT NULL REFERENCES source_videos(source_id) ON DELETE CASCADE,
  jersey_number  TEXT,
  jersey_conf    REAL,
  kit_color_name TEXT,
  tracklet_count INTEGER NOT NULL,
  screen_time_s  REAL NOT NULL,
  rep_crop_path  TEXT,
  status         TEXT NOT NULL
);

CREATE TABLE jersey_votes (
  vote_id     TEXT PRIMARY KEY,
  tracklet_id TEXT NOT NULL REFERENCES tracklets(tracklet_id) ON DELETE CASCADE,
  ts          REAL NOT NULL,
  crop_path   TEXT,
  text        TEXT NOT NULL,
  conf        REAL NOT NULL,
  model       TEXT NOT NULL
);
CREATE INDEX idx_votes_tracklet ON jersey_votes(tracklet_id);

CREATE TABLE user_clicks (
  click_id             TEXT PRIMARY KEY,
  project_id           TEXT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
  ts                   REAL NOT NULL,
  x_norm               REAL NOT NULL,
  y_norm               REAL NOT NULL,
  label                TEXT NOT NULL,
  status               TEXT NOT NULL,
  resolved_tracklet_id TEXT,
  sam2_job_id          TEXT,
  created_at           TEXT NOT NULL
);
CREATE INDEX idx_clicks_project ON user_clicks(project_id);

CREATE TABLE appearance_segments (
  segment_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
  cluster_id TEXT NOT NULL,
  start_ts   REAL NOT NULL,
  end_ts     REAL NOT NULL,
  score      REAL,
  included   INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX idx_segments_project ON appearance_segments(project_id, start_ts);

CREATE TABLE reel_outputs (
  output_id        TEXT PRIMARY KEY,
  project_id       TEXT NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
  profile          TEXT NOT NULL,
  overlay_mode     TEXT NOT NULL,
  status           TEXT NOT NULL,
  file_path        TEXT,
  duration_s       REAL,
  segment_ids_json TEXT NOT NULL,
  created_at       TEXT NOT NULL
);
