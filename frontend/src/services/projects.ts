import { apiRequest, apiUrl } from "./apiClient";
import type {
  ClickResolution,
  CoverageSegment,
  CoverageSummary,
  FrameDetections,
  GuidedProject,
  IdentityCandidate,
  PipelineJob,
  PlayerClick,
  TimelineResponse,
} from "../features/projects/guidedTypes";


export async function createProject(name = "Untitled project"): Promise<GuidedProject> {
  return apiRequest("/projects", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export async function getProject(projectId: string): Promise<GuidedProject> {
  return apiRequest(`/projects/${projectId}`);
}

export async function listProjects(): Promise<GuidedProject[]> {
  return apiRequest("/projects");
}

export async function attachSource(
  projectId: string,
  payload: Record<string, unknown> | FormData,
): Promise<{ source: Record<string, unknown>; jobs_queued: Array<{ job_id: string; stage: string }> }> {
  return apiRequest(`/projects/${projectId}/source`, {
    method: "POST",
    body: payload instanceof FormData ? payload : JSON.stringify(payload),
  });
}

export async function getJobs(projectId: string): Promise<{ jobs: PipelineJob[] }> {
  return apiRequest(`/projects/${projectId}/jobs`);
}

export async function runPipeline(
  projectId: string,
  stages?: string[],
  force = false,
): Promise<{ jobs_queued: Array<{ job_id: string; stage: string }> }> {
  return apiRequest(`/projects/${projectId}/pipeline/run`, {
    method: "POST",
    body: JSON.stringify({
      ...(stages ? { stages } : {}),
      ...(force ? { force: true } : {}),
    }),
  });
}

export function frameUrl(projectId: string, timestamp: number): string {
  return apiUrl(`/projects/${projectId}/frame?t=${encodeURIComponent(timestamp)}`);
}

export async function getFrameDetections(projectId: string, timestamp: number): Promise<FrameDetections> {
  return apiRequest(`/projects/${projectId}/frame-detections?t=${encodeURIComponent(timestamp)}`);
}

export async function postClick(
  projectId: string,
  payload: { t: number; x_norm: number; y_norm: number; label: "positive" | "negative" },
): Promise<ClickResolution> {
  return apiRequest(`/projects/${projectId}/clicks`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getClicks(projectId: string): Promise<{ clicks: PlayerClick[] }> {
  return apiRequest(`/projects/${projectId}/clicks`);
}

export async function getCandidates(
  projectId: string,
  clusterId?: string,
  anchorTrackletId?: string | null,
  anchorTimestamp?: number | null,
): Promise<{ candidates: IdentityCandidate[] }> {
  const query = new URLSearchParams();
  if (clusterId) query.set("cluster_id", clusterId);
  if (anchorTrackletId) query.set("anchor_tracklet_id", anchorTrackletId);
  if (anchorTimestamp != null) query.set("anchor_ts", String(anchorTimestamp));
  const encodedQuery = query.toString();
  const suffix = encodedQuery ? `?${encodedQuery}` : "";
  return apiRequest(`/projects/${projectId}/candidates${suffix}`);
}

export async function confirmTarget(
  projectId: string,
  clusterId: string,
): Promise<{ target_cluster_id: string; coverage: CoverageSummary }> {
  return apiRequest(`/projects/${projectId}/target`, {
    method: "POST",
    body: JSON.stringify({ cluster_id: clusterId }),
  });
}

export async function adjustTarget(
  projectId: string,
  payload: { add_tracklet_ids?: string[]; remove_tracklet_ids?: string[] },
): Promise<{ coverage: CoverageSummary }> {
  return apiRequest(`/projects/${projectId}/target/adjust`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function resetTarget(projectId: string): Promise<void> {
  return apiRequest(`/projects/${projectId}/target`, { method: "DELETE" });
}

export async function getTimeline(projectId: string): Promise<TimelineResponse> {
  return apiRequest(`/projects/${projectId}/timeline`);
}

export async function patchTimelineSegment(
  projectId: string,
  segmentId: string,
  payload: { included?: boolean; start_ts?: number; end_ts?: number },
): Promise<Pick<CoverageSegment, "segment_id" | "start_ts" | "end_ts" | "included">> {
  return apiRequest(`/projects/${projectId}/timeline/${segmentId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function putJerseyHint(
  projectId: string,
  jerseyHint: string | null,
): Promise<{ jersey_hint: string | null }> {
  return apiRequest(`/projects/${projectId}/jersey-hint`, {
    method: "PUT",
    body: JSON.stringify({ jersey_hint: jerseyHint }),
  });
}
