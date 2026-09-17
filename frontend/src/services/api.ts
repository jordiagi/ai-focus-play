import { Match, Highlight, Event, Drawing, RadarFrame, AnalyticsData } from '../types';

const API_BASE = '/api';

export const api = {
  async listMatches(): Promise<Match[]> {
    const res = await fetch(`${API_BASE}/matches`);
    if (!res.ok) throw new Error('Failed to fetch matches');
    return res.json();
  },

  async getMatch(id: string): Promise<Match> {
    const res = await fetch(`${API_BASE}/matches/${id}`);
    if (!res.ok) throw new Error(`Failed to fetch match ${id}`);
    return res.json();
  },

  async uploadMatch(formData: FormData): Promise<Match> {
    const res = await fetch(`${API_BASE}/matches/upload`, {
      method: 'POST',
      body: formData,
    });
    if (!res.ok) throw new Error('Upload failed');
    return res.json();
  },

  async getHighlights(matchId: string): Promise<Highlight[]> {
    const res = await fetch(`${API_BASE}/matches/${matchId}/highlights`);
    if (!res.ok) return [];
    return res.json();
  },

  async createHighlight(matchId: string, data: Partial<Highlight>): Promise<Highlight> {
    const res = await fetch(`${API_BASE}/matches/${matchId}/highlights`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error('Failed to create highlight');
    return res.json();
  },

  async deleteHighlight(matchId: string, highlightId: string): Promise<void> {
    await fetch(`${API_BASE}/matches/${matchId}/highlights/${highlightId}`, {
      method: 'DELETE',
    });
  },

  async getEvents(matchId: string): Promise<Event[]> {
    const res = await fetch(`${API_BASE}/matches/${matchId}/events`);
    if (!res.ok) return [];
    return res.json();
  },

  async getRadarFrames(matchId: string, time?: number): Promise<RadarFrame[]> {
    const url = time !== undefined 
      ? `${API_BASE}/matches/${matchId}/radar?time=${time}` 
      : `${API_BASE}/matches/${matchId}/radar`;
    const res = await fetch(url);
    if (!res.ok) return [];
    return res.json();
  },

  async getAnalytics(matchId: string): Promise<AnalyticsData | null> {
    const res = await fetch(`${API_BASE}/matches/${matchId}/analytics`);
    if (!res.ok) return null;
    return res.json();
  },

  async getDrawings(matchId: string): Promise<Drawing[]> {
    const res = await fetch(`${API_BASE}/matches/${matchId}/drawings`);
    if (!res.ok) return [];
    return res.json();
  },

  async saveDrawing(matchId: string, drawing: Omit<Drawing, 'id'>): Promise<Drawing> {
    const res = await fetch(`${API_BASE}/matches/${matchId}/drawings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(drawing),
    });
    if (!res.ok) throw new Error('Failed to save drawing');
    return res.json();
  },

  async clearDrawings(matchId: string, time?: number): Promise<void> {
    const url = time !== undefined 
      ? `${API_BASE}/matches/${matchId}/drawings?time=${time}`
      : `${API_BASE}/matches/${matchId}/drawings`;
    await fetch(url, { method: 'DELETE' });
  },

  async updateJournal(matchId: string, notes: string): Promise<void> {
    await fetch(`${API_BASE}/matches/${matchId}/journal`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ journal_notes: notes }),
    });
  },
};
