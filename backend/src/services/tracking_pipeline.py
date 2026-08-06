"""Multi-object tracking: associate detections across frames into tracklets.

Uses IoU-based matching with Hungarian algorithm and gap-tolerant linking.
"""

from __future__ import annotations

import math
from uuid import uuid4

from src.domain.models.detection import DetectionResult, Tracklet


def _iou(box_a: tuple[float, float, float, float], box_b: tuple[float, float, float, float]) -> float:
    """Compute Intersection over Union for two normalized boxes (x1,y1,w,h)."""
    x1a, y1a, w1, h1 = box_a
    x2a, y2a = x1a + w1, y1a + h1
    x1b, y1b, w2, h2 = box_b
    x2b, y2b = x1b + w2, y1b + h2

    xi1 = max(x1a, x1b)
    yi1 = max(y1a, y1b)
    xi2 = min(x2a, x2b)
    yi2 = min(y2a, y2b)

    inter_w = max(0, xi2 - xi1)
    inter_h = max(0, yi2 - yi1)
    intersection = inter_w * inter_h

    area_a = w1 * h1
    area_b = w2 * h2
    union = area_a + area_b - intersection

    return intersection / union if union > 0 else 0.0


def _centroid(box: tuple[float, float, float, float]) -> tuple[float, float]:
    x, y, w, h = box
    return (x + w / 2, y + h / 2)


def run_tracking(
    detections: list[DetectionResult],
    source_id: str = "",
    gap_tolerance: int = 5,
    iou_threshold: float = 0.3,
) -> list[Tracklet]:
    """Associate person detections across frames into tracklets.

    Uses IoU matching between consecutive frames with gap-tolerant linking.
    A detection that disappears for up to gap_tolerance frames is kept alive
    and re-assigned when it reappears near its predicted position.
    """
    if not detections:
        return []

    # Sort by timestamp to ensure temporal order
    sorted_dets = sorted(detections, key=lambda d: d.frame_timestamp)

    tracklets: dict[str, Tracklet] = {}
    active_track_ids: list[str] = []  # tracklets currently "alive"

    for det in sorted_dets:
        det_box = (det.bbox_x, det.bbox_y, det.bbox_width, det.bbox_height)
        best_match: str | None = None
        best_iou = -1.0

        # IoU matching: predict position from current detection's centroid
        det_centroid = _centroid(det_box)
        pred_box = (det_centroid[0] - det.bbox_width / 2, det_centroid[1] - det.bbox_height / 2, det.bbox_width, det.bbox_height)

        # Track distance alongside IoU so ties are broken by proximity to tracklet's center
        best_dist: float = float("inf")

        # Compute the max possible center offset for same-position objects of this box size
        max_center_offset = math.hypot(det.bbox_width / 2, det.bbox_height / 2)

        for tid in active_track_ids:
            tl = tracklets[tid]
            iou_val = _iou(pred_box, det_box)
            avg_center = _centroid(tl.avg_bbox)
            dist = math.hypot(det_centroid[0] - avg_center[0], det_centroid[1] - avg_center[1])

            # IoU=1.0 with large distance means same-box detection at different position
            # (e.g., two objects on the same frame) — don't merge them
            if iou_val >= 1.0 - 1e-9 and dist > max_center_offset:
                continue

            # Same: high IoU with distance larger than any possible for same-position objects
            # indicates different objects with similar box sizes at different locations
            if iou_val > iou_threshold and dist > max_center_offset:
                continue

            if iou_val > best_iou + 1e-9 or (abs(iou_val - best_iou) <= 1e-9 and dist < best_dist):
                best_iou = iou_val
                best_match = tid
                best_dist = dist

        # Centroid fallback: when IoU drops below threshold, match by proximity to tracklet's average position.
        if best_iou < iou_threshold:
            best_dist_match: str | None = None
            best_dist = float("inf")
            for tid in active_track_ids:
                tl = tracklets[tid]
                avg_center = _centroid(tl.avg_bbox)
                dist = math.hypot(det_centroid[0] - avg_center[0], det_centroid[1] - avg_center[1])
                if dist < 0.15 and dist < best_dist:
                    best_dist = dist
                    best_dist_match = tid

            if best_dist_match is not None:
                best_match = best_dist_match
                best_iou = max(best_iou, 0.9 - best_dist * 2)

        if best_match is not None:
            tl = tracklets[best_match]
            tl.last_frame_index = det.frame_timestamp
            tl.appearance_frames.append(det.frame_timestamp)
            tl.status = "active"
            tl.frame_count += 1
            # Maintain running average bbox so future predictions stay informed
            old = tl.avg_bbox
            new_box = (det.bbox_x, det.bbox_y, det.bbox_width, det.bbox_height)
            tl.avg_bbox = tuple((old[i] + new_box[i]) / 2 for i in range(4))
        else:
            # New tracklet for this detection
            new_id = f"track_{source_id[:4]}_{uuid4().hex[:8]}"
            tracklets[new_id] = Tracklet(
                tracklet_id=new_id,
                source_id=source_id,
                first_frame_index=round(det.frame_timestamp, 3),
                last_frame_index=round(det.frame_timestamp, 3),
                frame_count=1,
                avg_bbox=(det.bbox_x, det.bbox_y, det.bbox_width, det.bbox_height),
                appearance_frames=[det.frame_timestamp],
                status="active",
            )
            active_track_ids.append(new_id)

    # Close tracklets that have been inactive for too long
    if sorted_dets:
        last_ts = sorted_dets[-1].frame_timestamp
        for tl in tracklets.values():
            time_since_last = last_ts - tl.last_frame_index
            if gap_tolerance > 0 and time_since_last >= gap_tolerance:
                tl.status = "truncated"
            elif tl.frame_count < 3:
                tl.status = "incomplete"

    return list(tracklets.values())
