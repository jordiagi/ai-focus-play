import { Match, Highlight, Event, Drawing, RadarFrame, AnalyticsData, Capabilities } from '../types';

const API_BASE = '/api';

export class ApiError extends Error {
  status: number;
  url: string;

  constructor(message: string, status: number, url: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.url = url;
  }
}

async function handleResponse<T>(res: Response, url: string): Promise<T> {
  if (!res.ok) {
    let errorDetail = res.statusText;
    try {
      const data = await res.json();
      if (data && data.detail) errorDetail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail);
    } catch {
      // ignore json parse error
    }
    throw new ApiError(errorDetail || `Request failed with status ${res.status}`, res.status, url);
  }
  return res.json();
}

export const api = {
  async getCapabilities(signal?: AbortSignal): Promise<Capabilities> {
    const url = `${API_BASE}/capabilities`;
    const res = await fetch(url, { signal });
    return handleResponse<Capabilities>(res, url);
  },

  async listMatches(signal?: AbortSignal): Promise<Match[]> {
    const url = `${API_BASE}/matches`;
    const res = await fetch(url, { signal });
    return handleResponse<Match[]>(res, url);
  },

  async getMatch(id: string, signal?: AbortSignal): Promise<Match> {
    const url = `${API_BASE}/matches/${id}`;
    const res = await fetch(url, { signal });
    return handleResponse<Match>(res, url);
  },

  async uploadMatch(formData: FormData): Promise<Match> {
    const url = `${API_BASE}/matches/upload`;
    const res = await fetch(url, {
      method: 'POST',
      body: formData,
    });
    return handleResponse<Match>(res, url);
  },

  async getMatchProgress(id: string, signal?: AbortSignal): Promise<{ match_id: string; status: string; step: string; progress: number; error?: string }> {
    const url = `${API_BASE}/matches/${id}/progress`;
    const res = await fetch(url, { signal });
    return handleResponse(res, url);
  },

  async getHighlights(matchId: string, signal?: AbortSignal): Promise<Highlight[]> {
    const url = `${API_BASE}/matches/${matchId}/highlights`;
    const res = await fetch(url, { signal });
    return handleResponse<Highlight[]>(res, url);
  },

  async createHighlight(matchId: string, data: Partial<Highlight>): Promise<Highlight> {
    const url = `${API_BASE}/matches/${matchId}/highlights`;
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    return handleResponse<Highlight>(res, url);
  },

  async deleteHighlight(matchId: string, highlightId: string): Promise<void> {
    const url = `${API_BASE}/matches/${matchId}/highlights/${highlightId}`;
    const res = await fetch(url, {
      method: 'DELETE',
    });
    if (!res.ok) {
      throw new ApiError(`Failed to delete highlight ${highlightId}`, res.status, url);
    }
  },

  async getEvents(matchId: string, signal?: AbortSignal): Promise<Event[]> {
    const url = `${API_BASE}/matches/${matchId}/events`;
    const res = await fetch(url, { signal });
    return handleResponse<Event[]>(res, url);
  },

  async getRadarFrames(matchId: string, time?: number, signal?: AbortSignal): Promise<RadarFrame[]> {
    const url = time !== undefined 
      ? `${API_BASE}/matches/${matchId}/radar?time=${time}` 
      : `${API_BASE}/matches/${matchId}/radar`;
    const res = await fetch(url, { signal });
    return handleResponse<RadarFrame[]>(res, url);
  },

  async getRadarWindow(matchId: string, start: number, end: number, signal?: AbortSignal): Promise<RadarFrame[]> {
    const url = `${API_BASE}/matches/${matchId}/radar/window?start=${start}&end=${end}`;
    const res = await fetch(url, { signal });
    return handleResponse<RadarFrame[]>(res, url);
  },

  async getRadarMeta(matchId: string, signal?: AbortSignal): Promise<{ match_id: string; frame_count: number; duration: number; sample_fps: number }> {
    const url = `${API_BASE}/matches/${matchId}/radar/meta`;
    const res = await fetch(url, { signal });
    return handleResponse(res, url);
  },

  async getAnalytics(matchId: string, signal?: AbortSignal): Promise<AnalyticsData | null> {
    const url = `${API_BASE}/matches/${matchId}/analytics`;
    const res = await fetch(url, { signal });
    if (res.status === 404) return null;
    return handleResponse<AnalyticsData>(res, url);
  },

  async swapTeams(matchId: string): Promise<{ status: string; message: string }> {
    const url = `${API_BASE}/matches/${matchId}/teams/swap`;
    const res = await fetch(url, { method: 'POST' });
    return handleResponse(res, url);
  },

  async getDrawings(matchId: string, signal?: AbortSignal): Promise<Drawing[]> {
    const url = `${API_BASE}/matches/${matchId}/drawings`;
    const res = await fetch(url, { signal });
    return handleResponse<Drawing[]>(res, url);
  },

  async saveDrawing(matchId: string, drawing: Omit<Drawing, 'id'>): Promise<Drawing> {
    const url = `${API_BASE}/matches/${matchId}/drawings`;
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(drawing),
    });
    return handleResponse<Drawing>(res, url);
  },

  async clearDrawings(matchId: string, time?: number): Promise<void> {
    const url = time !== undefined 
      ? `${API_BASE}/matches/${matchId}/drawings?time=${time}`
      : `${API_BASE}/matches/${matchId}/drawings`;
    const res = await fetch(url, { method: 'DELETE' });
    if (!res.ok) throw new ApiError('Failed to clear drawings', res.status, url);
  },

  async updateJournal(matchId: string, notes: string): Promise<void> {
    const url = `${API_BASE}/matches/${matchId}/journal`;
    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ journal_notes: notes }),
    });
    if (!res.ok) throw new ApiError('Failed to update journal', res.status, url);
  },

  getExportHighlightsUrl(matchId: string): string {
    return `${API_BASE}/matches/${matchId}/highlights/export`;
  }
};
