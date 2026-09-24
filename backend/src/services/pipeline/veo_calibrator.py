"""Veo Camera Calibration and 3D Ground-Plane Projection Module.

Decodes Veo's camera calibration (.veo) files and converts between:
1. 3D pitch metric space (in metres, origin at pitch centre spot, Y=0 turf plane)
2. Normalized pitch coordinates ([0, 1] x [0, 1], as stored in veo_events_447.csv)
3. Spherical camera viewing angles (theta, phi)
4. Virtual broadcast camera pixels (using pan, tilt, zoom from detections_constrained.det)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional, Tuple
import numpy as np


class VeoCameraModel:
    """Rigid 3D camera model derived from Veo's physical camera calibration."""

    def __init__(
        self,
        camera2world: np.ndarray,
        field_length: float = 105.0,
        field_width: float = 65.85,
        va_camera: Optional[Dict[str, float]] = None,
    ):
        """
        Parameters
        ----------
        camera2world : np.ndarray
            4x4 transformation matrix mapping camera coordinates to world coordinates.
        field_length : float
            Length of pitch in metres along X-axis (standard 105.0m).
        field_width : float
            Width of pitch in metres along Z-axis (standard ~65.85m - 68.0m).
        va_camera : dict, optional
            Viewing angle limits in radians (left, right, top, bottom).
        """
        self.c2w = np.array(camera2world, dtype=np.float64).reshape((4, 4))
        self.w2c = np.linalg.inv(self.c2w)
        self.R_c2w = self.c2w[:3, :3]
        self.R_w2c = self.w2c[:3, :3]
        self.cam_pos = self.c2w[:3, 3]  # [Cx, Cy, Cz] in metres relative to centre spot

        self.field_length = float(field_length)
        self.field_width = float(field_width)
        self.va_camera = va_camera or {}

    @classmethod
    def from_veo_file(cls, path: str | Path) -> VeoCameraModel:
        """Instantiate directly from a .veo calibration file."""
        data = json.loads(Path(path).read_text())
        alignment = data["alignment"]
        c2w = np.array([float(x) for x in alignment["camera2world"].split(",")]).reshape((4, 4))
        fl = float(alignment.get("field_length", 105.0))
        fw = float(alignment.get("field_width", 65.85))
        va = alignment.get("va_camera")
        return cls(camera2world=c2w, field_length=fl, field_width=fw, va_camera=va)

    @property
    def camera_height(self) -> float:
        """Physical height of the camera pole above the ground plane in metres."""
        return abs(float(self.cam_pos[1]))

    @property
    def touchline_standoff(self) -> float:
        """Distance of camera behind the near sideline in metres."""
        near_sideline_z = -self.field_width / 2.0
        return abs(float(self.cam_pos[2] - near_sideline_z))

    def normalized_to_metric(self, x_norm: float, z_norm: float) -> Tuple[float, float]:
        """Convert normalized pitch coordinates [0, 1] x [0, 1] to metric metres relative to centre spot."""
        x_m = (x_norm - 0.5) * self.field_length
        z_m = (z_norm - 0.5) * self.field_width
        return x_m, z_m

    def metric_to_normalized(self, x_m: float, z_m: float) -> Tuple[float, float]:
        """Convert metric metres relative to centre spot to normalized pitch coordinates [0, 1] x [0, 1]."""
        x_norm = (x_m / self.field_length) + 0.5
        z_norm = (z_m / self.field_width) + 0.5
        return float(np.clip(x_norm, 0.0, 1.0)), float(np.clip(z_norm, 0.0, 1.0))

    def ground_to_camera_ray(self, x_m: float, z_m: float) -> np.ndarray:
        """Given a 2D metric point on the ground (Y=0), return unit ray direction in camera frame."""
        p_world = np.array([x_m, 0.0, z_m, 1.0], dtype=np.float64)
        p_cam = (self.w2c @ p_world)[:3]
        norm = np.linalg.norm(p_cam)
        return p_cam / (norm if norm > 1e-9 else 1.0)

    def camera_ray_to_ground(self, d_cam: np.ndarray) -> Optional[Tuple[float, float]]:
        """
        Given a unit ray direction in camera frame, compute intersection with turf plane Y=0.
        Returns (x_m, z_m) or None if ray points above horizon or is parallel to plane.
        """
        d_world = self.R_c2w @ d_cam
        # We need t such that Cy + t * d_world[1] = 0
        if abs(d_world[1]) < 1e-6:
            return None  # Ray parallel to ground
        t = -self.cam_pos[1] / d_world[1]
        if t <= 0:
            return None  # Points away from ground plane
        p_ground = self.cam_pos + t * d_world
        return float(p_ground[0]), float(p_ground[2])

    def broadcast_pixel_to_ground(
        self,
        u: float,
        v: float,
        pan: float,
        tilt: float,
        fov: float,
        width: int = 1920,
        height: int = 1080,
    ) -> Optional[Tuple[float, float]]:
        """
        Map a detection pixel (u, v) in a broadcast frame to ground metric (x_m, z_m).

        Parameters
        ----------
        u, v : float
            Pixel coordinates in the broadcast frame (0 <= u <= width, 0 <= v <= height).
        pan, tilt, fov : float
            Virtual camera parameters for the frame from detections_constrained.det:
            pan (yaw in radians), tilt (pitch in radians), fov (half vertical FOV in radians).
        """
        # Pixel normalized coordinates relative to center
        # Aspect ratio
        aspect = width / height
        tan_v = np.tan(fov)
        tan_h = tan_v * aspect

        # Normalized screen coordinates in [-1, 1]
        nx = (2.0 * u / width) - 1.0
        ny = 1.0 - (2.0 * v / height)

        # Ray direction in virtual camera frame
        d_vcam = np.array([nx * tan_h, ny * tan_v, 1.0], dtype=np.float64)
        d_vcam = d_vcam / np.linalg.norm(d_vcam)

        # Rotation from virtual camera to static rig camera (yaw then pitch)
        cos_p, sin_p = np.cos(pan), np.sin(pan)
        cos_t, sin_t = np.cos(tilt), np.sin(tilt)

        # R_pan (around Y) * R_tilt (around X)
        R_pan = np.array([[cos_p, 0, sin_p], [0, 1, 0], [-sin_p, 0, cos_p]])
        R_tilt = np.array([[1, 0, 0], [0, cos_t, -sin_t], [0, sin_t, cos_t]])
        R_v2c = R_pan @ R_tilt

        d_cam = R_v2c @ d_vcam
        return self.camera_ray_to_ground(d_cam)
