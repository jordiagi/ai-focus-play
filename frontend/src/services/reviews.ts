import { apiRequest } from "./apiClient";

export function startAnalysis(projectId: string, processingMode: "local" | "remote") {
  return apiRequest(`/projects/${projectId}/analysis`, {
    method: "POST",
    body: JSON.stringify({ processing_mode: processingMode }),
  });
}

export function listDetections(projectId: string) {
  return apiRequest(`/projects/${projectId}/detections`);
}

export function reviewDetection(projectId: string, detectionId: string, payload: Record<string, unknown>) {
  return apiRequest(`/projects/${projectId}/detections/${detectionId}/review`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

