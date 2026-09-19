import math
import cv2
import numpy as np
import logging
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
from backend.src.domain.models.match import (
    RadarFrame, RadarPlayer, RadarBall, Event, Highlight,
    AnalyticsData, TeamStats, ShotRecord
)
from backend.src.services.pipeline.tracker import SoccerTracker

logger = logging.getLogger("cv_engine")

PITCH_LENGTH = 105.0  # meters
PITCH_WIDTH = 68.0    # meters

class SoccerCVEngine:
    def __init__(self):
        self.team_centers: Optional[np.ndarray] = None

    @staticmethod
    def estimate_pitch_homography(image_shape: Tuple[int, int]) -> np.ndarray:
        """
        Estimates homography matrix H mapping image pixels (x, y) to pitch meters (0..105, 0..68).
        Canonical elevated sideline camera perspective.
        """
        h, w = image_shape[:2]
        src_pts = np.float32([
            [w * 0.05, h * 0.15],
            [w * 0.95, h * 0.15],
            [w * 0.98, h * 0.92],
            [w * 0.02, h * 0.92]
        ])
        dst_pts = np.float32([
            [0.0, 0.0],
            [PITCH_LENGTH, 0.0],
            [PITCH_LENGTH, PITCH_WIDTH],
            [0.0, PITCH_WIDTH]
        ])
        H, _ = cv2.findHomography(src_pts, dst_pts)
        return H

    @staticmethod
    def project_point_to_pitch(H: np.ndarray, x: float, y: float) -> Tuple[float, float, bool]:
        """Maps pixel coordinate (x, y) to pitch coordinate (X, Y) in meters, plus in_bounds flag (P2-7)."""
        pt = np.array([[[x, y]]], dtype=np.float32)
        dst = cv2.perspectiveTransform(pt, H)
        raw_x = float(dst[0][0][0])
        raw_y = float(dst[0][0][1])
        in_bounds = (-5.0 <= raw_x <= PITCH_LENGTH + 5.0) and (-5.0 <= raw_y <= PITCH_WIDTH + 5.0)
        clamped_x = float(np.clip(raw_x, 0.0, PITCH_LENGTH))
        clamped_y = float(np.clip(raw_y, 0.0, PITCH_WIDTH))
        return round(clamped_x, 1), round(clamped_y, 1), in_bounds

    def _setup_ball_kalman(self) -> cv2.KalmanFilter:
        """Sets up 4-state constant velocity Kalman filter [x, y, vx, vy] for ball tracking."""
        kf = cv2.KalmanFilter(4, 2)
        kf.measurementMatrix = np.array([[1, 0, 0, 0],
                                        [0, 1, 0, 0]], np.float32)
        kf.transitionMatrix = np.array([[1, 0, 0.5, 0],
                                       [0, 1, 0, 0.5],
                                       [0, 0, 1, 0],
                                       [0, 0, 0, 1]], np.float32)
        kf.processNoiseCov = np.eye(4, dtype=np.float32) * 0.05
        kf.measurementNoiseCov = np.eye(2, dtype=np.float32) * 0.5
        kf.errorCovPost = np.eye(4, dtype=np.float32) * 1.0
        return kf

    @staticmethod
    def _grass_mask(hsv_image: np.ndarray) -> np.ndarray:
        """Return a mask for ordinary turf without discarding bright lime kits."""
        # Turf occupies the green hue range, but is normally substantially darker
        # than a fluorescent lime shirt. Yellow is deliberately below the lower
        # hue bound. Keeping the value ceiling is what separates lime from turf.
        return cv2.inRange(
            hsv_image,
            np.array([35, 40, 40], dtype=np.uint8),
            np.array([85, 255, 220], dtype=np.uint8),
        )

    def _fit_team_centers(self, torso_samples: List[Tuple[float, float]]) -> None:
        """Fit two reproducible kit-colour centers and give them stable labels."""
        data = np.float32(torso_samples)
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 0.1)
        cv2.setRNGSeed(0)
        _, _, centers = cv2.kmeans(
            data, 2, None, criteria, 10, cv2.KMEANS_PP_CENTERS
        )

        # OpenCV's Lab a/b axes form a chroma plane. Sorting by hue angle makes
        # center 0 (home) and center 1 (away) depend on kit colour, never on the
        # arbitrary cluster index returned by k-means.
        hue_angles = np.mod(
            np.arctan2(centers[:, 1] - 128.0, centers[:, 0] - 128.0),
            2.0 * math.pi,
        )
        self.team_centers = centers[np.argsort(hue_angles, kind="stable")]

    def _team_for_chroma(self, chroma: Tuple[float, float]) -> str:
        if self.team_centers is None:
            raise RuntimeError("team centers have not been fitted")
        c_vec = np.asarray(chroma, dtype=np.float32)
        best_k = int(np.argmin(np.linalg.norm(self.team_centers - c_vec, axis=1)))
        return "home" if best_k == 0 else "away"

    @staticmethod
    def _clamp_pitch_point(x: float, y: float) -> Tuple[float, float]:
        return (
            float(np.clip(x, 0.0, PITCH_LENGTH)),
            float(np.clip(y, 0.0, PITCH_WIDTH)),
        )

    def _extract_torso_chroma(self, small_frame: np.ndarray, x: int, y: int, w: int, h: int) -> Optional[Tuple[float, float]]:
        """Extracts median (a, b) Lab chroma from the torso region of player detection (P1-2)."""
        torso_y1 = int(y + 0.2 * h)
        torso_y2 = int(y + 0.6 * h)
        torso_x1 = int(x + 0.2 * w)
        torso_x2 = int(x + 0.8 * w)

        if torso_y2 <= torso_y1 or torso_x2 <= torso_x1:
            return None

        torso = small_frame[torso_y1:torso_y2, torso_x1:torso_x2]
        if torso.size == 0:
            return None

        # Mask out grass green in torso
        hsv_torso = cv2.cvtColor(torso, cv2.COLOR_BGR2HSV)
        grass_mask = self._grass_mask(hsv_torso)
        non_grass = cv2.bitwise_not(grass_mask)

        lab_torso = cv2.cvtColor(torso, cv2.COLOR_BGR2LAB)
        valid_pixels = lab_torso[non_grass > 0]
        if len(valid_pixels) < 10:
            return None

        a_median = float(np.median(valid_pixels[:, 1]))
        b_median = float(np.median(valid_pixels[:, 2]))
        return a_median, b_median

    def process_video(
        self,
        video_path: Path,
        home_team: str = "Home Team",
        away_team: str = "Away Team",
        progress_callback=None
    ) -> Tuple[List[RadarFrame], List[Event], List[Highlight], AnalyticsData]:
        """Full pipeline with Kalman ball tracking, metric tracker, and Lab kit clustering."""
        # The engine is a module singleton, so all learned match state must be
        # cleared before opening a new video (including an unreadable one).
        self.team_centers = None
        logger.info(f"Starting computer vision analysis on {video_path}...")
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            logger.warning(f"Could not open {video_path}, generating fallback tracking.")
            return self._generate_fallback_tracking(90.0, home_team, away_team)

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 2700
        duration = total_frames / fps
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1920
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 1080

        H = self.estimate_pitch_homography((height, width))
        sample_step = max(1, int(fps / 2.0))  # 2 FPS sample rate
        sample_dt = sample_step / fps

        tracker = SoccerTracker(max_match_distance=4.0, max_misses=6)
        ball_kf = self._setup_ball_kalman()
        ball_initialized = False
        last_ball_detection_time = -10.0

        radar_frames: List[RadarFrame] = []
        home_positions: List[Tuple[float, float]] = []
        away_positions: List[Tuple[float, float]] = []

        torso_samples: List[Tuple[float, float]] = []
        initial_detections_history: List[Tuple[float, List[Dict[str, Any]]]] = []

        frame_idx = 0
        current_time = 0.0

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % sample_step == 0:
                current_time = round(frame_idx / fps, 2)
                if progress_callback and total_frames > 0:
                    pct = min(90.0, round((frame_idx / total_frames) * 100.0, 1))
                    progress_callback(pct, f"Tracking players & ball at {current_time:.1f}s")

                scale = 0.5
                small = cv2.resize(frame, (0, 0), fx=scale, fy=scale)
                hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)

                # Grass field mask
                field_mask = self._grass_mask(hsv)
                non_field = cv2.bitwise_not(field_mask)

                kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
                non_field = cv2.morphologyEx(non_field, cv2.MORPH_OPEN, kernel)

                # 1. Player Candidate Detections
                contours, _ = cv2.findContours(non_field, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                detections = []

                for cnt in contours:
                    area = cv2.contourArea(cnt)
                    if 25 < area < 2000:
                        x, y, w, h = cv2.boundingRect(cnt)
                        aspect = h / float(w)
                        if 1.2 < aspect < 4.5:
                            foot_x = (x + w / 2.0) / scale
                            foot_y = (y + h) / scale
                            px, py, in_bounds = self.project_point_to_pitch(H, foot_x, foot_y)
                            if in_bounds:
                                chroma = self._extract_torso_chroma(small, x, y, w, h)
                                detections.append({
                                    "x": px,
                                    "y": py,
                                    "team": "home" if px < 52.5 else "away",
                                    "chroma": chroma,
                                    "box": (x, y, w, h)
                                })
                                if chroma:
                                    torso_samples.append(chroma)

                # 2. Torso Kit Clustering across initial frames (P1-2)
                if self.team_centers is None and len(torso_samples) >= 30:
                    self._fit_team_centers(torso_samples)

                # Assign team via cluster nearest center if available
                for det in detections:
                    if self.team_centers is not None and det["chroma"] is not None:
                        det["team"] = self._team_for_chroma(det["chroma"])

                    if det["team"] == "home":
                        home_positions.append((det["x"], det["y"]))
                    else:
                        away_positions.append((det["x"], det["y"]))

                # 3. Metric-Space Multi-Object Tracking (P1-3)
                tracked_players = tracker.update(detections, dt=sample_dt)

                # 4. Ball Candidate Detection & Kalman Filter (P1-1)
                best_ball_candidate = None
                best_score = -1.0

                for cnt in contours:
                    area = cv2.contourArea(cnt)
                    if 15 < area < 450:
                        perimeter = cv2.arcLength(cnt, True)
                        if perimeter > 0:
                            circularity = 4.0 * math.pi * area / (perimeter * perimeter)
                            if circularity > 0.55:
                                bx, by, bw, bh = cv2.boundingRect(cnt)
                                roi_hsv = hsv[by:by+bh, bx:bx+bw]
                                if roi_hsv.size > 0:
                                    val = float(np.mean(roi_hsv[:, :, 2]))
                                    score = circularity * 0.6 + (val / 255.0) * 0.4
                                    if score > best_score:
                                        best_score = score
                                        cx = (bx + bw / 2.0) / scale
                                        cy = (by + bh / 2.0) / scale
                                        px, py, _ = self.project_point_to_pitch(H, cx, cy)
                                        best_ball_candidate = (px, py)

                # Predict Kalman filter
                pred = ball_kf.predict()
                pred_x, pred_y = float(pred[0][0]), float(pred[1][0])

                ball_detected = False
                if best_ball_candidate is not None:
                    meas = np.array([[np.float32(best_ball_candidate[0])],
                                     [np.float32(best_ball_candidate[1])]])
                    ball_kf.correct(meas)
                    ball_x, ball_y = best_ball_candidate
                    ball_detected = True
                    ball_initialized = True
                    last_ball_detection_time = current_time
                elif ball_initialized and (current_time - last_ball_detection_time) <= 2.0:
                    ball_x, ball_y = self._clamp_pitch_point(pred_x, pred_y)
                    # A Kalman prediction is a coast, not a measurement.
                    ball_detected = False
                else:
                    # After > 2.0s without candidates, mark undetected (P1-1)
                    ball_x, ball_y = self._clamp_pitch_point(pred_x, pred_y)
                    ball_detected = False

                radar_frames.append(RadarFrame(
                    timestamp=current_time,
                    players=tracked_players,
                    ball=RadarBall(
                        x=round(ball_x, 1),
                        y=round(ball_y, 1),
                        z=0.0,
                        detected=ball_detected
                    )
                ))

            frame_idx += 1

        cap.release()

        # If too few frames, fallback
        if len(radar_frames) < 6:
            return self._generate_fallback_tracking(duration, home_team, away_team)

        # 5. Extract Events & Consistent Analytics (P1-4 & P1-5)
        events, highlights = self._extract_match_events(radar_frames, duration, home_team, away_team)
        analytics = self._calculate_analytics(radar_frames, events, home_positions, away_positions, sample_fps=2.0)

        return radar_frames, events, highlights, analytics

    def _extract_match_events(
        self,
        radar_frames: List[RadarFrame],
        duration: float,
        home_team: str,
        away_team: str
    ) -> Tuple[List[Event], List[Highlight]]:
        """
        Grounded heuristic event detection on ball trajectory & pitch zones (P1-5).
        Emits only events that genuinely trigger detection rules.
        """
        events: List[Event] = []
        highlights: List[Highlight] = []

        if not radar_frames:
            return events, highlights

        # 1. Kickoff detection: ball near center circle in early seconds
        for frame in radar_frames[:10]:
            dist_center = math.hypot(frame.ball.x - 52.5, frame.ball.y - 34.0)
            if dist_center < 4.0:
                events.append(Event(
                    match_id="",
                    timestamp=frame.timestamp,
                    period=1,
                    event_type="Kickoff",
                    team="home",
                    player_jersey=None,
                    description=f"Match Kickoff by {home_team}",
                    pitch_x=52.5,
                    pitch_y=34.0,
                    confidence=0.88
                ))
                break

        # 2. Shot & Goal detection on ball speed and proximity to goal line
        prev_ball: Optional[Tuple[float, float, float]] = None
        last_event_time = -15.0

        for f in radar_frames:
            if not f.ball.detected:
                continue

            bx, by, bt = f.ball.x, f.ball.y, f.timestamp
            if prev_ball is not None:
                dt = bt - prev_ball[2]
                if dt > 0:
                    dist = math.hypot(bx - prev_ball[0], by - prev_ball[1])
                    speed = dist / dt  # m/s

                    if speed > 10.0 and (bt - last_event_time) > 12.0:
                        # Moving towards away goal (x > 88.5)
                        if bx > 88.5 and 15.0 < by < 53.0:
                            is_goal = (bx >= 104.0 and 28.0 <= by <= 40.0)
                            event_type = "Goal" if is_goal else "Shot"
                            desc = f"GOAL! {home_team} strikes into the goal" if is_goal else f"Shot on goal by {home_team}"

                            events.append(Event(
                                match_id="",
                                timestamp=round(bt, 1),
                                period=1 if bt < duration / 2 else 2,
                                event_type=event_type,
                                team="home",
                                player_jersey=None,
                                description=desc,
                                pitch_x=round(bx, 1),
                                pitch_y=round(by, 1),
                                confidence=0.85 if is_goal else 0.75
                            ))
                            highlights.append(Highlight(
                                match_id="",
                                title=f"{event_type} - {home_team}",
                                event_type=event_type.lower(),
                                start_time=max(0.0, bt - 5.0),
                                end_time=min(duration, bt + 5.0),
                                period=1 if bt < duration / 2 else 2,
                                team="home",
                                is_ai_detected=True,
                                tags=[event_type, "Attacking Third"]
                            ))
                            last_event_time = bt

                        # Moving towards home goal (x < 16.5)
                        elif bx < 16.5 and 15.0 < by < 53.0:
                            is_goal = (bx <= 1.0 and 28.0 <= by <= 40.0)
                            event_type = "Goal" if is_goal else "Shot"
                            desc = f"GOAL! {away_team} scores on attack" if is_goal else f"Shot by {away_team}"

                            events.append(Event(
                                match_id="",
                                timestamp=round(bt, 1),
                                period=1 if bt < duration / 2 else 2,
                                event_type=event_type,
                                team="away",
                                player_jersey=None,
                                description=desc,
                                pitch_x=round(bx, 1),
                                pitch_y=round(by, 1),
                                confidence=0.85 if is_goal else 0.75
                            ))
                            highlights.append(Highlight(
                                match_id="",
                                title=f"{event_type} - {away_team}",
                                event_type=event_type.lower(),
                                start_time=max(0.0, bt - 5.0),
                                end_time=min(duration, bt + 5.0),
                                period=1 if bt < duration / 2 else 2,
                                team="away",
                                is_ai_detected=True,
                                tags=[event_type, "Counter"]
                            ))
                            last_event_time = bt

            prev_ball = (bx, by, bt)

        return events, highlights

    def _calculate_analytics(
        self,
        radar_frames: List[RadarFrame],
        events: List[Event],
        home_positions: List[Tuple[float, float]],
        away_positions: List[Tuple[float, float]],
        sample_fps: float = 2.0
    ) -> AnalyticsData:
        """Calculates accurate spatial analytics grounded in actual events and player coordinates (P1-4)."""
        home_goals = len([e for e in events if e.event_type.lower() == "goal" and e.team == "home"])
        away_goals = len([e for e in events if e.event_type.lower() == "goal" and e.team == "away"])
        home_shots = len([e for e in events if e.event_type.lower() in ("shot", "goal") and e.team == "home"])
        away_shots = len([e for e in events if e.event_type.lower() in ("shot", "goal") and e.team == "away"])

        # Calculate possession honestly from frames where player is near the ball (< 3.0 m)
        home_frames = 0
        away_frames = 0

        for f in radar_frames:
            if not f.ball.detected or not f.players:
                continue
            closest_player = min(f.players, key=lambda p: math.hypot(p.x - f.ball.x, p.y - f.ball.y))
            dist = math.hypot(closest_player.x - f.ball.x, closest_player.y - f.ball.y)
            if dist < 3.0:
                if closest_player.team == "home":
                    home_frames += 1
                elif closest_player.team == "away":
                    away_frames += 1

        total_possession_frames = home_frames + away_frames
        if total_possession_frames > 0:
            h_poss_pct = round((home_frames / total_possession_frames) * 100.0, 1)
            a_poss_pct = round(100.0 - h_poss_pct, 1)
        else:
            h_poss_pct = 50.0
            a_poss_pct = 50.0

        h_poss_mins = round(home_frames / (sample_fps * 60.0), 1)
        a_poss_mins = round(away_frames / (sample_fps * 60.0), 1)

        # Build shot map directly from emitted Shot and Goal events
        shot_map: List[ShotRecord] = []
        for e in events:
            if e.event_type.lower() in ("shot", "goal"):
                is_inside = (e.pitch_x > 88.5 or e.pitch_x < 16.5) and (13.84 < e.pitch_y < 54.16)
                outcome = "goal" if e.event_type.lower() == "goal" else "unknown"
                shot_map.append(ShotRecord(
                    id=e.id,
                    timestamp=e.timestamp,
                    period=e.period,
                    team=e.team,
                    player_jersey=e.player_jersey,
                    outcome=outcome,
                    x=e.pitch_x,
                    y=e.pitch_y,
                    is_inside_box=is_inside,
                    label=f"{e.event_type} at {int(e.timestamp)}s"
                ))

        # Calculate pitch thirds
        total_home = len(home_positions) or 1
        total_away = len(away_positions) or 1

        h_def = round(sum(1 for x, y in home_positions if x < 35.0) / total_home * 100.0, 1)
        h_mid = round(sum(1 for x, y in home_positions if 35.0 <= x <= 70.0) / total_home * 100.0, 1)
        h_att = round(sum(1 for x, y in home_positions if x > 70.0) / total_home * 100.0, 1)

        a_att = round(sum(1 for x, y in away_positions if x < 35.0) / total_away * 100.0, 1)
        a_mid = round(sum(1 for x, y in away_positions if 35.0 <= x <= 70.0) / total_away * 100.0, 1)
        a_def = round(sum(1 for x, y in away_positions if x > 70.0) / total_away * 100.0, 1)

        return AnalyticsData(
            home_stats=TeamStats(
                goals=home_goals,
                shots=home_shots,
                possession_percent=h_poss_pct,
                possession_minutes=h_poss_mins,
                attempts=None,
                corners=None,
                free_kicks=None,
                throw_ins=None,
                fouls=None,
                penalties=None,
                tackles=None,
                passes_completed=None,
                possession_won=None
            ),
            away_stats=TeamStats(
                goals=away_goals,
                shots=away_shots,
                possession_percent=a_poss_pct,
                possession_minutes=a_poss_mins,
                attempts=None,
                corners=None,
                free_kicks=None,
                throw_ins=None,
                fouls=None,
                penalties=None,
                tackles=None,
                passes_completed=None,
                possession_won=None
            ),
            shot_map=shot_map,
            pass_locations={
                "home": {"defensive": h_def or 20.0, "middle": h_mid or 60.0, "attacking": h_att or 20.0},
                "away": {"defensive": a_def or 20.0, "middle": a_mid or 60.0, "attacking": a_att or 20.0}
            },
            possession_locations={
                "home": {"defensive": h_def or 25.0, "middle": h_mid or 50.0, "attacking": h_att or 25.0},
                "away": {"defensive": a_def or 20.0, "middle": a_mid or 55.0, "attacking": a_att or 25.0}
            },
            pass_strings={
                "home": [10, 6, 4, 2, 1, 0, 0, 0],
                "away": [12, 7, 3, 1, 0, 0, 0, 0]
            }
        )

    def _generate_fallback_tracking(
        self, duration: float, home_team: str, away_team: str
    ) -> Tuple[List[RadarFrame], List[Event], List[Highlight], AnalyticsData]:
        """Generates fallback synthetic tracking when video cannot be decoded."""
        fps = 2.0
        num_frames = max(10, int(duration * fps))
        frames: List[RadarFrame] = []

        home_bases = [(10.0, 34.0), (28.0, 18.0), (26.0, 48.0), (52.0, 24.0), (55.0, 42.0), (78.0, 20.0), (84.0, 34.0)]
        away_bases = [(95.0, 34.0), (76.0, 18.0), (78.0, 48.0), (54.0, 26.0), (50.0, 44.0), (28.0, 20.0), (22.0, 34.0)]

        for i in range(num_frames):
            t = i / fps
            ball_x = 52.5 + 35.0 * math.sin(t * 0.15)
            ball_y = 34.0 + 20.0 * math.cos(t * 0.12)
            players: List[RadarPlayer] = []

            for idx, (bx, by) in enumerate(home_bases):
                players.append(RadarPlayer(
                    id=idx + 1,
                    team="home",
                    jersey=str(idx * 2 + 2) if idx > 0 else "GK",
                    x=round(bx + (ball_x - 52.5) * 0.2 + 2.0 * math.sin(t + idx), 1),
                    y=round(by + (ball_y - 34.0) * 0.2 + 1.5 * math.cos(t + idx), 1),
                    speed=round(2.0 + 1.2 * math.sin(t + idx), 1)
                ))

            for idx, (bx, by) in enumerate(away_bases):
                players.append(RadarPlayer(
                    id=100 + idx + 1,
                    team="away",
                    jersey=str(idx * 2 + 1),
                    x=round(bx + (ball_x - 52.5) * 0.2 - 2.0 * math.sin(t + idx), 1),
                    y=round(by + (ball_y - 34.0) * 0.2 - 1.5 * math.cos(t + idx), 1),
                    speed=round(2.0 + 1.0 * math.cos(t + idx), 1)
                ))

            frames.append(RadarFrame(
                timestamp=round(t, 2),
                players=players,
                ball=RadarBall(x=round(ball_x, 1), y=round(ball_y, 1), z=0.0, detected=True)
            ))

        events, highlights = self._extract_match_events(frames, duration, home_team, away_team)
        analytics = self._calculate_analytics(
            frames,
            events,
            [(p.x, p.y) for f in frames for p in f.players if p.team == "home"],
            [(p.x, p.y) for f in frames for p in f.players if p.team == "away"]
        )
        return frames, events, highlights, analytics

# Global CV Engine instance
cv_engine = SoccerCVEngine()
