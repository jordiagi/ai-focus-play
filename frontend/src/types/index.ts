export interface DrawingCoordinate {
  x: number; // 0..1 normalized coordinate
  y: number; // 0..1 normalized coordinate
}

export interface Drawing {
  id: string;
  match_id: string;
  timestamp: number;
  tool_type: 'arrow' | 'spotlight' | 'circle' | 'pen' | 'text';
  color: string;
  coordinates: DrawingCoordinate[];
  text_label?: string;
  created_at?: number;
}

export interface Highlight {
  id: string;
  match_id: string;
  title: string;
  event_type: 'goal' | 'shot' | 'save' | 'foul' | 'corner' | 'kickoff' | 'custom';
  start_time: number;
  end_time: number;
  period: number;
  team: 'home' | 'away' | 'neutral';
  player_jersey?: string;
  player_name?: string;
  thumbnail_url?: string;
  clip_url?: string;
  is_ai_detected: boolean;
  tags: string[];
  comments_count: number;
  created_at?: number;
}

export interface Event {
  id: string;
  match_id: string;
  timestamp: number;
  period: number;
  event_type: string;
  team: 'home' | 'away';
  player_jersey?: string;
  player_name?: string;
  description: string;
  pitch_x: number;
  pitch_y: number;
}

export interface RadarPlayer {
  id: number;
  team: 'home' | 'away' | 'referee';
  jersey?: string;
  x: number; // 0..105m pitch
  y: number; // 0..68m pitch
  speed: number;
}

export interface RadarBall {
  x: number;
  y: number;
  z: number;
}

export interface RadarFrame {
  timestamp: number;
  players: RadarPlayer[];
  ball: RadarBall;
}

export interface ShotRecord {
  id: string;
  timestamp: number;
  period: number;
  team: 'home' | 'away';
  player_jersey?: string;
  outcome: 'goal' | 'saved' | 'missed' | 'blocked';
  x: number;
  y: number;
  is_inside_box: boolean;
  label: string;
}

export interface TeamStats {
  goals: number;
  shots: number;
  attempts: number;
  corners: number;
  free_kicks: number;
  throw_ins: number;
  fouls: number;
  penalties: number;
  tackles: number;
  passes_completed: number;
  possession_percent: number;
  possession_minutes: number;
  possession_won: number;
}

export interface AnalyticsData {
  home_stats: TeamStats;
  away_stats: TeamStats;
  shot_map: ShotRecord[];
  pass_locations: {
    home: { defensive: number; middle: number; attacking: number };
    away: { defensive: number; middle: number; attacking: number };
  };
  possession_locations: {
    home: { defensive: number; middle: number; attacking: number };
    away: { defensive: number; middle: number; attacking: number };
  };
  pass_strings: {
    home: number[];
    away: number[];
  };
  heatmaps?: {
    home: any[];
    away: any[];
  };
}

export interface PlayerRoster {
  jersey: string;
  name: string;
  position: 'GK' | 'DEF' | 'MID' | 'FWD';
  is_starter: boolean;
  is_captain?: boolean;
  is_player_of_match?: boolean;
  minutes_played: number;
}

export interface Match {
  id: string;
  title: string;
  home_team: string;
  away_team: string;
  home_score: number;
  away_score: number;
  date: string;
  duration_seconds: number;
  status: 'uploading' | 'processing' | 'ready' | 'error';
  processing_step?: string;
  processing_progress: number;
  error_message?: string;
  video_url: string;
  panoramic_url?: string;
  thumbnail_url?: string;
  views_count: number;
  lineup: PlayerRoster[];
  journal_notes: string;
}
