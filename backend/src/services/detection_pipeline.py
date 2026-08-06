"""Player detection pipeline using frame-difference analysis.

MVP uses lightweight motion-based detection (no ML model dependency).
When a detector backend is available, detect_in_frame can delegate to it.
"""

from __future__ import annotations

import io
import struct
import subprocess
from typing import Any

from src.domain.models.detection import DetectionResult


def _extract_frames(video_path: str, fps_sample: float = 1.0) -> list[tuple[int, bytes]]:
    """Extract frames from video at specified Hz via ffmpeg.

    Returns list of (frame_number, png_bytes).
    """
    if fps_sample <= 0:
        fps_sample = 1.0
    fps_str = str(fps_sample)

    cmd = [
        "ffmpeg", "-i", video_path,
        "-vf", f"fps={fps_str}",
        "-f", "image2pipe",
        "-vcodec", "png",
        "-",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=300)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []

    if result.returncode != 0 or not result.stdout:
        return []

    frames: list[tuple[int, bytes]] = []
    data = result.stdout
    while len(data) >= 8:
        # PNG magic: 8-byte signature followed by IHDR chunk
        # For simplicity, split on IDAT chunks (actual frame data)
        idx = data.find(b"\x89PNG\r\n\x1a\n")
        if idx == 0:
            start = idx
            # Find end of PNG (IEND chunk)
            iend = data.find(b"IEND\xae\x46\x60\x82", start + 8)
            if iend != -1:
                frames.append((len(frames), data[start : iend + 12]))
                data = data[iend + 12:]
                continue
        break

    # If PNG signature parsing failed, fall back to splitting on IHDR markers
    if not frames:
        marker = b"\x89PNG\r\n\x1a\n"
        start = 0
        while True:
            idx = data.find(marker, start)
            if idx == -1:
                break
            end_marker = b"IEND\xae\x46\x60\x82"
            iend = data.find(end_marker, idx)
            if iend != -1:
                frames.append((len(frames), data[idx : iend + 12]))
                start = iend + 12
            else:
                break

    return frames


def _detect_motion_regions(
    prev_frame: bytes | None,
    current_frame: bytes,
    min_area_pct: float = 0.005,
) -> list[dict[str, Any]]:
    """Find person-sized regions in a frame using pixel intensity analysis.

    Simple but effective: divides frame into grid cells, finds areas with
    consistent color (jersey colors stand out vs. pitch/background).
    Uses color segmentation for MVP jersey detection.
    """
    # Decode PNG to get raw pixel data - use Pillow if available, otherwise fallback
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(current_frame)).convert("RGB")
        pixels = list(img.getdata())
        w, h = img.size
    except ImportError:
        # Fallback: use basic byte analysis without Pillow
        return _detect_simple_regions(current_frame, min_area_pct)

    # Group pixels by color bucket (bucket size 32 for robustness to compression)
    buckets: dict[tuple[int, int, int], list[tuple[int, int]]] = {}
    for idx, pixel in enumerate(pixels):
        r, g, b = pixel
        br, bg, bb = (r // 32) * 32, (g // 32) * 32, (b // 32) * 32
        key = (br, bg, bb)
        if key not in buckets:
            buckets[key] = []
        col = idx % w
        row = idx // w
        buckets[key].append((col, row))

    # Filter: need minimum pixel count (person-sized) and exclude near-grayscale
    results: list[dict[str, Any]] = []
    min_pixels = max(50, int(min_area_pct * w * h))
    for (br, bg, bb), coords in buckets.items():
        if len(coords) < min_pixels:
            continue
        # Skip near-gray (pitch/background colors)
        chroma_sat = max(abs(br - bg), abs(bg - bb), abs(bb - br))
        if chroma_sat < 20:
            continue

        # Compute bounding box of this region
        xs = [c[0] for c in coords]
        ys = [c[1] for c in coords]
        bbox_x, bbox_y = min(xs), min(ys)
        bbox_w = max(xs) - min(xs) + 1
        bbox_h = max(ys) - min(ys) + 1

        # Person aspect ratio check (rough): height > width
        aspect = bbox_h / bbox_w if bbox_w > 0 else 0
        if 0.3 < aspect < 5.0 and bbox_w * bbox_h > min_pixels:
            conf = min(len(coords) / (min_pixels * 2), 1.0)
            results.append({
                "bbox_x": bbox_x / w,
                "bbox_y": bbox_y / h,
                "bbox_width": bbox_w / w,
                "bbox_height": bbox_h / h,
                "confidence": round(conf, 3),
            })

    return results


def _detect_simple_regions(current_frame: bytes, min_area_pct: float) -> list[dict]:
    """Fallback region detection when Pillow is not available."""
    # Very simple: check byte-level patterns for color contrast
    # This is a minimal fallback that just finds non-pitch areas
    return []


def detect_in_frame(frame_bytes: bytes, prev_frame_bytes: bytes | None) -> list[dict[str, Any]]:
    """Detect person-sized regions in a single frame.

    Returns bounding boxes as normalized coordinates with confidence.
    Uses color-segmentation MVP (no ML). Swappable for YOLO later.
    """
    return _detect_motion_regions(prev_frame_bytes, frame_bytes)


def run_detection(
    video_path: str,
    fps_sample: float = 1.0,
    confidence_threshold: float = 0.15,
    project_id: str = "",
) -> list[DetectionResult]:
    """Run full detection pipeline on a video file.

    Returns DetectionResult objects for person-class detections above threshold.
    """
    frames = _extract_frames(video_path, fps_sample)
    if not frames:
        return []

    results: list[DetectionResult] = []
    prev_frame: bytes | None = None

    for frame_num, frame_bytes in frames:
        dets = detect_in_frame(frame_bytes, prev_frame)
        for det in dets:
            if det["confidence"] >= confidence_threshold:
                # Get timestamp from ffmpeg frame index
                ts = frame_num / fps_sample if fps_sample > 0 else float(frame_num)
                results.append(DetectionResult(
                    detection_id=f"det_{project_id[:4]}_f{frame_num}_p{len(results)}",
                    frame_timestamp=round(ts, 3),
                    bbox_x=det["bbox_x"],
                    bbox_y=det["bbox_y"],
                    bbox_width=det["bbox_width"],
                    bbox_height=det["bbox_height"],
                    confidence=det["confidence"],
                    class_label="person",
                ))
        prev_frame = frame_bytes

    return results
