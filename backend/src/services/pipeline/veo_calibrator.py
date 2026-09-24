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

    def frame_pixel_to_ground(
        self,
        u: float,
        v: float,
        K: np.ndarray,
        R: np.ndarray,
    ) -> Optional[Tuple[float, float]]:
        """Map a pixel (u, v) in a video frame with intrinsic K and rotation R to ground metric (x_m, z_m)."""
        p_pix = np.array([u, v, 1.0], dtype=np.float64)
        K_inv = np.linalg.inv(K)
        d_local = K_inv @ p_pix
        norm = np.linalg.norm(d_local)
        if norm < 1e-9:
            return None
        d_local = d_local / norm
        d_cam = R @ d_local
        return self.camera_ray_to_ground(d_cam)

    def panorama_pixel_to_ground(
        self,
        u: float,
        v: float,
        scale: float,
        origin: Tuple[float, float] | list,
    ) -> Optional[Tuple[float, float]]:
        """Map a pixel (u, v) in a spherical panorama with scale and origin to ground metric (x_m, z_m)."""
        x0, y0 = origin
        theta = (u + x0) / scale
        psi = np.pi - (v + y0) / scale
        d_cam = np.array(
            [np.sin(psi) * np.sin(theta), np.cos(psi), np.sin(psi) * np.cos(theta)],
            dtype=np.float64,
        )
        norm = np.linalg.norm(d_cam)
        if norm < 1e-9:
            return None
        d_cam = d_cam / norm
        return self.camera_ray_to_ground(d_cam)

    def ground_to_radar(self, x_m: float, z_m: float) -> Tuple[float, float]:
        """Convert metric (x_m, z_m) to standard 2D Pitch Radar coordinates (x in [0, 105], y in [0, 68])."""
        x_norm, z_norm = self.metric_to_normalized(x_m, z_m)
        return float(x_norm * 105.0), float(z_norm * 68.0)

    def frame_pixel_to_radar(
        self,
        u: float,
        v: float,
        K: np.ndarray,
        R: np.ndarray,
    ) -> Optional[Tuple[float, float]]:
        """Map a frame pixel directly to 2D Pitch Radar coordinates (x in [0, 105], y in [0, 68])."""
        pt = self.frame_pixel_to_ground(u, v, K, R)
        if pt is None:
            return None
        return self.ground_to_radar(*pt)

    def panorama_pixel_to_radar(
        self,
        u: float,
        v: float,
        scale: float,
        origin: Tuple[float, float] | list,
    ) -> Optional[Tuple[float, float]]:
        """Map a panorama pixel directly to 2D Pitch Radar coordinates (x in [0, 105], y in [0, 68])."""
        pt = self.panorama_pixel_to_ground(u, v, scale, origin)
        if pt is None:
            return None
        return self.ground_to_radar(*pt)

    def project_bounding_box_to_radar(
        self,
        box: list | Tuple[float, float, float, float],
        K: np.ndarray,
        R: np.ndarray,
        foot_ratio: float = 1.0,
    ) -> Optional[Tuple[float, float]]:
        """
        Project a player bounding box [x1, y1, x2, y2] to 2D Pitch Radar coordinates.

        foot_ratio: 1.0 means bottom edge (feet contact on turf), 0.9 means lower 10%.
        """
        x1, y1, x2, y2 = box[:4]
        foot_u = (x1 + x2) / 2.0
        foot_v = y1 + foot_ratio * (y2 - y1)
        return self.frame_pixel_to_radar(foot_u, foot_v, K, R)
