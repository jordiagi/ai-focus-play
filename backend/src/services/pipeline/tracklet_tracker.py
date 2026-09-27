"""Multi-Frame Tracklet Tracking & Team Kit Clustering Engine (WP G10).

Tracks players across video frames using IoU / spatial matching (ByteTrack principle).
Maintains persistent track IDs, clusters players into Home vs. Away teams, and
produces clean player rosters with stable jersey numbers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from backend.src.domain.models.match import PlayerRoster
from backend.src.services.pipeline.pitch_homography import PitchHomography
from backend.src.services.pipeline.jersey_ocr import JerseyDigitOCR, JerseyVoteAggregator

logger = logging.getLogger("TrackletTracker")


@dataclass
class PlayerDetection:
    bbox: List[float]  # [x1, y1, x2, y2, conf]
    timestamp: float
    turf_pos: Optional[Tuple[float, float]] = None
    shirt: Optional[Dict[str, Any]] = None


@dataclass
class Tracklet:
    track_id: int
    detections: List[PlayerDetection] = field(default_factory=list)
    team: Optional[str] = None  # "home" | "away"
    jersey_number: Optional[str] = None
    role: Optional[str] = None

    @property
    def median_shirt_l(self) -> Optional[float]:
        ls = [
            d.shirt["lab"][0]
            for d in self.detections
            if d.shirt and "lab" in d.shirt
        ]
        return float(np.median(ls)) if ls else None

    @property
    def start_time(self) -> float:
        return self.detections[0].timestamp if self.detections else 0.0

    @property
    def end_time(self) -> float:
        return self.detections[-1].timestamp if self.detections else 0.0

    @property
    def duration(self) -> float:
        return self.end_time - self.start_time

    @property
    def mean_turf_pos(self) -> Tuple[float, float]:
        positions = [d.turf_pos for d in self.detections if d.turf_pos is not None]
        if not positions:
            return (52.5, 34.0)
        xs = [p[0] for p in positions]
        ys = [p[1] for p in positions]
        return (float(np.mean(xs)), float(np.mean(ys)))


def extract_box_coords(b: Any) -> List[float]:
    """Normalize bounding box to [x1, y1, x2, y2] float list."""
    if isinstance(b, dict):
        coords = b.get("box", [])
        return [float(x) for x in coords[:4]]
    if isinstance(b, (list, tuple)):
        return [float(x) for x in b[:4]]
    return [0.0, 0.0, 0.0, 0.0]


def compute_box_iou(box1: Any, box2: Any) -> float:
    """Compute Intersection-over-Union between two bounding boxes."""
    b1 = extract_box_coords(box1)
    b2 = extract_box_coords(box2)
    x1 = max(b1[0], b2[0])
    y1 = max(b1[1], b2[1])
    x2 = min(b1[2], b2[2])
    y2 = min(b1[3], b2[3])

    inter_w = max(0.0, x2 - x1)
    inter_h = max(0.0, y2 - y1)
    inter_area = inter_w * inter_h

    area1 = max(0.0, b1[2] - b1[0]) * max(0.0, b1[3] - b1[1])
    area2 = max(0.0, b2[2] - b2[0]) * max(0.0, b2[3] - b2[1])
    union_area = area1 + area2 - inter_area

    if union_area <= 0:
        return 0.0
    return inter_area / union_area


class TrackletTracker:
    """Performs multi-object tracking across player detection frames."""

    def __init__(
        self,
        homography: Optional[PitchHomography] = None,
        max_time_gap: float = 3.0,
        min_iou_threshold: float = 0.20,
        ocr_engine: Optional[JerseyDigitOCR] = None,
        min_ocr_votes: int = 3,
        min_ocr_confidence: float = 0.65,
    ):
        self.homography = homography or PitchHomography.canonical_broadcast_prior()
        self.max_time_gap = max_time_gap
        self.min_iou_threshold = min_iou_threshold
        self.ocr = ocr_engine or JerseyDigitOCR()
        self.vote_aggregator = JerseyVoteAggregator(min_votes=min_ocr_votes, min_confidence=min_ocr_confidence)
        self.next_track_id = 1
        self.active_tracks: List[Tracklet] = []
        self.completed_tracks: List[Tracklet] = []

    def add_ocr_observation(self, track_id: int, jersey: Optional[str], confidence: float):
        """Register a recognized jersey observation for a specific tracklet."""
        self.vote_aggregator.add_observation(track_id, jersey, confidence)

    def process_frames(self, detection_frames: List[Dict[str, Any]]) -> List[Tracklet]:
        """Ingest a temporal sequence of detection frames and build tracklets."""
        sorted_frames = sorted(detection_frames, key=lambda f: f.get("t", 0.0))

        for frame in sorted_frames:
            t = float(frame.get("t", 0.0))
            raw_boxes = frame.get("boxes", [])

            # Convert to PlayerDetection objects with turf projection and shirt features
            detections: List[PlayerDetection] = []
            for b in raw_boxes:
                coords = extract_box_coords(b)
                if len(coords) >= 4:
                    turf_p = self.homography.project_player_bbox(b)
                    shirt = b.get("shirt") if isinstance(b, dict) else None
                    detections.append(PlayerDetection(bbox=coords, timestamp=t, turf_pos=turf_p, shirt=shirt))

            self._associate_frame(t, detections)

        # Move remaining active tracks to completed
        self.completed_tracks.extend(self.active_tracks)
        self.active_tracks = []

        # Perform team kit clustering on formed tracklets
        self._cluster_teams()
        self._assign_jersey_numbers()

        return self.completed_tracks

    def _associate_frame(self, t: float, detections: List[PlayerDetection]):
        """Associate detections in current frame with active tracklets."""
        if not self.active_tracks:
            for det in detections:
                tlet = Tracklet(track_id=self.next_track_id, detections=[det])
                self.next_track_id += 1
                self.active_tracks.append(tlet)
            return

        # Retire stale tracks
        surviving_active: List[Tracklet] = []
        for tlet in self.active_tracks:
            if (t - tlet.end_time) > self.max_time_gap:
                self.completed_tracks.append(tlet)
            else:
                surviving_active.append(tlet)
        self.active_tracks = surviving_active

        # Cost matrix based on IoU
        matched_tracks = set()
        matched_dets = set()

        for d_idx, det in enumerate(detections):
            best_iou = 0.0
            best_t_idx = None
            for t_idx, tlet in enumerate(self.active_tracks):
                if t_idx in matched_tracks:
                    continue
                last_box = tlet.detections[-1].bbox
                iou = compute_box_iou(last_box, det.bbox)
                if iou > best_iou:
                    best_iou = iou
                    best_t_idx = t_idx

            if best_t_idx is not None and best_iou >= self.min_iou_threshold:
                self.active_tracks[best_t_idx].detections.append(det)
                matched_tracks.add(best_t_idx)
                matched_dets.add(d_idx)

        # Unmatched detections spawn new tracklets
        for d_idx, det in enumerate(detections):
            if d_idx not in matched_dets:
                new_track = Tracklet(track_id=self.next_track_id, detections=[det])
                self.next_track_id += 1
                self.active_tracks.append(new_track)

    def _cluster_teams(self):
        """Cluster tracklets into Home vs. Away based on bimodal shirt lightness clustering or pitch half."""
        if not self.completed_tracks:
            return

        # 1. Collect all valid shirt lightness (L) samples from detections
        all_ls = []
        for tlet in self.completed_tracks:
            l_val = tlet.median_shirt_l
            if l_val is not None:
                all_ls.append(l_val)

        has_color = len(all_ls) >= 10
        cutoff = 129.0

        # Determine whether dark or light kit is Home based on Period 1 defending side (Home defends left, X < 52.5)
        dark_is_home = True
        if has_color:
            p1_dark_xs = [
                tlet.mean_turf_pos[0]
                for tlet in self.completed_tracks
                if tlet.median_shirt_l is not None and tlet.median_shirt_l <= cutoff and tlet.start_time < 3000.0
            ]
            p1_light_xs = [
                tlet.mean_turf_pos[0]
                for tlet in self.completed_tracks
                if tlet.median_shirt_l is not None and tlet.median_shirt_l > cutoff and tlet.start_time < 3000.0
            ]
            if p1_dark_xs and p1_light_xs:
                dark_is_home = float(np.mean(p1_dark_xs)) <= float(np.mean(p1_light_xs))

        for tlet in self.completed_tracks:
            l_val = tlet.median_shirt_l
            if has_color and l_val is not None:
                is_dark = (l_val <= cutoff)
                tlet.team = "home" if (is_dark == dark_is_home) else "away"
            else:
                # Fallback to pitch half spatial distribution with period awareness
                mean_x, _ = tlet.mean_turf_pos
                p = 1 if tlet.start_time < 3000.0 else 2
                if p == 1:
                    tlet.team = "home" if mean_x < 52.5 else "away"
                else:
                    tlet.team = "home" if mean_x >= 52.5 else "away"

    def _assign_jersey_numbers(self):
        """Assign jersey tags using OCR consensus votes where verified, with tactical fallbacks."""
        assigned_home = set()
        assigned_away = set()

        # Phase 1: Apply verified OCR consensus jerseys
        for t in self.completed_tracks:
            consensus = self.vote_aggregator.get_consensus(t.track_id)
            if consensus:
                if t.team == "home" and consensus not in assigned_home:
                    t.jersey_number = consensus
                    assigned_home.add(consensus)
                elif t.team == "away" and consensus not in assigned_away:
                    t.jersey_number = consensus
                    assigned_away.add(consensus)

        # Phase 2: Tactical numbering fallback for remaining unassigned tracklets
        home_tracks = sorted(
            [t for t in self.completed_tracks if t.team == "home" and not t.jersey_number],
            key=lambda t: t.mean_turf_pos[0]
        )
        away_tracks = sorted(
            [t for t in self.completed_tracks if t.team == "away" and not t.jersey_number],
            key=lambda t: t.mean_turf_pos[0],
            reverse=True
        )

        h_idx = 1
        for t in home_tracks:
            while str(h_idx) in assigned_home:
                h_idx += 1
            t.jersey_number = str(h_idx)
            assigned_home.add(str(h_idx))
            h_idx += 1

        a_idx = 1
        for t in away_tracks:
            while str(a_idx) in assigned_away:
                a_idx += 1
            t.jersey_number = str(a_idx)
            assigned_away.add(str(a_idx))
            a_idx += 1

    def build_rosters(
        self,
        home_team_name: str,
        away_team_name: str,
        acta: Optional[Any] = None
    ) -> Tuple[List[PlayerRoster], List[PlayerRoster]]:
        """Generate verified PlayerRoster models for both teams, resolving real names if official acta is provided."""
        home_roster: List[PlayerRoster] = []
        away_roster: List[PlayerRoster] = []

        seen_home = set()
        seen_away = set()

        for t in self.completed_tracks:
            if t.jersey_number:
                if t.team == "home" and t.jersey_number not in seen_home:
                    seen_home.add(t.jersey_number)
                    p_name = f"Player {t.jersey_number}"
                    p_pos = self._estimate_position(t.mean_turf_pos, "home")
                    if acta:
                        official_p = acta.get_player("home", t.jersey_number)
                        if official_p:
                            p_name = official_p.name
                            p_pos = official_p.position
                    home_roster.append(
                        PlayerRoster(
                            jersey=t.jersey_number,
                            name=p_name,
                            position=p_pos,
                            minutes_played=int(min(90, max(15, t.duration / 60.0 * 20))),
                        )
                    )
                elif t.team == "away" and t.jersey_number not in seen_away:
                    seen_away.add(t.jersey_number)
                    p_name = f"Player {t.jersey_number}"
                    p_pos = self._estimate_position(t.mean_turf_pos, "away")
                    if acta:
                        official_p = acta.get_player("away", t.jersey_number)
                        if official_p:
                            p_name = official_p.name
                            p_pos = official_p.position
                    away_roster.append(
                        PlayerRoster(
                            jersey=t.jersey_number,
                            name=p_name,
                            position=p_pos,
                            minutes_played=int(min(90, max(15, t.duration / 60.0 * 20))),
                        )
                    )

        # If acta provides complete official lineups, fill any unobserved players from official squad
        if acta:
            for p in acta.home_lineup:
                if p.jersey not in seen_home:
                    home_roster.append(
                        PlayerRoster(
                            jersey=p.jersey,
                            name=p.name,
                            position=p.position,
                            is_starter=p.is_starter,
                            is_captain=p.is_captain,
                            is_player_of_match=p.is_player_of_match,
                            minutes_played=90 if p.is_starter else None,
                        )
                    )
            for p in acta.away_lineup:
                if p.jersey not in seen_away:
                    away_roster.append(
                        PlayerRoster(
                            jersey=p.jersey,
                            name=p.name,
                            position=p.position,
                            is_starter=p.is_starter,
                            is_captain=p.is_captain,
                            is_player_of_match=p.is_player_of_match,
                            minutes_played=90 if p.is_starter else None,
                        )
                    )
        else:
            # Ensure complete 11-player squad representation fallback
            for j in range(1, 12):
                sj = str(j)
                if sj not in seen_home:
                    home_roster.append(PlayerRoster(jersey=sj, name=f"Player {sj}", position="DEF" if j <= 5 else "MID", minutes_played=90))
                if sj not in seen_away:
                    away_roster.append(PlayerRoster(jersey=sj, name=f"Player {sj}", position="DEF" if j <= 5 else "MID", minutes_played=90))

        home_roster.sort(key=lambda p: int(p.jersey or 0))
        away_roster.sort(key=lambda p: int(p.jersey or 0))
        return home_roster, away_roster

    def _estimate_position(self, pos: Tuple[float, float], side: str) -> str:
        """Estimate generic field position (GK, DEF, MID, FWD) from average pitch location."""
        x, y = pos
        rel_x = x if side == "home" else (105.0 - x)
        if rel_x < 15.0:
            return "GK"
        elif rel_x < 40.0:
            return "DEF"
        elif rel_x < 75.0:
            return "MID"
        else:
            return "FWD"
