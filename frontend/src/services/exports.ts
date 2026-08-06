import { apiRequest, apiUrl } from "./apiClient";
import type { OverlayMode, ReelExportItem, ReelProfile } from "../features/projects/guidedTypes";

export type CreateExportPayload = {
  profile: ReelProfile;
  overlay_mode: OverlayMode;
};

export function createExport(
  projectId: string,
  payload: CreateExportPayload,
): Promise<{ output_id: string; job_id: string }> {
  return apiRequest(`/projects/${projectId}/exports`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function listExports(projectId: string): Promise<{ outputs: ReelExportItem[] }> {
  return apiRequest(`/projects/${projectId}/exports`);
}

export function exportDownloadUrl(projectId: string, outputId: string): string {
  return apiUrl(`/projects/${projectId}/exports/${outputId}/download`);
}
