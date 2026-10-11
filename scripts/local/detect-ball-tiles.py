#!/usr/bin/env python3
"""Tiled small-ball CANDIDATE detection on a prepared local clip, CPU only.

Runs the full frame plus an nx*ny grid of overlapping tiles per frame, offsets
tile boxes to frame coordinates, merges them with deterministic NMS and caps the
result per frame. Outputs ball candidates only: no events, possession, teams or
accuracy claims. Candidate counts are not precision/recall.
"""
import argparse
from datetime import datetime, timezone
from fractions import Fraction
import importlib.util
import json
import math
from pathlib import Path
import os
import re
import shutil
import sys
import tempfile
import time

# Reuse hashing, local-path and lazy model loading from the existing detector.
_spec = importlib.util.spec_from_file_location(
    "detect_video_pilot_shared", Path(__file__).resolve().parent / "detect-video-pilot.py")
_shared = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_shared)
sha256_file = _shared.sha256_file
local_path = _shared.local_path
load_model = _shared.load_model

BALL_CLASS = 32
BATCH_SIZE = 6          # max images per predict() call; bounds CPU memory. The full frame is always
                        # predicted alone; tiles are grouped by identical shape, then chunked <= this
NMS_IOU = 0.5           # global duplicate-suppression IoU threshold (suppress when IoU > this)
TOP_K = 20              # max candidates kept per frame after NMS
CV2_THREADS = 2
COUNT_TOLERANCE = 1     # same |actual-expected| tolerance as detect-video-pilot


def tile_grid(width, height, nx, ny, overlap):
    """Return row-major (x0, y0, x1, y1) tiles covering every pixel edge to edge.

    Tile size is ceil(L / (n - (n-1)*overlap)) (exact rational math), clamped to L;
    origins are spread with integer floor so the first tile starts at 0 and the last
    ends exactly at L. Since n*size >= L the stride never exceeds the size, so no gaps.
    """
    for name, value in (("width", width), ("height", height), ("nx", nx), ("ny", ny)):
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f"{name} must be an integer >= 1")
    if isinstance(overlap, bool) or not isinstance(overlap, (int, float)) or not math.isfinite(overlap) \
            or not 0 <= overlap < 1:
        raise ValueError("overlap must lie in [0, 1)")
    if nx > width or ny > height:
        raise ValueError("tile grid is finer than the frame (more tiles than pixels)")

    def axis(length, count):
        size = min(length, math.ceil(Fraction(length) / (count - (count - 1) * Fraction(overlap))))
        if count == 1:
            return [(0, length)]
        return [((i * (length - size)) // (count - 1), (i * (length - size)) // (count - 1) + size)
                for i in range(count)]

    xs, ys = axis(width, nx), axis(height, ny)
    tiles = [(x0, y0, x1, y1) for (y0, y1) in ys for (x0, x1) in xs]
    if any(x1 - x0 > width or y1 - y0 > height for x0, y0, x1, y1 in tiles):
        raise ValueError("tile larger than frame")
    return tiles


def offset_box(box, x0, y0, width, height):
    """Shift a tile-local xyxy box into frame coordinates and clip; None if degenerate."""
    values = [float(v) for v in box]
    if not all(math.isfinite(v) for v in values):
        raise ValueError("non-finite box from model")
    bx1, by1, bx2, by2 = values
    out = [min(max(bx1 + x0, 0.0), float(width)), min(max(by1 + y0, 0.0), float(height)),
           min(max(bx2 + x0, 0.0), float(width)), min(max(by2 + y0, 0.0), float(height))]
    return out if out[2] > out[0] and out[3] > out[1] else None


def iou(a, b):
    iw = min(a[2], b[2]) - max(a[0], b[0])
    ih = min(a[3], b[3]) - max(a[1], b[1])
    if iw <= 0 or ih <= 0:
        return 0.0
    inter = iw * ih
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def _source_rank(source):
    return -1 if source == "full" else int(source)


def nms(candidates, iou_threshold=NMS_IOU, top_k=TOP_K):
    """Deterministic greedy NMS; result is independent of input order.

    Sort: confidence desc, then bbox coords, then source ("full" before tiles by index).
    Then cap to top_k. Each candidate: {"bbox": xyxy, "conf": float, "source": "full"|int}.
    """
    ordered = sorted(candidates, key=lambda c: (-c["conf"], tuple(c["bbox"]), _source_rank(c["source"])))
    kept = []
    for cand in ordered:
        if all(iou(cand["bbox"], k["bbox"]) <= iou_threshold for k in kept):
            kept.append(cand)
            if len(kept) >= top_k:
                break
    return kept


def candidate_record(cand, frame_index, timestamp):
    x1, y1, x2, y2 = cand["bbox"]
    return {"frame": frame_index, "t": timestamp, "bbox": [x1, y1, x2, y2],
            "cx": (x1 + x2) / 2, "cy": (y1 + y2) / 2, "size": max(x2 - x1, y2 - y1),
            "conf": cand["conf"], "source": cand["source"]}


def validate_pilot(pilot):
    """Strict pilot validation (same checks as detect-video-pilot, plus symlink refusal)."""
    raw = Path(str(pilot)).expanduser()
    if raw.is_symlink():
        raise ValueError("pilot directory must not be a symlink")
    pilot = local_path(pilot)
    clip, prep_path = pilot / "clip.mp4", pilot / "pilot_manifest.json"
    if clip.is_symlink() or prep_path.is_symlink():
        raise ValueError("clip.mp4 and pilot_manifest.json must not be symlinks")
    if not clip.is_file() or not prep_path.is_file():
        raise ValueError("pilot requires clip.mp4 and pilot_manifest.json")
    prep = json.loads(prep_path.read_text())
    if not isinstance(prep, dict):
        raise ValueError("pilot manifest must be a JSON object")
    provenance = prep.get("input_provenance", {})
    if not isinstance(provenance, dict):
        raise ValueError("pilot manifest must attest video-only preparation without inference or evaluation labels")
    if (prep.get("artifact_type") != "video_pilot_preparation" or
            prep.get("inference_performed") is not False or
            provenance.get("mode") != "video_only" or provenance.get("evaluation_labels_used") is not False):
        raise ValueError("pilot manifest must attest video-only preparation without inference or evaluation labels")
    source_hash = provenance.get("video_sha256", "")
    if not isinstance(source_hash, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", source_hash):
        raise ValueError("invalid source video SHA256 attestation")
    clip_hash = sha256_file(clip)
    clip_meta = prep.get("clip")
    if not isinstance(clip_meta, dict):
        raise ValueError("pilot manifest clip field must be an object")
    if clip_hash != clip_meta.get("sha256"):
        raise ValueError("clip hash differs from preparation manifest")
    sampling = prep.get("sampling", {})
    if not isinstance(sampling, dict):
        raise ValueError("invalid pilot sampling values")
    try:
        if any(isinstance(sampling.get(k), bool) for k in ("start_s", "fps", "duration_s")):
            raise TypeError
        start, fps, duration = (float(sampling.get(key, float("nan"))) for key in ("start_s", "fps", "duration_s"))
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid pilot sampling values") from exc
    if not all(math.isfinite(v) for v in (start, fps, duration)) or start < 0 or fps <= 0 or duration <= 0:
        raise ValueError("pilot sampling must specify finite source start, positive fps and duration")
    expected = duration * fps
    if not math.isfinite(expected):
        raise ValueError("invalid expected sampling frame count")
    return {"clip": clip, "prep_path": prep_path, "source_hash": source_hash, "clip_hash": clip_hash,
            "sampling": sampling, "start": start, "fps": fps, "duration": duration, "expected_frames": expected}


def opencv_version():
    try:
        import cv2
        return cv2.__version__
    except ImportError:
        return None


def open_frames(path):
    """Yield BGR frames sequentially from a video (overridable in tests)."""
    try:
        import cv2
    except ImportError as exc:
        raise ValueError("opencv-python (cv2) is required to decode frames; install it in the local "
                         "inference environment") from exc
    cv2.setNumThreads(CV2_THREADS)
    capture = cv2.VideoCapture(str(path))
    try:
        if not capture.isOpened():
            raise ValueError("could not open clip.mp4 for decoding")
        while True:
            ok, frame = capture.read()
            if not ok:
                return
            yield frame
    finally:
        capture.release()


def _contiguous(crop):
    flags = getattr(crop, "flags", None)
    if flags is not None and not flags["C_CONTIGUOUS"]:
        return crop.copy()
    return crop


def _predict_chunk(model, images, imgsz, conf):
    """One predict() call; return per-image lists of (xyxy, conf) for ball-class boxes only."""
    results = list(model.predict(source=images, classes=[BALL_CLASS], device="cpu", imgsz=imgsz,
                                 conf=conf, verbose=False, save=False))
    if len(results) != len(images):
        raise ValueError("model returned a different number of results than images")
    rows = []
    for result in results:
        found = []
        if result.boxes is not None:
            for box, confidence, cls in zip(result.boxes.xyxy.cpu().tolist(), result.boxes.conf.cpu().tolist(),
                                            result.boxes.cls.cpu().tolist()):
                if int(cls) == BALL_CLASS:
                    if not math.isfinite(float(confidence)):
                        raise ValueError("non-finite confidence from model")
                    found.append((box, float(confidence)))
        rows.append(found)
    return rows


def _predict_frame(model, frame, tile_images, imgsz, conf):
    """Predict full frame alone, then tiles grouped by shape in chunks <= BATCH_SIZE.

    Returns (full_found, [found per tile in tile order]). Same-shape batches keep
    preprocessing independent of chunking.
    """
    full = _predict_chunk(model, [frame], imgsz, conf)[0]
    groups = {}
    for position, image in enumerate(tile_images):
        groups.setdefault(tuple(image.shape), []).append(position)
    per_tile = [None] * len(tile_images)
    for shape in sorted(groups):
        positions = groups[shape]
        for start in range(0, len(positions), BATCH_SIZE):
            chunk = positions[start:start + BATCH_SIZE]
            for position, found in zip(chunk, _predict_chunk(model, [tile_images[i] for i in chunk], imgsz, conf)):
                per_tile[position] = found
    return full, per_tile


def detect_ball_tiles(pilot, weights, out, nx=3, ny=2, overlap=.15, imgsz=640, conf=.25, max_frames=None):
    for name, value in (("nx", nx), ("ny", ny)):
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise ValueError(f"{name} must be an integer >= 1")
    if isinstance(overlap, bool) or not math.isfinite(overlap) or not 0 <= overlap < 1:
        raise ValueError("overlap must lie in [0, 1)")
    if isinstance(imgsz, bool) or not isinstance(imgsz, int) or imgsz <= 0 or not math.isfinite(conf) \
            or not 0 <= conf <= 1:
        raise ValueError("imgsz must be positive and confidence must lie in [0, 1]")
    if max_frames is not None and (isinstance(max_frames, bool) or not isinstance(max_frames, int) or max_frames < 1):
        raise ValueError("max_frames must be a positive integer")
    weights_arg = weights
    weights = local_path(weights)
    if Path(str(weights_arg)).expanduser().is_symlink():
        raise ValueError("--weights must not be a symlink")
    if Path(str(out)).expanduser().is_symlink():  # also catches dangling links before resolving
        raise ValueError("output directory must be new; refusing overwrite")
    output = local_path(out)
    if output.exists() or output.is_symlink():
        raise ValueError("output directory must be new; refusing overwrite")
    if not weights.is_file() or weights.suffix.lower() != ".pt":
        raise ValueError("--weights requires an existing local .pt checkpoint; downloads are disabled")
    info = validate_pilot(pilot)
    model_hash = sha256_file(weights)
    model, versions = load_model(weights)
    names = getattr(model, "names", None)
    try:
        ball_name = names[BALL_CLASS]
    except (TypeError, KeyError, IndexError) as exc:
        raise ValueError("checkpoint must map class 32 to sports ball") from exc
    if ball_name != "sports ball":
        raise ValueError("checkpoint must map class 32 to sports ball")
    versions = dict(versions)
    versions["opencv"] = opencv_version()
    versions["python"] = sys.version.split()[0]

    start, fps, expected = info["start"], info["fps"], info["expected_frames"]
    frames, tiles, size = [], None, None
    raw_total = kept_total = frames_with = 0
    exhausted = True
    started = time.perf_counter()
    stream = open_frames(info["clip"])
    try:
        for index, frame in enumerate(stream):
            if max_frames is not None and index >= max_frames:
                exhausted = False
                break
            shape = tuple(frame.shape)
            if len(shape) < 2:
                raise ValueError("decoded frame has no height/width")
            height, width = int(shape[0]), int(shape[1])
            if size is None:
                size = (width, height)
                tiles = tile_grid(width, height, nx, ny, overlap)
            elif size != (width, height):
                raise ValueError(f"decoded frame {index} is {width}x{height}, expected {size[0]}x{size[1]}")
            tile_images = [_contiguous(frame[y0:y1, x0:x1]) for x0, y0, x1, y1 in tiles]
            full, per_tile = _predict_frame(model, frame, tile_images, imgsz, conf)
            origins = [(0, 0)] + [(x0, y0) for x0, y0, _, _ in tiles]
            sources = ["full"] + list(range(len(tiles)))
            pool = []
            for source, (ox, oy), found in zip(sources, origins, [full] + per_tile):
                for box, confidence in found:
                    moved = offset_box(box, ox, oy, width, height)
                    if moved is not None:
                        pool.append({"bbox": moved, "conf": confidence, "source": source})
            merged = nms(pool)
            timestamp = start + index / fps
            raw_total += len(pool)
            kept_total += len(merged)
            frames_with += bool(merged)
            frames.append({"frame": index, "t": timestamp, "w": width, "h": height,
                           "candidates": [candidate_record(c, index, timestamp) for c in merged]})
    finally:
        close = getattr(stream, "close", None)
        if close:
            close()
    elapsed = time.perf_counter() - started
    if not frames:
        raise ValueError("no decoded frames")
    actual = len(frames)
    holds = abs(actual - expected) <= COUNT_TOLERANCE + 1e-9
    if max_frames is None:
        if not holds:
            raise ValueError(f"decoded frame count {actual} differs from expected {expected:g}; "
                             "source-clock timestamps cannot be trusted")
        status = "complete"
    else:
        # --max-frames is a smoke test: complete only if the whole stream was consumed and counts hold.
        status = "complete" if exhausted and holds else "partial"
    provenance = {"mode": "video_only", "evaluation_labels_used": False, "video_sha256": info["source_hash"],
                  "clip_sha256": info["clip_hash"],
                  "attestation": "producer_attested_not_independent_isolation_proof"}
    config = {"device": "cpu", "threads": 2, "cv2_threads": CV2_THREADS, "imgsz": imgsz, "conf": conf,
              "classes": [BALL_CLASS], "verbose": False,
              "tiles": {"nx": nx, "ny": ny, "overlap": overlap, "grid": [list(t) for t in tiles],
                        "frame_width": size[0], "frame_height": size[1], "includes_full_frame": True},
              "nms": {"iou_threshold": NMS_IOU, "order": "conf desc, bbox, source", "scope": "full+tiles"},
              "top_k_per_frame": TOP_K, "batch_size": BATCH_SIZE, "max_frames": max_frames}
    manifest = {"schema_version": 1, "artifact_type": "video_pilot_tiled_ball_candidates",
                "created_at": datetime.now(timezone.utc).isoformat(), "status": status,
                "input_provenance": provenance, "pilot_manifest_sha256": sha256_file(info["prep_path"]),
                "model": {"path": str(weights), "sha256": model_hash, "versions": versions,
                          "class_names": {"32": ball_name}},
                "config": config, "sampling": info["sampling"],
                "counts": {"frames": actual, "raw_candidates": raw_total, "ball_candidates": kept_total,
                           "frames_with_ball_candidate": frames_with},
                "coverage": {"frames_processed": actual, "expected_frames": expected,
                             "stream_exhausted": exhausted},
                "frame_integrity": {"expected_frames": expected, "actual_frames": actual,
                                    "tolerance_frames": COUNT_TOLERANCE,
                                    "holds": holds,
                                    "whole_stream_consumed": exhausted},
                "performance": {"predict_decode_wall_s": elapsed,
                                "frames_per_second": actual / elapsed if elapsed > 0 else None},
                "limitations": ["Ball candidates only; no events, possession, teams, tracking or accuracy claims.",
                                "Counts are candidate presence, not precision or recall; false positives are expected.",
                                "Source SHA256 is attested by preparation; clip SHA256 was verified here."
                                + (" Run is partial (--max-frames): not full-clip coverage." if status == "partial" else "")],
                "outputs": ["ball_candidates.json"]}
    artifacts = {"ball_candidates.json": {"job": "local CPU tiled ball candidates", "status": status,
                                          "frames": actual, "frames_with_candidate": frames_with,
                                          "input_provenance": provenance, "detections": frames},
                 "detection_manifest.json": manifest}
    payloads = {name: json.dumps(data, indent=2, allow_nan=False) + "\n" for name, data in artifacts.items()}
    # Write into a temp sibling directory, then rename into place; clean up on any failure.
    output.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}.tmp-", dir=output.parent))
    try:
        for filename, text in payloads.items():
            with (staging / filename).open("x") as handle:
                handle.write(text)
        if output.exists() or output.is_symlink():
            raise ValueError("output directory must be new; refusing overwrite")
        os.rename(staging, output)  # fails if output is a non-empty dir; never replaces files
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return output / "detection_manifest.json"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot", required=True)
    parser.add_argument("--weights", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--nx", type=int, default=3)
    parser.add_argument("--ny", type=int, default=2)
    parser.add_argument("--overlap", type=float, default=.15)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--conf", type=float, default=.25)
    parser.add_argument("--max-frames", type=int, default=None,
                        help="smoke test: process only N frames; manifest status becomes partial")
    args = parser.parse_args(argv)
    try:
        manifest = detect_ball_tiles(args.pilot, args.weights, args.out, args.nx, args.ny, args.overlap,
                                     args.imgsz, args.conf, args.max_frames)
    except (ValueError, OSError, RuntimeError, TypeError, KeyError) as exc:
        parser.exit(2, f"tiled ball detection failed: {exc}\n")
    print(manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
