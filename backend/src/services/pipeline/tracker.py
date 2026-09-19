import math
import numpy as np
from typing import List, Dict, Any, Optional
from scipy.optimize import linear_sum_assignment
from backend.src.domain.models.match import RadarPlayer

class Track:
    def __init__(self, track_id: int, x: float, y: float, team: str, jersey: Optional[str] = None):
        self.track_id = track_id
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0
        self.team = team
        self.jersey = jersey
        self.hits = 1
        self.misses = 0
        self.confirmed = False

    def predict(self, dt: float):
        self.x += self.vx * dt
        self.y += self.vy * dt
        # Clamp within pitch bounds (0..105, 0..68)
        self.x = max(0.0, min(105.0, self.x))
        self.y = max(0.0, min(68.0, self.y))

    def update(self, x: float, y: float, team: str, dt: float, jersey: Optional[str] = None):
        if dt > 0:
            # Smooth velocity update with alpha filter
            new_vx = (x - self.x) / dt
            new_vy = (y - self.y) / dt
            self.vx = 0.7 * self.vx + 0.3 * new_vx
            self.vy = 0.7 * self.vy + 0.3 * new_vy

        self.x = x
        self.y = y
        self.team = team
        if jersey:
            self.jersey = jersey
        self.hits += 1
        self.misses = 0
        if self.hits >= 2:
            self.confirmed = True

    def mark_miss(self):
        self.misses += 1

    @property
    def speed(self) -> float:
        s = math.hypot(self.vx, self.vy)
        return round(float(min(12.0, max(0.0, s))), 1)

class SoccerTracker:
    def __init__(self, max_match_distance: float = 4.0, max_misses: int = 6):
        self.next_id = 1
        self.tracks: List[Track] = []
        self.max_match_distance = max_match_distance
        self.max_misses = max_misses

    def update(self, detections: List[Dict[str, Any]], dt: float = 0.5) -> List[RadarPlayer]:
        """
        Updates player tracks in metric pitch space using Hungarian algorithm.
        detections: list of {"x": float, "y": float, "team": str, "jersey": Optional[str]}
        """
        # 1. Predict existing tracks
        for track in self.tracks:
            track.predict(dt)

        # 2. Match tracks to detections
        matched_tracks = set()
        matched_dets = set()

        if self.tracks and detections:
            cost_matrix = np.zeros((len(self.tracks), len(detections)), dtype=np.float32)
            for i, track in enumerate(self.tracks):
                for j, det in enumerate(detections):
                    dist = math.hypot(track.x - det["x"], track.y - det["y"])
                    # Bonus penalty if team labels differ
                    if track.team != det["team"]:
                        dist += 2.0
                    cost_matrix[i, j] = dist

            row_ind, col_ind = linear_sum_assignment(cost_matrix)

            for r, c in zip(row_ind, col_ind):
                if cost_matrix[r, c] <= self.max_match_distance:
                    det = detections[c]
                    self.tracks[r].update(det["x"], det["y"], det["team"], dt, det.get("jersey"))
                    matched_tracks.add(r)
                    matched_dets.add(c)

        # 3. Unmatched tracks mark misses
        for i, track in enumerate(self.tracks):
            if i not in matched_tracks:
                track.mark_miss()

        # 4. Remove dead tracks
        self.tracks = [t for t in self.tracks if t.misses <= self.max_misses]

        # 5. Spawn new candidate tracks from unmatched detections
        for j, det in enumerate(detections):
            if j not in matched_dets:
                new_track = Track(
                    track_id=self.next_id,
                    x=det["x"],
                    y=det["y"],
                    team=det["team"],
                    jersey=det.get("jersey")
                )
                self.next_id += 1
                self.tracks.append(new_track)

        # 6. Return only tracks corroborated by at least two detections. Candidate
        # tracks remain internal until confirmed, so one-frame noise is not drawn.
        active_players: List[RadarPlayer] = []
        for t in self.tracks:
            if not t.confirmed:
                continue
            active_players.append(RadarPlayer(
                id=t.track_id,
                team=t.team,
                jersey=t.jersey,
                x=round(t.x, 1),
                y=round(t.y, 1),
                speed=t.speed
            ))

        return active_players
