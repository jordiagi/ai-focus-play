import { apiRequest } from "./apiClient";
import type { SourceCatalogItem } from "../features/projects/guidedTypes";


export async function listLocalSources(): Promise<{ video_root: string; items: SourceCatalogItem[] }> {
  return apiRequest("/sources/local");
}
