#!/usr/bin/env python3
"""Autonomous Computer Vision Detection Extractor for Baltimore Armor Match.

Extracts:
1. `players_colour.json`: 600 frames sampled across the match recording with player
   bounding boxes and grass-filtered upper-torso CIELAB lightness (L) values.
2. `ball_candidates.json`: Ball candidate detections on the turf plane with pixel coordinates,
   size, and confidence scores across paired 0.5s intervals for ball tracking, possession
   attribution, and physics shot detection.
"""

from __future__ import annotations

import json
import logging
import math
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import cv2
import numpy as np

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from backend.src.services.pipeline.pitch_homography import PitchHomography

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("BaltimoreExtractor")

VIDEO_PATH = REPO / "backend/.local/media/baltimore_armor_full.mp4"
OUTPUT_DIR = REPO / "backend/.local/artifacts/baltimore-armor-20260906"


def _extract_ball_candidates(gray: np.ndarray, non_turf: np.ndarray) -> List[List[float]]:
    """Extract candidate soccer ball centroids from non-turf mask."""
    contours, _ = cv2.findContours(non_turf, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cands = []
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if 6 < area < 300:
            peri = cv2.arcLength(cnt, True)
            if peri > 0:
                circ = 4.0 * np.pi * area / (peri * peri)
                bx, by, bw, bh = cv2.boundingRect(cnt)
                aspect = bh / float(bw)
                if 0.5 < aspect < 2.0 and circ > 0.35:
                    patch = gray[by:by + bh, bx:bx + bw]
                    mean_lum = float(np.mean(patch))
                    if mean_lum > 125:
                        conf = min(0.95, (circ * 0.4) + (mean_lum / 255.0 * 0.6))
                        cands.append([
                            round(bx + bw / 2.0, 1),
                            round(by + bh / 2.0, 1),
                            round(max(bw, bh), 1),
                            round(conf, 3),
                        ])
    cands.sort(key=lambda c: c[3], reverse=True)
    return cands[:5]


def extract_player_and_ball_detections(
    video_path: Path,
    output_dir: Path,
    num_player_frames: int = 600,
    start_time_s: float = 250.0,
    end_time_s: float = 6650.0,
):
    """Sample video and generate blind detection artifacts."""
    output_dir.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise FileNotFoundError(f"Could not open video at {video_path}")

    homography = PitchHomography.canonical_broadcast_prior()
    fps = cap.get(cv2.CAP_PROP_FPS) or 29.97
    total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    duration_s = total_frames / fps
    logger.info(f"Opened video: duration={duration_s:.1f}s ({duration_s/60:.1f}m), fps={fps:.2f}")

    player_timestamps = np.linspace(start_time_s, end_time_s, num_player_frames)
    player_detections: List[Dict[str, Any]] = []
    ball_detections: List[Dict[str, Any]] = []

    kernel_3x3 = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    t_start = time.time()
    logger.info(f"Extracting {num_player_frames} player and ball frames across [{start_time_s}s, {end_time_s}s]...")

    for i, t in enumerate(player_timestamps):
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000.0)
        ret, frame = cap.read()
        if not ret:
            continue

        h, w = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)

        # 1. Turf masking (olive green turf in Baltimore stadium)
        turf_mask = cv2.inRange(hsv, (20, 30, 30), (85, 255, 255))
        non_turf = cv2.bitwise_not(turf_mask)

        pitch_roi = np.zeros_like(non_turf)
        pitch_roi[int(h * 0.28):int(h * 0.95), int(w * 0.04):int(w * 0.96)] = 255
        non_turf = cv2.bitwise_and(non_turf, pitch_roi)
        non_turf_clean = cv2.morphologyEx(non_turf, cv2.MORPH_OPEN, kernel_3x3)

        contours, _ = cv2.findContours(non_turf_clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        frame_boxes = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            bx, by, bw, bh = cv2.boundingRect(cnt)

            if 40 < area < 4500:
                aspect = bh / float(bw)
                if 1.1 < aspect < 5.0 and bh > 14:
                    foot_x = bx + bw / 2.0
                    foot_y = by + bh
                    pt_turf = homography.project_point(foot_x, foot_y)
                    if pt_turf and 0.0 <= pt_turf[0] <= 105.0 and 0.0 <= pt_turf[1] <= 68.0:
                        ya = int(round(by + 0.15 * bh))
                        yb = int(round(by + 0.45 * bh))
                        xa = int(round(bx + 0.20 * bw))
                        xb = int(round(bx + 0.80 * bw))
                        ya, yb = max(ya, 0), min(yb, h)
                        xa, xb = max(xa, 0), min(xb, w)
                        if yb > ya and xb > xa:
                            torso_hsv = hsv[ya:yb, xa:xb]
                            torso_lab = lab[ya:yb, xa:xb]
                            t_turf = cv2.inRange(torso_hsv, (20, 30, 30), (85, 255, 255))
                            shirt_pixels = torso_lab[t_turf == 0]
                            if len(shirt_pixels) >= 5:
                                med_lab = np.median(shirt_pixels, axis=0)
                            else:
                                med_lab = np.median(torso_lab.reshape(-1, 3), axis=0)

                            frame_boxes.append({
                                "box": [float(bx), float(by), float(bx + bw), float(by + bh)],
                                "conf": 0.85,
                                "shirt": {
                                    "lab": [round(float(v), 1) for v in med_lab],
                                    "px": int((yb - ya) * (xb - xa)),
                                },
                            })

        player_detections.append({
            "t": round(float(t), 3),
            "w": w,
            "h": h,
            "boxes": frame_boxes,
        })

        # Ball at t
        top_balls_t0 = _extract_ball_candidates(gray, non_turf_clean)
        ball_detections.append({
            "t": round(float(t), 3),
            "c": top_balls_t0,
        })

        # Fast paired grab for t + 0.5s (15 frames ahead)
        sub_t = t + 0.5
        if sub_t <= end_time_s:
            for _ in range(14):
                cap.grab()
            ret_sub, frame_sub = cap.read()
            if ret_sub:
                gray_sub = cv2.cvtColor(frame_sub, cv2.COLOR_BGR2GRAY)
                hsv_sub = cv2.cvtColor(frame_sub, cv2.COLOR_BGR2HSV)
                turf_sub = cv2.inRange(hsv_sub, (20, 30, 30), (85, 255, 255))
                non_turf_sub = cv2.bitwise_not(turf_sub)
                non_turf_sub = cv2.bitwise_and(non_turf_sub, pitch_roi)
                non_turf_sub_clean = cv2.morphologyEx(non_turf_sub, cv2.MORPH_OPEN, kernel_3x3)
                top_balls_sub = _extract_ball_candidates(gray_sub, non_turf_sub_clean)
                ball_detections.append({
                    "t": round(float(sub_t), 3),
                    "c": top_balls_sub,
                })

        if (i + 1) % 50 == 0 or (i + 1) == num_player_frames:
            elapsed = time.time() - t_start
            rate = (i + 1) / elapsed
            logger.info(f"Processed {i + 1}/{num_player_frames} frames ({rate:.1f} fps, elapsed={elapsed:.1f}s)")

    cap.release()

    # Write players_colour.json
    players_doc = {
        "job": "baltimore player detection with grass filtering and shirt lab extraction",
        "frames": len(player_detections),
        "detections": player_detections,
    }
    players_file = output_dir / "players_colour.json"
    players_file.write_text(json.dumps(players_doc))
    logger.info(f"Saved {len(player_detections)} player frames to {players_file} ({players_file.stat().st_size / 1024:.1f} KB)")

    # Sort ball frames by timestamp
    ball_detections.sort(key=lambda b: b["t"])
    ball_doc = {
        "job": "baltimore ball candidates extraction",
        "frames": len(ball_detections),
        "detections": ball_detections,
    }
    ball_file = output_dir / "ball_candidates.json"
    ball_file.write_text(json.dumps(ball_doc))
    logger.info(f"Saved {len(ball_detections)} ball frames to {ball_file} ({ball_file.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    extract_player_and_ball_detections(VIDEO_PATH, OUTPUT_DIR, num_player_frames=600)
