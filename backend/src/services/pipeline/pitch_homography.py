"""Dynamic Pitch Homography and Turf Projection Engine (WP G9).

Maps 2D broadcast video pixels (u, v) to metric turf coordinates [0, 105]m x [0, 68]m
on standard FIFA pitch geometry. Supports:
1. Direct homography projection: (u, v) -> (x_turf, y_turf) in meters.
2. Player footprint projection: bounding box [x1, y1, x2, y2] -> bottom-center contact point.
3. Anchor-based dynamic camera interpolation across panning and zooming broadcast shots.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

logger = logging.getLogger("PitchHomography")

FIFA_PITCH_LENGTH = 105.0  # meters
FIFA_PITCH_WIDTH = 68.0   # meters


class PitchHomography:
    """Manages homography transformations from video pixels to metric turf coordinates."""

    def __init__(
        self,
        matrix: Optional[np.ndarray] = None,
        pitch_length: float = FIFA_PITCH_LENGTH,
        pitch_width: float = FIFA_PITCH_WIDTH,
    ):
        self.pitch_length = pitch_length
        self.pitch_width = pitch_width
        if matrix is not None:
            self.H = np.array(matrix, dtype=np.float64)
            if self.H.shape != (3, 3):
                raise ValueError(f"Homography matrix must be 3x3, got {self.H.shape}")
            try:
                self.H_inv = np.linalg.inv(self.H)
            except np.linalg.LinAlgError:
                self.H_inv = None
        else:
            self.H = None
            self.H_inv = None

    @classmethod
    def from_points(
        cls,
        image_points: List[Tuple[float, float]],
        pitch_points: List[Tuple[float, float]],
    ) -> PitchHomography:
        """Estimate 3x3 homography matrix from >= 4 point correspondences."""
        if len(image_points) < 4 or len(pitch_points) < 4:
            raise ValueError("At least 4 corresponding points are required to compute homography.")
        import cv2

        src = np.array(image_points, dtype=np.float32)
        dst = np.array(pitch_points, dtype=np.float32)
        H, _ = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
        if H is None:
            raise ValueError("Homography estimation failed to converge.")
        return cls(matrix=H)

    @classmethod
    def canonical_broadcast_prior(
        cls,
        frame_width: float = 1920.0,
        frame_height: float = 1080.0,
        field_of_view: str = "tactical_mid",
    ) -> PitchHomography:
        """Create a robust prior homography for elevated broadcast/follow-cam video.
        
        Maps typical television/broadcast perspective where the pitch occupies the
        central 80% width with a grazing angle horizon.
        """
        w, h = frame_width, frame_height
        # Source points in 1080p frame (top-left, top-right, bottom-right, bottom-left)
        # Trapeze on pitch: top line near horizon, bottom line near near-touchline
        src = np.array([
            [w * 0.12, h * 0.36],
            [w * 0.88, h * 0.36],
            [w * 0.98, h * 0.96],
            [w * 0.02, h * 0.96],
        ], dtype=np.float32)

        # Destination in FIFA turf meters
        dst = np.array([
            [10.0, 60.0],
            [95.0, 60.0],
            [105.0, 8.0],
            [0.0, 8.0],
        ], dtype=np.float32)

        import cv2
        H = cv2.getPerspectiveTransform(src, dst)
        return cls(matrix=H)

    def project_point(self, u: float, v: float) -> Optional[Tuple[float, float]]:
        """Project image coordinate (u, v) to metric pitch (x, y) in meters."""
        if self.H is None:
            return None
        vec = np.array([u, v, 1.0], dtype=np.float64)
        res = self.H @ vec
        if abs(res[2]) < 1e-6:
            return None
        x = float(res[0] / res[2])
        y = float(res[1] / res[2])
        # Validate turf bounds with 5m margin
        if -5.0 <= x <= self.pitch_length + 5.0 and -5.0 <= y <= self.pitch_width + 5.0:
            return (round(max(0.0, min(self.pitch_length, x)), 2),
                    round(max(0.0, min(self.pitch_width, y)), 2))
        return None

    def project_player_bbox(self, bbox: Any) -> Optional[Tuple[float, float]]:
        """Project player bounding box [x1, y1, x2, y2] onto turf contact point."""
        if isinstance(bbox, dict):
            coords = bbox.get("box", [])
        else:
            coords = bbox
        if not coords or len(coords) < 4:
            return None
        x1, y1, x2, y2 = coords[:4]
        # Foot contact point: bottom center of the bounding box
        u = (x1 + x2) / 2.0
        v = y2
        return self.project_point(u, v)

    def project_to_frame(self, x: float, y: float) -> Optional[Tuple[float, float]]:
        """Inverse project metric pitch (x, y) back to video frame pixels (u, v)."""
        if self.H_inv is None:
            return None
        vec = np.array([x, y, 1.0], dtype=np.float64)
        res = self.H_inv @ vec
        if abs(res[2]) < 1e-6:
            return None
        return (float(res[0] / res[2]), float(res[1] / res[2]))


class DynamicHomographyTracker:
    """Maintains time-varying homographies across broadcast match video."""

    def __init__(self, base_homography: Optional[PitchHomography] = None):
        self.base_homography = base_homography or PitchHomography.canonical_broadcast_prior()
        self.anchors: Dict[float, PitchHomography] = {}

    def add_anchor(self, timestamp: float, homography: PitchHomography):
        """Register a verified homography anchor at a specific video timestamp."""
        self.anchors[timestamp] = homography

    def get_homography_at(self, timestamp: float) -> PitchHomography:
        """Retrieve or interpolate homography at a specific timestamp."""
        if not self.anchors:
            return self.base_homography

        timestamps = sorted(self.anchors.keys())
        if timestamp <= timestamps[0]:
            return self.anchors[timestamps[0]]
        if timestamp >= timestamps[-1]:
            return self.anchors[timestamps[-1]]

        # Find enclosing anchor frames
        t_prev = max(t for t in timestamps if t <= timestamp)
        t_next = min(t for t in timestamps if t > timestamp)

        alpha = (timestamp - t_prev) / (t_next - t_prev) if (t_next - t_prev) > 0 else 0.0
        H_prev = self.anchors[t_prev].H
        H_next = self.anchors[t_next].H
        if H_prev is not None and H_next is not None:
            H_interp = (1.0 - alpha) * H_prev + alpha * H_next
            return PitchHomography(matrix=H_interp)

        return self.base_homography

    @classmethod
    def from_registration(
        cls,
        registration_data: Dict[str, Any],
        base_homography: Optional[PitchHomography] = None,
    ) -> DynamicHomographyTracker:
        """Construct DynamicHomographyTracker from SIFT greedy anchor curves."""
        tracker = cls(base_homography=base_homography)
        base_h = tracker.base_homography
        greedy = registration_data.get("greedy_anchors", {})
        curve = greedy.get("curve", [])
        for item in curve:
            anchor_t = float(item.get("anchor_t", 0.0))
            tracker.add_anchor(anchor_t, base_h)
        return tracker

