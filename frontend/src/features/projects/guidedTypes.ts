export type WorkflowStep = "add_video" | "find_player" | "build_reel" | "complete";

export type AnalysisStage = "proxy" | "detect_track" | "embed_cluster" | "jersey_ocr" | "assemble_candidates" | "sam2_refine" | "export" | "sleep_demo";
export type JobStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";

export type PipelineJob = {
  job_id: string;
  stage: AnalysisStage;
  status: JobStatus;
  progress_pct: number;
  progress_message: string | null;
  error: string | null;
  created_at: string;
  started_at?: string | null;
  finished_at?: string | null;
};

export type DetectionBox = {
  tracklet_id: string | null;
  cluster_id?: string | null;
  x: number;
  y: number;
  w: number;
  h: number;
  is_target: boolean;
};

export type FrameDetections = {
  ts_actual: number;
  analyzed: boolean;
  boxes: DetectionBox[];
};

export type PlayerClick = {
  click_id: string;
  t: number;
  x_norm: number;
  y_norm: number;
  label: "positive" | "negative";
  status: "resolved" | "pinned" | "refining" | "no_player";
  resolved_tracklet_id?: string | null;
  cluster_id?: string | null;
};

export type CandidateEvidence = {
  ts: number;
  thumbnail_uri: string;
  clip_uri?: string;
  tracklet_id: string;
};

export type IdentityCandidate = {
  cluster_id: string;
  jersey_number: string | null;
  jersey_agreement: { readings: number; agrees_with_hint: boolean | null };
  kit_color_name: string | null;
  screen_time_s: number;
  tracklet_count: number;
  rep_crop_uri: string;
  evidence: CandidateEvidence[];
  timeline_spans: Array<{ start_ts: number; end_ts: number }>;
  ambiguous?: boolean;
};

export type CoverageSummary = {
  segment_count: number;
  total_s: number;
  gaps: Array<{ start_ts: number; end_ts: number }>;
};

export type ClickResolution =
  | { click_id: string; resolution: "tracklet"; tracklet_id: string; cluster_id: string | null; box: Omit<DetectionBox, "tracklet_id" | "cluster_id" | "is_target"> }
  | { click_id: string; resolution: "pinned"; message: string }
  | { click_id: string; resolution: "sam2_queued"; job_id: string }
  | { click_id: string; resolution: "no_player_here"; message: string };

export type CoverageSegment = {
  segment_id: string;
  start_ts: number;
  end_ts: number;
  score: number;
  included: boolean;
  thumbnail_uri: string;
  preview_clip_uri: string;
  tracklet_ids?: string[];
};

export type TimelineSummary = {
  segment_count: number;
  total_s: number;
  included_count: number;
};

export type TimelineResponse = {
  summary: TimelineSummary;
  segments: CoverageSegment[];
};

export type ReelProfile = "short_highlight" | "medium_best_plays" | "full_appearances";
export type OverlayMode = "none" | "target_marker";

export type ReelExportItem = {
  output_id: string;
  profile: string;
  overlay_mode: string;
  status: "queued" | "rendering" | "ready" | "failed";
  duration_s?: number | null;
  created_at: string;
};

export type SourceType = "discovered_local" | "relative_local_path" | "youtube";

export type SourceCatalogItem = {
  catalog_id: string;
  display_name: string;
  relative_path: string;
  duration_seconds?: number;
  file_size_bytes?: number;
  last_modified_at?: string;
  details: string;
};

export type GuidedProject = {
  project_id: string;
  name?: string;
  status: string;
  workflow_step?: WorkflowStep;
  source_id?: string | null;
  target_cluster_id?: string | null;
  jersey_hint?: string | null;
  source?: Record<string, unknown> | null;
  analysis?: {
    overall_status: "not_started" | "running" | "complete" | "failed";
    stages: PipelineJob[];
    no_readable_jersey_numbers: boolean;
  };
};

export const guidedStepLabels = ["Add video", "Find your player", "Build the reel"] as const;
