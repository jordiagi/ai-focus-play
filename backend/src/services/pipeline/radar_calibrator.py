"""Calibrated 2D Pitch Radar Generator using Veo Rigid Physical Extrinsics.

Resolves the ill-conditioned unconstrained 8-point homography failure by projecting
detected player footprints and ball trajectories through Veo's measured physical
camera model (Y=0 turf plane intersection in camera frame).

Converts:
1. Video frame player bounding boxes -> Foot-contact rays -> Metric (X_m, Z_m) -> 2D Pitch Radar (0..105m, 0..68m)
2. Spherical panorama ball coordinates (u, v) -> Camera rays -> Metric (X_m, Z_m) -> 2D Pitch Radar (0..105m, 0..68m)
3. Player shirt CIELAB lightness -> Home (L <= 120) vs Away (L > 120) attribution
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import numpy as np

from backend.src.domain.models.match import RadarBall, RadarFrame, RadarPlayer
from backend.src.services.pipeline.veo_calibrator import VeoCameraModel

REPO = Path(__file__).resolve().parents[4]


class CalibratedPitchRadar:
    """Projects detection bounding boxes and ball trajectories to standard 2D Pitch Radar coordinates."""

    def __init__(
        self,
        camera_model: VeoCameraModel,
        cameras: Optional[List[Dict]] = None,
        scale: float = 1139.0188664958027,
        origin: Tuple[float, float] | list = (-1915.0, 1480.0),
        ball_track: Optional[List[Dict]] = None,
        team_lightness_threshold: float = 120.0,
    ):
        self.camera_model = camera_model
        self.cameras = cameras or []
        self.camera_times = np.array([c["t"] for c in self.cameras]) if self.cameras else np.array([])
        self.scale = float(scale)
        self.origin = origin
        self.ball_track = ball_track or []
        self.team_lightness_threshold = float(team_lightness_threshold)

        # Precompute indexed ball lookup by 0.1s rounded timestamp
        self._ball_by_time: Dict[float, Dict] = {}
        if self.ball_track:
            for b in self.ball_track:
                key = round(float(b["t"]), 1)
                if key not in self._ball_by_time or b.get("conf", 0.0) > self._ball_by_time[key].get("conf", 0.0):
                    self._ball_by_time[key] = b

    @classmethod
    def from_artifacts(
        cls,
        veo_calib_path: Union[str, Path],
        cameras_path: Optional[Union[str, Path]] = None,
        ball_track_path: Optional[Union[str, Path]] = None,
    ) -> CalibratedPitchRadar:
        """Instantiate calibrator from raw calibration and artifact files."""
        model = VeoCameraModel.from_veo_file(veo_calib_path)
        cameras = []
        scale = 1139.0188664958027
        origin = (-1915.0, 1480.0)
        if cameras_path and Path(cameras_path).exists():
            c_data = json.loads(Path(cameras_path).read_text())
            cameras = c_data.get("cameras", [])
            scale = float(c_data.get("scale", scale))
            origin = c_data.get("origin", origin)

        if not cameras:
            fallback_cams = REPO / "backend/.local/artifacts/mosaic/cameras.json"
            if fallback_cams.exists():
                c_data = json.loads(fallback_cams.read_text())
                cameras = c_data.get("cameras", [])
                scale = float(c_data.get("scale", scale))
                origin = c_data.get("origin", origin)

        ball_track = []
        if ball_track_path and Path(ball_track_path).exists():
            ball_track = json.loads(Path(ball_track_path).read_text())

        return cls(
            camera_model=model,
            cameras=cameras,
            scale=scale,
            origin=origin,
            ball_track=ball_track,
        )

    def get_camera_at(self, t: float) -> Optional[Dict]:
        """Find the nearest camera keyframe for timestamp t."""
        if len(self.camera_times) == 0:
            return None
        idx = int(np.argmin(np.abs(self.camera_times - t)))
        return self.cameras[idx]

    def calibrate_player_box(
        self,
        box: list | Tuple[float, float, float, float],
        K: np.ndarray,
        R: np.ndarray,
        foot_ratio: float = 1.0,
    ) -> Optional[Tuple[float, float]]:
        """Project foot contact center of player box to 2D pitch coordinates (0..105, 0..68)."""
        radar_pt = self.camera_model.project_bounding_box_to_radar(
            box=box,
            K=K,
            R=R,
            foot_ratio=foot_ratio,
        )
        if radar_pt is None:
            return None
        rx, ry = radar_pt
        # Filter detections outside pitch boundary with 5m margin
        if not (-5.0 <= rx <= 110.0 and -5.0 <= ry <= 73.0):
            return None
        return float(np.clip(rx, 0.0, 105.0)), float(np.clip(ry, 0.0, 68.0))

    def classify_team(self, shirt_dict: Optional[Dict]) -> str:
        """Classify team as home or away based on CIELAB lightness (L*)."""
        if not shirt_dict:
            return "home"
        lab = shirt_dict.get("lab", [100.0, 128.0, 128.0])
        l_channel = float(lab[0])
        # High lightness (white/light gold) is away team, low lightness (dark blue/red) is home
        return "away" if l_channel > self.team_lightness_threshold else "home"

    def get_ball_at(self, t: float, max_dt: float = 0.5) -> RadarBall:
        """Fetch ball position on 2D pitch radar.

        Honesty rule: If no ball was detected within max_dt, marked as detected=False.
        """
        # Check direct lookup first
        key = round(t, 1)
        ball_cand = self._ball_by_time.get(key)

        if not ball_cand and self.ball_track:
            # Linear scan within max_dt if not found on 0.1s boundary
            best_dt = float("inf")
            for b in self.ball_track:
                dt = abs(float(b["t"]) - t)
                if dt < best_dt and dt <= max_dt:
                    best_dt = dt
                    ball_cand = b

        if ball_cand:
            u, v = float(ball_cand["u"]), float(ball_cand["v"])
            radar_pt = self.camera_model.panorama_pixel_to_radar(
                u, v, self.scale, self.origin
            )
            if radar_pt is not None:
                rx, ry = radar_pt
                if 0.0 <= rx <= 105.0 and 0.0 <= ry <= 68.0:
                    return RadarBall(
                        x=round(rx, 1),
                        y=round(ry, 1),
                        z=0.0,
                        detected=True,
                    )

        # Ball undetected in this frame: assert detected=False
        return RadarBall(x=52.5, y=34.0, z=0.0, detected=False)

    def calibrate_frame(
        self,
        frame_det: Dict,
        min_conf: float = 0.4,
        foot_ratio: float = 1.0,
    ) -> Optional[RadarFrame]:
        """Convert a detection frame into a metric-calibrated RadarFrame."""
        t = float(frame_det["t"])
        cam = self.get_camera_at(t)
        if not cam:
            return None

        K = np.array(
            [
                [cam["focal"], 0.0, cam["ppx"]],
                [0.0, cam["focal"] * cam["aspect"], cam["ppy"]],
                [0.0, 0.0, 1.0],
            ],
            dtype=np.float64,
        )
        R = np.array(cam["R"], dtype=np.float64)

        fw = float(frame_det.get("w", 1280))
        fh = float(frame_det.get("h", 720))
        sx = 1280.0 / fw
        sy = 720.0 / fh

        players: List[RadarPlayer] = []
        pid = 1

        for b in frame_det.get("boxes", []):
            if isinstance(b, (list, tuple)):
                if len(b) >= 5 and float(b[4]) < min_conf:
                    continue
                box = b[:4]
                shirt_data = None
            elif isinstance(b, dict):
                if float(b.get("conf", 1.0)) < min_conf:
                    continue
                box = b.get("box", [0, 0, 0, 0])
                shirt_data = b.get("shirt")
            else:
                continue

            foot_u = ((box[0] + box[2]) / 2.0) * sx
            foot_v = (box[1] + foot_ratio * (box[3] - box[1])) * sy

            radar_pt = self.camera_model.frame_pixel_to_radar(foot_u, foot_v, K, R)
            if radar_pt is None:
                continue
            rx, ry = radar_pt
            if not (-5.0 <= rx <= 110.0 and -5.0 <= ry <= 73.0):
                continue
            rx = float(np.clip(rx, 0.0, 105.0))
            ry = float(np.clip(ry, 0.0, 68.0))

            team = self.classify_team(shirt_data)
            players.append(
                RadarPlayer(
                    id=pid,
                    team=team,
                    x=round(rx, 1),
                    y=round(ry, 1),
                    speed=0.0,
                )
            )
            pid += 1

        ball = self.get_ball_at(t)

        return RadarFrame(
            timestamp=round(t, 2),
            players=players,
            ball=ball,
        )

    def calibrate_all_frames(
        self,
        detections: List[Dict],
        min_conf: float = 0.4,
        foot_ratio: float = 1.0,
    ) -> List[RadarFrame]:
        """Calibrate a sequence of detection frames."""
        frames: List[RadarFrame] = []
        for d in detections:
            rf = self.calibrate_frame(d, min_conf=min_conf, foot_ratio=foot_ratio)
            if rf:
                frames.append(rf)
        return frames
